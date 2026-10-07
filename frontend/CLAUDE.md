# Frontend (React 19 + Vite + React Router 7)
Chargé automatiquement dès qu'un fichier de `frontend/` est lu ou modifié. Règles
opérationnelles ; le document en renvoi (`dev-docs/`) n'est PAS chargé
automatiquement : le lire AVANT de modifier le mécanisme concerné, il fait foi en
cas d'écart. Commandes : CLAUDE.md racine. Pas de lanceur de tests frontend.

# Direction visuelle
- `DESIGN.md` à la racine est la référence unique pour tout ce qui touche au
  style : densité, échelle typographique, espacements, usage de la couleur,
  interdits. Le lire AVANT toute modification de CSS ou de rendu.
- Cockpit est un outil dense, consulté plusieurs fois par jour (référence de
  densité : Notion). La couleur et l'espace signalent, ils ne décorent pas.
- Les tokens (couleurs, espacements, typo) sont dupliqués dans le bloc `<style>`
  de `extension/popup.html` : toute modification de `tokens.css` doit y être
  répercutée dans la même passe. Deux exceptions, VOLONTAIRES :
  `--color-surface-band` (bandes de section de la landing) et
  `--color-surface-column` (colonnes du kanban), absents de la popup qui n'en a pas
  l'usage (cf. DESIGN.md, « Duplication à surveiller »).
- La landing page a une zone de liberté propre (échelle typographique, fonds de
  section alternés, ombre, teal d'identité), limitée aux écarts listés dans la
  section « Landing page » de DESIGN.md. L'application plafonne à 28px.

# Architecture frontend
- `api/` centralise les appels backend. TOUS passent par `apiFetch`
  (api/client.js), qui ajoute le Bearer et purge le token sur 401.
  Jamais de `fetch` direct dans un composant.
- Aucun composant n'appelle `localStorage` directement : CHAQUE CLÉ a son propre
  module d'accès, et c'est le seul endroit autorisé à y toucher :
  `auth/token.js` (cockpit_token), `theme/storage.js` (cockpit_theme),
  `boards/lastBoard.js` (cockpit_last_board), `preferences/storage.js`
  (cockpit_sidebar_collapsed). Une nouvelle clé = un nouveau module de ce type.
  Le stockage peut être indisponible (navigation privée, données de site
  bloquées) et LEVER à la lecture comme à l'écriture : hors token, chaque module
  l'entoure d'un `try/catch` (lecture = valeur par défaut, écriture ignorée,
  sans erreur). Sans cela, `initTheme()` planterait avant le premier rendu.
- Repli de la sidebar des tableaux : état PARTAGÉ (`preferences/`,
  `SidebarProvider` monté dans main.jsx au-dessus du routeur), commun au kanban
  et à la page d'archives, mémorisé, dépliée par défaut. Repliée, la sidebar est
  `inert` (hors clavier) et les cibles de dépôt de `Sidebar.jsx` sont désactivées.
- Contexte d'auth (auth/) : état isAuthenticated, login/logout, plus `user`
  (chargé via GET /auth/me dès qu'un token existe, rechargeable par refreshUser).
  `user` peut être null même connecté (chargement, ou /auth/me en échec) : son
  absence ne bloque JAMAIS l'app, elle masque seulement le bandeau de vérification.
- Routes protégées (ProtectedRoute) et routes invité (GuestRoute). Les pages
  atteintes depuis un lien email (/forgot-password, /reset-password,
  /verify-email) n'ont AUCUNE garde : le token de l'URL fait autorité, pas la
  session — un connecté qui clique son lien de vérification ne doit pas être
  redirigé.
- `constants/applicationStatuses.js` = source unique des statuts (clé technique
  + libellé français + ordre des colonnes). Miroir exact de l'enum
  `ApplicationStatus` côté backend : toute évolution se fait des deux côtés
  (5 statuts depuis le retrait de « rejected »). Pour RETIRER un statut, le front
  passe en premier (cf. « Migrations », ordre de déploiement).
- Cartes du kanban : la carte entière est cliquable et ouvre la modale
  d'édition. Aucune action n'est affichée sur la carte. Le titre reste un lien
  vers l'offre (stopPropagation), sans style de lien. Le drag & drop
  (@dnd-kit) est pointeur uniquement : vérifier qu'un ajout d'élément
  interactif sur une carte ne le perturbe pas.
- URL du backend : `VITE_API_BASE_URL` (cf. frontend/.env.example), lue dans
  api/client.js avec repli `http://127.0.0.1:8000`. Le « / » final est retiré,
  les endpoints étant concaténés directement.

# Glisser-déposer du kanban
Détail et historique : `dev-docs/frontend-kanban-dnd.md`.
- Logique partagée par le kanban et la landing : `kanban/useKanbanDrag.js` et
  `utils/kanbanOrder.js`. Ne pas la dupliquer.
- L'ÉTAT React suit le survol dans onDragOver ET `event.preventDefault()` y
  désactive le tri optimiste de dnd-kit : sans cela, une carte traversant une
  colonne puis déposée sur l'archive ou un tableau démonte toute l'application
  (`NotFoundError: removeChild`).
- Au dépôt, lire la place finale dans la REF, jamais dans l'état (onDragOver est
  différé par `startTransition`, dragend ne l'est pas).
- Dépôt sur un tableau de la sidebar ou sur l'archive : seule compte la place
  d'ORIGINE. Mise à jour optimiste ; en cas d'échec, `restoreCard`.
- Modale : statut changé → la carte passe en haut de sa nouvelle colonne, comme
  côté serveur.

# Landing page
Détail et historique : `dev-docs/landing-page.md`.
- Style : section « Landing page » de DESIGN.md, seule zone hors plafond de 28px.
- Barre propre à la landing (pas `Navbar.jsx`). Jamais `scroll-padding-top` sur
  `<html>` (chaque tabulation dans la barre ferait remonter la page) :
  `scroll-margin-top` sur le contenu.
- Bouton d'inscription différé : repli sûr = VISIBLE.
- Démo : composants du kanban réutilisés tels quels, AUCUN appel API ; cartes
  sorties de la tabulation par un MutationObserver local, sans modifier les
  composants partagés.
- Section confiance : revérifier chaque phrase si l'extension change. Ne JAMAIS
  écrire « aucun scraping » (l'extension lit la page visitée).
- Pas de promesse sur l'avenir ; ne pas réintroduire « Gratuit, sans carte
  bancaire » sans accord ; public = tous types de contrat.
- Tester la démo dans un navigateur AU PREMIER PLAN (requestAnimationFrame est
  figé en arrière-plan).

# Blocage après un 429
Détail et historique : `dev-docs/rate-limit-cooldown.md`.
- Une seule logique pour connexion, inscription et mot de passe oublié :
  `auth/useRateLimitCooldown.js` + `utils/retryAfter.js`, pas trois copies.
- `Retry-After` accepté seulement en secondes entières (24 h max) ; jamais de
  date HTTP (l'horloge du poste peut être déréglée).
- Sans délai lisible, le 429 est une erreur ordinaire : ne jamais bloquer sur une
  durée inventée.
- Aucune mémorisation du blocage (pas de localStorage).

# Suppression de compte
Détail : `dev-docs/account-deletion.md`.
- Jamais `window.confirm` ni `window.alert` : une modale de l'application. Après
  succès : purge du token local, puis /login (replace).

# Variables Vite
Détail et historique : `dev-docs/vite-build-variables.md`.
- `VITE_*` est remplacé AU BUILD : changer `VITE_API_BASE_URL` impose de
  rebuilder et redéployer le front ; redémarrer ne suffit pas.
- Tout ce qui est préfixé `VITE_` est public : jamais de secret.
