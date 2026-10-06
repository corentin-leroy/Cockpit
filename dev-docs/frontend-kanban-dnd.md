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
  Emplacement d'insertion : le placeholder de dnd-kit (`[data-dnd-placeholder]`,
  masqué par défaut) rendu visible en creux pointillé (components.css), qui suit la
  carte de rang en rang. Sémantique standard d'une liste triable : un
  réordonnancement n'a lieu qu'au CHANGEMENT de carte survolée (venir d'en dessous
  d'une carte place la carte glissée après elle) ; l'emplacement affiché est
  toujours celui du dépôt.
