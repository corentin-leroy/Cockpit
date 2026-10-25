# Emails, reset de mot de passe et vérification
- `app/email.py` est la SEULE frontière avec Brevo (API transactionnelle). Le
  reste du code n'appelle que `send_password_reset_email` /
  `send_verification_email` / `send_google_sign_in_notice_email`. Mode DEV : sans
  BREVO_API_KEY (ou sans BREVO_SENDER_EMAIL), rien n'est envoyé et le lien est
  logué dans la console.
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
    donc pour la seule requête gagnante. Ordre du reset : consommer, puis refuser
    un compte sans mot de passe, puis bcrypt, puis écrire (mot de passe,
    `is_verified`, `token_version + 1`, autres liens caducs), un seul commit ; un
    jeton invalide échoue toujours avant bcrypt. Si la transaction du gagnant est
    annulée, la consommation l'est aussi.
  - Garde : `tests/test_token_race.py`. Aucune migration (aucun changement de
    schéma).
- Vérification d'email NON BLOQUANTE (décision produit) : un compte non vérifié
  se connecte et utilise l'app normalement. `User.is_verified` est exposé dans
  UserRead pour que le front affiche un bandeau d'invitation.
- Un reset de mot de passe réussi passe `is_verified` à True : cliquer sur un
  lien reçu à cette adresse prouve qu'on y a accès, soit exactement ce que
  démontre la vérification d'email. Il RÉVOQUE aussi toutes les sessions ouvertes
  du compte (`token_version + 1`, cf. `dev-docs/jwt-session.md`) : un mot de passe
  change souvent parce qu'il a fuité.
- COMPTES SANS MOT DE PASSE (`hashed_password` NULL : connexion avec Google, cf.
  `dev-docs/google-sign-in.md`). Ils n'en retrouvent JAMAIS :
  - /auth/forgot-password : MÊME réponse à l'écran, AUCUN jeton émis. À la place,
    l'email `send_google_sign_in_notice_email` (Brevo), sujet « Connexion à votre
    compte Cockpit », titre « Votre compte se connecte avec Google » : « Vous avez
    demandé à réinitialiser le mot de passe de votre compte Cockpit. Ce compte n'a
    pas de mot de passe : il se connecte avec Google. Sur la page de connexion,
    choisissez « Continuer avec Google ». Si vous n'êtes pas à l'origine de cette
    demande, ignorez cet email. » Bouton « Se connecter » vers FRONTEND_URL +
    `/login` : aucun lien de réinitialisation, aucun jeton.
  - Plafond de cet email : 3 par heure et par COMPTE, SILENCIEUX (même réponse
    au-delà, aucun 429). Compteur EN MÉMOIRE (`limiters.google_notice`,
    app/rate_limit.py) et non `security_tokens.created_at` : aucun jeton n'est
    émis, il n'y a rien à compter en base. Remis à zéro par un redémarrage
    (accepté : 3 envois de plus au pire). Les 10 demandes par heure et par IP
    s'appliquent avant, comme pour tout compte.
  - /auth/reset-password : un lien encore en attente (demandé quand le compte
    avait un mot de passe, avant sa liaison à Google au lot 2) renvoie le MÊME 400
    qu'un jeton inconnu (`INVALID_LINK_DETAIL`, constante partagée avec
    `_consume_token`), APRÈS la consommation et AVANT bcrypt. Rien n'est commité :
    la consommation est annulée avec la session, rien ne change en base.
  - Lot 1 : aucun compte sans mot de passe n'existe encore, cet email ne part donc
    jamais en production avant le lot 2.
- Endpoints : POST /auth/forgot-password (public), /auth/reset-password (public,
  token), /auth/verify-email (public, token), /auth/resend-verification
  (authentifié). GET /auth/me (authentifié) renvoie l'utilisateur courant
  (UserRead) : le JWT ne portant que l'id et la version des sessions, c'est le
  SEUL canal qui dit au front si l'adresse est vérifiée et si le compte a un mot
  de passe (`has_password`) — et il reste à jour, contrairement à un état qui
  serait figé dans le token à la connexion.
- Domaine : les liens partent de FRONTEND_URL (`https://cockpitemploi.fr` en prod).
  Le domaine n'est pas encore authentifié dans Brevo ; ce jour-là, l'include SPF de
  Brevo se FUSIONNE dans le TXT SPF existant d'OVH (un seul SPF sur le domaine) :
  cf. `dev-docs/domain.md`.
