# Variables d'environnement (backend/.env, cf. .env.example)
- DATABASE_URL (SQLite ou PostgreSQL, cf. `dev-docs/database.md`)
- ACCESS_TOKEN_EXPIRE_MINUTES : FACULTATIVE, défaut 720 (12 h). Durée de vie du
  jeton de session (cf. section « Session JWT »). Valeur non entière ou négative
  → échec explicite au démarrage, jamais de repli silencieux sur le défaut.
- JWT_SECRET_KEY : obligatoire en dev ET en prod (clé DIFFÉRENTE en prod).
  Absente, l'app démarre mais toute connexion échoue (RuntimeError explicite).
- CORS_ORIGINS : origines autorisées à appeler l'API depuis un NAVIGATEUR (le site),
  lues au démarrage par `get_allowed_origins()` (app/main.py). Format exact :
  séparées par des virgules ; espaces autour de chaque origine retirés ; « / » final
  retiré par le code (l'écrire quand même sans) ; guillemets NON retirés (saisir la
  valeur sans guillemets : un `"` ferait partie de l'origine, qui ne correspondrait
  jamais, et le front serait bloqué) ; casse non normalisée (minuscules, comme
  l'en-tête Origin) ; ni chemin ni port. Vide ou absente : http://localhost:5173.
  Prod : `https://cockpitemploi.fr,https://cockpit-front-production.up.railway.app`
  (l'ancienne origine tant que l'ancienne URL du site est servie, cf.
  `dev-docs/domain.md`). Jamais d'origine `chrome-extension://` : l'extension est
  exemptée du CORS par ses `host_permissions` (vérifié avec la 1.1.0).
- FRONTEND_URL : base des liens emails (défaut http://localhost:5173). Prod :
  `https://cockpitemploi.fr`. La changer laisse les liens déjà envoyés sur
  l'ancienne adresse (lien de vérification valable 24 h) : garder l'ancienne
  adresse servie au moins 24 h après le changement.
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
