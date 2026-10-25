# Session JWT : durée de vie et révocation
- 12 HEURES (720 minutes), pour couvrir une journée d'utilisation sans
  reconnexion. Réglable par ACCESS_TOKEN_EXPIRE_MINUTES sans redéploiement ;
  `ACCESS_TOKEN_EXPIRE_MINUTES` (app/security.py) est la seule source.
- Aucune session n'est stockée côté serveur. Un jeton est valide si sa signature
  et son expiration le sont, PLUS une comparaison par compte (depuis la migration
  0006) : son claim `token_version` doit être égal à `users.token_version`.
  Contrôle dans `get_current_user` (app/dependencies.py), sur l'utilisateur déjà
  chargé : aucune requête de plus. Écart, ou claim qui n'est pas un entier (un
  booléen ou un flottant non plus : `True == 1` et `1.0 == 1` en Python) → le même
  401 générique qu'un jeton invalide, jamais un 500.
- RÉVOCATION PAR COMPTE, toutes sessions ensemble : incrémenter la colonne, par
  l'expression SQL `token_version + 1` et jamais `+= 1` en Python (deux
  incréments simultanés en perdraient un sous PostgreSQL, qui verrouille par
  ligne ; SQLite sérialise les écritures et ne le révèle pas).
  - Révoque : une réinitialisation de mot de passe réussie ; au lot 2 de la
    connexion Google, la liaison d'un compte non vérifié
    (`dev-docs/google-sign-in.md`).
  - Ne révoque PAS : la déconnexion, qui efface seulement la copie locale du
    jeton. Une copie dérobée reste valable jusqu'à son expiration, tant que le
    compte ne révoque rien : L'EXPIRATION RESTE LA BORNE à l'exploitation d'un
    jeton volé sans révocation (12 h, douze fois la fenêtre de l'ancienne heure ;
    compromis accepté contre le confort d'une journée sans reconnexion).
  - On ne révoque pas UN appareil seul : c'est le rôle des refresh tokens (V3).
- Claim ABSENT = 0, la valeur de départ de chaque compte (`server_default`). Les
  jetons émis avant la 0006, et ceux de l'ancienne version du code pendant un
  déploiement, restent donc valables jusqu'à leur expiration, et sont refusés dès
  la première révocation. Pendant ce recouvrement, une réinitialisation servie par
  l'ancien code n'incrémente rien (accepté : fenêtre courte).
- Nom du claim : `token_version` (`TOKEN_VERSION_CLAIM`, app/security.py). Jamais
  renommé : les jetons en circulation le portent. Pas `ver`, que d'autres
  émetteurs emploient pour la version du FORMAT du jeton.
- ⚠ Un DOWNGRADE de la 0006 supprime la colonne : les sessions révoquées
  REDEVIENNENT valables pour l'ancien code, jusqu'à leur expiration.
- Clients : un 401 purge le jeton du site (`apiFetch`) et envoie `session:clear` à
  l'extension ; après une réinitialisation réussie, ResetPasswordPage déconnecte
  déjà un utilisateur connecté. Rien à modifier côté site ni extension.
- Levier global restant : changer JWT_SECRET_KEY, qui invalide les jetons de TOUS
  les utilisateurs d'un coup. Mesure d'incident, pas de gestion courante.
- Baisser la valeur ne raccourcit PAS les sessions en cours : l'expiration est
  inscrite dans chaque jeton à l'émission. Le changement ne vaut que pour les
  connexions suivantes.
- ⚠ NE PAS ALLONGER DAVANTAGE sans introduire des REFRESH TOKENS (déjà en V3,
  cf. hors périmètre). C'est la réponse propre au dilemme confort/sécurité, et
  elle ne consiste pas à étirer la durée : un jeton d'accès COURT (15-30 min,
  donc fenêtre de vol réduite) accompagné d'un refresh token long, stocké EN BASE
  et donc révocable individuellement. On récupère alors ce que `token_version` ne
  permet pas — déconnecter UN appareil, invalider une seule session compromise —
  sans toucher aux autres sessions ni aux autres utilisateurs. Prolonger encore la
  durée actuelle ne ferait qu'aggraver le problème que les refresh tokens
  résolvent.
- L'expiration est couverte par test_auth.py (jeton expiré rejeté en 401 sur
  /auth/me et sur les endpoints de données, `exp` conforme à la durée
  configurée, jeton signé d'une autre clé rejeté). Ces tests n'existaient pas
  avant l'allongement : une régression sur la validation de `exp` serait
  parfaitement silencieuse — tout continuerait de marcher, les jetons ne
  cesseraient simplement jamais d'être valables.
- La révocation est couverte par test_token_version.py (claim émis égal à la
  version stockée ; jeton sans claim accepté à 0 ; version incrémentée → 401 sur
  /auth/me et /boards, pour ce compte seulement ; claims booléen, flottant, chaîne,
  nul, liste, objet, négatif, énorme → 401 ; réinitialisation réussie → +1 et
  sessions refusées, refusée → rien) et test_token_race.py (20 réinitialisations
  simultanées avec le même lien → version 1 exactement).
