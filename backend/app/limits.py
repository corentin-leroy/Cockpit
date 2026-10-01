"""Limites de quantité — garde-fous anti-abus, vérifiés CÔTÉ SERVEUR.

Ces plafonds protègent la base d'un usage abusif (création en boucle de tableaux
ou de candidatures, corps de requête démesurés). Ils sont TOUJOURS contrôlés à la
création côté backend : le front peut les afficher pour l'UX, mais ne fait jamais
autorité — un client qui contourne le front (extension, curl…) reste plafonné.

Source unique : ces constantes sont importées par les routers concernés
(boards, applications) et par le middleware de taille de requête (main.py).
"""

from datetime import datetime

# Nombre maximum de tableaux par utilisateur. Un compte a toujours ≥ 1 tableau
# (board par défaut à l'inscription) ; ce plafond borne l'autre extrémité.
MAX_BOARDS_PER_USER = 10

# Nombre maximum de candidatures par utilisateur, GLOBAL (tous tableaux confondus).
# Ce n'est PAS une limite par tableau : l'utilisateur répartit librement ses 300
# candidatures entre ses tableaux. Le total se compte via la chaîne d'ownership
# (candidatures dont le board appartient à l'utilisateur).
MAX_APPLICATIONS_PER_USER = 300

# Nombre maximum de candidatures ARCHIVÉES par utilisateur, GLOBAL (tous
# tableaux confondus), compté via la même chaîne d'ownership que
# MAX_APPLICATIONS_PER_USER. Distinct de ce dernier : une candidature archivée
# ne compte PLUS dans la limite des actives (cf. create_application), donc les
# deux plafonds ne se recoupent jamais pour une même ligne.
MAX_ARCHIVED_APPLICATIONS_PER_USER = 2000

# Taille maximale du corps d'une requête HTTP, en octets (1 Mo). Évite qu'une
# charge utile énorme (ex. un champ `notes` de plusieurs Mo) ne consomme mémoire
# et stockage. Appliqué globalement par un middleware (voir main.py).
MAX_REQUEST_BODY_BYTES = 1 * 1024 * 1024

# --- Longueurs de champs (en CARACTÈRES sauf mention contraire) ---
# Bornes de validation des entrées, importées par schemas.py. Elles ne doivent
# JAMAIS dépasser la longueur de la colonne correspondante (models.py) : une borne
# plus large que la colonne laisse passer la validation puis échoue à l'écriture
# en PostgreSQL (500 au lieu d'un 422). tests/test_input_validation.py vérifie
# cette cohérence. SQLite n'applique pas les longueurs de VARCHAR : seul PostgreSQL
# révèle l'écart, d'où ce test indépendant du moteur.
MAX_TITLE_LENGTH = 255  # applications.title  String(255)
MAX_COMPANY_LENGTH = 255  # applications.company String(255)
MAX_LOCATION_LENGTH = 255  # applications.location String(255)
MAX_URL_LENGTH = 2048  # applications.url String(2048)
MAX_BOARD_NAME_LENGTH = 100  # boards.name String(255) : borne API plus stricte
# notes : applications.notes String(MAX_NOTES_LENGTH). models.py lit CETTE
# constante pour la longueur de la colonne (migration 0004, lot 3e) : borne API et
# colonne ne peuvent plus diverger. La modifier exige une nouvelle migration.
MAX_NOTES_LENGTH = 5000

# Mot de passe CHOISI (inscription, réinitialisation), en OCTETS UTF-8 (un « é » en
# pèse 2) : bcrypt ignore tout ce qui dépasse 72 octets, donc deux mots de passe qui
# ne diffèrent qu'après le 72e ouvriraient le même compte. Accepter davantage laisse
# croire que toute la longueur compte. Le minimum (8 CARACTÈRES) est dans schemas.py.
# Les comptes existants au mot de passe plus long continuent de se connecter : bcrypt
# les tronquait déjà de façon identique à l'inscription (cf. MAX_PASSWORD_INPUT_BYTES).
MAX_CHOSEN_PASSWORD_BYTES = 72
# Mot de passe PRÉSENTÉ (login, suppression de compte), en OCTETS UTF-8 et non en
# caractères : passlib compte les octets et lève PasswordSizeError au-delà de 4096.
# Une borne en caractères laisserait un 500 pour les mots de passe multi-octets
# (2049 « é » = 4098 octets). Borne haute technique uniquement, jamais un minimum :
# on ne rejoue pas la politique d'inscription à la connexion.
MAX_PASSWORD_INPUT_BYTES = 4096

# Plage acceptée pour la date de candidature (applied_at), en UTC naïf, bornes
# INCLUSES. PostgreSQL stocke des dates de 4713 av. J.-C. à l'an 294276 alors que
# Python et psycopg ne relisent que les années 1 à 9999 : une date hors de cette
# plage (obtenue par ex. en convertissant en UTC un an 1 avec fuseau) est écrite
# et commitée, puis sa RELECTURE échoue — la ligne devient illisible, la liste des
# candidatures de tout le compte donne 500 et même la suppression échoue. Une plage
# large mais bornée protège de ça sans rejeter de saisie réaliste.
MIN_APPLIED_AT = datetime(1900, 1, 1)
MAX_APPLIED_AT = datetime(2100, 12, 31, 23, 59, 59, 999999)

# ---------------------------------------------------------------------------
# Limites de débit (app/rate_limit.py), en FENÊTRE GLISSANTE, compteurs en mémoire.
# Les seuils par IP sont volontairement LARGES : derrière une IP partagée (école,
# entreprise), des dizaines de personnes légitimes apparaissent comme une seule
# adresse.
# ---------------------------------------------------------------------------
# Connexion : toutes tentatives confondues, par IP.
LOGIN_MAX_ATTEMPTS_PER_IP = 60
LOGIN_IP_WINDOW_SECONDS = 60
# Connexion : ÉCHECS seulement, par COUPLE (IP, email visé) ; une connexion réussie
# remet le compteur à zéro. Le couple et non l'email seul : sinon n'importe qui
# bloquerait le compte d'un autre en échouant volontairement sur son adresse.
LOGIN_MAX_FAILURES_PER_PAIR = 5
LOGIN_PAIR_WINDOW_SECONDS = 15 * 60
# Inscription : par IP (chaque inscription fait envoyer un email par Brevo).
REGISTER_MAX_PER_IP = 20
REGISTER_IP_WINDOW_SECONDS = 60 * 60
# Mot de passe oublié : par IP, EN PLUS du plafond de 3 envois par heure et par
# compte (routers/auth.py, MAX_EMAILS_PER_HOUR), qui reste inchangé et silencieux.
FORGOT_PASSWORD_MAX_PER_IP = 10
FORGOT_PASSWORD_IP_WINDOW_SECONDS = 60 * 60
# Mémoire bornée : nombre maximal de CLÉS suivies par compteur. Atteint avec des
# clés encore vivantes, la moins récemment active est oubliée (jamais de refus des
# nouvelles clés : cela permettrait de bloquer tout le monde en remplissant la table).
RATE_LIMIT_MAX_TRACKED_KEYS = 10_000

# Plus grand identifiant accepté : entier signé 32 bits, le type `integer` de
# PostgreSQL. Au-delà, la base lève « integer out of range » (500). Les
# identifiants sont des entiers >= 1 : 0 et les négatifs sont malformés (422).
MAX_ID = 2_147_483_647
