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
