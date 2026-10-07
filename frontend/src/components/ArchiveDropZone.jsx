// Zone de dépôt d'archivage : apparaît UNIQUEMENT pendant un glisser-déposer de
// carte, fixée en bas de l'écran. Positionnée par rapport au VIEWPORT (pas à
// une colonne), elle reste donc atteignable depuis n'importe quelle colonne,
// sans défilement horizontal supplémentaire.
//
// Elle ne rend jamais une partie du kanban inatteignable pendant le geste :
// .board-main--dragging (styles/components.css, posée par BoardPage pendant le
// drag) réserve sa hauteur en fin de défilement de la zone .kanban (c'est elle
// qui défile sur la page du kanban, pas la page) au lieu de la superposer. Faire
// défiler une colonne longue révèle donc toujours ses dernières cartes AU-DESSUS
// de la barre, jamais en dessous.
//
// Toujours MONTÉE, visible ou non : un composant démonté puis remonté en cours
// de drag perdrait son enregistrement useDroppable au moment précis où on en a
// besoin. La visibilité est purement du CSS (opacity + pointer-events),
// pilotée par useDragOperation() ; le droppable lui-même est désactivé hors
// glisser (même principe que le tableau courant dans Sidebar.jsx).

import { useDragOperation, useDroppable } from '@dnd-kit/react'
import { Archive } from '@phosphor-icons/react'

export default function ArchiveDropZone() {
  const { source } = useDragOperation()
  const isDragging = source != null

  const { ref, isDropTarget } = useDroppable({
    id: 'archive-drop-zone',
    data: { type: 'archive' },
    disabled: !isDragging,
  })

  const className = [
    'archive-drop-zone',
    isDragging ? 'archive-drop-zone--visible' : '',
    isDropTarget ? 'archive-drop-zone--drop-target' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div ref={ref} className={className} aria-hidden={!isDragging}>
      <Archive size={16} aria-hidden="true" />
      Déposer ici pour archiver
    </div>
  )
}
