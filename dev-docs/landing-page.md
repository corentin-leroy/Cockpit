# Landing page (extrait de « Architecture frontend »)
- Landing page (`pages/LandingPage.jsx`, `styles/landing.css`, classes préfixées
  `landing-`, route `/` derrière GuestRoute). Règles de style et écarts au reste de
  l'application : section « Landing page » de DESIGN.md.
  - Barre du haut PROPRE à la landing (pas `Navbar.jsx`), collée en haut pendant le
    défilement (`position: sticky`, CSS seul), fond opaque, au-dessus du panneau du
    kanban (z-index 2 contre 1). Contenu : logo, thème, « Se connecter », « Créer un
    compte » en style SECONDAIRE (le teal reste unique à l'écran).
  - « Créer un compte » de la barre n'apparaît qu'une fois celui du HERO entièrement
    sorti de l'écran, barre comprise. `IntersectionObserver` sur le bouton du hero
    (marge haute négative = hauteur de la barre), recréé par un `ResizeObserver` quand
    cette hauteur change (63px, 55px à 768px et moins). Aucun écouteur de défilement,
    aucun état React : un attribut `data-signup` sur l'en-tête, lu par le CSS.
    Emplacement réservé (`opacity` + `visibility`), fondu de 180ms instantané sous
    `prefers-reduced-motion` (règle explicite : base.css ne réduit pas les délais),
    gardé visible tant qu'il a le focus. Premier calcul dans un `useLayoutEffect`
    (rien n'apparaît puis disparaît au chargement) ; transitions activées après le
    premier verdict de l'observateur (pas de fondu sur une page rechargée déjà
    défilée). REPLI SÛR : sans observateur ou avant tout calcul, il est VISIBLE.
  - Focus jamais masqué par la barre : `scroll-margin-top` sur le CONTENU (`main`,
    pied de page). JAMAIS `scroll-padding-top` sur `<html>` : chaque tabulation vers
    un élément de la barre ferait remonter la page (mesuré : de 1500 à 1047px).
  - Le hero réutilise `KanbanColumn` et `ApplicationCard` tels quels, avec des
    candidatures FICTIVES codées en dur (`DEMO_APPLICATIONS`). Leurs dates sont
    calculées à partir d'aujourd'hui (`daysAgo`, ISO naïf UTC comme le backend) : l'âge
    affiché reste plausible à chaque visite.
  - Démo déplaçable à titre d'exemple : un `DragDropProvider` LOCAL, l'état dans un
    `useState`, le MÊME réordonnancement que le kanban (`useKanbanDrag`, à
    n'importe quel rang, dans sa colonne ou vers une autre) ; `onDragEnd` ne fait
    que rétablir la carte sur Échap. AUCUN appel API, rien de stocké (vérifié : aucun
    fetch pendant les glisser) : un rechargement remet les cartes à leur place. Pas
    de zone d'archivage. Sans `DragDropProvider`, `useDraggable`/`useDroppable` créent des
    instances inertes (dnd-kit : `useInstance` tolère un manager absent) : c'est ce
    qui permet de réutiliser les composants du kanban hors de `BoardPage`.
  - Cartes HORS de l'ordre de tabulation : dnd-kit pose `tabindex="0"` sur chaque
    carte (seulement si l'attribut est absent, et de façon différée). La landing force
    `tabindex="-1"` avec un `MutationObserver` local plutôt que de modifier les
    composants partagés pour un besoin propre à une page.
  - ⚠ Tester la démo dans un navigateur AU PREMIER PLAN : dnd-kit met à jour la
    position par `requestAnimationFrame`, qui ne s'exécute pas dans un onglet masqué
    (ni dans un navigateur piloté en arrière-plan). La carte reste alors figée et le
    dépôt retombe sur la colonne d'origine, sans erreur.
  - SECTION CONFIANCE (« Ce que Cockpit fait de vos données ») : chaque phrase a été
    vérifiée dans le code, et DOIT être revérifiée si l'extension change (permissions,
    extraction, authentification). Ce qui la fonde : l'extension n'a que `activeTab`,
    `scripting` et `storage` ; l'extraction n'a lieu qu'à l'ouverture de la popup, sur
    l'onglet courant, et rien n'est envoyé avant la validation du formulaire ; le seul
    mot de passe demandé est celui de Cockpit (aucun mot de passe de site d'emploi) ;
    DELETE /auth/me efface le compte et, par cascade, ses tableaux et candidatures.
    Ne JAMAIS écrire « aucun scraping » : l'extension lit bien le contenu de la page
    d'offre visitée, à la demande de l'utilisateur.
  - Pas de promesse sur l'avenir : la page décrit ce qui existe. La mention « Gratuit,
    sans carte bancaire », ajoutée un temps près du bouton, a été retirée à la
    demande du propriétaire (« fait un peu trop ») : ne pas la réintroduire sans
    accord. Le public est TOUS les types de contrat (alternance, CDI, CDD, stage) : le
    nom du dépôt est un héritage.
