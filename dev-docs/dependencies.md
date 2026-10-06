# Versions des dépendances (figées volontairement)
- requirements.txt et requirements-dev.txt épinglent des versions EXACTES (`==`),
  pas des minimums (`>=`). Figées le 2026-07-21 à partir des versions réellement
  installées et testées. Objectif : STABILITÉ DE DÉPLOIEMENT — un rebuild Railway
  dans six mois installe exactement la même chose qu'aujourd'hui. Avec des `>=`,
  un rebuild sans le moindre commit pouvait tirer une version majeure
  incompatible (FastAPI 1.0, SQLAlchemy 2.1…) et casser la prod sans prévenir.
- CONTREPARTIE ASSUMÉE : plus aucun correctif de sécurité n'arrive tout seul.
  Ces versions doivent être relevées À LA MAIN de temps en temps (tous les 2-3
  mois, ou dès qu'une CVE touche une de ces briques). Ce n'est pas optionnel :
  un pin oublié pendant deux ans est un risque de sécurité, pas une garantie.
- Procédure de mise à jour :
  1. `.venv\Scripts\python.exe -m pip install --upgrade <paquet>`
  2. `.venv\Scripts\python.exe -m pytest` — la suite doit rester au vert
  3. reporter la nouvelle version dans le fichier concerné, et mettre à jour la
     date « figées le … » en tête de requirements.txt
  4. déployer et vérifier /health avant de considérer la mise à jour faite
- Points de vigilance sur deux pins :
  - `bcrypt==4.0.1` : passlib 1.7.4 lit `bcrypt.__about__.__version__`, attribut
    SUPPRIMÉ en bcrypt 4.1. Ne pas relever bcrypt sans vérifier ce point (c'est
    l'ancienne borne `bcrypt<4.1`, désormais exprimée par un pin exact). Autre
    raison de ne pas le relever : bcrypt 5.x LÈVE au-delà de 72 octets au lieu de
    tronquer, ce qui casserait la connexion des comptes existants au mot de passe
    plus long (cf. « Validation des entrées »).
  - ⚠ `passlib==1.7.4` n'est plus maintenue (dernière publication en 2020, à ma
    connaissance) : c'est elle qui impose le pin `bcrypt==4.0.1` ci-dessus. Rien
    n'est changé pour l'instant. Un éventuel passage à Argon2 (et la migration des
    hashes existants au fil des connexions) serait un chantier À PART.
  - Les extras (`uvicorn[standard]`, `pydantic[email]`, `psycopg[binary]`,
    `passlib[bcrypt]`) n'apparaissent PAS dans `pip freeze`. Ne JAMAIS écraser
    requirements.txt avec un copier-coller de `pip freeze` : les extras seraient
    perdus et le déploiement casserait (pydantic sans email-validator ne démarre
    pas, psycopg sans [binary] tente une compilation C).
- Seules les dépendances DIRECTES sont épinglées ; les dépendances transitives
  (starlette, pydantic-core, anyio…) restent résolues par pip. C'est délibéré :
  un `pip freeze` complet fait sous Windows n'est PAS portable vers le conteneur
  Linux (il omet uvloop, que uvicorn[standard] installe uniquement hors Windows,
  et inclut colorama). Un verrou transitif complet devrait être généré pour la
  plateforme cible (pip-compile/uv avec `--python-platform linux`, ou depuis le
  conteneur) — à faire si une dépendance transitive casse un jour un build.
