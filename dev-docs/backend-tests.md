# Tests backend (backend/tests/, `.venv\Scripts\python.exe -m pytest`)
- Portée VOLONTAIREMENT ciblée : la matrice sécurité déjà validée manuellement
  (auth + ownership) et les garde-fous anti-abus, pas une couverture exhaustive.
  On teste les points où une régression serait silencieuse et coûteuse (fuite du
  mot de passe, perte de l'anti-énumération, cloisonnement par user, plafonds).
- Fichiers : `test_auth.py`, `test_boards_ownership.py`,
  `test_applications_ownership.py`, `test_limits.py`,
  `test_account_deletion.py`, `test_migrations.py`, `test_input_validation.py`,
  `test_registration_race.py`, `test_error_messages.py`, `test_archiving.py`,
  `test_token_race.py`, `test_email_normalization.py`, `test_password_limit.py`,
  `test_rate_limit.py`, `test_client_ip.py`, `test_auth_rate_limit.py`,
  `test_positions.py`, `test_position_race.py`, `test_token_version.py`,
  `test_passwordless_accounts.py`.
- `test_token_version.py` (révocation par compte, `dev-docs/jwt-session.md`) : claim
  émis égal à la version stockée ; jeton SANS claim accepté tant que la version vaut
  0 ; version incrémentée → 401 générique sur /auth/me ET /boards, pour ce compte
  seulement, nouvelle connexion acceptée ; claims `True`, `False`, `1.0`, `0.0`,
  `"1"`, `"0"`, `null`, liste, objet, négatif, 2**70 → 401, jamais 500 ;
  réinitialisation réussie → version +1, ancien jeton et jeton sans claim refusés ;
  réinitialisation refusée → rien ne change. Nom du claim écrit EN DUR (contrat avec
  les jetons émis). `test_token_race.py` vérifie en plus `token_version == 1` après
  les 20 réinitialisations simultanées. Vérifié par 4 mutations, toutes détectées :
  contrôle retiré de get_current_user, `isinstance` au lieu de `type(...) is int`
  (booléens acceptés), claim absent à l'émission, incrément retiré. SURVIVANTE dans
  la suite : `+= 1` en Python au lieu de l'expression SQL. Aucun chemin du code
  actuel ne fait écrire token_version par deux transactions à la fois : deux
  réinitialisations simultanées par deux liens DIFFÉRENTS n'aboutissent jamais
  toutes les deux (MESURÉ sur PostgreSQL 18.6, 2026-10-24 : 200 manches sur 200 en
  interblocage, une 200 et un 500, `token_version` = 1, avec ou sans la mutation).
  Tuée sous PostgreSQL 18.6 par un test HORS SUITE qui simule un autre écrivain
  commité pendant la réinitialisation (enveloppe de `hash_password`, connexion
  séparée) : 2 attendu, 1 avec la mutation. Impossible sous SQLite (« database is
  locked » : la réinitialisation tient déjà le verrou d'écriture).
- `test_passwordless_accounts.py` (comptes sans mot de passe, empreinte effacée
  DIRECTEMENT en base après une inscription : aucun endpoint du lot 1 n'en crée) :
  connexion → réponse identique (code, corps, en-têtes) à celle d'un mot de passe
  faux et d'un email inconnu, y compris avec l'ancien mot de passe et avec le TEXTE
  DU LEURRE ; un seul `verify_password`, contre `DUMMY_PASSWORD_HASH` ; 5 échecs puis
  le même 429 qu'une adresse inconnue ; mot de passe oublié → même réponse, aucun
  jeton, l'email Google seul, plafonné à 3 par heure (horloge factice) ; compte avec
  mot de passe → toujours le lien de reset ; email Google : bouton vers
  FRONTEND_URL + /login, ni `reset-password` ni `token` ; lien de reset en attente →
  même 400 qu'un jeton inconnu, bcrypt jamais appelé, rien ne change ; suppression →
  409, données intactes, session toujours valable ; UserRead = exactement `id`,
  `email`, `is_verified`, `created_at`, `has_password`. ⚠ Constaté en écrivant ces
  tests : passlib 1.7.4 accepte `verify(secret, None)` (son propre leurre, puis
  faux) : sans le contrôle explicite, la connexion échouait DÉJÀ en 401 et la
  suppression en 403, sans 500. C'est le test « un seul verify, contre le leurre »
  qui garde le comportement voulu. Vérifié par 10 mutations, toutes détectées :
  garde None retirée à la connexion, leurre retiré (401 avant bcrypt), condition
  d'échec réduite à `user is None` (le texte du leurre ouvrait le compte), refus de
  réinitialiser retiré, garde de la suppression retirée, branche du mot de passe
  oublié inversée, plafond de l'email retiré, `has_password` inversé, bouton de
  l'email vers une autre page, `google_notice` absent de `RateLimiters.reset()`.
- `test_positions.py` (ordre du kanban) : arrivée en haut sur chaque chemin
  (création formulaire et extension, PATCH statut, PATCH tableau, désarchivage) ;
  PATCH qui renvoie le MÊME statut et le MÊME tableau (comme le formulaire) ou ne
  touche que d'autres champs : la carte ne bouge pas ; /move dans une colonne
  (vers le haut, vers le bas), vers une autre colonne à un rang donné, vers une
  colonne vide, au-delà de la fin (ramené en fin), à sa propre place ; voisines
  sans changement d'updated_at ; colonnes des autres tableaux et utilisateurs
  intactes ; 409 sur une archivée, 404 chez autrui, 401 anonyme, 422 sur les corps
  malformés (message nommant « La position ») ; `position` ignorée par le PATCH et
  absente des réponses ; lignes NULL listées en tête puis réparées, avec doublons et
  trous, à la prochaine écriture ; tri qui ne dépend plus d'updated_at. Chaque test
  vérifie l'INVARIANT sur l'état stocké (0..n-1 par colonne active, NULL pour les
  archivées). Les insertions directes de `test_limits.py` et `test_archiving.py`
  (sans position) restent valides : elles exercent la réparation.
- `test_position_race.py` : 5 manches de 40 écritures simultanées tirées au hasard
  (graine fixe) parmi /move, PATCH statut et tableau, archivage, désarchivage,
  création, suppression, sur une base SQLite FICHIER (comme test_token_race.py) ;
  après chaque manche, invariant vérifié en base et aucun 500 (codes admis : 2xx,
  404 d'une carte supprimée en parallèle, 409). ~8 s.
  Vérifié par 15 mutations, toutes détectées : verrou retiré, verrou pris APRÈS la
  lecture, PATCH comparant la présence du champ, updated_at des voisines non
  préservé, tri revenu à updated_at, NULL en fin, rang non ramené en fin,
  archivage sans compacter, archivage sans NULL, suppression sans compacter, PATCH
  d'une archivée renuméroté, et quatre mutations de la migration 0005 (ordre
  croissant, égalités par id croissant, archivées numérotées, partition sans le
  tableau).
- Limites de débit (tests) : `conftest.py` remet les compteurs à zéro AVANT chaque
  test (fixture autouse `_reset_rate_limiting`) et fournit une horloge factice
  (`clock`, fenêtres testées sans attendre). Sans la remise à zéro, les centaines
  d'inscriptions de la suite depuis la même adresse de test dépasseraient 20 par
  heure. `test_registration_race.py` DÉSACTIVE le limiteur (`limiters.enabled`) :
  ses 40 inscriptions simultanées depuis une IP en refuseraient la moitié en 429 et
  masqueraient la contrainte unique qu'il vérifie.
- `test_rate_limit.py` (compteur) : seuil atteint puis dépassé, glissement de la
  fenêtre, `Retry-After`, tentative refusée non enregistrée, indépendance des clés,
  purge des clés expirées, plafond de clés (la moins récente est oubliée, une
  NOUVELLE clé n'est jamais refusée), journal limité, atomicité sous 200 threads,
  les cinq seuils décidés écrits en dur, et `RateLimiters.reset()` qui atteint
  chacun d'eux (l'horloge factice est réinstallée après la remise à zéro : sinon
  l'horloge réelle, très en avance, fait paraître expirées les tentatives non
  effacées et le test passe toujours). `test_client_ip.py` (lecture de l'IP) : la
  forme MESURÉE sur Railway, valeurs forgées à gauche (en ajout ou en remplacement,
  en-têtes répétés, énorme en-tête), replis (trop peu d'entrées, entrée invalide,
  adresse TCP hors du réseau des proxys), IPv6 par /64, IPv4 mappée, réglages
  invalides refusés. `test_auth_rate_limit.py` (HTTP) : chaque seuil atteint puis
  dépassé, glissement, remise à zéro après succès, indépendance des couples, 429
  identique que le compte existe ou non, limite vérifiée AVANT bcrypt (compteur
  d'appels), plafond de 3 envois par compte inchangé, compteur par vrai client
  derrière le proxy, garde « la dépendance est branchée à la route », et une rafale
  de 20 mauvais mots de passe simultanés avec le VRAI bcrypt (exactement 5 calculs).
  Vérifié par 16 mutations (limite après bcrypt, pas de remise à zéro, couple sans
  IP ou sans email, verrou retiré, pas de purge ni de plafond, nouvelles clés
  refusées, tentative refusée enregistrée, 429 selon l'existence du compte,
  dépendance retirée, `Retry-After` absent, seuil modifié, lecture de la première
  valeur de X-Forwarded-For, réseau des proxys non vérifié, IPv6 non regroupé) :
  chacune fait échouer au moins un test.
- `test_password_limit.py` : 72 octets acceptés et 73 refusés à l'inscription ET à
  la réinitialisation, en ASCII, accents (« é »), mélange et émojis ; minimum de 8
  caractères inchangé ; messages exacts avec le bon `field`, sans écho de la valeur ;
  un mot de passe refusé laisse le lien de réinitialisation utilisable (puis usage
  unique toujours garanti) ; comptes existants (100, 128 caractères, 120 octets)
  toujours connectables et supprimables. Le 72 y est écrit EN DUR (il fixe le
  contrat, il ne suit pas limits.py). Vérifié par mutation : retour à 128 caractères
  → 13 tests rouges ; limite appliquée au login → 10 rouges ; lien consommé (commit)
  avant le refus → le test de non-consommation rouge. Le test de cohérence
  borne/colonne n'est PAS concerné : le mot de passe n'est jamais stocké, seul son
  hash l'est.
- `test_email_normalization.py` : inscription `Case@` puis `case@` → 409 identique
  au doublon exact et un seul compte ; adresse stockée en minuscules et sans
  espaces ; connexion réussie quelle que soit la casse tapée ; mot de passe oublié
  en autre casse → un jeton de reset est émis pour le BON compte ; anti-énumération
  (forgot-password et 401 du login identiques, compte existant ou non, toutes
  casses) ; espace intérieur, espaces seuls et valeur vide toujours en 422 sur les
  trois points d'entrée ; NUL et surrogate refusés avant la normalisation ;
  idempotence ; GARDE (champ email non normalisé) + preuve que le garde détecte un
  schéma fautif. Vérifié par mutation : normalisation neutralisée → 7 tests rouges ;
  un schéma revenu à `EmailStr` → le garde le nomme.
- `test_input_validation.py` : pour chaque champ borné, la valeur maximale passe
  et la valeur maximale + 1 donne 422 (création ET modification) ; NUL et
  surrogate isolé refusés dans chaque champ texte de chaque schéma d'entrée ;
  mot de passe borné en octets au login et à la suppression ; `null` en PATCH ;
  identifiants hors plage ; gardes contre l'oubli (héritage d'`InputModel`,
  paramètres entiers bornés) ; cohérence borne/colonne ; corps 422 sans la valeur
  soumise ; `applied_at` (bornes 1900/2100 acceptées et refusées, fuseau converti
  en UTC naïf, débordements à la conversion, liste toujours lisible ensuite). Le
  client de test LÈVE les exceptions non gérées : un 500 fait échouer le test
  bruyamment. Limite : l'assertion « la liste reste lisible » ne peut pas échouer
  sous SQLite (qui relit l'an 1 sans problème) ; ce qui protège en test, c'est le
  422 et « rien n'est écrit ». Le vrai empoisonnement ne se prouve que sur
  PostgreSQL (sondes HTTP contre un PostgreSQL jetable).
- `test_error_messages.py` : format de réponse d'erreur (app/error_messages.py).
  Les deux trous du 401 anonyme et du 500 catch-all ; un cas HTTP réel par type
  d'erreur du catalogue (bornes, identifiants hors plage, enum/liste fermée,
  email, NUL/surrogate, mot de passe trop long, null interdit, date hors plage,
  JSON invalide, corps pas un objet) ; garde de couverture (tout type du
  catalogue est exercé par un cas de test) ; garde des libellés (tout champ a
  une entrée dans FIELD_LABELS) ; repli générique jamais un plantage ; jamais la
  valeur soumise dans la réponse. Trouvé et corrigé PENDANT l'écriture de ces
  tests (pas seulement supposé) : `int_from_float` absent du catalogue (un
  identifiant flottant, ex. 1.5) ; `is_body_field` confondait un décalage
  d'octet JSON («loc == ("body", 0)») avec un vrai nom de champ, exposant
  `"field": "0"` sur un JSON syntaxiquement invalide ; `bool_parsing`/
  `bool_type` retirés du catalogue (aucun champ booléen dans les schémas
  actuels, donc invérifiables — à réintroduire avec le premier champ booléen).
- `test_archiving.py` : archiver pose `archived_at` et conserve le statut,
  désarchiver l'inverse ; 409 explicite sur une action redondante (archiver une
  archivée, désarchiver une active) ; ownership ; filtre `?archived=` (exclusion
  par défaut, combinaison avec `board_id`/`status_filter`) ; accès par
  identifiant qui reste possible sur une archivée (GET/PATCH/DELETE) ; les deux
  plafonds (2000 archivées, 300 actives au désarchivage) ; LE test de la
  correction du comptage des 300 (archiver doit réellement libérer une place) ;
  cascade de suppression d'un tableau sur une candidature archivée, assertion
  sur l'état stocké (comme test_account_deletion.py) ; compteurs de `BoardRead`.
  Seedé DIRECTEMENT en base pour les plafonds (comme test_limits.py), pas par
  2000 requêtes HTTP.
- `test_registration_race.py` : 40 inscriptions simultanées de la même adresse,
  5 manches, sur une base SQLite FICHIER (une connexion par requête, pool par
  défaut) et non la base en mémoire à connexion unique des autres tests, qui ne
  permettrait pas de vraie concurrence. Exige exactement une 201, le reste en 409,
  zéro exception, un seul compte et un seul tableau par manche (~2 s au total).
  Plus un test déterministe (contrôle préalable rendu aveugle) et un test de garde
  (une autre `IntegrityError` reste un 500, jamais déguisée en 409).
- `test_token_race.py` : 20 reset-password et 40 verify-email simultanés avec le
  MÊME jeton, 5 manches, base SQLite FICHIER (comme test_registration_race.py).
  Exige exactement une 200, le reste en 400 au corps identique à celui d'un jeton
  consommé ; pour le reset, chaque requête envoie un mot de passe différent et
  celui du gagnant doit être celui de la base. Jetons semés directement en base.
  ~12 s (écritures SQLite sérialisées). Vérifié qu'il détecte le défaut : sur
  l'ancien code il échoue avec 15 x 200.
- `test_migrations.py` migre sa PROPRE base SQLite en mémoire (connexion injectée
  via `config.attributes["connection"]`, cf. alembic/env.py) et vérifie : une
  seule tête de migration ; `upgrade head` depuis le vide produit EXACTEMENT le
  schéma des modèles (`alembic check`) ; `downgrade base` ne laisse aucune table.
  C'est lui qui fait échouer la suite quand models.py change SANS migration,
  et il couvre aussi le garde-fou de la migration 0002 (une ligne REJECTED
  interrompt l'upgrade, sans rien modifier) et la conservation des lignes dans
  les deux sens, ainsi que celui de la 0004 (une note de 5001 caractères
  interrompt l'upgrade, rien n'est tronqué ; NULL, vide et 5000 caractères sont
  conservés dans les deux sens). Sous SQLite, le DDL `VARCHAR(5000)` n'est PAS
  appliqué : l'application de la borne par la base ne se prouve que sur
  PostgreSQL (fait, cf. révision 0004).
  Garde SQLite d'env.py (`sqlite_foreign_keys_disabled`) : TÉMOIN du piège (sans
  garde, recréer une table parente vide ses enfants), enfants conservés et
  `foreign_keys` rétabli à 1 (aussi après un échec), refus des écritures non
  commitées (directement et par `command.upgrade`, révision inchangée), échec
  bruyant de `foreign_key_check` sur une ligne orpheline. Les helpers de
  remplissage COMMITTENT avant de migrer (la garde l'exige). Migration 0006 :
  aller-retour sans perte (toutes les lignes des quatre tables, comptes existants
  à `token_version` 0 et `google_sub` NULL), insertion « comme l'ancien code »
  sans les nouvelles colonnes (seule garde du `server_default`, invisible pour
  `alembic check`), deux NULL admis et doublon de `google_sub` refusé, downgrade
  refusé tant qu'un compte n'a pas de mot de passe. Vérifié par 8 mutations,
  toutes détectées : garde retirée d'env.py (la 0006 perd tableaux et jetons),
  contrôle des écritures non commitées retiré, PRAGMA OFF retiré, commit après le
  PRAGMA retiré, `foreign_key_check` retiré, rétablissement de `foreign_keys=ON`
  retiré, `server_default` retiré, garde du downgrade retirée. Le chemin
  `engine.connect()` d'env.py (hors tests) est vérifié par la commande Alembic
  réelle sur une copie de cockpit.db (cf. révision 0006).
  Limites : SQLite uniquement, les types enum natifs de PostgreSQL n'y sont pas
  exercés. ⚠ POINT AVEUGLE : `alembic check` ne compare PAS les libellés d'un
  enum (vérifié sur SQLite ET sur PostgreSQL : aucun écart signalé alors que le
  type en base avait une valeur de moins que le modèle). Un changement de
  valeurs d'enum n'est donc protégé par AUCUN test automatique : il se teste à
  la main sur un PostgreSQL jetable (Docker, `postgres:18`, même version majeure
  que la prod) et se vérifie en prod en lisant les libellés (`pg_enum`).
- `test_account_deletion.py` couvre DELETE /auth/me (mot de passe exigé, refus en
  403, cloisonnement vis-à-vis des autres comptes) ET la cascade elle-même : ses
  assertions portent sur l'ÉTAT STOCKÉ, seul moyen de détecter des orphelins —
  une cascade non appliquée ne produit aucune erreur d'API.
- Dans `test_limits.py`, les candidatures de remplissage sont insérées DIRECTEMENT
  en base (300 POST seraient lents et n'apporteraient rien) : c'est l'état stocké
  qui détermine la limite, et c'est bien lui qu'on met en place.
- Isolation de la base : `tests/conftest.py` pose les variables d'environnement
  AVANT d'importer l'app (l'import de app.main appelle load_dotenv, qui n'écrase
  pas une variable déjà définie). On force ainsi (a) DATABASE_URL=sqlite://
  jetable, filet de sécurité pour qu'aucun test ne puisse viser cockpit.db, (b)
  BREVO_API_KEY/SENDER vides → mode DEV, aucun email réel, (c) un JWT_SECRET_KEY
  de test. La vraie base de test est un SQLite EN MÉMOIRE dédié (StaticPool, pour
  qu'une seule base soit partagée entre connexions), injecté en surchargeant la
  dépendance get_db. Schéma recréé puis détruit à CHAQUE test (fixture `client`) :
  tests indépendants, exécutables seuls et dans n'importe quel ordre.
- Fixtures réutilisables (conftest) : `client` (TestClient sur base vierge),
  `db_session` (assertions directes sur le stockage), et les factories
  `make_user` (inscrit + connecte, renvoie token/headers/board par défaut),
  `make_board`, `make_application`.
