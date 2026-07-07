// Menu latéral listant les tableaux de l'utilisateur. Le tableau courant est mis
// en évidence ; cliquer sur un tableau le définit comme courant. Chaque tableau
// expose au survol (ou s'il est courant) deux actions : renommer et supprimer.
// Un bouton « + Nouveau tableau » termine la liste.
//
// Purement présentationnel : la source de vérité (liste, tableau courant) et les
// mutations vivent dans BoardsProvider ; ce composant reçoit tout en props.

import { useState } from 'react'

const asideStyle = {
  flex: '0 0 200px',
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
const rowStyle = {
  display: 'flex',
  alignItems: 'center',
  gap: 2,
  borderRadius: 8,
  border: '1px solid transparent',
}

const activeRowStyle = {
  background: 'var(--accent-bg)',
  border: '1px solid var(--accent-border)',
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

export default function Sidebar({
  boards,
  currentBoardId,
  onSelect,
  onCreate,
  onRename,
  onDelete,
  deletingBoardId,
}) {
  const [hoveredId, setHoveredId] = useState(null)

  // Règle métier « pas le dernier tableau » côté UX : sans au moins deux tableaux,
  // on masque l'action supprimer (le backend renverrait 409 de toute façon).
  const canDelete = boards.length > 1

  return (
    <aside style={asideStyle}>
      <h2 style={headingStyle}>Tableaux</h2>

      {boards.map((board) => {
        const active = board.id === currentBoardId
        // Actions visibles au survol, et en permanence sur le tableau courant.
        const showActions = hoveredId === board.id || active
        const deleting = deletingBoardId === board.id

        return (
          <div
            key={board.id}
            style={{ ...rowStyle, ...(active ? activeRowStyle : {}) }}
            onMouseEnter={() => setHoveredId(board.id)}
            onMouseLeave={() => setHoveredId(null)}
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
      })}

      <button type="button" style={newBoardButtonStyle} onClick={onCreate}>
        + Nouveau tableau
      </button>
    </aside>
  )
}
