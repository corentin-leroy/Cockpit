# Partage de session site → extension (`externally_connectable`)
Mécanisme PRÉVU pour l'extension 1.2.0, pas encore implémenté : le code actuel
(popup avec formulaire de connexion, URL de l'API sur le domaine Railway) ne suit
pas encore ce document. Avancement : feuille de route du CLAUDE.md racine. Une fois
livré, ce document reste la référence du mécanisme : retirer alors ce paragraphe.

# Principe
- L'extension est un REFLET de la session du site : on se connecte et se déconnecte
  sur le site, qui transmet sa session à l'extension. L'extension n'a plus aucun
  écran de connexion.

# Décisions
- Manifeste : `externally_connectable` limité à l'hôte EXACT du frontend
  (`cockpitemploi.fr`), sans joker (ni sous-domaines, ni `<all_urls>`) et SANS champ
  `ids` (aucune autre extension ne peut s'y connecter). Toute page autorisée là
  pourrait pousser une session : la liste reste réduite au seul site.
  - Manifeste de DEV seulement (produit par le script d'empaquetage) :
    `http://localhost:5173/*`. Le port est à vérifier en chargeant ce manifeste ; s'il
    est refusé, repli sur `http://localhost/*`, jamais dans le manifeste du Store. En
    dev, le site s'ouvre TOUJOURS sur `http://localhost:5173` (pas `127.0.0.1`) :
    l'origine vérifiée côté extension en dépend.
- Canal à SENS UNIQUE : le site pousse, l'extension ne renvoie JAMAIS le jeton
  (aucun message ne permet de le lire depuis une page).
- Deux messages seulement :
  - `{type: "session:set", token}` : le site transmet son jeton ;
  - `{type: "session:clear"}` : le site signale la fin de session. Envoyé sur la
    déconnexion explicite ET sur un 401 (jeton refusé par le backend). L'extension
    efface alors son jeton SANS CONDITION (pas de comparaison avec le jeton stocké).
  - Réponse de l'extension au site : `{ok: true}` ou `{ok: false}`, RIEN d'autre
    (jamais le jeton, jamais l'email). `ok: true` = le jeton est stocké (ou l'était
    déjà).
- Écouteur dans le service worker EXISTANT (`background.js`), pas dans un nouveau
  script : `chrome.runtime.onMessageExternal` (les messages d'une page n'arrivent
  pas sur `onMessage`). Avant tout traitement : `sender.origin` égal à l'origine
  exacte du site (`SITE_ORIGIN`, `config.js`), `type` parmi les deux attendus,
  `token` de type chaîne. Tout autre message est ignoré.
- Validation du jeton AVANT stockage : `GET /auth/me` avec ce jeton.
  - 200 : le jeton ET l'email renvoyé sont stockés (via `storage.js`, seul accès au
    stockage de l'extension).
  - 401, ou échec réseau : RIEN n'est stocké, réponse `{ok: false}`. Le site renverra
    sa session au prochain chargement.
  - Raccourci : si le jeton reçu est IDENTIQUE au jeton stocké ET qu'un email est
    déjà stocké, réponse `{ok: true}` sans appeler l'API (évite un `/auth/me` à chaque
    chargement du site). Un jeton stocké sans email (popup de la 1.1.0, qui ne
    stockait que le jeton) passe donc par `/auth/me`, qui complète l'email.
- Email affiché dans la popup (« Connecté en tant que … ») : c'est la parade contre
  l'injection d'un jeton ÉTRANGER (le site pousserait la session d'un autre compte,
  et les offres capturées partiraient dans ce compte) ; l'utilisateur voit le compte.
- Course entre `session:set` et `session:clear` : un compteur de GÉNÉRATION dans le
  service worker. `session:clear` l'incrémente ; `session:set` relève le compteur
  avant l'appel à `/auth/me` et ne stocke que s'il n'a pas changé pendant l'appel
  (sinon `{ok: false}`). Sans cela, une déconnexion pendant la validation laissait
  le jeton stocké après l'effacement.
- Côté site : un module unique envoie les messages (`chrome.runtime.sendMessage`),
  avec un garde quand `chrome.runtime` est absent (extension non installée, autre
  navigateur) et une lecture de `chrome.runtime.lastError` : l'échec est SILENCIEUX
  (aucune erreur, aucun message à l'utilisateur), ce qui permet de déployer le site
  avant la 1.2.0.
- Identifiant d'extension côté site : l'ID du Store, déjà présent dans le code
  (`frontend/src/constants/links.js`, `EXTENSION_URL`), sert de valeur par défaut.
  `VITE_EXTENSION_ID` ne sert qu'en dev, dans `frontend/.env.local` (ID de
  l'extension non empaquetée chargée depuis `extension/dist/dev/`). PAS de champ
  `key` dans le manifeste : l'ID de dev dépend donc du chemin du dossier chargé, que
  le script reconstruit toujours au même endroit.
- Popup : formulaire de connexion et bouton de déconnexion SUPPRIMÉS, remplacés par
  un bouton qui ouvre la page de connexion du site (`/login`).
- Manifeste construit avec les seuls domaines DÉFINITIFS : `host_permissions` vers
  `api.cockpitemploi.fr` (et `API_BASE_URL` de `config.js` alignée, cf.
  extension/CLAUDE.md). Le changement d'hôte déclenchera un avertissement de
  permission à la mise à jour : accepté, car il n'y a pas encore d'utilisateurs.
- Script d'empaquetage `extension/package_extension.py`, bibliothèque standard
  uniquement, sorties dans `extension/dist/` (déjà ignoré par le `dist/` du
  .gitignore racine). Les sources gardent les valeurs de PRODUCTION. Le module
  `extension/config.js` regroupe `API_BASE_URL` et `SITE_ORIGIN`. Deux cibles :
  - `dev` : copie dans `extension/dist/dev/`, et réécrit SEULEMENT `config.js` et
    `manifest.json` (`host_permissions`, `externally_connectable`) avec les valeurs
    locales. Remplace la bascule manuelle d'URL, jamais committée, décrite jusqu'ici
    dans extension/CLAUDE.md et README.md ;
  - `store` : zip construit à partir d'une liste EXPLICITE de fichiers (sans
    `icon512.png`, `README.md` ni `CLAUDE.md`). Échec s'il reste une occurrence de
    `localhost`, `127.0.0.1` ou `railway`. Échec aussi si la liste et le code
    divergent, contrôlé par ATTEIGNABILITÉ : partir des fichiers cités par le
    manifeste (service worker, popup, icônes : les icônes déclarées comptent comme
    atteintes), lire les `<script src>` et `<link href>` de chaque page HTML
    atteinte, suivre récursivement les imports relatifs de chaque fichier JS ; tout
    fichier atteint doit figurer dans la liste, et aucun fichier de la liste ne doit
    être inatteignable.

# Limites acceptées
- L'ancienne URL Railway du site (`cockpit-front-production.up.railway.app`) ne
  partage PAS la session : elle n'est pas dans `externally_connectable` (et le
  paquet Store refuse toute occurrence de `railway`). Un utilisateur connecté à
  cette adresse garde une extension déconnectée.
- Si l'utilisateur efface les données du site sans se déconnecter, aucun
  `session:clear` n'est envoyé et la popup n'a plus de bouton de déconnexion :
  l'extension garde son jeton jusqu'à son expiration (12 h au plus, cf.
  `dev-docs/jwt-session.md`).

# Ordre des lots
1. Script d'empaquetage et `config.js`, SANS changement de comportement (les sources
   gardent les valeurs de la 1.1.0 : la cible `store` échoue donc sur `railway`
   jusqu'au lot 2, c'est attendu).
2. Site et extension développés et testés ENSEMBLE en local, en commits séparés : le
   front d'abord, puis l'extension avec `docs/privacy.md`. La politique de
   confidentialité décrit le réveil du service worker par un message du site, le
   transfert du jeton et l'email stocké localement ; elle est publiée en même temps
   que la 1.2.0 (le push de `docs/` la rend publique aussitôt via GitHub Pages).
3. Déploiement du site (échec silencieux tant que la 1.2.0 n'est pas publiée), puis
   soumission de la 1.2.0 au Store APRÈS l'approbation de la 1.1.0.
4. Après la publication de la 1.2.0 : retrait du domaine Railway de l'API (cf.
   ci-dessous).

# Conséquence sur le domaine
- La publication de la 1.2.0 conditionne le retrait du domaine Railway de l'API
  (cf. `dev-docs/domain.md`, « Transition »).
