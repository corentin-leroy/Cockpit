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

import { useState } from 'react'
import { useDroppable } from '@dnd-kit/react'

// Largeur DURE : width + minWidth + maxWidth identiques neutralisent le
// min-width:auto (basé sur le contenu) qui, avec un simple flex-basis, laissait un
// nom long élargir la sidebar. box-sizing:border-box → padding/bordure inclus dans
// les 220px. flexShrink:0 pour ne pas se comprimer face au kanban.
const asideStyle = {
  width: 220,
  minWidth: 220,
  maxWidth: 220,
  flexShrink: 0,
  boxSizing: 'border-box',
  borderRight: '1px solid var(--border)',
  padding: 16,
  display: 'flex',
  flexDirection: 'column',
  gap: 4,
}

const headingStyle = {
  margin: '0 0 8px',
  fontSize: 12,
  textTransform: 'uppercase',
  letterSpacing: 0.5,
  opacity: 0.6,
}

// Ligne d'un tableau : le bouton de sélection (nom) + les actions au survol.
// minWidth:0 : autorise la ligne à rétrécir sous son contenu, condition nécessaire
// pour que la troncature du nom (bouton enfant) opère réellement.
const rowStyle = {
  display: 'flex',
  alignItems: 'center',
  gap: 2,
  minWidth: 0,
  borderRadius: 8,
  border: '1px solid transparent',
  transition: 'border-color 120ms, background 120ms',
}

const activeRowStyle = {
  background: 'var(--accent-bg)',
  border: '1px solid var(--accent-border)',
}

// Surbrillance quand une carte glissée survole ce tableau (miroir du feedback des
// colonnes du kanban, cf. KanbanColumn).
const dropTargetRowStyle = {
  borderColor: 'var(--accent-border)',
  background: 'var(--accent-bg)',
}

const nameButtonStyle = {
  flex: 1,
  minWidth: 0,
  textAlign: 'left',
  padding: '8px 10px',
  borderRadius: 8,
  border: 'none',
  background: 'transparent',
  color: 'inherit',
  font: 'inherit',
  cursor: 'pointer',
  // Tronque un nom trop long au lieu de casser la mise en page.
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
}

const activeNameStyle = { color: 'var(--text-h)' }

const iconButtonStyle = {
  flex: '0 0 auto',
  padding: '4px 6px',
  borderRadius: 6,
  border: 'none',
  background: 'transparent',
  color: 'inherit',
  font: 'inherit',
  fontSize: 13,
  lineHeight: 1,
  cursor: 'pointer',
  opacity: 0.7,
}

const newBoardButtonStyle = {
  marginTop: 8,
  width: '100%',
  textAlign: 'left',
  padding: '8px 10px',
  borderRadius: 8,
  border: '1px dashed var(--border)',
  background: 'transparent',
  color: 'inherit',
  font: 'inherit',
  cursor: 'pointer',
  opacity: 0.85,
}

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

  return (
    <div
      ref={ref}
      style={{
        ...rowStyle,
        ...(active ? activeRowStyle : {}),
        ...(isDropTarget ? dropTargetRowStyle : {}),
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <button
        type="button"
        aria-current={active ? 'true' : undefined}
        style={{ ...nameButtonStyle, ...(active ? activeNameStyle : {}) }}
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
            style={iconButtonStyle}
            onClick={() => onRename(board)}
          >
            ✎
          </button>
          {canDelete && (
            <button
              type="button"
              aria-label={`Supprimer le tableau ${board.name}`}
              title="Supprimer"
              style={{
                ...iconButtonStyle,
                ...(deleting ? { opacity: 0.4, cursor: 'not-allowed' } : {}),
              }}
              onClick={() => onDelete(board)}
              disabled={deleting}
            >
              🗑
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
    <aside style={asideStyle}>
      <h2 style={headingStyle}>Tableaux</h2>

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

      <button type="button" style={newBoardButtonStyle} onClick={onCreate}>
        + Nouveau tableau
      </button>
    </aside>
  )
}
