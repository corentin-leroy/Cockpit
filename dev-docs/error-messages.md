# Messages d'erreur (extrait de « Validation des entrées »)
- Messages d'erreur, RÉDIGÉS PAR LE BACKEND (décision produit, lot 3b) : pas
  traduits par chaque client (frontend, extension) — une table de correspondance
  dupliquée dans les deux aurait divergé avec le temps. Catalogue UNIQUE :
  `app/error_messages.py`, importé par les gestionnaires d'exception de `main.py`
  et par `rate_limit.py` (messages des 429, cf. « Limites de débit »).
  `schemas.py` décide QUOI a échoué (un type d'erreur stable + un
  contexte minimal) ; `error_messages.py` décide COMMENT le dire en français.
  Changer un texte ne touche jamais la logique de validation.
- Format de réponse d'erreur, UNIQUE pour tous les codes (422 compris) :
  `detail` est TOUJOURS une CHAÎNE française directement affichable (avant le
  lot 3b, un 422 avait `detail` en TABLEAU brut de Pydantic — cause du
  « [object Object] » côté client ; réparé sans qu'aucun client n'ait dû
  changer, `data?.detail` était déjà ce qu'ils lisaient). Sur un 422 seulement,
  une clé `errors` additive liste chaque erreur : `{"field": "title", "message":
  "..."}`. `field` n'apparaît QUE pour un champ réellement soumis dans le corps
  (`loc == ("body", "<nom>")`) — jamais pour un paramètre de chemin/requête, ni
  pour un corps illisible dans son ensemble (JSON invalide, pas un objet) : ces
  cas n'ont rien à colorer dans un formulaire. `detail` reprend le message de
  la PREMIÈRE erreur (un message actionnable plutôt qu'un décompte).
- Validateurs personnalisés (schemas.py) : PydanticCustomError avec un CODE
  STABLE, JAMAIS un ValueError nu. Sans code stable, les 5 validateurs
  personnalisés (NUL, surrogate isolé, mot de passe trop long, null interdit,
  date hors plage) partageraient tous le type générique `value_error` de
  Pydantic — impossible de choisir le bon message français sans deviner d'après
  le texte de l'exception (fragile). Effet de bord utile, vérifié par
  exécution : un ValueError nu place l'OBJET EXCEPTION Python dans `ctx`, non
  sérialisable proprement ; PydanticCustomError n'y met que le contexte explicite
  passé à l'appel. Tout NOUVEAU validateur personnalisé doit suivre ce patron.
- Libellés de champs (`error_messages.FIELD_LABELS`) : UNE forme, toujours au
  SINGULIER (« Le contenu des notes », jamais « Les notes ») — élimine l'accord
  du verbe, un seul gabarit de phrase sert alors tous les champs. GARDE
  (tests/test_error_messages.py) : tout champ d'un schéma d'entrée, et tout
  paramètre de chemin/requête entier, doit y avoir une entrée. Un type d'erreur
  non catalogué retombe sur `FALLBACK_MESSAGE`, jamais sur le texte brut de
  Pydantic. Une AUTRE garde vérifie que toute entrée du catalogue (générique ou
  dédiée) est exercée par au moins un test réel : un type ajouté sans cas de
  test correspondant fait échouer la suite.
- Deux trous corrigés au lot 3b, tous deux plus souvent vus que les 422 :
  - 401 ANONYME (aucun `Authorization`) : `OAuth2PasswordBearer` lève LUI-MÊME
    un 401 « Not authenticated », EN ANGLAIS, codé en dur dans FastAPI, avant
    même d'atteindre notre code — le message le plus souvent vu par un
    utilisateur réel (une session expirée). Fixé avec `auto_error=False`
    (dependencies.py) : le schéma renvoie `None` au lieu de lever, et
    `get_current_user` décide du message (le même 401 générique que pour un
    token invalide). Attention si ce fichier est retouché : `decode_access_token
    (None)` lèverait une exception NON gérée (500) sans le contrôle explicite
    `if token is None` AVANT l'appel.
  - 500 NON PRÉVU : Starlette renvoyait par défaut un corps VIDE ou non-JSON
    (« Internal Server Error ») ; `response.json()` échouait côté client, qui
    retombait sur `response.statusText` (anglais, sans rapport avec l'erreur).
    `unhandled_exception_handler` (main.py, `@app.exception_handler(Exception)`)
    renvoie désormais un JSON français générique
    (`error_messages.GENERIC_SERVER_ERROR_DETAIL`) ; le texte et la trace de
    l'exception ne sont JAMAIS renvoyés au client, seulement journalisés
    (`logger.exception`, logs locaux et Railway). Ne modifie PAS le
    comportement des exceptions déjà gérées ailleurs (HTTPException,
    RequestValidationError) : FastAPI dispatche toujours au gestionnaire le
    plus spécifique. N'intercepte PAS non plus le comportement de test :
    `TestClient(app, raise_server_exceptions=True)` (le défaut, utilisé par la
    fixture `client`) continue de faire remonter l'exception dans le PROCESSUS
    DE TEST même quand ce gestionnaire produit une réponse — c'est le
    comportement réel d'un serveur déployé qu'il faut simuler avec
    `raise_server_exceptions=False` pour l'observer en test (voir
    test_error_messages.py).
