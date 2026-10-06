# Validation des entrées (schémas Pydantic)
- RÈGLE : aucune entrée d'un client ne doit produire un 500. Une valeur invalide
  est refusée en 422 AVANT la base. SQLite n'applique pas les longueurs de
  VARCHAR(n) et accepte les NUL : un écart entre borne et colonne, ou un caractère
  non enregistrable, n'échoue qu'en PostgreSQL (prod) — d'où des tests qui portent
  sur la validation, indépendants du moteur (tests/test_input_validation.py).
- Constantes dans `app/limits.py`, à côté des plafonds de quantité : longueurs de
  champs (titre, entreprise, lieu 255 ; url 2048 ; notes 5000 ; nom de tableau
  100), `MAX_CHOSEN_PASSWORD_BYTES` (72, mot de passe choisi, en octets),
  `MAX_PASSWORD_INPUT_BYTES` (4096), `MAX_ID`.
  Une borne ne doit JAMAIS dépasser la colonne de `models.py` (un test le vérifie).
- Tous les schémas d'ENTRÉE héritent de `InputModel` (schemas.py) : un validateur
  `'*'` refuse, dans tout champ texte, le NUL (U+0000 : PostgreSQL et bcrypt le
  rejettent) et le surrogate isolé (`\ud800` : pas d'encodage UTF-8). REFUSÉS en
  422, jamais nettoyés en silence (dans un mot de passe, retirer un caractère
  changerait l'identifiant). Les schémas de SORTIE (`*Read`, Token,
  MessageResponse) n'en héritent pas. Deux tests gardent l'oubli : tout schéma de
  `schemas.py` est classé entrée/sortie, et tout corps de requête réel des routes
  est un `InputModel`. Un nouveau schéma d'entrée doit donc en hériter.
- Création et modification d'une candidature partagent les MÊMES types (alias
  Title, Company, Location, Url, Notes, RowId) : une valeur acceptée à la création
  l'est à la modification. L'écart entre les deux causait des 500 (location et url
  non bornés en PATCH).
- `notes` : 5000 caractères, appliqués PAR L'API (Pydantic) ET PAR LA BASE : la
  colonne est `String(MAX_NOTES_LENGTH)` (models.py lit la constante de
  limits.py, migration 0004, lot 3e). Elle n'était avant que `Text`, sans limite :
  tout chemin contournant l'API (script de maintenance, SQL manuel, futur import)
  n'était pas protégé. Vérifié sur PostgreSQL 18.6 : la base refuse elle-même une
  note de 5001 caractères, en INSERT comme en UPDATE (« value too long for type
  character varying(5000) »). Modifier `MAX_NOTES_LENGTH` exige une nouvelle
  migration (test_migrations.py échoue sinon). Tous les champs texte sont donc
  désormais bornés à la fois par l'API et par leur colonne ; le test de cohérence
  (test_input_validation.py) ÉCHOUE, au lieu de sauter, si une colonne bornée
  n'a plus de longueur (repassée à `Text`).
- `source` : liste fermée `manual` | `extension` (Literal dans schemas.py,
  colonne String(50) inchangée). `ApplicationRead.source` reste un `str` pour
  qu'une valeur ancienne quelconque se lise toujours.
- PATCH : un `null` EXPLICITE est refusé (422) sur les champs NOT NULL (title,
  company, status, board_id) et reste permis sur location, url, notes, applied_at
  (c'est le moyen de les vider). Pour ne pas modifier un champ, on l'OMET.
- Identifiants : entiers >= 1 et <= 2147483647 (type `integer` de PostgreSQL).
  `IdPath` / `IdQuery` (dependencies.py) pour l'URL et la requête, `RowId`
  (schemas.py) pour le corps. 0 et les négatifs sont MALFORMÉS : 422, pas 404. Un
  test refuse tout paramètre entier de route non borné.
- Mot de passe CHOISI (inscription, réinitialisation) : au moins 8 CARACTÈRES, au
  plus 72 OCTETS UTF-8 (type `ChosenPassword`, schemas.py). POURQUOI 72 : bcrypt
  ignore tout ce qui dépasse 72 octets (vérifié, bcrypt 4.0.1 + passlib 1.7.4 : il
  tronque en silence, sans erreur ; « a » x 72 + « X » et « a » x 72 + « Y » ouvrent
  le même compte). L'ancienne borne de 128 caractères laissait croire que toute la
  longueur comptait. En OCTETS et non en caractères, comme bcrypt (un « é » en pèse
  2, un émoji 4). Au-delà : 422, code stable `chosen_password_too_long` (distinct de
  `password_too_many_bytes`, qui vise le mot de passe présenté : l'inscription et le
  login nomment tous deux leur champ `password`, un message dédié par (type, champ)
  leur aurait donné le même texte). Le message parle en CARACTÈRES (« Le mot de
  passe est trop long : 72 caractères maximum, moins s'il contient des accents. » ;
  à la réinitialisation « Le nouveau mot de passe… »), jamais en octets, et ne
  renvoie jamais la valeur saisie. Le front (`PASSWORD_MAX_LENGTH = 72`) compte en
  caractères : un mot de passe accentué peut passer le maxLength et être refusé par
  le backend, accepté (le serveur fait autorité).
  - Un refus ne consomme JAMAIS le lien de réinitialisation : la validation du corps
    précède l'endpoint, donc `_consume_token` n'est pas atteint (test explicite).
    Même un refus tardif avant le commit serait annulé par la fermeture de la session.
  - Les comptes EXISTANTS dont le mot de passe dépasse 72 octets continuent de se
    connecter (et de supprimer leur compte) : le login garde sa borne de 4096 octets
    et bcrypt tronque à la connexion exactement comme à l'inscription. Verrouillé par
    des tests (hash semé directement en base). Ces tests supposent bcrypt < 5 : la 5.x
    LÈVE au-delà de 72 octets, un relèvement du pin les ferait échouer, ce qui est
    voulu. Ces comptes restent exposés à la troncature jusqu'à ce que leur
    propriétaire change de mot de passe (alors limité à 72 octets).
  Mot de passe PRÉSENTÉ (login, suppression de compte) : au plus 4096 OCTETS UTF-8, en
  octets car passlib compte les octets (2049 « é » suffisent à le faire lever
  PasswordSizeError). Borne haute technique, jamais un minimum : au-delà, 422 ; le
  401 reste réservé à un mot de passe bien formé mais incorrect. La validation
  précède la recherche du compte : la réponse ne dépend pas de l'existence de
  l'email (anti-énumération préservée).
- Messages d'erreur (catalogue, format de réponse, validateurs
  personnalisés, libellés, 401 anonyme et 500) : `dev-docs/error-messages.md`.
- Avant de changer ces règles ou d'ajouter un champ : sonder l'API contre un
  PostgreSQL 18 jetable (Docker), pas seulement SQLite.
- `applied_at` (PATCH) : ramené en UTC NAÏF puis borné à 1900-01-01 .. 2100-12-31
  (`MIN_APPLIED_AT` / `MAX_APPLIED_AT`, limits.py), hors plage → 422. POURQUOI :
  PostgreSQL accepte des dates de 4713 av. J.-C. à l'an 294276, mais psycopg ne
  relit que les années 1 à 9999. Un fuseau converti en UTC pouvait sortir de cette
  plage (`0001-01-01T00:00:00+02:00`, `9999-12-31T23:59:59-12:00`) : la date était
  ÉCRITE ET COMMITÉE, puis sa relecture (`db.refresh`, juste après le commit)
  échouait. La requête donnait 500 alors que l'écriture avait eu lieu, et la ligne
  restait illisible pour toujours : la LISTE des candidatures du compte (le
  kanban) donnait 500, et même DELETE (il charge la ligne d'abord). Seul un UPDATE
  en base réparait. C'est un empoisonnement de DONNÉES, pas de session. La
  normalisation règle aussi une divergence entre moteurs : `10:00+02:00` était
  écrit 08:00 par PostgreSQL mais 10:00 par SQLite (qui ignore le fuseau).
  Vérification avant déploiement : une requête en lecture seule compte les
  `applied_at` hors plage (cast en TEXTE : un timestamp hors plage ferait échouer
  la lecture elle-même).
- Inscription concurrente de la même adresse : le contrôle de doublon lit puis
  insère, donc plusieurs requêtes passent le contrôle avant qu'aucune n'ait commité.
  C'est le `flush()` (l'INSERT dans users) qui lève la violation de la contrainte
  unique, pas le commit : le `try/except IntegrityError` de `register` couvre les
  deux. Sur violation : rollback, puis RELECTURE de l'email (pas d'analyse du
  message d'erreur : les noms de contraintes diffèrent entre PostgreSQL et SQLite).
  Le compte existe → le MÊME 409 que le contrôle préalable (constante
  `EMAIL_TAKEN_DETAIL`, corps identique par construction) ; il n'existe pas → autre
  violation d'intégrité, elle remonte en 500 visible et n'est jamais déguisée en
  « email déjà pris ». Le contrôle préalable est conservé. Le nombre de perdantes
  n'est pas aléatoire : 14 = 15 (pool 5 + 10) − 1. Avant correction : 14 x 500 /
  25 x 409 / 1 x 201 par manche de 40 requêtes, sous PostgreSQL comme SQLite.
- Adresses email NORMALISÉES à l'entrée (minuscules, sans espaces autour), par UN
  type partagé `NormalizedEmail` (schemas.py) : `Annotated[EmailStr,
  BeforeValidator(_normalize_email)]`. Avant, `Case@Example.com` et
  `case@example.com` donnaient deux comptes (l'index unique compare la casse ;
  EmailStr ne met en minuscules que le DOMAINE) et la connexion échouait dès que
  la casse tapée différait de celle de l'inscription. Aujourd'hui TOUS les champs
  email des schémas d'entrée l'utilisent (UserCreate, UserLogin,
  ForgotPasswordRequest) : l'index unique existant suffit alors à empêcher les
  doublons, sans contrainte supplémentaire en base (choix assumé : pas de
  `CHECK (email = lower(email))`, la normalisation à l'entrée et les tests font
  foi), et sans migration (production et cockpit.db : aucune adresse à convertir,
  vérifié le 2026-10-01).
  - Pourquoi un TYPE dédié et pas le validateur `'*'` d'InputModel : celui-ci vise
    tous les champs texte, mots de passe compris ; y passer en minuscules serait
    catastrophique. Le type suit le patron des alias existants (PresentedPassword…).
  - ORDRE (vérifié par exécution) : le `'*'` d'InputModel refuse d'abord le NUL et
    le surrogate isolé sur la valeur BRUTE, puis la normalisation, puis EmailStr
    valide l'adresse normalisée. Une valeur non textuelle traverse la
    normalisation intacte : EmailStr produit son erreur habituelle (catalogue de
    messages inchangé). Espaces à l'INTÉRIEUR : toujours refusés par EmailStr
    (EmailStr retirait déjà les espaces autour ; le `strip()` rend la règle
    explicite, indépendante d'un détail de Pydantic).
  - `lower()` et non `casefold()` (« ß » deviendrait « ss » : l'identité de
    l'adresse changerait). Idempotent.
  - Anti-énumération INCHANGÉE : les endpoints reçoivent la valeur déjà normalisée
    et ne se branchent jamais sur la casse ; la réponse de /auth/forgot-password et
    le 401 générique du login (corps ET en-têtes) sont identiques que le compte
    existe ou non, quelle que soit la casse (tests).
  - Un NOUVEAU schéma d'entrée portant un email doit utiliser `NormalizedEmail`.
    GARDE (test_email_normalization.py) : tout champ d'un InputModel typé `EmailStr`
    ou dont le nom contient « email » (même typé `str`) sans ce normaliseur fait
    échouer la suite. `UserRead.email` (sortie) reste un `EmailStr` nu : il relit
    la valeur stockée.
- Connus et NON traités : durcissements de fond prévus dans un lot séparé : schéma
  d'URL (`javascript:` accepté), espaces seuls acceptés côté backend. Saturation du
  pool : inscription et login gardent leur connexion pendant le hachage bcrypt
  (~0,2 s) ; environ 15 requêtes simultanées saturent le pool par défaut (5 + 10)
  et, au-delà de 30 s d'attente, `QueuePool timeout` donne un 500. Les limites de
  débit (cf. « Limites de débit ») la RÉDUISENT sans la supprimer : elles bornent
  chaque IP (au plus 60 connexions par minute, soit ~12 s de bcrypt) mais pas la
  concurrence GLOBALE ; un attaquant disposant de nombreuses adresses reste hors de
  leur portée. Un plafond global de hachages simultanés serait un lot séparé.
