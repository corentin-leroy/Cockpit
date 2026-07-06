# Extension Alternance Cockpit

## Installation en mode développeur (Chrome / Edge / Brave)

1. Ouvrir `chrome://extensions`
2. Activer **Mode développeur** (toggle en haut à droite)
3. **Charger l'extension non empaquetée** → sélectionner ce dossier `extension/`
4. Épingler l'icône dans la barre d'outils (icône puzzle → punaise)

## Utilisation

1. Lancer le backend (`py -m uvicorn app.main:app --reload` depuis `backend/`)
2. Cliquer sur l'icône de l'extension → la **popup** s'ouvre
3. Se connecter (même identifiants que le front) : le token est stocké dans
   `chrome.storage.local`
4. Sur une page d'offre, la popup **pré-remplit un formulaire** (intitulé,
   entreprise, lieu, lien) à partir de l'extraction. Corriger/compléter si besoin,
   puis **« Ajouter au cockpit »** → confirmation dans la popup
5. Vérifier sur http://127.0.0.1:8000/docs (GET /applications)

Le token reste stocké entre les sessions ; « Déconnexion » l'efface. Si le token
expire, la prochaine tentative d'ajout renvoie la popup vers l'écran de connexion.

Après chaque modification du code : bouton ⟳ sur la carte de l'extension
dans `chrome://extensions`.

## Architecture (Manifest V3)

- `manifest.json` — `action.default_popup` (le clic ouvre la popup), permissions
  `activeTab` (accès à l'onglet courant au clic), `scripting` (injection),
  `storage` (token), `host_permissions` vers l'API. Service worker en module ES.
- `popup.html` / `popup.js` — l'UI : formulaire de connexion (POST /auth/login),
  ou formulaire de correction de l'offre pré-rempli + « Déconnexion » selon la
  présence d'un token.
- `storage.js` — **seul** accès à `chrome.storage.local` pour le token
  (get/set/clear).
- `api.js` — couche API partagée popup/service worker : `login()` et
  `createApplication()` (ajoute le Bearer, purge le token sur 401).
- `background.js` — service worker, deux messages : `EXTRACT_OFFER` injecte
  `extractOffer()` et renvoie l'offre à la popup (sans rien poster) ; `ADD_OFFER`
  poste les données validées vers l'API depuis le contexte extension (immunisé
  contre la CSP des sites), avec le token lu dans `chrome.storage`.

## Pistes d'amélioration

- Extracteurs spécifiques par site (WTTJ, HelloWork) quand le JSON-LD est absent
- Popup avec formulaire de correction avant envoi
- URL de l'API configurable (options page) pour pointer vers la prod
- Icônes (requises pour la publication sur le Web Store)
