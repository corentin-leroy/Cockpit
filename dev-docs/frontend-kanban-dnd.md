# Réordonnancement par glisser-déposer (extrait de « Architecture frontend »)
- Réordonnancement par glisser-déposer (cf. « Ordre des cartes du kanban ») : les
  cartes sont TRIABLES (`useSortable`, `group` = statut, `index` = rang) ; la
  colonne garde un `useDroppable` (id = statut, `accept: 'card'`,
  `collisionPriority` basse) pour les colonnes vides. Logique partagée par le
  kanban et la landing : `kanban/useKanbanDrag.js` (hook) et `utils/kanbanOrder.js`
  (fonctions pures). Deux pièges, vérifiés dans le navigateur :
  - dnd-kit fournit un TRI OPTIMISTE qui déplace LUI-MÊME les nœuds DOM pendant le
    glisser. Une carte ainsi glissée dans une autre colonne puis déposée sur la
    zone d'archivage (ou un tableau) est retirée de l'état : React tente de la
    retirer de son parent d'ORIGINE → `NotFoundError: removeChild`, et TOUTE
    l'application se démonte (écran blanc). Reproduit en neutralisant notre
    onDragOver. Parade : l'ÉTAT suit le survol (`move` de @dnd-kit/helpers dans
    onDragOver) ET `event.preventDefault()` y désactive le plugin ; React reste seul
    à déplacer les nœuds. (Sans le preventDefault mais avec l'état, pas d'erreur :
    le plugin s'abstient quand React a déjà réordonné ; les deux protections sont
    gardées.)
  - dnd-kit exécute onDragOver dans un `startTransition` (rendu différé) mais émet
    dragend IMMÉDIATEMENT : au dépôt, l'état React peut refléter un survol
    précédent. L'ordre en cours de glisser est donc tenu dans une REF, mise à jour
    de façon synchrone ; la place finale est lue dans la ref, jamais dans l'état.
  Dépôt : sur une carte, une colonne ou HORS de toute cible → la carte va là où
  l'emplacement d'insertion la montrait (POST /move si sa place a changé) ; sur un
  tableau de la sidebar ou sur l'archive → seule compte la place d'ORIGINE (une
  colonne traversée ne change pas le statut envoyé). Optimiste ; en cas d'échec la
  carte revient à sa place d'origine (`restoreCard`), message dans `actionError`.
  Échap annule (vraie touche : un KeyboardEvent synthétique n'est pas reconnu).
  Modale : statut changé → la carte passe EN HAUT de sa nouvelle colonne
  localement (comme le serveur) ; statut inchangé → elle reste à sa place.
  En-tête ACCROCHÉ (règle de rendu : DESIGN.md « Mise en page des écrans ») : un
  ONGLET, haut arrondi, bas droit, filet, sans ombre (`--shadow-md` essayée puis
  retirée à la demande). Diagnostic de la version
  précédente, arrondie aux quatre coins : sur une colonne longue, les cartes qui
  défilaient dessous apparaissaient dans ses coins du bas. Vérification à rejouer
  après toute retouche de cet en-tête, tableau défilé jusqu'en bas :
  `document.elementFromPoint` à 1px à l'intérieur des quatre coins de chaque en-tête
  doit renvoyer l'en-tête (jamais `.app-card`), sur une colonne longue ET une colonne
  courte ; l'absence de décalage au repos se prouve par A/B dans la même page
  (injecter l'ancien rendu, comparer les rectangles), un relevé d'une autre session
  pouvant différer par les données ou le zoom du navigateur (constaté : 110 %).
  Une comparaison de RECTANGLES ne voit pas un trait MASQUÉ (rien ne bouge) : pour
  le rendu au repos, comparer des captures PNG de la même zone, au même zoom, pixel
  à pixel, et lire la couleur de la ligne du trait haut de chaque cadre (méthode du
  2026-10-07 : version commitée servie temporairement sur 5173, seule origine admise
  par l'API, captures décodées dans un canvas). Tester à un zoom NON entier (110 %,
  125 %) : une bordure de 1px y est arrondie à un pixel réel, pas un décalage en px.
  Écart connu et ACCEPTÉ (2026-10-08, raison dans DESIGN.md) : le texte des en-têtes
  est lissé en gris et non plus en ClearType (Chrome sous Windows ne l'emploie que
  dans une couche entièrement opaque ; l'en-tête collant, transparent au repos, ne
  l'est plus). Position du texte identique. Mesure : écart moyen entre composantes
  R, V, B des pixels de bord de lettre, 67 en ClearType contre 6,8 en gris.
  Zones de dépôt d'une colonne (KanbanColumn, 2026-10-07) : la colonne est une
  ENVELOPPE invisible, étirée à la hauteur de la plus longue (pour que son en-tête
  collant reste affiché, cf. DESIGN.md « Mise en page des écrans »), qui contient le
  CADRE visible (la liste) puis un espace vide. Deux droppables :
  - le CADRE, id = statut, comme avant (même rectangle que l'ancienne colonne). Sur
    cette cible, `move` (@dnd-kit/helpers 0.5.0) insère en haut ou en bas selon que
    le pointeur est au-dessus ou au-dessous du CENTRE de la zone. C'est pourquoi la
    zone « colonne » n'est PAS l'enveloppe : son centre est à mi-hauteur de la
    colonne la plus longue, et une carte lâchée juste sous une colonne courte
    serait partie EN HAUT ;
  - l'espace VIDE sous le cadre, id `<statut>:end`, `data: { type: 'column-end',
    status }` : `reorderOnDragOver` le traite AVANT `move`, par `moveToColumnEnd`
    (kanbanOrder.js, pure ; renvoie la même liste si la carte est déjà en dernier).
    Vérifié dans le navigateur, écritures bloquées : pointeur AU-DESSUS du centre de
    l'enveloppe, la carte va à la fin (POST /move position = longueur de la colonne),
    sur la landing comme sur le tableau, cadre visible ou sorti de l'écran.
  Une fois l'emplacement inséré, le cadre grandit sous le pointeur : la cible devient
  la carte glissée elle-même, rien ne bouge plus (stable).
  Emplacement d'insertion : le placeholder de dnd-kit (`[data-dnd-placeholder]`,
  masqué par défaut) rendu visible en creux pointillé (components.css), qui suit la
  carte de rang en rang. Sémantique standard d'une liste triable : un
  réordonnancement n'a lieu qu'au CHANGEMENT de carte survolée (venir d'en dessous
  d'une carte place la carte glissée après elle) ; l'emplacement affiché est
  toujours celui du dépôt.
