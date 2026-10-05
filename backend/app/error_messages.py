"""Catalogue UNIQUE des messages d'erreur affichables (français, sans vocabulaire
Pydantic ni FastAPI). Importé uniquement par `main.py` (les gestionnaires
d'exception) : `schemas.py` décide QUOI a échoué (un type d'erreur stable + un
contexte minimal), ce module décide COMMENT le dire en français. Changer un texte
ne touche donc jamais la logique de validation.

Principe de nommage des types d'erreur personnalisés (schemas.py) : PydanticCustomError
avec un CODE STABLE, jamais un simple ValueError. Sans code stable, cinq validateurs
différents (NUL, surrogate isolé, mot de passe trop long, null interdit, date hors
plage) partageraient tous le type générique `value_error` de Pydantic — impossible de
choisir le bon message français sans deviner d'après le texte de l'exception (fragile,
casserait au moindre changement de formulation). Vérifié en exécutant les schémas
réels (Pydantic 2.13.4, installée) : les `type`/`ctx` cités ci-dessous sont observés,
pas supposés.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Libellés de champs : UNE forme, toujours au SINGULIER (élimine l'accord du
# verbe : "Les notes ne doivent pas..." vs "Le titre ne doit pas..." — un seul
# gabarit de phrase sert alors tous les champs, sans branche grammaticale).
# GARDE (tests/test_error_messages.py) : tout champ des schémas d'entrée, et tout
# paramètre de chemin/requête entier (IdPath/IdQuery), doit avoir une entrée ici.
# ---------------------------------------------------------------------------
FIELD_LABELS: dict[str, str] = {
    "email": "L'adresse email",
    "password": "Le mot de passe",
    "new_password": "Le nouveau mot de passe",
    "token": "Le lien",
    "name": "Le nom du tableau",
    "title": "L'intitulé du poste",
    "company": "L'entreprise",
    "location": "Le lieu",
    "url": "Le lien de l'offre",
    "notes": "Le contenu des notes",
    "board_id": "Le tableau",
    "application_id": "La candidature",
    "status_filter": "Le filtre de statut",
    "position": "La position",
    # Ces trois champs n'utilisent normalement PAS le gabarit générique (ils ont
    # un message dédié, ci-dessous) : gardés ici en filet de sécurité, au cas où
    # un type d'erreur non prévu les toucherait un jour.
    "status": "Le statut",
    "source": "L'origine de la candidature",
    "applied_at": "La date de candidature",
}

# Libellé neutre quand `field` est inconnu de FIELD_LABELS (ne devrait pas
# arriver : test de garde ci-dessus) ou absent (erreur qui ne désigne aucun champ
# précis, ex. corps de requête entier illisible).
_UNKNOWN_FIELD_LABEL = "Cette information"

# Jamais affiché : filet de sécurité si un type d'erreur nouveau (ex. un futur
# champ, une future version de Pydantic) n'a pas encore d'entrée dans ce
# catalogue. Toujours préférable au texte brut de Pydantic.
FALLBACK_MESSAGE = "Une des informations fournies n'est pas valide."

# Réponse du gestionnaire d'exception générique (500) : ne JAMAIS exposer le
# texte ni la trace de l'exception réelle (fuite d'information technique) — elle
# est journalisée côté serveur (cf. main.py), jamais renvoyée au client.
GENERIC_SERVER_ERROR_DETAIL = "Une erreur inattendue est survenue. Réessayez dans un instant."

# Réponses 429 (limites de débit, app/rate_limit.py). Statiques : la durée d'attente
# est dans l'en-tête Retry-After. Elles ne dépendent JAMAIS de l'existence d'un compte
# (anti-énumération) : le même texte sort que l'adresse visée existe ou non.
RATE_LIMITED_LOGIN_DETAIL = (
    "Trop de tentatives de connexion. Patientez quelques minutes avant de réessayer, "
    "ou utilisez « Mot de passe oublié »."
)
RATE_LIMITED_REGISTER_DETAIL = (
    "Trop d'inscriptions depuis cette connexion. Réessayez plus tard."
)
RATE_LIMITED_FORGOT_PASSWORD_DETAIL = (
    "Trop de demandes de réinitialisation depuis cette connexion. Réessayez plus tard."
)

# ---------------------------------------------------------------------------
# Gabarits GÉNÉRIQUES : un message par `type` Pydantic, valable pour N'IMPORTE
# QUEL champ (utilisent {label}, jamais un nom de champ technique brut).
# `ctx` est injecté tel quel dans .format() ; les clés inutilisées par un gabarit
# donné sont simplement ignorées par str.format (aucun risque d'erreur).
# ---------------------------------------------------------------------------
_REQUIRED_TEMPLATE = "{label} est obligatoire."

GENERIC_TEMPLATES: dict[str, str] = {
    "missing": _REQUIRED_TEMPLATE,
    # string_too_short avec min_length == 1 est un champ vide : traité comme
    # "obligatoire" (cas spécial géré dans _message_for, pas ici).
    "string_too_long": "{label} ne doit pas dépasser {max_length} caractères.",
    "string_type": "{label} n'a pas un format valide.",
    "int_type": "{label} n'a pas un format valide.",
    "int_parsing": "{label} doit être un nombre entier.",
    # Un flottant non entier (1.5) pour un identifiant : vérifié par exécution,
    # type distinct de int_parsing (qui couvre une CHAÎNE illisible).
    "int_from_float": "{label} doit être un nombre entier.",
    "datetime_type": "{label} n'a pas un format valide.",
    # Pas de champ booléen dans nos schémas d'entrée actuels : bool_parsing/
    # bool_type sont donc VOLONTAIREMENT absents (inatteignables, invérifiables
    # par un test réel). Le jour où un champ booléen existera, il retombera
    # d'abord sur FALLBACK_MESSAGE (sûr) jusqu'à l'ajout de ces deux entrées.
    # Bornes numériques : jamais les valeurs ge/le (illisibles pour un humain,
    # ce sont nos identifiants techniques MAX_ID etc.).
    "greater_than_equal": "{label} n'est pas valide.",
    "less_than_equal": "{label} n'est pas valide.",
    # Nos codes personnalisés (schemas.py, PydanticCustomError) : génériques,
    # car NUL/surrogate peuvent survenir sur n'importe quel champ texte, et
    # "null interdit" sur n'importe lequel des 4 champs obligatoires en PATCH.
    "nul_character": "{label} contient un caractère qui n'est pas autorisé.",
    "surrogate_character": "{label} contient un caractère qui n'est pas autorisé.",
    "null_not_allowed": _REQUIRED_TEMPLATE,
    # Mot de passe CHOISI trop long (inscription : « Le mot de passe », réinitialisation :
    # « Le nouveau mot de passe »). La limite est en OCTETS (bcrypt), le message parle en
    # CARACTÈRES : {max_length} vient du contexte (MAX_CHOSEN_PASSWORD_BYTES), jamais
    # recopié en dur ici, et la valeur saisie n'y figure jamais.
    "chosen_password_too_long": (
        "{label} est trop long : {max_length} caractères maximum, "
        "moins s'il contient des accents."
    ),
}

# ---------------------------------------------------------------------------
# Messages DÉDIÉS : (type, field) précis, quand le gabarit générique dirait
# quelque chose de faux ou d'inutilisable (ex. lister les valeurs techniques
# d'un enum, ou le format d'une date).
# ---------------------------------------------------------------------------
DEDICATED_MESSAGES: dict[tuple[str, str | None], str] = {
    # `field=None` : erreur qui ne désigne aucun champ précis (le corps de la
    # requête tout entier est illisible). Vérifié par exécution : un JSON
    # syntaxiquement invalide et un JSON qui n'est pas un objet (ex. un tableau)
    # produisent chacun un type distinct, tous deux avec `field=None`.
    ("json_invalid", None): "La requête est mal formée.",
    ("model_attributes_type", None): "La requête est mal formée.",
    ("value_error", "email"): "L'adresse email n'est pas valide.",
    ("enum", "status"): "Le statut choisi n'est pas valide.",
    ("literal_error", "source"): "L'origine de la candidature n'est pas valide.",
    # Vérifié par exécution (Pydantic 2.13.4) : une date illisible (chaîne mal
    # formée) produit `datetime_from_date_parsing`. Le type voisin
    # `datetime_parsing` existe dans Pydantic mais je n'ai trouvé aucune entrée,
    # sur ce schéma précis, qui le déclenche réellement (un nombre est ACCEPTÉ —
    # coercition en timestamp — et un objet/une liste donnent `datetime_type`,
    # déjà couvert par le gabarit générique). Non ajouté ici tant qu'aucun test
    # ne peut prouver qu'il est atteignable : le repli générique protège quand
    # même si ce cas se présentait un jour.
    ("datetime_from_date_parsing", "applied_at"): "La date n'est pas reconnue.",
    # Notre code personnalisé (schemas.py) : {min}/{max} viennent du contexte
    # passé par le validateur (formatés depuis MIN_APPLIED_AT/MAX_APPLIED_AT,
    # app/limits.py) — jamais recopiés en dur ici, pour rester exacts si ces
    # constantes changent un jour.
    ("applied_at_out_of_range", "applied_at"): (
        "Choisissez une date de candidature entre le {min} et le {max}."
    ),
    ("password_too_many_bytes", "password"): "Le mot de passe saisi est trop long.",
}


def _field_name(loc: tuple) -> str | None:
    """Nom du champ désigné par `loc`, ou None quand `loc` n'en désigne aucun.

    Nos schémas sont PLATS (aucun champ imbriqué) : un vrai champ a toujours
    `loc == (<"body"|"path"|"query">, "<nom>")`, exactement deux éléments, le
    second étant une CHAÎNE. Vérifié par exécution : un JSON syntaxiquement
    invalide produit `loc == ("body", <décalage entier>)` — le second élément
    est alors un INDEX DE POSITION, pas un nom de champ (`str(0)` donnerait
    "0", un faux « champ » trompeur si on ne filtrait pas sur le type)."""
    if len(loc) == 2 and isinstance(loc[1], str):
        return loc[1]
    return None


def is_body_field(loc: tuple) -> bool:
    """Vrai seulement pour un champ RÉELLEMENT soumis dans le corps
    (`loc == ("body", "<nom>")`) : la seule catégorie exposée avec `field` dans
    `errors[]`, destinée à colorer un champ de formulaire précis. Un identifiant
    de chemin, un paramètre de requête, ou un décalage de position (JSON
    invalide) n'est jamais un champ de formulaire à colorer."""
    return len(loc) == 2 and loc[0] == "body" and isinstance(loc[1], str)


def message_for_error(error_type: str, field: str | None, ctx: dict | None) -> str:
    """Message français pour UNE erreur Pydantic (type + champ + contexte).

    Ordre de résolution :
    1. message DÉDIÉ (type, field) exact ;
    2. cas spécial `string_too_short` avec min_length == 1 (champ vide, traité
       comme "obligatoire" plutôt que "doit contenir au moins 1 caractère") ;
    3. gabarit GÉNÉRIQUE par type, appliqué avec le libellé du champ ;
    4. repli générique (FALLBACK_MESSAGE) — jamais le texte brut de Pydantic.
    """
    ctx = ctx or {}
    label = FIELD_LABELS.get(field, _UNKNOWN_FIELD_LABEL) if field else _UNKNOWN_FIELD_LABEL

    if (error_type, field) in DEDICATED_MESSAGES:
        template = DEDICATED_MESSAGES[(error_type, field)]
    elif error_type == "string_too_short" and ctx.get("min_length") == 1:
        template = _REQUIRED_TEMPLATE
    elif error_type == "string_too_short":
        template = "{label} doit contenir au moins {min_length} caractères."
    elif error_type in GENERIC_TEMPLATES:
        template = GENERIC_TEMPLATES[error_type]
    else:
        return FALLBACK_MESSAGE

    try:
        return template.format(label=label, **ctx)
    except (KeyError, IndexError):
        # Gabarit qui référence une clé absente du contexte réel : ne jamais
        # planter ni laisser passer un gabarit à moitié rempli ("{max_length}
        # caractères" littéral) — repli sûr.
        return FALLBACK_MESSAGE


def build_validation_error_body(pydantic_errors: list[dict]) -> dict:
    """Construit le corps JSON d'une réponse 422 à partir des erreurs BRUTES de
    Pydantic (`RequestValidationError.errors()`).

    Format renvoyé, contrat unique pour tous les clients (frontend, extension) :
      {"detail": "<message FR de la 1re erreur>",
       "errors": [{"field": "title", "message": "..."},  # présent seulement
                   {"message": "..."}]}                   # pour un champ du corps

    `detail` reste une CHAÎNE (jamais un tableau, contrairement au comportement
    par défaut de FastAPI) : c'est ce qui répare le « [object Object] » observé
    côté client, sans qu'aucun client n'ait besoin d'être modifié pour en
    bénéficier. `errors` est additif, ignoré sans risque par un client qui ne le
    lit pas encore."""
    entries = []
    for error in pydantic_errors:
        loc = tuple(error.get("loc", ()))
        field = _field_name(loc)
        message = message_for_error(error.get("type", ""), field, error.get("ctx"))
        entry = {"message": message}
        if is_body_field(loc):
            entry["field"] = field
        entries.append(entry)

    detail = entries[0]["message"] if entries else FALLBACK_MESSAGE
    return {"detail": detail, "errors": entries}
