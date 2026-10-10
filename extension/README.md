# Extension Cockpit

## Installation en mode développeur (Chrome / Edge / Brave)

1. Ouvrir `chrome://extensions`
2. Activer **Mode développeur** (toggle en haut à droite)
3. **Charger l'extension non empaquetée** → sélectionner ce dossier `extension/`
   (API de production) ; pour un backend local, sélectionner `extension/dist/dev/`
   produit par le script (cf. « Développer contre un backend local »)
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

Le code committé vise **uniquement la production** (`config.js` et
`manifest.json`), et ne se modifie jamais pour le dev. Le script d'empaquetage en
produit une copie réécrite pour le local :

1. Lancer le backend depuis `backend/` :
   `.venv\Scripts\python.exe -m uvicorn app.main:app --reload`
2. Construire la copie de dev, depuis la racine du dépôt :
   `backend\.venv\Scripts\python.exe extension\package_extension.py dev`
   → `extension/dist/dev/` (ignoré par Git), où `config.js` vise
   `http://127.0.0.1:8000` (API) et `http://localhost:5173` (site), et
   `host_permissions` du manifeste `http://127.0.0.1:8000/*`.
3. Charger `extension/dist/dev/` comme extension non empaquetée (une seule fois),
   puis, après chaque nouvelle construction, ⟳ dans `chrome://extensions`.

Le dossier est reconstruit au même endroit à chaque fois : l'identifiant de
l'extension de dev (qui dépend du chemin du dossier chargé, il diffère de celui du
Store) reste donc stable. Modifier le code dans `extension/`, jamais dans
`dist/dev/` (écrasé à la construction suivante). Vérification côté serveur sur
http://127.0.0.1:8000/docs (GET /applications).

**URL de l'API et `host_permissions` vont toujours ensemble.** C'est
`host_permissions` qui exempte la popup et le service worker du contrôle CORS ;
désalignés, les appels retombent sous le régime CORS ordinaire (préflight compris)
et échouent sans que le code ne signale rien d'anormal. Le script refuse de
construire (cible dev comme store) si `config.js` et le manifeste divergent.

## Paquet pour le Chrome Web Store

`backend\.venv\Scripts\python.exe extension\package_extension.py store`
→ `extension/dist/cockpit-extension-<version>.zip` (version lue dans le manifeste).

Le zip contient la liste EXPLICITE `FILES` du script (ni `icons/icon512.png`, ni
`README.md`, ni `CLAUDE.md`). Le script échoue, sans rien écrire, si :
- un fichier de `FILES` manque ;
- le manifeste déclare une clé qui cite des fichiers qu'il ne sait pas suivre
  (`content_scripts`, `options_page`, `web_accessible_resources`…) ;
- `config.js` ne contient pas exactement une ligne
  `export const NOM = "valeur";` par constante ;
- `config.js` et le manifeste ne désignent pas les mêmes adresses ;
- `FILES` et le code divergent : en partant du manifeste (service worker, popup,
  icônes), des `<script src>` / `<link href>` des pages HTML et des imports
  relatifs des fichiers JS, tout fichier atteint doit être dans `FILES`, et tout
  fichier de `FILES` doit être atteint (contrôle aussi fait par la cible dev) ;
- un fichier texte du paquet contient `localhost`, `127.0.0.1` ou `railway`,
  commentaires compris (store uniquement).

Tant que la 1.1.0 vise l'ancien domaine de l'API, la cible store échoue sur
`railway` : c'est attendu jusqu'au passage aux domaines définitifs (1.2.0).

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
utilisateurs. Une URL en dur (`config.js`) borne la destination du token à un
hôte unique, déclaré dans `host_permissions` et **vérifiable dans le manifest**
par la revue du Web Store comme par n'importe qui. Les valeurs locales n'existent
que dans le script d'empaquetage, au moment de construire la copie de dev :
l'extension publiée n'a aucun moyen d'en changer.

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
- `config.js` — adresses figées : `API_BASE_URL` (alignée sur
  `host_permissions`) et `SITE_ORIGIN` (partage de session de la 1.2.0). Seul
  fichier que le script réécrit, avec le manifeste, pour la cible dev.
- `api.js` — couche API partagée popup/service worker : `login()`, `getBoards()`
  et `createApplication()` (ajoutent le Bearer, purgent le token sur 401), avec
  `API_BASE_URL` importée de `config.js`.
- `background.js` — service worker, trois messages : `EXTRACT_OFFER` injecte
  l'extracteur et renvoie l'offre à la popup (sans rien poster) ; `GET_BOARDS`
  renvoie les tableaux de l'utilisateur ; `ADD_OFFER` poste les données validées
  vers l'API depuis le contexte extension (immunisé contre la CSP des sites),
  avec le token lu dans `chrome.storage`.
- `adapters/` — extracteurs spécifiques à un site, injectés à la place de
  l'extraction générique (`extractOffer`, background.js). `index.js` choisit
  l'adaptateur d'après l'hôte de l'onglet ; `francetravail.js` lit les offres de
  `candidat.francetravail.fr` (mode panneau et page seule), `indeed.js` celles de
  `fr.indeed.com` (idem). Sur tout autre site, rien ne change. Détails : CLAUDE.md de
  l'extension.
- `limits.js` — miroir des bornes de validation du backend (cf. CLAUDE.md de
  l'extension), appliqué aux champs du formulaire de correction.
- `urlCleanup.js` — nettoyage d'une URL d'offre trop longue (> 2048
  caractères) : liste EXPLICITE et volontairement minimale de paramètres de
  suivi à retirer, jamais une règle générale. Documentée dans le fichier
  lui-même, y compris comment l'étendre.
- `package_extension.py` — script d'empaquetage (bibliothèque standard Python),
  cibles `dev` et `store` (cf. sections ci-dessus). Hors du paquet.
- `dist/` — sorties du script (copie de dev, zip du Store), ignorées par Git.

## Pistes d'amélioration

- Extracteurs spécifiques par site (WTTJ, HelloWork) quand le JSON-LD est absent
  (France Travail et Indeed en ont un : `adapters/francetravail.js`,
  `adapters/indeed.js`)

*URL de l'API configurable : écartée volontairement, cf. section ci-dessus.*
