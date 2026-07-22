# Extension Cockpit

## Installation en mode développeur (Chrome / Edge / Brave)

1. Ouvrir `chrome://extensions`
2. Activer **Mode développeur** (toggle en haut à droite)
3. **Charger l'extension non empaquetée** → sélectionner ce dossier `extension/`
4. Épingler l'icône dans la barre d'outils (icône puzzle → punaise)

## Utilisation

L'extension pointe sur l'**API de production** : aucun backend local n'est requis.

1. Cliquer sur l'icône de l'extension → la **popup** s'ouvre
2. Se connecter (même identifiants que le front) : le token est stocké dans
   `chrome.storage.local`
3. Sur une page d'offre, la popup **pré-remplit un formulaire** (intitulé,
   entreprise, lieu, lien) à partir de l'extraction. Corriger/compléter si besoin,
   puis **« Ajouter au cockpit »** → confirmation dans la popup
4. La candidature apparaît dans le tableau choisi, sur le front déployé

Le token reste stocké entre les sessions ; « Déconnexion » l'efface. Si le token
expire, la prochaine tentative d'ajout renvoie la popup vers l'écran de connexion.

Après chaque modification du code : bouton ⟳ sur la carte de l'extension
dans `chrome://extensions`.

## Développer contre un backend local

Le code committé vise **uniquement la production**. Pour travailler contre un
backend local, modifier les **deux** valeurs ci-dessous — et **ne pas les
committer** :

1. `api.js` → `API_BASE_URL = "http://127.0.0.1:8000"`
2. `manifest.json` → `host_permissions: ["http://127.0.0.1:8000/*"]`

Puis recharger l'extension (⟳ dans `chrome://extensions` — une modification du
manifest n'est pas prise en compte à chaud), et lancer le backend
(`py -m uvicorn app.main:app --reload` depuis `backend/`). Vérification côté
serveur sur http://127.0.0.1:8000/docs (GET /applications).

**Les deux valeurs vont toujours ensemble.** C'est `host_permissions` qui exempte
la popup et le service worker du contrôle CORS ; n'en changer qu'une fait
retomber les appels sous le régime CORS ordinaire (préflight compris), et ils
échouent alors sans que le code ne signale rien d'anormal.

Avant de committer : `git diff extension/` doit être vide sur ces deux lignes.

## Pourquoi pas de page d'options pour l'URL de l'API

**Décision actée : l'URL de l'API n'est pas configurable par l'utilisateur.**

Une page d'options rendrait le basculement dev/prod plus confortable, mais elle
créerait une vulnérabilité disproportionnée : l'extension détient un **token
d'authentification** qu'elle envoie en `Authorization: Bearer` à chaque appel.
Une URL modifiable permettrait de diriger ce token vers un serveur arbitraire —
il suffirait de convaincre un utilisateur de coller une adresse (support
falsifié, tutoriel piégé) pour que ses identifiants de session partent chez un
tiers, sans qu'aucune alerte du navigateur ne se déclenche.

Le confort concerne un seul développeur ; le risque concerne tous les
utilisateurs. Une URL en dur borne la destination du token à un hôte unique,
déclaré dans `host_permissions` et **vérifiable dans le manifest** par la revue
du Web Store comme par n'importe qui.

## Architecture (Manifest V3)

- `manifest.json` — `action.default_popup` (le clic ouvre la popup), permissions
  `activeTab` (accès à l'onglet courant au clic), `scripting` (injection),
  `storage` (token), `host_permissions` vers l'API. Service worker en module ES.
- `icons/` — jeu 16/32/48/128 déclaré deux fois dans le manifest : `icons`
  (page des extensions, fiche du Web Store, écran d'installation) et
  `action.default_icon` (barre d'outils). `icon512.png` n'est pas déclaré : il
  sert aux visuels de la fiche du Store, à téléverser depuis le tableau de bord.
- `popup.html` / `popup.js` — l'UI : formulaire de connexion (POST /auth/login),
  ou formulaire de correction de l'offre pré-rempli + « Déconnexion » selon la
  présence d'un token.
- `storage.js` — **seul** accès à `chrome.storage.local` pour le token
  (get/set/clear).
- `api.js` — couche API partagée popup/service worker : `login()`, `getBoards()`
  et `createApplication()` (ajoutent le Bearer, purgent le token sur 401), plus
  la constante `API_BASE_URL`.
- `background.js` — service worker, deux messages : `EXTRACT_OFFER` injecte
  `extractOffer()` et renvoie l'offre à la popup (sans rien poster) ; `ADD_OFFER`
  poste les données validées vers l'API depuis le contexte extension (immunisé
  contre la CSP des sites), avec le token lu dans `chrome.storage`.

## Pistes d'amélioration

- Extracteurs spécifiques par site (WTTJ, HelloWork) quand le JSON-LD est absent

*URL de l'API configurable : écartée volontairement, cf. section ci-dessus.*
