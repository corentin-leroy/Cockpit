"""Empaquetage de l'extension Chrome : deux cibles, `dev` et `store`.

Les sources de extension/ gardent TOUJOURS les valeurs de production (config.js et
manifest.json). Ce script ne les modifie jamais ; il écrit uniquement dans
extension/dist/ (ignoré par Git).

- `dev`   : copie de l'extension dans dist/dev/, avec config.js et manifest.json
            réécrits pour viser le backend et le site locaux. Remplace l'ancienne
            bascule manuelle d'URL. Le dossier est reconstruit au MÊME chemin à
            chaque fois : l'identifiant de l'extension non empaquetée (qui dépend
            du chemin) ne change donc pas.
- `store` : zip pour le Chrome Web Store dans dist/, construit à partir de la
            liste EXPLICITE `FILES`. Refusé s'il reste une valeur de
            développement ou l'ancien domaine (`FORBIDDEN_TERMS`).

Avant toute écriture, les deux cibles contrôlent les sources : présence des
fichiers de `FILES`, clés du manifeste non gérées, forme de config.js, alignement
entre config.js et le manifeste, et atteignabilité (tout fichier cité depuis le
manifeste est dans `FILES`, et tout fichier de `FILES` est cité).

Bibliothèque standard uniquement. Lancement (depuis la racine du dépôt) :
    backend\\.venv\\Scripts\\python.exe extension\\package_extension.py dev
    backend\\.venv\\Scripts\\python.exe extension\\package_extension.py store

Décisions et justification : dev-docs/extension-session-sharing.md.
"""

import argparse
import json
import posixpath
import re
import shutil
import sys
import zipfile
from html.parser import HTMLParser
from pathlib import Path

EXTENSION_DIR = Path(__file__).resolve().parent
DIST_DIR = EXTENSION_DIR / "dist"
DEV_DIR = DIST_DIR / "dev"

MANIFEST_FILE = "manifest.json"
CONFIG_FILE = "config.js"

# Contenu EXACT du paquet (chemins relatifs à extension/, séparateur « / »).
# Ajouter un fichier à l'extension = l'ajouter ici : le contrôle d'atteignabilité
# échoue sinon. Exclus volontairement : icons/icon512.png (visuel de la fiche du
# Store, téléversé depuis le tableau de bord, non déclaré dans le manifeste),
# README.md, CLAUDE.md, ce script et dist/.
FILES: tuple[str, ...] = (
    "manifest.json",
    "background.js",
    "config.js",
    "api.js",
    "storage.js",
    "limits.js",
    "urlCleanup.js",
    "popup.html",
    "popup.js",
    "adapters/index.js",
    "adapters/francetravail.js",
    "adapters/indeed.js",
    "icons/icon16.png",
    "icons/icon32.png",
    "icons/icon48.png",
    "icons/icon128.png",
)

# Constantes de config.js que le script sait lire et réécrire.
CONFIG_CONSTANTS: tuple[str, ...] = ("API_BASE_URL", "SITE_ORIGIN")

# Valeurs locales de la cible dev. Le backend local écoute sur 127.0.0.1:8000 ; le
# site de dev s'ouvre TOUJOURS sur localhost:5173 (l'origine vérifiée par
# l'extension en dépend, cf. dev-docs/extension-session-sharing.md).
DEV_API_BASE_URL = "http://127.0.0.1:8000"
DEV_SITE_ORIGIN = "http://localhost:5173"
# Motif externally_connectable du manifeste de dev (utilisé à partir de la 1.2.0).
# Si Chrome refuse le port à son chargement : remplacer par "http://localhost/*",
# ICI seulement (jamais dans le manifeste des sources).
DEV_SITE_MATCH = DEV_SITE_ORIGIN + "/*"

# Refusés (sans tenir compte de la casse) dans les fichiers texte du paquet Store,
# commentaires compris : valeurs de développement et ancien domaine de l'API.
FORBIDDEN_TERMS: tuple[str, ...] = ("localhost", "127.0.0.1", "railway")
TEXT_SUFFIXES: tuple[str, ...] = (".js", ".json", ".html")

# Clés du manifeste qui citent des fichiers et que le contrôle d'atteignabilité NE
# SAIT PAS suivre : leur présence fait échouer le script, plutôt que de laisser un
# fichier échapper au contrôle. Pour en utiliser une, étendre `_manifest_roots`.
UNSUPPORTED_MANIFEST_KEYS: tuple[str, ...] = (
    "browser_action",
    "chrome_settings_overrides",
    "chrome_url_overrides",
    "content_scripts",
    "declarative_net_request",
    "default_locale",
    "devtools_page",
    "file_handlers",
    "options_page",
    "options_ui",
    "page_action",
    "sandbox",
    "side_panel",
    "storage",
    "theme",
    "web_accessible_resources",
)
UNSUPPORTED_BACKGROUND_KEYS: tuple[str, ...] = ("page", "scripts")

# Imports relatifs d'un fichier JS, lus sur le texte ENTIER (un import peut
# s'étendre sur plusieurs lignes) : `from "x"`, `import "x"` et `import("x")`.
IMPORT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"""\bfrom\s*(["'])(.+?)\1"""),
    re.compile(r"""\bimport\s*(["'])(.+?)\1"""),
    re.compile(r"""\bimport\s*\(\s*(["'])(.+?)\1\s*\)"""),
)

# URL avec schéma (https:, data:, chrome:...), relative au protocole ou ancre :
# pas un fichier du paquet.
EXTERNAL_REF = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.-]*:|//|#)")


class PackagingError(Exception):
    """Échec contrôlé : un titre et la liste de tous les problèmes trouvés."""

    def __init__(self, title: str, problems: list[str]) -> None:
        super().__init__(title)
        self.title = title
        self.problems = problems


def _fail_if(title: str, problems: list[str]) -> None:
    """Lève PackagingError si `problems` n'est pas vide."""
    if problems:
        raise PackagingError(title, problems)


def _read_text(relative_path: str) -> str:
    """Lit un fichier texte des sources (UTF-8)."""
    return (EXTENSION_DIR / relative_path).read_text(encoding="utf-8")


def check_files_exist() -> None:
    """Vérifie que chaque fichier de FILES existe dans extension/."""
    problems = [
        f"Fichier de la liste FILES introuvable : {path}. Restaurez-le ou "
        "retirez-le de FILES (package_extension.py)."
        for path in FILES
        if not (EXTENSION_DIR / path).is_file()
    ]
    _fail_if("fichiers manquants.", problems)


def load_manifest() -> dict:
    """Lit manifest.json et vérifie la présence de la version."""
    try:
        manifest = json.loads(_read_text(MANIFEST_FILE))
    except (OSError, ValueError) as error:
        raise PackagingError("manifeste illisible.", [f"manifest.json illisible : {error}."])
    if not isinstance(manifest, dict):
        raise PackagingError(
            "manifeste illisible.", ["manifest.json illisible : objet JSON attendu."]
        )
    if not isinstance(manifest.get("version"), str) or not manifest["version"]:
        raise PackagingError("manifeste incomplet.", ["manifest.json : champ version absent."])
    return manifest


def check_unsupported_keys(manifest: dict) -> None:
    """Refuse les clés du manifeste qui citent des fichiers non contrôlés."""
    keys = [key for key in UNSUPPORTED_MANIFEST_KEYS if key in manifest]
    background = manifest.get("background")
    if isinstance(background, dict):
        keys += [
            f"background.{key}" for key in UNSUPPORTED_BACKGROUND_KEYS if key in background
        ]
    problems = [
        f"manifest.json déclare {key}, qui cite des fichiers que le script ne "
        "contrôle pas encore : étendre package_extension.py."
        for key in keys
    ]
    _fail_if("clé de manifeste non gérée.", problems)


def _config_pattern(name: str) -> re.Pattern[str]:
    """Motif de la ligne `export const NOM = "valeur";`.

    Groupe 1 = valeur ; groupe 2 = « \\r » éventuel, conservé à la réécriture
    (le fichier est lu sans conversion des fins de ligne).
    """
    return re.compile(rf'^export const {name} = "([^"\r\n]*)";(\r?)$', re.MULTILINE)


def read_config() -> dict[str, str]:
    """Lit les constantes de config.js ; chacune doit apparaître une seule fois."""
    text = _read_text(CONFIG_FILE)
    values: dict[str, str] = {}
    problems: list[str] = []
    for name in CONFIG_CONSTANTS:
        matches = [match.group(1) for match in _config_pattern(name).finditer(text)]
        if len(matches) != 1:
            problems.append(
                f'config.js : la ligne « export const {name} = "..."; » doit '
                f"apparaître exactement une fois (trouvée {len(matches)} fois). Le "
                "script ne sait la réécrire que sous cette forme."
            )
        else:
            values[name] = matches[0]
    _fail_if("config.js mal formé.", problems)
    return values


def check_alignment(manifest: dict, config: dict[str, str]) -> None:
    """Vérifie que le manifeste désigne les mêmes adresses que config.js."""
    problems: list[str] = []

    api_base_url = config["API_BASE_URL"]
    expected_hosts = [api_base_url + "/*"]
    host_permissions = manifest.get("host_permissions")
    if host_permissions != expected_hosts:
        problems.append(
            f"manifest.json (host_permissions = {json.dumps(host_permissions)}) et "
            f"config.js (API_BASE_URL = {api_base_url}) ne désignent pas le même "
            f"hôte : attendu {json.dumps(expected_hosts)}. Désalignés, les appels "
            "de l'extension retombent sous le contrôle CORS et échouent sans signal."
        )

    # externally_connectable n'existe qu'à partir de la 1.2.0 : contrôlé s'il est là.
    if "externally_connectable" in manifest:
        site_origin = config["SITE_ORIGIN"]
        expected_matches = [site_origin + "/*"]
        connectable = manifest["externally_connectable"]
        matches = connectable.get("matches") if isinstance(connectable, dict) else None
        if matches != expected_matches:
            problems.append(
                "manifest.json (externally_connectable.matches = "
                f"{json.dumps(matches)}) et config.js (SITE_ORIGIN = {site_origin}) "
                "ne désignent pas le même site : attendu "
                f"{json.dumps(expected_matches)}."
            )

    _fail_if("adresses désalignées entre config.js et manifest.json.", problems)


def _manifest_roots(manifest: dict) -> list[tuple[str, str]]:
    """Fichiers cités par le manifeste, sous la forme (clé, chemin)."""
    roots: list[tuple[str, str]] = []
    background = manifest.get("background")
    if isinstance(background, dict) and "service_worker" in background:
        roots.append(("background.service_worker", background["service_worker"]))
    action = manifest.get("action")
    if isinstance(action, dict):
        if "default_popup" in action:
            roots.append(("action.default_popup", action["default_popup"]))
        default_icon = action.get("default_icon")
        if isinstance(default_icon, dict):
            roots += [(f"action.default_icon.{size}", p) for size, p in default_icon.items()]
        elif default_icon is not None:
            roots.append(("action.default_icon", default_icon))
    icons = manifest.get("icons")
    if isinstance(icons, dict):
        roots += [(f"icons.{size}", path) for size, path in icons.items()]
    return roots


class _HtmlRefCollector(HTMLParser):
    """Relève les `<script src>` et `<link href>` d'une page HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.refs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "script" and attributes.get("src"):
            self.refs.append(attributes["src"])
        elif tag == "link" and attributes.get("href"):
            self.refs.append(attributes["href"])

    handle_startendtag = handle_starttag


def _html_refs(path: str) -> list[str]:
    """Références de fichiers d'une page HTML (URL externes exclues)."""
    collector = _HtmlRefCollector()
    collector.feed(_read_text(path))
    refs = [ref.split("?")[0].split("#")[0] for ref in collector.refs]
    return [ref for ref in refs if ref and not EXTERNAL_REF.match(ref)]


def _js_imports(path: str) -> list[str]:
    """Spécificateurs de tous les imports d'un fichier JS."""
    text = _read_text(path)
    return [match.group(2) for pattern in IMPORT_PATTERNS for match in pattern.finditer(text)]


def _resolve(source: str, reference: str) -> str | None:
    """Chemin, relatif à extension/, d'une référence lue dans `source`.

    `/x` part de la racine de l'extension, le reste du dossier de `source`. Renvoie
    None si le chemin sort de extension/.
    """
    if reference.startswith("/"):
        joined = reference.lstrip("/")
    else:
        joined = posixpath.join(posixpath.dirname(source), reference)
    normalized = posixpath.normpath(joined)
    if normalized == "." or normalized == ".." or normalized.startswith("../"):
        return None
    return normalized


def check_reachability(manifest: dict) -> None:
    """Contrôle d'atteignabilité, dans les deux sens.

    Part des fichiers cités par le manifeste (service worker, popup, icônes), lit
    les `<script src>` / `<link href>` de chaque page HTML atteinte et suit
    récursivement les imports relatifs de chaque fichier JS. Tout fichier atteint
    doit figurer dans FILES, et aucun fichier de FILES ne doit être inatteignable.
    """
    listed = set(FILES)
    reached = {MANIFEST_FILE}
    to_visit: list[str] = []
    problems: list[str] = []

    def reach(source: str, reference: str) -> None:
        target = _resolve(source, reference)
        if target is None:
            problems.append(f"{source} cite {reference}, qui sort du dossier extension/.")
            return
        if target not in listed:
            if (EXTENSION_DIR / target).is_file():
                problems.append(f"{source} cite {target}, absent de la liste FILES.")
            else:
                problems.append(f"{source} cite {target}, introuvable dans extension/.")
            return
        if target not in reached:
            reached.add(target)
            to_visit.append(target)

    for key, path in _manifest_roots(manifest):
        if not isinstance(path, str) or not path:
            problems.append(f"manifest.json : {key} doit être un chemin de fichier.")
            continue
        reach(MANIFEST_FILE, path)

    while to_visit:
        current = to_visit.pop()
        if current.endswith(".html"):
            for reference in _html_refs(current):
                reach(current, reference)
        elif current.endswith(".js"):
            for specifier in _js_imports(current):
                if specifier.startswith(("./", "../", "/")):
                    reach(current, specifier)
                else:
                    problems.append(
                        f"{current} importe « {specifier} » : un import non relatif "
                        "ne peut pas être résolu dans une extension."
                    )

    problems += [
        f"{path} figure dans FILES mais aucun fichier atteint depuis le manifeste ne "
        "le cite : retirez-le de FILES, ou vérifiez la référence qui devait le citer."
        for path in FILES
        if path not in reached
    ]
    _fail_if("la liste FILES et le code divergent.", problems)


def check_forbidden_terms() -> None:
    """Refuse toute valeur de développement ou l'ancien domaine dans le paquet."""
    problems: list[str] = []
    for path in FILES:
        if not path.endswith(TEXT_SUFFIXES):
            continue
        for number, line in enumerate(_read_text(path).splitlines(), start=1):
            lowered = line.lower()
            problems += [
                f"{path}:{number} : « {term} »" for term in FORBIDDEN_TERMS if term in lowered
            ]
    _fail_if(
        "paquet Store refusé : valeur de développement ou ancien domaine trouvé :",
        problems,
    )


def run_checks() -> tuple[dict, dict[str, str]]:
    """Contrôles communs aux deux cibles, sur les SOURCES. Renvoie manifeste et config."""
    check_files_exist()
    manifest = load_manifest()
    check_unsupported_keys(manifest)
    config = read_config()
    check_alignment(manifest, config)
    check_reachability(manifest)
    return manifest, config


def _rewrite_config(text: str, values: dict[str, str]) -> str:
    """Remplace la valeur des constantes de config.js (fins de ligne conservées)."""
    for name, value in values.items():
        text = _config_pattern(name).sub(
            lambda match, n=name, v=value: f'export const {n} = "{v}";{match.group(2)}',
            text,
            count=1,
        )
    return text


def build_dev(manifest: dict) -> None:
    """Construit dist/dev/ : copie de FILES, config.js et manifeste réécrits."""
    if DEV_DIR.is_symlink():
        raise PackagingError("sortie invalide.", [f"{DEV_DIR} est un lien : refusé."])
    if DEV_DIR.exists():
        shutil.rmtree(DEV_DIR)
    for path in FILES:
        destination = DEV_DIR / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(EXTENSION_DIR / path, destination)

    # newline="" : ni lecture ni écriture ne convertissent les fins de ligne, la
    # copie ne diffère de la source que par les deux valeurs réécrites.
    config_path = DEV_DIR / CONFIG_FILE
    with config_path.open(encoding="utf-8", newline="") as source:
        config_text = source.read()
    with config_path.open("w", encoding="utf-8", newline="") as destination:
        destination.write(
            _rewrite_config(
                config_text,
                {"API_BASE_URL": DEV_API_BASE_URL, "SITE_ORIGIN": DEV_SITE_ORIGIN},
            )
        )

    dev_manifest = json.loads(json.dumps(manifest))
    dev_manifest["host_permissions"] = [DEV_API_BASE_URL + "/*"]
    if isinstance(dev_manifest.get("externally_connectable"), dict):
        dev_manifest["externally_connectable"]["matches"] = [DEV_SITE_MATCH]
    (DEV_DIR / MANIFEST_FILE).write_text(
        json.dumps(dev_manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(f"Build de dev prête : extension/dist/dev ({len(FILES)} fichiers).")
    print(f"  API : {DEV_API_BASE_URL}  -  site : {DEV_SITE_ORIGIN}")
    print("  Rechargez l'extension dans chrome://extensions (bouton de rechargement).")


def build_store(manifest: dict) -> None:
    """Construit le zip du Chrome Web Store dans dist/."""
    check_forbidden_terms()

    DIST_DIR.mkdir(exist_ok=True)
    zip_path = DIST_DIR / f"cockpit-extension-{manifest['version']}.zip"
    replaced = zip_path.exists()
    temporary_path = zip_path.with_suffix(".zip.tmp")
    with zipfile.ZipFile(temporary_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in FILES:
            archive.write(EXTENSION_DIR / path, arcname=path)
    temporary_path.replace(zip_path)

    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
    if names != list(FILES):
        raise PackagingError(
            "zip incohérent.",
            [f"Le zip contient {names}, attendu {list(FILES)}."],
        )

    action = "remplacé" if replaced else "créé"
    print(f"Paquet Store {action} : extension/dist/{zip_path.name}")
    print(f"  Version {manifest['version']}, {len(names)} fichiers.")


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée : 0 si succès, 1 si un contrôle échoue (2 : usage, argparse)."""
    parser = argparse.ArgumentParser(
        description="Empaquette l'extension Chrome de Cockpit.",
    )
    parser.add_argument(
        "target",
        choices=("dev", "store"),
        help="dev : copie locale dans extension/dist/dev ; "
        "store : zip pour le Chrome Web Store dans extension/dist",
    )
    arguments = parser.parse_args(argv)

    try:
        manifest, _config = run_checks()
        if arguments.target == "dev":
            build_dev(manifest)
        else:
            build_store(manifest)
    except PackagingError as error:
        print(f"ERREUR : {error.title}", file=sys.stderr)
        for problem in error.problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
