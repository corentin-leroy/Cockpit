// Menu latéral listant les tableaux de l'utilisateur. Le tableau courant est mis
// en évidence ; cliquer sur un tableau le définit comme courant.
//
// Purement présentationnel : il reçoit la liste, l'id courant et le callback de
// sélection en props (la source de vérité vit dans BoardsProvider).

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

const itemStyle = {
  width: '100%',
  textAlign: 'left',
  padding: '8px 10px',
  borderRadius: 8,
  border: '1px solid transparent',
  background: 'transparent',
  color: 'inherit',
  font: 'inherit',
  cursor: 'pointer',
}

const activeItemStyle = {
  background: 'var(--accent-bg)',
  border: '1px solid var(--accent-border)',
  color: 'var(--text-h)',
}

export default function Sidebar({ boards, currentBoardId, onSelect }) {
  return (
    <aside style={asideStyle}>
      <h2 style={headingStyle}>Tableaux</h2>
      {boards.map((board) => {
        const active = board.id === currentBoardId
        return (
          <button
            key={board.id}
            type="button"
            aria-current={active ? 'true' : undefined}
            style={{ ...itemStyle, ...(active ? activeItemStyle : {}) }}
            onClick={() => onSelect(board.id)}
          >
            {board.name}
          </button>
        )
      })}
    </aside>
  )
}
