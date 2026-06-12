# Extension Alternance Cockpit

## Installation en mode développeur (Chrome / Edge / Brave)

1. Ouvrir `chrome://extensions`
2. Activer **Mode développeur** (toggle en haut à droite)
3. **Charger l'extension non empaquetée** → sélectionner ce dossier `extension/`
4. Épingler l'icône dans la barre d'outils (icône puzzle → punaise)

## Utilisation

1. Lancer le backend (`py -m uvicorn app.main:app --reload` depuis `backend/`)
2. Naviguer sur une page d'offre d'emploi
3. Cliquer sur l'icône de l'extension → toast de confirmation
4. Vérifier sur http://127.0.0.1:8000/docs (GET /applications)

Après chaque modification du code : bouton ⟳ sur la carte de l'extension
dans `chrome://extensions`.

## Architecture (Manifest V3)

- `manifest.json` — déclare les permissions : `activeTab` (accès à l'onglet
  courant au clic uniquement), `scripting` (injection de code), et
  `host_permissions` vers l'API locale.
- `background.js` — service worker : injecte `extractOffer()` dans la page,
  récupère les données, POST vers l'API depuis le contexte extension
  (immunisé contre la CSP des sites).

## Pistes d'amélioration

- Extracteurs spécifiques par site (WTTJ, HelloWork) quand le JSON-LD est absent
- Popup avec formulaire de correction avant envoi
- URL de l'API configurable (options page) pour pointer vers la prod
- Icônes (requises pour la publication sur le Web Store)
