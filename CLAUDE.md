# Cockpit

SaaS de suivi de candidatures, tous types de contrats : CRM kanban (cœur du
produit) + extension navigateur pour l'ajout d'offres depuis n'importe quel site.
Agrégation via API officielles (La Bonne Alternance, France Travail) reportée
en V1.5. AUCUN scraping serveur, AUCUN stockage de credentials de sites tiers.

# Stack
- Backend : FastAPI + SQLAlchemy 2.0 + SQLite (dev/tests) ou PostgreSQL (prod)
- Frontend : React 19 + Vite + React Router 7 (dossier frontend/)
- Extension : Chrome Manifest V3 (dossier extension/)

# Commandes
Backend (depuis backend/, venv activé) :
- Installer : `.venv\Scripts\python.exe -m pip install -r requirements-dev.txt`
  (requirements-dev.txt inclut requirements.txt + pytest/httpx ; la PRODUCTION
  n'installe que requirements.txt)
- Créer/mettre à jour la base : `.venv\Scripts\python.exe -m alembic upgrade head`
  (l'API ne crée PLUS aucune table au démarrage : un cockpit.db neuf, ou en
  retard sur le schéma, s'obtient par cette commande. Cf. « Migrations »).
- Lancer l'API : `.venv\Scripts\python.exe -m uvicorn app.main:app --reload`
- Tests : `.venv\Scripts\python.exe -m pytest` (depuis backend/) — suite ciblée
  sécurité (auth, ownership). Base SQLite EN MÉMOIRE isolée, recréée à chaque
  test ; ne touche jamais cockpit.db et n'envoie aucun email (Brevo forcé en
  mode DEV dans tests/conftest.py). Voir « Tests backend » plus bas.
Frontend (depuis frontend/) :
- Installer : `npm install`
- Lancer : `npm run dev` (http://localhost:5173)
- Build : `npm run build` ; Lint : `npm run lint`

# Direction visuelle
- `DESIGN.md` à la racine est la référence unique pour tout ce qui touche au
  style : densité, échelle typographique, espacements, usage de la couleur,
  interdits. Le lire AVANT toute modification de CSS ou de rendu.
- Cockpit est un outil dense, consulté plusieurs fois par jour (référence de
  densité : Notion). La couleur et l'espace signalent, ils ne décorent pas.
- Les tokens (couleurs, espacements, typo) sont dupliqués dans le bloc `<style>`
  de `extension/popup.html` : toute modification de `tokens.css` doit y être
  répercutée dans la même passe.

# Architecture backend
- `app/models.py` = tables SQLAlchemy ; `app/schemas.py` = contrats Pydantic.
  Ne jamais exposer un modèle ORM directement dans une réponse API.
- Un router par ressource dans `app/routers/` (auth, boards, applications).
- Hiérarchie des données : User → Boards → Applications.
  - Un Board (tableau kanban) appartient à un User (board.user_id).
  - Une Application appartient à un Board (application.board_id). Elle ne porte
    PLUS de user_id : le propriétaire se déduit en chaîne (application → board →
    user), pour éviter toute redondance.
- Ownership : cloisonné par user. Pour un board, filtre direct sur board.user_id
  (helper `get_owned_board` dans routers/boards.py, réutilisé par applications).
  Pour une candidature, jointure application → board et filtre sur board.user_id.
  Accès à la ressource d'autrui → 404 (pas 403), pour ne pas confirmer un id.
- À l'inscription, un board par défaut "Mes candidatures" est créé : un user a
  TOUJOURS au moins un tableau. Corollaire : la suppression du DERNIER tableau
  d'un user est refusée (409). Supprimer un board supprime ses candidatures.
- Créer une candidature exige un board_id ; le serveur vérifie qu'il appartient
  au current_user (sinon 404). GET /applications filtre par ?board_id=,
  ?status_filter= et/ou ?archived= (cf. « Archivage des candidatures »).
- Le statut d'une candidature n'est PAS modifiable à la création (démarre
  toujours en "saved"/Repérée). Il évolue ensuite par PATCH, via deux chemins :
  le drag & drop entre colonnes, et le champ « statut » du formulaire, affiché
  UNIQUEMENT en mode édition (jamais à la création).

# Cascade de suppression (schéma + ORM)
- Déclarée à DEUX niveaux, complémentaires et non redondants :
  - SCHÉMA : `ondelete="CASCADE"` sur chaque ForeignKey (board.user_id →
    users.id, application.board_id → boards.id, security_token.user_id →
    users.id). C'est la BASE qui garantit qu'aucune ligne ne survit à son parent,
    quel que soit le chemin : ORM, script de maintenance, psql, migration. Sans
    cela, toute suppression contournant l'ORM échouait en PostgreSQL sur une
    violation de contrainte (le défaut d'une FK est NO ACTION, qui REFUSE de
    supprimer un parent encore référencé).
  - ORM : `cascade="all, delete-orphan"` sur les relations parentes. Toujours
    nécessaire — il porte la sémantique ORPHELIN (retirer un enfant de la
    collection de son parent le supprime), que la base ne connaît pas.
- `passive_deletes=True` sur ces mêmes relations articule les deux : SQLAlchemy
  ne charge plus les enfants pour les supprimer un par un, il émet UN SEUL DELETE
  sur le parent et laisse la base propager. Supprimer un user passait de
  1 SELECT par board + 1 DELETE par ligne à un unique `DELETE FROM users`.
  Comportement observable inchangé (test de non-régression dans
  test_account_deletion.py).
- SQLite n'applique PAS les clés étrangères par défaut, et le réglage est propre
  à CHAQUE CONNEXION. `app/database.py` pose donc un écouteur `connect` qui
  exécute `PRAGMA foreign_keys=ON` sur toute connexion SQLite. Sans lui, la
  cascade serait purement décorative en dev et dans les tests : supprimer un user
  laisserait des orphelins EN SILENCE, alors que la prod (PostgreSQL) irait bien.
  L'écouteur est posé sur la CLASSE `Engine`, pas sur l'instance : le moteur de
  test créé par tests/conftest.py en bénéficie sans le savoir.
- ⚠ CHANGEMENT DE SCHÉMA : toute modification de models.py exige une migration
  Alembic (cf. « Migrations »). Un changement de contrainte ou de colonne ne
  s'applique JAMAIS tout seul à une table existante, et rien ne le signale.
  Vérifié le 2026-09-25 : la prod PostgreSQL porte bien les `ON DELETE CASCADE`
  ci-dessus (les 3 FK), au même titre que cockpit.db.

# Limites de quantité (garde-fous anti-abus)
- Toutes les constantes sont dans `app/limits.py` (source unique, importée par
  les routers et par main.py) :
  - MAX_BOARDS_PER_USER = 10
  - MAX_APPLICATIONS_PER_USER = 300 (candidatures ACTIVES seulement, cf.
    « Archivage des candidatures »)
  - MAX_ARCHIVED_APPLICATIONS_PER_USER = 2000 (cf. même section)
  - MAX_REQUEST_BODY_BYTES = 1 Mo
- Vérifiées CÔTÉ SERVEUR à la création, jamais côté front : le front peut les
  afficher pour l'UX mais ne fait pas autorité (extension, curl… restent
  plafonnés). Dépassement → 409, et RIEN n'est créé.
- La limite de candidatures est GLOBALE par utilisateur, tous tableaux confondus
  (comptée via la chaîne d'ownership : jointure application → board, filtre sur
  board.user_id). Ce n'est PAS une limite par tableau : l'utilisateur répartit
  ses 300 candidatures librement. Répartir sur plusieurs tableaux ne permet donc
  pas d'en créer davantage.
- Le DÉPLACEMENT d'une candidature (PATCH board_id) ne fait AUCUN contrôle de
  limite, et c'est volontaire : déplacer ne change pas le total de l'utilisateur,
  donc la limite globale ne peut pas être contournée ainsi. Seule la création
  compte. Le PATCH garde évidemment son contrôle d'ownership sur le board cible.
- Taille des corps de requête : middleware ASGI `BodySizeLimitMiddleware`
  (main.py), qui refuse en 413 sur la foi de l'en-tête Content-Length, avant que
  l'endpoint ne bufferise le corps. Défense en profondeur applicative (utile en
  dev, sans proxy) ; en production le garde-fou AUTORITAIRE reste le reverse
  proxy (nginx `client_max_body_size`), seul capable de couper un client qui ment
  sur Content-Length ou l'omet (chunked). On n'implémente pas de comptage à la
  volée côté ASGI : renvoyer un 413 au milieu d'un flux déjà pris en charge par
  l'app provoque un double envoi de réponse.

# Limites de débit (connexion, inscription, mot de passe oublié)
- MENACES : deviner un mot de passe par essais répétés ; tester en masse des
  identifiants volés ailleurs ; créer des comptes en masse (chaque inscription fait
  envoyer un email par Brevo, sur le quota) ; saturer le serveur (une connexion coûte
  ~0,2 s de bcrypt et une connexion du pool). Code : `app/rate_limit.py` (compteurs,
  dépendances FastAPI), `app/client_ip.py` (lecture de l'IP), seuils dans `limits.py`.
- SEUILS, en FENÊTRE GLISSANTE, constantes dans `limits.py` :
  - connexion : 60 tentatives par minute et par IP, TOUTES confondues (celles dont
    le corps est invalide comptent aussi) ;
  - connexion : 5 ÉCHECS par quart d'heure et par COUPLE (IP, email visé) ; seuls
    les échecs comptent, une connexion réussie remet ce compteur à zéro. Le couple et
    non l'email seul : sinon n'importe qui bloquerait le compte d'un autre en
    échouant volontairement sur son adresse (il n'épuise que SON compteur) ;
  - inscription : 20 par heure et par IP (409 et 422 comptent aussi) ;
  - mot de passe oublié : 10 par heure et par IP, EN PLUS du plafond de 3 envois par
    heure et par compte, qui reste inchangé et silencieux.
  Les seuils par IP sont LARGES volontairement : derrière une IP partagée (école,
  entreprise), des dizaines de personnes légitimes apparaissent comme une adresse.
- RÉPONSE : 429, `{"detail": "<français>"}`, en-tête `Retry-After` (secondes entières,
  au moins 1 : le délai avant que la plus ancienne tentative comptée sorte de la
  fenêtre). Textes dans `error_messages.py` (`RATE_LIMITED_*_DETAIL`), statiques. Celui
  de la connexion invite à patienter ou à utiliser « Mot de passe oublié ».
- ORDRE : TOUTES les vérifications précèdent le calcul bcrypt, sinon elles ne
  protégeraient pas le serveur. Seuils par IP : dépendances de route (avant le corps
  de l'endpoint). Couple : `reserve_login_attempt` au tout début de `login`.
- ATOMICITÉ : `SlidingWindowCounter.hit` vérifie ET enregistre sous un verrou. Pour le
  couple, la tentative est RÉSERVÉE avant bcrypt puis effacée si la connexion réussit :
  seuls les échecs restent. Un contrôle séparé de l'enregistrement de l'échec laissait
  passer les ~15 requêtes simultanées (taille du pool) avant qu'aucune ne soit comptée
  (test de rafale : 20 mauvais mots de passe simultanés = exactement 5 bcrypt réels).
- ANTI-ÉNUMÉRATION : le compteur de couple s'incrémente de la même façon que le compte
  existe ou non (un email inconnu compte comme un mot de passe faux) : le 429 arrive au
  même moment, avec le même corps et le même `Retry-After`. La limite par IP de
  /auth/forgot-password peut être EXPLICITE (429) : elle ne dépend pas de l'existence
  du compte ; le plafond par compte, lui, reste silencieux. L'email du couple est celui
  du schéma, déjà normalisé : la casse ne permet pas d'esquiver.
- STOCKAGE EN MÉMOIRE, sans dépendance (décision). ⚠ HYPOTHÈSE D'INSTANCE UNIQUE : le
  backend tourne en UN SEUL processus (railway.json ne passe pas `--workers` ; le nombre
  de RÉPLICAS du service, réglage Railway, doit rester à 1). Conséquences acceptées :
  un redémarrage remet les compteurs à zéro ; pendant un déploiement l'ancienne et la
  nouvelle instance coexistent brièvement avec des compteurs séparés. À PLUSIEURS
  instances (workers, réplicas) chaque instance compterait de son côté : les seuils
  seraient multipliés par leur nombre. Il faudrait alors des compteurs PARTAGÉS (Redis
  avec expiration, ou une table PostgreSQL) en gardant l'interface de
  `SlidingWindowCounter` (`hit`, `clear`, `reset`) ; la lecture de l'IP ne change pas.
- MÉMOIRE BORNÉE (un attaquant qui varie IP ou emails ne peut pas la faire grossir) :
  - par clé, jamais plus de `limite` horodatages (une tentative refusée n'est pas
    enregistrée : marteler une clé bloquée ne prolonge pas le blocage) ;
  - PURGE : les clés sont gardées dans l'ordre de leur dernière tentative enregistrée,
    donc les expirées forment un préfixe ; chaque appel dépile par l'avant (coût
    amorti constant, ni balayage ni thread) ;
  - PLAFOND : `RATE_LIMIT_MAX_TRACKED_KEYS` = 10 000 clés par compteur. Atteint avec des
    clés encore vivantes, la MOINS RÉCEMMENT ACTIVE est oubliée (son quota est rendu)
    et un WARNING limité en fréquence est journalisé. On ne refuse JAMAIS une nouvelle
    clé : cela permettrait de bloquer tout le monde en remplissant la table. Une IP
    seule ne crée que 60 clés par minute ; seul un réseau d'adresses distinctes en
    profite, et il contourne déjà les seuils par IP ;
  - MESURÉ (tracemalloc, pire cas : 10 000 clés toutes pleines) : ~14,7 Mo (connexion
    par IP, 60 horodatages par clé), ~9,8 Mo (couple), ~9,5 Mo (inscription), ~9,5 Mo
    (mot de passe oublié), soit ~43 Mo si les quatre sont au plafond ; plusieurs
    centaines de milliers d'opérations par seconde.
- LECTURE DE L'IP DERRIÈRE RAILWAY (`client_ip.py`). MESURÉ en production le 2026-10-01
  par un diagnostic temporaire (commits fb9f5b0 puis son revert e60d5db), sans
  hypothèse sur Railway :
  - uvicorn ne réécrit PAS l'adresse (FORWARDED_ALLOW_IPS absente, défaut 127.0.0.1) :
    `request.client.host` vaut 100.64.0.x, plusieurs proxys internes différents ;
    limiter dessus partagerait des compteurs entre tous les utilisateurs ;
  - `X-Forwarded-For` arrive sous la forme « <client>, <saut du proxy> » ; un en-tête
    falsifié par le client (une ou deux valeurs) est ÉCARTÉ par Railway ; `X-Real-IP`
    porte le client (la valeur falsifiée est écrasée) ; `Forwarded` traverse TEL QUEL
    (falsifiable : JAMAIS lu) ;
  - NON mesuré : client IPv6 (la machine d'essai n'en avait pas), autre point d'entrée
    que bcn1, en-tête répété sur plusieurs lignes.
  MÉTHODE : avec N proxys de confiance (`TRUSTED_PROXY_COUNT`, 2 sur Railway), le client
  est la N-ième entrée de X-Forwarded-For EN PARTANT DE LA DROITE. Ce que le client
  écrit se retrouve à gauche et n'est jamais lu : correct que le proxy écrase l'en-tête
  (cas mesuré) ou qu'il y ajoute (d'où le choix contre la lecture de la première valeur
  ou de X-Real-IP). IPv6 regroupé par préfixe /64 (un client en contrôle un entier),
  IPv4 mappée ramenée à l'IPv4.
  REPLIS (toujours l'adresse TCP : compteur PARTAGÉ, jamais un contournement) avec
  WARNING limité en fréquence : moins d'entrées que de proxys, entrée qui n'est pas une
  IP, adresse TCP hors de `TRUSTED_PROXY_NETWORKS` (accès direct : en-tête forgeable).
  RISQUE RÉSIDUEL, sans repli ni avertissement : Railway retirerait un saut ET se
  mettrait à AJOUTER au lieu d'écraser. Refaire la vérification après tout changement
  d'infrastructure.
  ⚠ Ne JAMAIS poser FORWARDED_ALLOW_IPS / `--forwarded-allow-ips` : avec `*`, uvicorn
  prend la PREMIÈRE valeur (celle de gauche, falsifiable) comme adresse du client.
  `client_ip.py` suppose que `request.client` est l'adresse TCP brute.
- NON COUVERT (volontairement) : /auth/reset-password et /auth/verify-email (jetons de
  256 bits non devinables) ; DELETE /auth/me (vérifie un mot de passe avec bcrypt mais
  exige un jeton de session valide) ; la concurrence GLOBALE de hachages (un attaquant
  disposant de nombreuses adresses n'est pas borné, cf. « Saturation du pool »).
- CORS : `Retry-After` est dans `expose_headers` (main.py). Sans cela, un navigateur
  ne le montre pas au JavaScript d'une autre origine (front sur un autre domaine que
  l'API) : le front ne pourrait pas afficher le temps d'attente et retomberait EN
  SILENCE sur « bouton utilisable ». Gardé par un test
  (`test_retry_after_is_exposed_to_the_browser_on_a_cross_origin_429`). Affichage côté
  front : cf. « Architecture frontend », blocage après un 429.
- VÉRIFICATION APRÈS DÉPLOIEMENT (sans route de diagnostic) :
  1. AVANT de déployer : variable `TRUSTED_PROXY_COUNT=2` posée sur le service Railway,
     `FORWARDED_ALLOW_IPS` absente, réplicas = 1. Un déploiement qui démarre prouve que
     la valeur est syntaxiquement valide (une valeur invalide échoue au démarrage).
  2. Preuve que la valeur est LUE : 6 connexions ratées d'affilée sur un email inconnu,
     depuis UNE machine, doivent donner 401 x 5 puis 429 EXACTEMENT à la 6e, avec
     `Retry-After` proche de 900 ; répété sur 3 emails différents. Si la variable
     n'était pas lue, la clé serait l'adresse du proxy interne (3 proxys observés, les
     requêtes d'un même client se répartissent entre eux) : un 429 net à la 6e, trois
     fois de suite, est très improbable.
  3. Un autre réseau (partage de connexion du téléphone) : la 1re tentative sur l'un
     de ces emails déjà bloqués doit donner 401, pas 429 (le compteur suit le client).
  4. Un X-Forwarded-For forgé, différent à chaque requête, ne retarde pas le 429.
  5. Journaux Railway : aucun WARNING « Lecture de l'IP du client » (sinon la
     topologie diffère : repli sur l'adresse TCP).
  6. Une connexion normale depuis le navigateur fonctionne. Après 5 échecs sur un
     même compte (couple IP et email), le 6e envoi affiche le message du 429 dans le
     formulaire ET désactive le bouton avec le temps restant (« Réessayer dans 14
     min ») : cela prouve aussi que `Retry-After` est lisible depuis le front déployé.
     Un mot de passe de test sur un compte jetable évite de se bloquer soi-même
     (le blocage ne vise que cette IP et cet email, pendant 15 minutes).

# Archivage des candidatures
- `Application.archived_at` (DateTime nullable, migration 0003) : NULL = active,
  renseignée = archivée à cette date. Le SERVEUR pose la date (`utcnow()`),
  jamais le client : `archived_at` n'est PAS exposé en écriture dans
  `ApplicationUpdate`, seulement en lecture dans `ApplicationRead`. Deux
  endpoints dédiés, `POST /applications/{id}/archive` et `/unarchive` — pas de
  PATCH générique sur ce champ.
- Le STATUT (ApplicationStatus) n'est JAMAIS modifié par l'archivage ou le
  désarchivage : il reste celui qu'il était au moment d'archiver.
- 409 EXPLICITE (pas d'idempotence silencieuse) sur une action redondante :
  archiver une candidature déjà archivée, ou désarchiver une candidature déjà
  active. Un succès sur une action qui n'a rien fait masquerait un bug côté
  client — cohérent avec le reste du projet (ex. le 409 du dernier tableau).
- Deux plafonds DISTINCTS, comptés GLOBALEMENT par utilisateur (même chaîne
  d'ownership que les autres limites), une candidature ne comptant jamais dans
  les deux à la fois :
  - MAX_APPLICATIONS_PER_USER (300) sur les ACTIVES, à la CRÉATION.
  - MAX_ARCHIVED_APPLICATIONS_PER_USER (2000) sur les ARCHIVÉES, à
    l'ARCHIVAGE. 409 : « Limite de 2000 candidatures archivées atteinte.
    Supprimez d'anciennes archives pour en archiver de nouvelles. »
  - Le DÉSARCHIVAGE est lui aussi plafonné par les 300 actives — sans ce
    contrôle, la limite se contournerait en archivant puis désarchivant. 409 :
    « Limite de 300 candidatures actives atteinte. Supprimez ou archivez une
    candidature active pour faire de la place. » La candidature visée est
    encore archivée au moment du contrôle, donc jamais comptée par erreur
    parmi les 300 actives comparées au plafond.
- ⚠ CORRECTION DE COMPORTEMENT (pas un simple ajout) : le comptage des 300
  actives à la CRÉATION (`create_application`) filtrait auparavant TOUTES les
  candidatures, archivées comprises. Sans le filtre `archived_at IS NULL`,
  archiver ne libérait AUCUNE place — l'archivage n'aurait eu aucun intérêt.
  Test de non-régression : `test_creating_application_counts_only_active_towards_the_cap`
  (tests/test_archiving.py), qui aurait échoué avant cette correction.
- Toutes les LECTURES DE LISTE excluent les archivées par défaut, via
  `?archived=` sur `GET /applications` (`bool`, PAS optionnel : vaut `false`
  quand il est absent — un client qui ignore l'archivage, extension comprise,
  reçoit le comportement sûr). `?archived=true` n'affiche QUE les archivées,
  jamais un mélange.
  Le garde-fou vit dans `_visible_applications_query` (routers/applications.py),
  dont le paramètre `archived` n'a PAS de valeur par défaut : tout futur
  endpoint de liste qui la réutiliserait doit choisir explicitement — l'oubli
  lève une `TypeError` immédiate, pas un bug silencieux. Ce n'est PAS la valeur
  par défaut du paramètre de requête qui protège (elle ne protège que CET
  endpoint), c'est celle-ci.
- L'ACCÈS PAR IDENTIFIANT (`_get_owned_application`, donc `GET`/`PATCH`/`DELETE
  /applications/{id}`) N'EST PAS filtré par `archived_at`, décision
  DÉLIBÉRÉE : la correction d'une candidature depuis la future page d'archives
  en dépend (un PATCH doit rester possible sur une archivée, sans la
  désarchiver au passage).
- La cascade de suppression d'un tableau (cf. « Cascade de suppression »)
  emporte les candidatures ARCHIVÉES comme les actives — `ON DELETE CASCADE` ne
  distingue pas `archived_at`, aucune logique possible à ce niveau.
- `BoardRead` expose `active_applications_count` et `archived_applications_count`
  (routers/boards.py, `_to_board_read`), pour que le frontend puisse annoncer
  le nombre d'archives concernées avant de confirmer la suppression d'un
  tableau (lot frontend séparé). Calculés par DEUX requêtes COUNT par tableau
  (pas une agrégation), donc jusqu'à 2×MAX_BOARDS_PER_USER (20) requêtes
  supplémentaires sur `GET /boards`. MESURÉ (pas supposé), le 2026-09-28, sur
  PostgreSQL 18 jetable, 10 tableaux et ~200 candidatures chacun (2000 lignes,
  mélange actif/archivé) : 34 ms médiane sur 20 appels — négligeable à cette
  échelle (MAX_BOARDS_PER_USER = 10). À reconsidérer seulement si ce plafond
  changeait significativement.

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
  colonne String(50) inchangée). Les sources d'API (V1.5) s'ajouteront à cette
  liste le jour où elles existeront. `ApplicationRead.source` reste un `str` pour
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
  `test_rate_limit.py`, `test_client_ip.py`, `test_auth_rate_limit.py`.
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
  NOUVELLE clé n'est jamais refusée), journal limité, atomicité sous 200 threads, et
  les quatre seuils décidés écrits en dur. `test_client_ip.py` (lecture de l'IP) : la
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

# Emails, reset de mot de passe et vérification
- `app/email.py` est la SEULE frontière avec Brevo (API transactionnelle). Le
  reste du code n'appelle que `send_password_reset_email` /
  `send_verification_email`. Mode DEV : sans BREVO_API_KEY (ou sans
  BREVO_SENDER_EMAIL), rien n'est envoyé et le lien est logué dans la console.
- Les liens envoyés par email sont des `SecurityToken` : UNE table pour les deux
  usages, discriminés par `purpose` (password_reset | email_verification).
  Stockage du SHA-256 du token (jamais du clair) ; `secrets.token_urlsafe(32)` à
  la génération ; expiration 60 min (reset) / 24 h (vérification) ; usage unique
  via `consumed_at`. La vérification filtre TOUJOURS sur `purpose` : un lien de
  vérification ne doit jamais pouvoir réinitialiser un mot de passe.
- USAGE UNIQUE GARANTI, y compris en requêtes SIMULTANÉES. `_consume_token`
  (routers/auth.py) valide et consomme en UNE SEULE instruction : un
  `UPDATE security_tokens SET consumed_at = :now WHERE token_hash = :h AND
  purpose = :p AND consumed_at IS NULL AND expires_at >= :now RETURNING user_id`.
  Une ligne renvoyée = gagnante ; aucune = 400 identique à celui d'un jeton
  inconnu, expiré ou déjà consommé (rien de plus n'est révélé). Le défaut
  d'origine (SELECT, test de `consumed_at` en Python, écriture plus tard) laissait
  passer plusieurs requêtes avec le même jeton. MESURÉ avant correction : 15 x 200
  sur 20 reset simultanés (15 = pool 5 + 10), 15 x 200 sur 40 vérifications
  (SQLite) et 3 à 5 x 200 sur PostgreSQL 18 ; après : exactement 1 x 200, partout.
  - Pourquoi un UPDATE conditionnel et non `SELECT ... FOR UPDATE` : le même SQL
    tourne sur PostgreSQL et SQLite. SQLAlchemy IGNORE `FOR UPDATE` sur SQLite, les
    tests n'auraient alors exercé aucun verrou. PostgreSQL (READ COMMITTED) fait
    attendre la seconde requête sur le verrou de ligne puis réévalue le WHERE ;
    SQLite sérialise les écritures. `RETURNING` exige SQLite >= 3.35 (3.50.4 ici).
  - L'UPDATE doit rester la PREMIÈRE instruction de la transaction (sous SQLite,
    lire puis écrire expose à un « database is locked » immédiat), et le commit
    reste à l'appelant : mot de passe, `is_verified` et invalidation des autres
    liens de reset s'écrivent APRÈS la consommation, dans la même transaction,
    donc pour la seule requête gagnante. Ordre du reset : consommer, puis bcrypt,
    puis écrire, un seul commit ; un jeton invalide échoue toujours avant bcrypt.
    Si la transaction du gagnant est annulée, la consommation l'est aussi.
  - Garde : `tests/test_token_race.py`. Aucune migration (aucun changement de
    schéma).
- Vérification d'email NON BLOQUANTE (décision produit) : un compte non vérifié
  se connecte et utilise l'app normalement. `User.is_verified` est exposé dans
  UserRead pour que le front affiche un bandeau d'invitation.
- Un reset de mot de passe réussi passe `is_verified` à True : cliquer sur un
  lien reçu à cette adresse prouve qu'on y a accès, soit exactement ce que
  démontre la vérification d'email.
- Endpoints : POST /auth/forgot-password (public), /auth/reset-password (public,
  token), /auth/verify-email (public, token), /auth/resend-verification
  (authentifié). GET /auth/me (authentifié) renvoie l'utilisateur courant
  (UserRead) : le JWT ne portant que l'id, c'est le SEUL canal qui dit au front
  si l'adresse est vérifiée — et il reste à jour, contrairement à un état qui
  serait figé dans le token à la connexion.

# Session JWT : durée de vie et révocation
- 12 HEURES (720 minutes), pour couvrir une journée d'utilisation sans
  reconnexion. Réglable par ACCESS_TOKEN_EXPIRE_MINUTES sans redéploiement ;
  `ACCESS_TOKEN_EXPIRE_MINUTES` (app/security.py) est la seule source.
- Les jetons sont SANS ÉTAT : rien n'est stocké côté serveur, la signature suffit
  à les valider. Conséquence directe, ils sont IRRÉVOCABLES — se déconnecter
  efface le jeton du navigateur, mais une copie dérobée reste valable jusqu'à son
  expiration, et aucune action serveur ne peut l'annuler. L'EXPIRATION EST DONC
  LA SEULE BORNE à l'exploitation d'un jeton volé : 12 h, c'est douze fois la
  fenêtre d'attaque de l'ancienne heure. Compromis accepté en connaissance de
  cause, contre le confort d'une journée sans reconnexion.
- Seul levier de révocation existant : changer JWT_SECRET_KEY, qui invalide les
  jetons de TOUS les utilisateurs d'un coup. Mesure d'incident, pas de gestion
  courante.
- Baisser la valeur ne raccourcit PAS les sessions en cours : l'expiration est
  inscrite dans chaque jeton à l'émission. Le changement ne vaut que pour les
  connexions suivantes.
- ⚠ NE PAS ALLONGER DAVANTAGE sans introduire des REFRESH TOKENS (déjà en V3,
  cf. hors périmètre). C'est la réponse propre au dilemme confort/sécurité, et
  elle ne consiste pas à étirer la durée : un jeton d'accès COURT (15-30 min,
  donc fenêtre de vol réduite) accompagné d'un refresh token long, stocké EN BASE
  et donc révocable individuellement. On récupère alors ce que le sans-état
  interdit aujourd'hui — déconnecter un appareil, invalider une session
  compromise, sans toucher aux autres utilisateurs. Prolonger encore la durée
  actuelle ne ferait qu'aggraver le problème que les refresh tokens résolvent.
- L'expiration est couverte par test_auth.py (jeton expiré rejeté en 401 sur
  /auth/me et sur les endpoints de données, `exp` conforme à la durée
  configurée, jeton signé d'une autre clé rejeté). Ces tests n'existaient pas
  avant l'allongement : une régression sur la validation de `exp` serait
  parfaitement silencieuse — tout continuerait de marcher, les jetons ne
  cesseraient simplement jamais d'être valables.

# Suppression de compte (droit à l'effacement, RGPD)
- DELETE /auth/me (authentifié) supprime définitivement le compte courant et,
  par cascade, ses tableaux, leurs candidatures et ses jetons de sécurité. C'est
  un EFFACEMENT, pas une désactivation : aucune donnée personnelle ne subsiste.
- Le corps de la requête porte le MOT DE PASSE courant, vérifié avant toute
  suppression. Le JWT ne suffit délibérément pas : il prouve la session, pas
  l'identité. Un token peut fuiter et vit 12 h ; il autorise des actions
  réversibles, jamais la destruction définitive du compte. C'est une
  ré-authentification, pas une case à cocher.
- Mot de passe faux → 403, et non 401. L'appelant est DÉJÀ authentifié comme cet
  utilisateur : on ne lui apprend rien sur l'existence du compte (pas de sujet
  d'énumération ici). Un 401 signifierait « session invalide » et ferait purger
  le token côté front alors que la session est parfaitement valide.
- Front : page /account (protégée, atteignable depuis la navbar), avec une zone
  de suppression nettement séparée et une modale de confirmation exigeant le mot
  de passe. Ni window.confirm ni window.alert : une boîte native ne peut pas
  porter de champ de saisie, ignore les tokens et le thème, et son bouton « OK »
  ne nomme pas l'action. Après succès : purge du token local puis redirection
  vers /login (replace).
- Anti-énumération : /auth/forgot-password renvoie TOUJOURS le même message, que
  le compte existe ou non — y compris quand le plafond d'envois est atteint (pas
  de 429, qui trahirait l'existence du compte). Même principe que le 401
  générique du login.
- Rate limiting des emails sortants : 3 par heure et par (utilisateur, usage),
  compté sur `security_tokens.created_at` — pas de compteur dédié, pas de Redis,
  et le plafond survit à un redémarrage. /auth/resend-verification, lui, est
  authentifié : il peut répondre explicitement 429. Ce plafond par COMPTE reste
  inchangé et silencieux ; les limites par IP de /auth/forgot-password s'y ajoutent
  (cf. « Limites de débit »).

# Base de données : SQLite (dev) et PostgreSQL (prod)
- Le MÊME code tourne sur les deux : seule DATABASE_URL change. Tout ce qui
  dépend du moteur est concentré dans `app/database.py`, nulle part ailleurs.
  - dev/tests : `sqlite:///./cockpit.db` (défaut si la variable est absente)
  - prod : `postgresql+psycopg://user:mdp@hote:5432/base`
- Driver PostgreSQL : psycopg v3 (`psycopg[binary]`), pas psycopg2. C'est le
  driver maintenu, supporté nativement par SQLAlchemy 2.0 via le dialecte
  `postgresql+psycopg`. L'extra [binary] évite toute compilation C.
- `normalize_database_url()` réécrit l'URL au démarrage :
  - `postgres://` (fourni tel quel par Railway, Heroku, Render…) est un alias
    que SQLAlchemy REFUSE depuis la 1.4 → réécrit en `postgresql+psycopg://`.
  - `postgresql://` nu est aussi réécrit, sinon SQLAlchemy chercherait psycopg2,
    qui n'est pas installé.
  - Une URL déjà explicite n'est jamais touchée.
- Options de connexion branchées sur le moteur : `check_same_thread=False` est
  une option du module sqlite3 et ferait ÉCHOUER psycopg → SQLite uniquement.
  `pool_pre_ping=True` ne sert qu'en PostgreSQL (les hébergeurs managés coupent
  les connexions inactives ; sans ping, la première requête après une période
  creuse échoue sur une connexion morte).
- Convention datetime : toutes les colonnes DateTime sont NAIVES en UTC, via le
  helper `utcnow()` (security.py) — y compris les `default`/`onupdate` des
  modèles. Ne JAMAIS y mettre un `datetime.now(timezone.utc)` « aware » : SQLite
  laisse tomber le fuseau en silence, PostgreSQL le convertit vers le fuseau de
  la session avant stockage. Le même code écrirait des heures différentes selon
  le moteur, et fausserait le rate limiting des emails (comparaison sur
  created_at).
- Les tests restent sur SQLite en mémoire (cf. conftest.py) : rapides, isolés,
  aucune dépendance à un PostgreSQL local.
- Session SQLAlchemy par requête (`get_db`, database.py) : ouverte, puis fermée
  dans un `finally` (`db.close()`) ; aucun `rollback` explicite dans l'application,
  et il n'en faut pas : `Session.close()` termine la transaction en cours. Un
  EMPOISONNEMENT DE SESSION (une transaction non annulée qui ferait échouer les
  requêtes suivantes sur la même connexion) a été soupçonné après une DataError et
  ÉCARTÉ, preuve à l'appui, le 2026-09-26 : sur un vrai uvicorn et un PostgreSQL 18
  jetable, pool réduit à UNE connexion, la même connexion (un seul pid, 56
  emprunts) a servi toutes les requêtes ; juste après l'erreur, lectures et
  écritures du même compte et d'un autre compte réussissent, et aucune connexion
  n'est restée `idle in transaction`. Témoin : un `get_db` qui ne ferme jamais la
  session épuise le pool (`QueuePool ... timed out`, 500 en 6 s), donc le test sait
  détecter une session qui fuit. Ce qui ressemblait à un empoisonnement était un
  empoisonnement de DONNÉES (cf. `applied_at`, section « Validation des entrées »).
  Ne pas refaire ce diagnostic ; le pool n'est pas configurable dans l'app
  (database.py : `create_engine` sans `pool_size`), le montage d'essai remplaçait
  `sqlalchemy.create_engine` avant l'import de l'app.

# Migrations (Alembic)
- Le schéma est géré par Alembic (`alembic==1.20.0`, backend/alembic/), en dev
  comme en prod. `main.py` n'appelle PLUS `create_all()` : un `create_all`
  ne modifie jamais une table existante, c'est ce qui l'a fait remplacer.
  Les tests créent leur propre schéma (fixture `client`).
- Commandes (depuis backend/, toujours via le venv) :
  - `.venv\Scripts\python.exe -m alembic upgrade head` : applique les migrations
    (crée une base neuve).
  - `... -m alembic revision --autogenerate -m "description"` : génère une
    migration d'après models.py. TOUJOURS la relire : l'autogénération ne voit
    pas tout (renommage = drop + create, enums PostgreSQL, données).
  - `... -m alembic check` : liste les écarts modèles/base (code de sortie ≠ 0).
  - `... -m alembic current` / `history` : état et historique.
- Changer models.py exige une migration DANS LE MÊME lot : test_migrations.py
  échoue sinon.
- `alembic/env.py` prend l'URL dans `app.database.DATABASE_URL` (jamais dans
  alembic.ini, qui n'en contient aucune), donc normalisée comme celle de l'app.
  Il charge le .env, puis DATABASE_URL posée dans le shell PRIME. Il affiche
  `[alembic] cible : ...` à chaque commande : LIRE cette ligne avant d'écrire.
- Viser la PROD depuis le poste : poser `$env:DATABASE_URL` (valeur de
  `DATABASE_PUBLIC_URL` de Railway, l'URL interne n'est pas joignable) dans la
  SESSION shell uniquement, jamais dans .env, puis la retirer
  (`Remove-Item Env:DATABASE_URL`) ou fermer la fenêtre. Une session restée
  configurée vise la prod à la commande suivante.
- Historique : la révision 0001 (« baseline ») décrit le schéma tel que créé par
  l'ancien create_all. Elle a été marquée appliquée en prod et sur cockpit.db
  par `alembic stamp 0001` (2026-09-25), après comparaison en lecture seule
  (0 écart, `ON DELETE CASCADE` présents, libellés d'enum identiques). Elle ne
  s'exécute que pour bâtir une base neuve.
- Révision 0002 (« remove rejected status ») : retire `REJECTED` de l'enum
  `applicationstatus`. Voir la procédure ci-dessous, qui sert de modèle pour tout
  retrait de valeur d'enum.
- Révision 0003 (« archive applications ») : ajoute `applications.archived_at`
  (DateTime nullable, sans valeur par défaut). À l'opposé de 0002 : une SEULE
  instruction `ADD COLUMN`, aucun ajustement manuel du fichier généré. Mesuré
  (pas supposé), PostgreSQL 18, table de 50 000 lignes : 68 ms — une opération
  de métadonnées, pas une réécriture de table. Toutes les lignes existantes
  valent NULL après la migration (donc actives) : aucune donnée réinterprétée.
- Révision 0004 (« notes string 5000 ») : passe `applications.notes` de `Text` à
  `String(5000)`. Dans UNE transaction : `LOCK TABLE ... ACCESS EXCLUSIVE`, puis
  garde-fou qui échoue explicitement (nombre de notes et longueur maximale dans
  le message) si une note dépasse déjà 5000 caractères — il ne TRONQUE JAMAIS —,
  puis `ALTER COLUMN ... TYPE VARCHAR(5000)`. La valeur 5000 est en dur dans la
  migration (état figé du schéma), pas importée de limits.py. MESURÉ (pas
  supposé) sur PostgreSQL 18.6 jetable, 50 000 lignes, 18 Mo :
  - `text` → `varchar(5000)` RÉÉCRIT TOUTE LA TABLE (`relfilenode` change) :
    ~950 ms sous verrou exclusif. Négligeable pour cette base (quelques
    lignes), mais à savoir : sur une grosse table les écritures seraient
    bloquées pendant la réécriture.
  - Une valeur trop longue FAIT ÉCHOUER la conversion (« value too long for type
    character varying(5000) »), la transaction est annulée et rien n'est
    tronqué : même sans le garde-fou, aucune donnée n'est perdue. Le garde-fou
    sert à rendre l'échec lisible et actionnable.
  - Le downgrade (`varchar(5000)` → `text`) ne réécrit pas la table et ne perd
    rien (md5 du contenu identique dans les deux sens).
  Compatible avec la version précédente du code (elle n'écrit déjà que des notes
  de 5000 caractères au plus) : si le déploiement échoue, l'ancienne version
  continue de servir sur le schéma migré.
- Enums : SQLAlchemy stocke les NOMS des membres (`APPLIED`), pas les valeurs
  (`applied`) — à retenir pour toute requête SQL manuelle. Sous PostgreSQL ce
  sont des types natifs (`applicationstatus`, `tokenpurpose`) : on n'y retire
  pas une valeur (pas de `DROP VALUE`), il faut recréer le type, et l'opération
  échoue s'il reste une ligne portant la valeur retirée.
- Procédure de retrait d'une valeur d'enum (celle de 0002), dans UNE transaction :
  `LOCK TABLE ... ACCESS EXCLUSIVE` (aucune écriture concurrente entre contrôle
  et DDL), garde-fou qui échoue explicitement s'il reste une ligne portant la
  valeur, `ALTER TYPE ... RENAME TO ..._old`, `CREATE TYPE` à la nouvelle liste,
  `ALTER COLUMN ... TYPE ... USING col::text::type`, `DROP TYPE ..._old`. Un
  échec annule tout (vérifié : aucun type `_old` orphelin). Les valeurs sont
  écrites EN DUR dans la migration, jamais importées de app.models (une migration
  décrit un état figé du schéma). Le downgrade fait l'inverse et ne perd aucune
  ligne.
- ORDRE de déploiement pour RETIRER une valeur de statut : (1) le FRONT d'abord
  (retirer une colonne est compatible avec l'ancien backend, l'inverse ne l'est
  pas) ; vérifier en prod qu'aucune ligne ne porte la valeur (comptage en
  MAJUSCULES) et recharger tous les onglets ouverts (un ancien bundle peut encore
  écrire la valeur) ; (2) ensuite migration + backend. Une ligne restée avec la
  valeur retirée deviendrait invisible dans l'interface (BoardPage ignore un
  statut inconnu) et ne se corrigerait que par SQL ou par l'API.
- Migrations 0001 et 0002 testées sur un PostgreSQL 18.6 jetable (Docker) :
  upgrade/downgrade/upgrade, contenu des lignes identique (md5), libellés du type
  lus, cas d'échec, verrou face à une transaction concurrente, et
  `downgrade base` puis remontée depuis le vide (le `downgrade` de la baseline,
  qui supprime les types enum, fonctionne sur PostgreSQL).
- Une migration doit rester COMPATIBLE AVEC LA VERSION PRÉCÉDENTE DU CODE : si le
  nouveau code échoue son healthcheck, l'ancienne version continue de servir sur
  le schéma déjà migré (ajout de colonne nullable : oui ; renommage ou
  suppression : en deux déploiements).

# Variables d'environnement (backend/.env, cf. .env.example)
- DATABASE_URL (SQLite ou PostgreSQL, cf. section ci-dessus)
- ACCESS_TOKEN_EXPIRE_MINUTES : FACULTATIVE, défaut 720 (12 h). Durée de vie du
  jeton de session (cf. section « Session JWT »). Valeur non entière ou négative
  → échec explicite au démarrage, jamais de repli silencieux sur le défaut.
- JWT_SECRET_KEY : obligatoire en dev ET en prod (clé DIFFÉRENTE en prod).
  Absente, l'app démarre mais toute connexion échoue (RuntimeError explicite).
- CORS_ORIGINS : origines autorisées, séparées par des virgules, SANS slash
  final. Défaut http://localhost:5173.
- FRONTEND_URL : base des liens emails (défaut http://localhost:5173)
- BREVO_API_KEY, BREVO_SENDER_EMAIL (adresse validée dans Brevo),
  BREVO_SENDER_NAME (optionnel) — absentes = mode DEV, aucun envoi.
- TRUSTED_PROXY_COUNT : nombre de proxys entre le client et l'application, pour lire
  l'IP réelle dans X-Forwarded-For (limites de débit, cf. « Limites de débit »).
  Défaut 0 = l'en-tête est IGNORÉ (dev, tests). **2 sur Railway** (mesuré). Valeur non
  entière ou hors 0..10 → échec explicite au démarrage, jamais de repli silencieux.
- TRUSTED_PROXY_NETWORKS : FACULTATIVE, défaut `100.64.0.0/10`. Réseau(x) d'où
  viennent les connexions du proxy ; hors de là, l'en-tête est ignoré (accès direct).
- ⚠ Ne JAMAIS définir FORWARDED_ALLOW_IPS (ni `--forwarded-allow-ips`) : uvicorn
  lirait la valeur de GAUCHE de X-Forwarded-For, falsifiable (cf. « Limites de débit »).
- OBLIGATOIRES en production : DATABASE_URL, JWT_SECRET_KEY, CORS_ORIGINS,
  FRONTEND_URL, BREVO_API_KEY, BREVO_SENDER_EMAIL, **TRUSTED_PROXY_COUNT**. Les
  défauts des trois variables d'URL pointent sur localhost : oubliées, l'app démarre
  SANS erreur mais le front est bloqué par CORS et les liens emails sont inutilisables.
  TRUSTED_PROXY_COUNT oubliée : l'app démarre aussi sans erreur, mais l'IP lue est
  celle du proxy interne : TOUS les utilisateurs partagent quelques compteurs (un par
  proxy, 100.64.0.x), des utilisateurs légitimes sont bloqués. Aucun contournement
  possible (repli sûr), mais un blocage visible. La vérification après déploiement
  (cf. « Limites de débit ») confirme qu'elle est lue.

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

# Déploiement (Railway)
- Le backend vit dans `backend/`, pas à la racine : le service Railway doit
  avoir son **Root Directory réglé sur `backend`**, sinon ni requirements.txt ni
  railway.json ne sont trouvés. C'est le réglage qu'on oublie en premier.
- `backend/railway.json` porte la config de déploiement (préféré au Procfile :
  il exprime aussi le healthcheck et la politique de redémarrage) :
  - startCommand : `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`.
    Sans `--reload` (dev uniquement : il surveille les fichiers et redémarre).
    `0.0.0.0` et non 127.0.0.1, sinon le conteneur n'accepte aucune connexion
    venue de l'extérieur. `$PORT` est injecté par Railway et doit être respecté.
  - preDeployCommand `alembic upgrade head` : migre la base avant le démarrage
    (cf. plus bas). `alembic` est appelé nu, comme `uvicorn` : trouvé sous
    Nixpacks, confirmé au premier déploiement.
  - healthcheckPath `/health` : Railway attend que l'app réponde avant de
    basculer le trafic — pas de fenêtre d'erreurs au redémarrage.
- `backend/.python-version` épingle Python 3.13 (version de dev). Si le log de
  build montre une autre version, le repli est `runtime.txt` ou la variable
  NIXPACKS_PYTHON_VERSION.
- La base PostgreSQL est un service Railway séparé ; référencer
  `DATABASE_URL=${{Postgres.DATABASE_URL}}` plutôt que copier l'URL en dur.
- Migrations : `preDeployCommand` (`alembic upgrade head`, dans railway.json)
  s'exécute UNE fois par déploiement, avant le démarrage du nouveau conteneur.
  Si elle échoue, le déploiement est en échec et l'ANCIENNE version continue de
  servir ; PostgreSQL exécute le DDL en transaction, donc une migration en échec
  est annulée en bloc (base inchangée). Pas dans startCommand : cela
  s'exécuterait à chaque redémarrage et réplica, et `restartPolicyType:
  ON_FAILURE` (10 essais) rejouerait dix fois la même erreur.
- /health reste un test de vie et n'interroge PAS la base ni alembic_version :
  le coupler ferait tomber le service pour des raisons étrangères au schéma.
- Ordre de mise en place (fait le 2026-09-25) : la prod a été marquée
  `alembic stamp 0001` AVANT le premier déploiement contenant le pre-deploy.
  Sinon `upgrade head` aurait tenté de recréer des tables existantes (échec sans
  gravité mais déploiement rouge). Une NOUVELLE base (autre environnement) n'a
  pas besoin de stamp : `upgrade head` la construit.

# Architecture frontend
- `api/` centralise les appels backend. TOUS passent par `apiFetch`
  (api/client.js), qui ajoute le Bearer et purge le token sur 401.
  Jamais de `fetch` direct dans un composant.
- Aucun composant n'appelle `localStorage` directement : CHAQUE CLÉ a son propre
  module d'accès, et c'est le seul endroit autorisé à y toucher :
  `auth/token.js` (cockpit_token), `theme/storage.js` (cockpit_theme),
  `boards/lastBoard.js` (cockpit_last_board), `preferences/storage.js`
  (cockpit_sidebar_collapsed). Une nouvelle clé = un nouveau module de ce type.
  Le stockage peut être indisponible (navigation privée, données de site
  bloquées) et LEVER à la lecture comme à l'écriture : hors token, chaque module
  l'entoure d'un `try/catch` (lecture = valeur par défaut, écriture ignorée,
  sans erreur). Sans cela, `initTheme()` planterait avant le premier rendu.
- Repli de la sidebar des tableaux : état PARTAGÉ (`preferences/`,
  `SidebarProvider` monté dans main.jsx au-dessus du routeur), commun au kanban
  et à la page d'archives, mémorisé, dépliée par défaut. Repliée, la sidebar est
  `inert` (hors clavier) et les cibles de dépôt de `Sidebar.jsx` sont désactivées.
- Contexte d'auth (auth/) : état isAuthenticated, login/logout, plus `user`
  (chargé via GET /auth/me dès qu'un token existe, rechargeable par refreshUser).
  `user` peut être null même connecté (chargement, ou /auth/me en échec) : son
  absence ne bloque JAMAIS l'app, elle masque seulement le bandeau de vérification.
- Routes protégées (ProtectedRoute) et routes invité (GuestRoute). Les pages
  atteintes depuis un lien email (/forgot-password, /reset-password,
  /verify-email) n'ont AUCUNE garde : le token de l'URL fait autorité, pas la
  session — un connecté qui clique son lien de vérification ne doit pas être
  redirigé.
- `constants/applicationStatuses.js` = source unique des statuts (clé technique
  + libellé français + ordre des colonnes). Miroir exact de l'enum
  `ApplicationStatus` côté backend : toute évolution se fait des deux côtés
  (5 statuts depuis le retrait de « rejected »). Pour RETIRER un statut, le front
  passe en premier (cf. « Migrations », ordre de déploiement).
- Cartes du kanban : la carte entière est cliquable et ouvre la modale
  d'édition. Aucune action n'est affichée sur la carte. Le titre reste un lien
  vers l'offre (stopPropagation), sans style de lien. Le drag & drop
  (@dnd-kit) est pointeur uniquement : vérifier qu'un ajout d'élément
  interactif sur une carte ne le perturbe pas.
- Landing page (`pages/LandingPage.jsx`, `styles/landing.css`, route `/` derrière
  GuestRoute). Règles de style : section « Landing page » de DESIGN.md.
  - Le hero réutilise `KanbanColumn` et `ApplicationCard` tels quels, avec des
    candidatures FICTIVES codées en dur (`DEMO_APPLICATIONS`). Leurs dates sont
    calculées à partir d'aujourd'hui (`daysAgo`, ISO naïf UTC comme le backend) : l'âge
    affiché reste plausible à chaque visite.
  - Démo déplaçable à titre d'exemple : un `DragDropProvider` LOCAL, l'état dans un
    `useState`, `onDragEnd` qui ne fait que changer le statut. AUCUN appel API, rien
    de stocké : un rechargement remet les cartes à leur place. Pas de zone
    d'archivage. Sans `DragDropProvider`, `useDraggable`/`useDroppable` créent des
    instances inertes (dnd-kit : `useInstance` tolère un manager absent) : c'est ce
    qui permet de réutiliser les composants du kanban hors de `BoardPage`.
  - Cartes HORS de l'ordre de tabulation : dnd-kit pose `tabindex="0"` sur chaque
    carte (seulement si l'attribut est absent, et de façon différée). La landing force
    `tabindex="-1"` avec un `MutationObserver` local plutôt que de modifier les
    composants partagés pour un besoin propre à une page.
  - ⚠ Tester la démo dans un navigateur AU PREMIER PLAN : dnd-kit met à jour la
    position par `requestAnimationFrame`, qui ne s'exécute pas dans un onglet masqué
    (ni dans un navigateur piloté en arrière-plan). La carte reste alors figée et le
    dépôt retombe sur la colonne d'origine, sans erreur.
  - SECTION CONFIANCE (« Ce que Cockpit fait de vos données ») : chaque phrase a été
    vérifiée dans le code, et DOIT être revérifiée si l'extension change (permissions,
    extraction, authentification). Ce qui la fonde : l'extension n'a que `activeTab`,
    `scripting` et `storage` ; l'extraction n'a lieu qu'à l'ouverture de la popup, sur
    l'onglet courant, et rien n'est envoyé avant la validation du formulaire ; le seul
    mot de passe demandé est celui de Cockpit (aucun mot de passe de site d'emploi) ;
    DELETE /auth/me efface le compte et, par cascade, ses tableaux et candidatures.
    Ne JAMAIS écrire « aucun scraping » : l'extension lit bien le contenu de la page
    d'offre visitée, à la demande de l'utilisateur.
  - Pas de promesse sur l'avenir : la page décrit ce qui existe. La mention « Gratuit,
    sans carte bancaire », ajoutée un temps près du bouton, a été retirée à la
    demande du propriétaire (« fait un peu trop ») : ne pas la réintroduire sans
    accord. Le public est TOUS les types de contrat (alternance, CDI, CDD, stage) : le
    nom du dépôt est un héritage.
- Blocage après un 429 (limites de débit, cf. « Limites de débit ») : connexion,
  inscription et mot de passe oublié partagent UNE logique, pas trois copies.
  - `ApiError.retryAfter` (api/client.js) : délai du serveur en SECONDES ENTIÈRES lu
    dans l'en-tête `Retry-After`, ou `null`. `utils/retryAfter.js` (fonctions pures,
    sans React ni Vite) : seul le format « secondes entières » est accepté, plafonné à
    24 h ; une date HTTP, du texte, 0, un négatif ou une valeur démesurée donnent
    `null`. Aucune date n'est interprétée : la comparer à l'horloge du poste
    produirait une durée fausse sur un poste déréglé.
  - `auth/useRateLimitCooldown.js` : le hook. `handle(err)` renvoie true si c'est un
    429 AVEC un délai lisible ; le message du serveur reste alors affiché pendant tout
    le blocage (même si l'utilisateur modifie les champs), le bouton est désactivé et
    indique le temps restant arrondi à la minute SUPÉRIEURE (« Réessayer dans 14
    min »), mis à jour chaque minute par UN `setTimeout` calé sur le prochain
    changement de minute (pas de `setInterval`, pas de compte à la seconde). À
    l'échéance, le message disparaît et le bouton redevient actif. `handleSubmit`
    refuse aussi d'envoyer pendant le blocage. L'heure courante vit dans un état
    (jamais lue pendant le rendu : règles du compilateur React du lint). Un onglet
    masqué voit ses minuteurs ralentis par le navigateur : `visibilitychange`
    recalcule au retour.
  - SANS délai lisible (en-tête absent ou illisible), `handle` renvoie false : la page
    traite le 429 comme une erreur ordinaire (message affiché, bouton utilisable). On
    ne bloque jamais l'utilisateur sur une durée inventée ; le serveur continue de
    refuser tant qu'il le faut.
  - AUCUNE mémorisation, aucun accès à localStorage : un rechargement oublie le blocage,
    la tentative suivante renvoie un 429 avec le délai à jour.
  - Inscription réussie puis connexion automatique refusée en 429 : le compte EXISTE.
    RegisterPage redirige vers /login avec `state: { accountCreated: { until } }` ;
    LoginPage affiche « Votre compte est créé. … vous pourrez vous connecter à partir
    de HH:MM » (heure d'échéance arrondie à la minute supérieure) et désactive le
    bouton. Contrairement aux autres messages de blocage, celui-ci porte une
    information durable : à l'échéance il NE disparaît PAS, il devient « Votre compte
    est créé, vous pouvez maintenant vous connecter. » (variante succès) et ne
    disparaît qu'à l'envoi suivant. Sans délai lisible : « …connexion momentanément
    limitée : réessayez dans quelques minutes », bouton actif. L'état de navigation
    est recopié dans un état local puis effacé de l'historique (même schéma que
    `sessionExpired`) : un rechargement repart vierge.
  - Vérifié dans le navigateur (backend local aux fenêtres raccourcies, Vite sur un
    autre port, donc en cross-origin réel) : message conservé pendant la saisie,
    bouton et libellé « 2 min » puis « 1 min », levée à l'échéance, envoi forcé sans
    appel réseau, `Retry-After` absent ou en date HTTP (bouton utilisable), inscription
    puis connexion bloquée, 429 sur l'inscription et sur /forgot-password. Le frontend
    n'a pas de lanceur de tests : les fonctions pures ont été vérifiées par un script
    node jetable, pas par un test du dépôt.
- URL du backend : `VITE_API_BASE_URL` (cf. frontend/.env.example), lue dans
  api/client.js avec repli `http://127.0.0.1:8000`. Le « / » final est retiré,
  les endpoints étant concaténés directement.

# Variables Vite : injectées au BUILD, pas au runtime
- Différence FONDAMENTALE avec le backend, qui lit `os.getenv` au démarrage et
  qu'il suffit donc de redémarrer : Vite ne lit pas d'environnement dans le
  navigateur (il n'y en a pas). `npm run build` REMPLACE textuellement chaque
  `import.meta.env.VITE_X` par sa valeur littérale dans le bundle. Le JS livré
  contient l'URL en dur ; il n'existe plus aucune variable à l'exécution.
- Conséquences pour le déploiement :
  - `VITE_API_BASE_URL` doit être définie AU MOMENT DU BUILD (variable du
    service front sur Railway, pas du service backend).
  - Changer l'URL de l'API impose de REBUILDER et redéployer le front.
    Redémarrer le conteneur ne change rien : le bundle est déjà figé.
  - Une variable ajoutée après coup dans le dashboard n'a AUCUN effet tant
    qu'aucun build n'a été relancé — symptôme classique : le front déployé
    continue d'appeler 127.0.0.1:8000 et échoue chez tous les utilisateurs.
  - Tout ce qui est préfixé VITE_ est PUBLIC (lisible dans le bundle) : jamais
    de secret. Les secrets restent côté backend.

# Règles
- Toujours valider les entrées API avec des modèles Pydantic.
- Jamais de secrets en dur : tout passe par les variables d'environnement
  (.env backend, VITE_ pour le front).
- Installer les dépendances Python UNIQUEMENT via
  `.venv\Scripts\python.exe -m pip install -r requirements-dev.txt`
  (chemin explicite, ne jamais utiliser `py` ni `pip` nus).
  Une dépendance nécessaire EN PRODUCTION va dans requirements.txt ; une
  dépendance de test uniquement va dans requirements-dev.txt. Toute nouvelle
  dépendance s'ajoute avec une version EXACTE (==), cf. section ci-dessus.
- Style backend : type hints partout, docstrings en français, code en anglais.
- Commits en anglais, format conventional commits (feat:, fix:, docs:...).
- Ne pas ajouter de dépendance sans la justifier dans le message de commit.
- Toute modification de style suit DESIGN.md (cf. « Direction visuelle »).

# Roadmap V1
1. [fait] CRUD candidatures + extension navigateur (extraction générique + JSON-LD)
2. [fait] Auth JWT multi-utilisateurs (inscription, login, protection, ownership)
3. Front React
   - [fait] Setup Vite + structure
   - [fait] Couche API + contexte d'auth
   - [fait] Écrans Login/Register + routes protégées
   - [fait] Kanban en lecture seule
   - [fait] Création / édition / suppression de candidatures (modale)
   - [fait] Drag & drop des cartes entre colonnes
   - [fait] Champ statut dans le formulaire, en mode édition uniquement
4. Reconnecter l'extension à l'auth (elle ne peut plus créer sans token)
5. Multi-tableaux (Boards)
   - [fait] Backend : modèle Board, CRUD, ownership en chaîne, board par défaut,
     dernier tableau non supprimable, cascade
   - [fait] Front : sélection/gestion des tableaux, board_id à la création
6. Design du site (en cours)
   - [fait] DESIGN.md : direction visuelle, échelle typo, espacements, couleur
   - [fait] Refonte du kanban : densité, carte cliquable, tokens, contrastes
   - [fait] Refonte de la landing page : slogan en titre, vrai kanban de démonstration
     déplaçable (sans persistance), section confiance, extension présentée une fois,
     tous types de contrat, anciens styles `.landing-*` supprimés de components.css
   - [à faire] Reste de l'application (formulaires, page compte)
7. Mot de passe oublié + vérification d'email (Brevo)
   - [fait] Backend : app/email.py, SecurityToken, 4 endpoints, rate limiting
   - [fait] Front : écrans /forgot-password, /reset-password, /verify-email
     (routes PUBLIQUES, sans garde) + bandeau "confirmez votre adresse"
     (is_verified via GET /auth/me) avec renvoi de l'email
8. Déploiement (backend + PostgreSQL sur Railway)
9. [fait] Archivage des candidatures
   - [fait, déployé le 2026-09-28] Backend : champ archived_at (migration
     0003), statut conservé à l'archivage, endpoints /archive et /unarchive,
     plafond de 2000 archivées, plafond de 300 actives au désarchivage,
     correction du comptage des 300 (n'exclut plus les archivées à tort),
     filtre ?archived= par défaut sur les listes, compteurs sur BoardRead —
     confirmé en production (`alembic current` → 0003 head)
   - [fait] Front : page d'archives (liste, recherche insensible aux accents
     et à la casse, tri par date d'archivage), archivage depuis la modale
     d'édition et par glisser-déposer sur le kanban, ancienneté affichée sur
     les cartes (en bas à droite, sur la ligne du lieu — présente même sans
     lieu), mise en page de la page d'archives (bordures de ligne alignées,
     largeurs de colonnes fixes, page centrée, recherche à 440px, cellules
     plafonnées à deux lignes) — committé et poussé sur origin/main (`git
     log`), déployé comme le reste du front
   - [à faire] Filtre par tableau sur la page d'archives (emplacement réservé
     dans la mise en page)
   - [à faire] Confirmation de suppression d'un tableau annonçant le nombre
     d'archives concernées (BoardRead expose déjà
     archived_applications_count, rien ne l'utilise côté front)
   - [fait] Suppression du statut "Refusée" : front (2a) déployé ; migration
     0002 + backend (2b) déployés le 2026-09-26 (confirmé : `alembic current`
     → 0002 head, cinq libellés d'enum relus en base) ; textes résiduels de la
     landing, du README et des commentaires nettoyés
10. [fait] Durcissement de la validation des entrées (lots 3a-3e)
    - [fait, déployé] 3a : mini-lot applied_at (bornes 1900-2100, conversion
      UTC) et correctif de la course d'inscription concurrente
    - [fait, déployé] 3b/3c : schémas Pydantic (InputModel, rejet du NUL et du
      surrogate isolé, PydanticCustomError), catalogue de messages d'erreur,
      format de réponse unique (detail + errors), les deux trous corrigés (401
      anonyme, 500 catch-all)
    - [fait, committé, en attente de republication sur le Chrome Web Store]
      3d : extension alignée sur les mêmes limites (troncature du lieu,
      nettoyage des URL trop longues, maxLength, ApiError.data) — la version
      publiée est antérieure à ce lot, numéro de version du manifest inchangé
    - [fait] 3e : migration 0004, `notes` passe de
      `Text` à `String(5000)` (longueur tirée de MAX_NOTES_LENGTH) : la borne est
      désormais appliquée par l'API ET par la base, comme tous les autres champs
      texte. Garde-fou explicite si une note dépasse déjà 5000 caractères,
      jamais de troncature. Testée sur PostgreSQL 18.6 jetable (aller-retour avec
      données, échec du garde-fou, échec de conversion sans troncature)

# Hors périmètre V1 (ne pas implémenter sans demande explicite)
- Agrégation API officielles (La Bonne Alternance, France Travail) → V1.5
- Formulaire de correction dans l'extension → V2
- Alertes email, statistiques, paiement → V2
- Connexion Google, refresh tokens, UUID → V3
