// Menu latéral listant les tableaux de l'utilisateur. Le tableau courant est mis
// en évidence ; cliquer sur un tableau le définit comme courant. Chaque tableau
// expose au survol (ou s'il est courant) deux actions : renommer et supprimer.
// Un bouton « + Nouveau tableau » termine la liste.
//
// Chaque tableau est aussi une CIBLE de dépôt (@dnd-kit/react) : glisser une carte
// du kanban sur un tableau y déplace la candidature. Le tableau courant n'est PAS
// une cible (la carte y est déjà) : il est marqué `disabled` côté droppable.
//
// Présentationnel côté données (liste, tableau courant, mutations viennent de
// BoardsProvider via props) ; seule l'intégration drag & drop est locale.
// L'apparence vit dans styles/components.css (.sidebar, .board-row…).

import { useState } from 'react'
import { useDroppable } from '@dnd-kit/react'

// Une ligne de tableau. Extraite en composant pour pouvoir appeler le hook
// useDroppable (interdit dans un callback .map) : chaque tableau devient une cible
// de dépôt. L'identifiant du droppable est préfixé `board:` et porte dans `data`
// le type (« board ») et le boardId : c'est ce qui permet à onDragEnd de
// distinguer un dépôt sur un tableau d'un dépôt sur une colonne (cf. BoardPage).
function BoardRow({ board, active, canDelete, deleting, onSelect, onRename, onDelete }) {
  const [hovered, setHovered] = useState(false)

  // Le tableau courant n'est pas une cible : la carte glissée en provient déjà.
  // `disabled` empêche à la fois la détection de collision et la surbrillance.
  const { ref, isDropTarget } = useDroppable({
    id: `board:${board.id}`,
    data: { type: 'board', boardId: board.id },
    disabled: active,
  })

  // Actions visibles au survol, et en permanence sur le tableau courant.
  const showActions = hovered || active

  const className = [
    'board-row',
    active ? 'board-row--active' : '',
    isDropTarget ? 'board-row--drop-target' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div
      ref={ref}
      className={className}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <button
        type="button"
        aria-current={active ? 'true' : undefined}
        className="board-row__name"
        onClick={() => onSelect(board.id)}
        title={board.name}
      >
        {board.name}
      </button>

      {showActions && (
        <>
          <button
            type="button"
            aria-label={`Renommer le tableau ${board.name}`}
            title="Renommer"
            className="btn btn--ghost btn--icon"
            onClick={() => onRename(board)}
          >
            <span aria-hidden="true">✎</span>
          </button>
          {canDelete && (
            <button
              type="button"
              aria-label={`Supprimer le tableau ${board.name}`}
              title="Supprimer"
              className="btn btn--ghost btn--icon"
              onClick={() => onDelete(board)}
              disabled={deleting}
            >
              <span aria-hidden="true">🗑</span>
            </button>
          )}
        </>
      )}
    </div>
  )
}

export default function Sidebar({
  boards,
  currentBoardId,
  onSelect,
  onCreate,
  onRename,
  onDelete,
  deletingBoardId,
}) {
  // Règle métier « pas le dernier tableau » côté UX : sans au moins deux tableaux,
  // on masque l'action supprimer (le backend renverrait 409 de toute façon).
  const canDelete = boards.length > 1

  return (
    <aside className="sidebar">
      <h2 className="sidebar__title">Tableaux</h2>

      {boards.map((board) => (
        <BoardRow
          key={board.id}
          board={board}
          active={board.id === currentBoardId}
          canDelete={canDelete}
          deleting={deletingBoardId === board.id}
          onSelect={onSelect}
          onRename={onRename}
          onDelete={onDelete}
        />
      ))}

      <button
        type="button"
        className="btn btn--dashed btn--block"
        onClick={onCreate}
      >
        + Nouveau tableau
      </button>
    </aside>
  )
}
