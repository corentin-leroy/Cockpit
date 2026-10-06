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
    cette hauteur change (57px, 49px à 768px et moins). Aucun écouteur de défilement,
    aucun état React : un attribut `data-signup` sur l'en-tête, lu par le CSS.
    Emplacement de largeur NULLE en haut de page, qui s'élargit en glissant (180ms)
    quand le bouton apparaît en fondu (`opacity` + `visibility`) ; le tout instantané
    sous `prefers-reduced-motion` (règle explicite : base.css ne réduit pas les
    délais), gardé visible, emplacement ouvert, tant qu'il a le focus. Premier calcul
    dans un `useLayoutEffect` (rien n'apparaît puis disparaît au chargement) ;
    transitions activées après le premier verdict de l'observateur (ni fondu ni
    glissement sur une page rechargée déjà défilée). REPLI SÛR : sans observateur ou
    avant tout calcul, il est VISIBLE.
  - Glissement de la barre (2026-10-06). AVANT : emplacement réservé en permanence,
    bouton seulement rendu invisible ; en haut de page, un vide à droite de « Se
    connecter » le faisait paraître mal aligné (logo collé à gauche, lui non).
    APRÈS : `.landing-topbar__signup-slot` (LandingPage.jsx, un `<span>` autour du
    lien, aucune logique ajoutée), grille `minmax(0, 0fr)` ↔ `minmax(0, 1fr)` pilotée
    par le même attribut `data-signup`. Écart à DESIGN.md (animation de mise en
    page), inscrit dans ses « Interdits ». Précautions, toutes nécessaires :
    - `white-space: nowrap` sur le bouton : passé sur deux lignes dans l'emplacement
      étroit, il ferait grandir la barre (décalage de toute la page, et le
      ResizeObserver recréerait l'observateur en pleine animation).
    - Plancher `minmax(0, …)` : `0fr` seul ne descend pas sous le padding et la
      bordure du bouton. MESURÉ avant correction : 26px restaient (12 + 12 + 1 + 1),
      « Se connecter » à 50px du bord droit contre 24px pour le logo.
    - `justify-content: end` : une fraction inférieure à 1 s'applique deux fois
      (largeur du conteneur, puis de la colonne) ; la colonne, plus étroite que
      l'emplacement pendant l'animation, calée à gauche, faisait RECULER le bouton
      de 33px avant de le ramener au bord (mesuré image par image). Corrigé : bord
      droit du bouton constant à chaque image, à l'aller comme au retour.
    - `justify-self: unsafe end` : le bouton garde sa pleine largeur et déborde à
      gauche, rogné par `overflow: clip` (pas `hidden`, qui ferait de l'emplacement
      une zone défilable à la prise de focus).
    - Padding de 4px compensé par une marge négative : l'anneau de focus (2px + 2px)
      n'est pas rogné (vérifié visuellement, focus clavier sur le bouton).
    - `--topbar-gap` replié avec l'emplacement (marge gauche animée) : sinon l'écart
      de 8px (4px à 768px et moins) restait devant un emplacement vide.
    - `pointer-events: none` sur l'emplacement, rétabli sur le bouton : masqué, il
      chevauche la fin de « Se connecter » et lui volerait des clics.
    VÉRIFIÉ dans Chrome (thèmes clair et sombre) : symétrie en haut de page (24px de
    chaque côté ; 16px à 390 et 768px), barre sur une ligne dans les deux états
    (63px ; 55px à 390 et 768px, hauteurs de l'époque : 57 et 49px depuis les
    boutons-icônes carrés de 32px, cf. plus bas), aucun débordement horizontal ; glissement de
    ~175ms dans les deux sens ; aucun décalage enregistré au chargement, en haut
    comme sur une page rechargée à 700px ; tabulation qui saute le bouton masqué,
    absent de l'arbre d'accessibilité ; bouton gardé visible et emplacement ouvert
    sous le focus clavier, refermés au Maj+Tab ; mouvement réduit simulé (règles du
    bloc `@media` injectées hors condition, l'extension ne pouvant pas émuler la
    préférence) : bascule en une image, sans délai de visibilité. 390 et 768px testés
    dans des iframes de cette largeur (Chrome refuse une fenêtre aussi étroite).
    COÛT EN STABILITÉ (CLS) : le défilement n'excuse pas un décalage
    (`hadRecentInput` faux), ce glissement compte donc chez les vrais utilisateurs.
    MESURÉ par l'API `layout-shift` pendant un défilement réel à la molette, par
    apparition ou disparition : ~0,00033 à 1920px, ~0,0018 à 768px, ~0,0037 à 390px
    (seuil « bon » : 0,1). Sources : le bloc d'actions de la barre uniquement. Un
    audit Lighthouse classique ne le verrait pas (il ne fait pas défiler la page).
    Seule une animation par `transform` (technique FLIP, en JavaScript) y
    échapperait.
  - Boutons-icônes carrés (2026-10-06), barre de la landing ET navbar de l'app
    (même composant ThemeToggle, même règle CSS que le repli de la sidebar).
    AVANT : glyphes Unicode ☾ / ☀ / ☰, dessinés par des polices de secours ; MESURÉ,
    le bouton de thème faisait 29,4 x 38px en clair et 34,9 x 38px en sombre (il
    décalait ses voisins à chaque bascule) et imposait seul la hauteur des barres
    (63px ; 55px à 768px et moins). APRÈS : icônes SVG Phosphor (Sun, Moon, List),
    16px, dans un carré fixe de 32px ; barres à 57px (49px à 768px et moins).
    `aria-pressed` retiré de la bascule de thème : avec un libellé qui change, il
    produisait une annonce contradictoire. VÉRIFIÉ dans Chrome : 32 x 32px dans les
    deux thèmes, icône centrée au pixel, « Se connecter » immobile à la bascule ;
    déclenchement de « Créer un compte » exact au pixel (masqué tant que le bouton
    du hero dépasse de 2px sous la barre, affiché dès qu'il y est caché de 2px) en
    bureau, à 768 et à 390px ; barre sur une ligne et symétrique à 390px ; navbar
    de l'app à 57px. COÛT au build : exactement 3 icônes dans le bundle (SunIcon,
    MoonIcon, ListIcon, sur 1512 que compte la bibliothèque), +8 831 octets bruts,
    +2,55 kB compressés (chaque icône embarque ses six graisses).
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
