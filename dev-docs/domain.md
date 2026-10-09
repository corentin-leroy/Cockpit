# Nom de domaine (cockpitemploi.fr)
Configuration du domaine et règles de transition depuis les adresses Railway
d'origine. L'avancement de la bascule (ce qui reste à faire) est suivi uniquement
dans la feuille de route du CLAUDE.md racine.

- Domaine `cockpitemploi.fr`, acheté chez OVH, qui n'est que le REGISTRAIRE : la
  zone DNS est déléguée à Cloudflare. Les enregistrements se modifient dans
  Cloudflare, jamais chez OVH.
- Adresses (domaines personnalisés ajoutés dans Railway) :
  - site, service frontend : `https://cockpitemploi.fr`
  - API, service backend : `https://api.cockpitemploi.fr`
  Les domaines `*.up.railway.app` d'origine restent actifs (cf. « Transition »).
- Enregistrements Railway en « DNS only » (nuage gris) : aucun proxy Cloudflare.
  ⚠ Activer le proxy Cloudflare (nuage orange) sur l'API ajouterait un
  intermédiaire : le nombre de proxys de confiance (`TRUSTED_PROXY_COUNT`) changerait
  et la lecture de l'IP du client serait faussée (limites de débit). Ne JAMAIS
  l'activer sans refaire la « VÉRIFICATION APRÈS DÉPLOIEMENT » de
  `dev-docs/rate-limiting.md`.
- DNSSEC : désactivé chez OVH pour la délégation. Pour le réactiver : l'activer
  d'abord dans Cloudflare, puis recopier l'enregistrement DS fourni par Cloudflare
  dans l'onglet « DS Records » d'OVH. Ne JAMAIS le réactiver avec l'interrupteur
  d'OVH (il publierait les clés d'OVH, que la zone servie par Cloudflare ne porte
  pas : le domaine cesserait de se résoudre).
- Messagerie : une boîte email OVH existe sur le domaine. Ses enregistrements (MX,
  SRV, CNAME de messagerie et le TXT SPF d'OVH) sont dans la zone Cloudflare : ne
  pas les supprimer en nettoyant la zone.
  ⚠ UN SEUL enregistrement SPF (TXT `v=spf1 ...`) sur le domaine. Le jour où le
  domaine sera authentifié dans Brevo (ce n'est pas le cas aujourd'hui), FUSIONNER
  l'include de Brevo dans ce même TXT, ne jamais créer un second enregistrement SPF.
- Variables de production (posées) :
  - backend `CORS_ORIGINS=https://cockpitemploi.fr,https://cockpit-front-production.up.railway.app`
    (format exact : `dev-docs/environment-variables.md`)
  - backend `FRONTEND_URL=https://cockpitemploi.fr` (liens des emails)
  - frontend `VITE_API_BASE_URL=https://api.cockpitemploi.fr`, figée au build :
    toute modification impose un rebuild (cf. `dev-docs/vite-build-variables.md`)

# Transition
- Ancienne URL du site, `https://cockpit-front-production.up.railway.app` : son
  origine reste dans CORS_ORIGINS tant que cette URL sert le site (sinon le site
  servi à cette adresse ne peut plus appeler l'API). Elle ne concerne QUE le site.
- L'extension n'est pas concernée par le CORS : ses `host_permissions` l'en
  exemptent (cf. le commentaire de `extension/api.js`). Aucune origine
  `chrome-extension://` dans CORS_ORIGINS (vérifié : la 1.1.0 fonctionne sans).
- ⚠ Ancienne adresse de l'API, `https://cockpit-production-6afb.up.railway.app` : ne
  PAS retirer ce domaine du service backend avant la publication de l'extension
  1.2.0. La 1.1.0 (étiquette `extension-v1.1.0`, commit 40b8048, en revue sur le
  Chrome Web Store depuis le 2026-10-08) appelle l'API à cette adresse, figée dans
  `api.js` et `host_permissions` : la retirer couperait l'extension. La 1.2.0 passe
  sur `api.cockpitemploi.fr` (cf. `dev-docs/extension-session-sharing.md`).
- Ordre des retraits : l'ancienne origine de CORS_ORIGINS une fois l'ancienne URL du
  site plus servie ; le domaine Railway de l'API seulement après la publication de
  la 1.2.0.
