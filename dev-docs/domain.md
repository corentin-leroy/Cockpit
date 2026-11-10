# Nom de domaine (cockpitemploi.fr)
Configuration du domaine et historique de la transition depuis les adresses
Railway d'origine.

- Domaine `cockpitemploi.fr`, acheté chez OVH, qui n'est que le REGISTRAIRE : la
  zone DNS est déléguée à Cloudflare. Les enregistrements se modifient dans
  Cloudflare, jamais chez OVH.
- Adresses (domaines personnalisés ajoutés dans Railway) :
  - site, service frontend : `https://cockpitemploi.fr`
  - API, service backend : `https://api.cockpitemploi.fr`
  Ce sont les seules adresses : les domaines Railway d'origine ont été supprimés le
  2026-11-10 (cf. « Transition »).
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
  - backend `CORS_ORIGINS=https://cockpitemploi.fr`
    (format exact : `dev-docs/environment-variables.md`). L'extension n'est pas
    concernée par le CORS : ses `host_permissions` l'en exemptent (cf. le
    commentaire de `extension/api.js`). Aucune origine `chrome-extension://` dans
    CORS_ORIGINS (vérifié : la 1.1.0 fonctionnait sans).
  - backend `FRONTEND_URL=https://cockpitemploi.fr` (liens des emails)
  - frontend `VITE_API_BASE_URL=https://api.cockpitemploi.fr`, figée au build :
    toute modification impose un rebuild (cf. `dev-docs/vite-build-variables.md`)

# Transition
Historique d'une transition TERMINÉE le 2026-11-10. Anciennes adresses, supprimées :
- site : `https://cockpit-front-production.up.railway.app`
- API : `https://cockpit-production-6afb.up.railway.app`

Déroulé :
- 2026-10-09 : bascule vers `cockpitemploi.fr` (domaines personnalisés ajoutés,
  variables de production posées). Les domaines Railway d'origine restaient
  actifs, et l'origine de l'ancienne URL du site restait dans CORS_ORIGINS tant
  que cette URL servait le site (sinon le site servi à cette adresse ne pouvait
  plus appeler l'API).
- 2026-10-10 : « VÉRIFICATION APRÈS DÉPLOIEMENT » de `dev-docs/rate-limiting.md`
  (lecture de l'IP) refaite via `api.cockpitemploi.fr` : 6 étapes conformes.
- 2026-10-12 : extension 1.1.0 (étiquette `extension-v1.1.0`, commit 40b8048)
  approuvée sur le Chrome Web Store. Elle appelait l'ancienne adresse de l'API,
  figée dans `api.js` et `host_permissions` : ce domaine devait rester actif.
- 2026-10-15 : extension 1.2.0 publiée, sur `api.cockpitemploi.fr` (cf.
  `dev-docs/extension-session-sharing.md`). Le retrait du domaine Railway de l'API
  devenait possible (lot 4 de la 1.2.0).
- 2026-11-10 : les deux anciens domaines supprimés dans Railway ; CORS_ORIGINS
  réduit à `https://cockpitemploi.fr`.
