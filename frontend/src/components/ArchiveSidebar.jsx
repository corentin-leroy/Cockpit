// Sidebar de navigation pour la page d'archives — volontairement SÉPARÉE de
// Sidebar.jsx (celle du kanban), pas une réutilisation ni une variante.
// Sidebar.jsx gère le renommage, la suppression et sert de cible de
// glisser-déposer (useDroppable, qui suppose un <DragDropProvider> — absent
// ici, cette page n'a pas de kanban). Un composant dédié évite de coupler
// cette page à cette logique et ne touche pas au composant du kanban.
//
// Ici, la sidebar sert UNIQUEMENT de navigation : cliquer un tableau le
// mémorise comme tableau courant (même mécanisme que Sidebar.jsx, pour que
// /app l'affiche en arrivant) puis ramène au kanban. Elle ne filtre PAS les
// archives affichées. Aucun tableau n'est jamais marqué courant sur cette
// page : les archives n'appartiennent à aucun tableau en particulier à
// l'écran, un board-row--active n'aurait pas de sens ici.

import { useNavigate } from 'react-router-dom'

import { useBoards } from '../boards/useBoards.js'

export default function ArchiveSidebar() {
  const { boards, selectBoard } = useBoards()
  const navigate = useNavigate()

  function goToBoard(boardId) {
    selectBoard(boardId)
    navigate('/app')
  }

  return (
    <aside className="sidebar">
      <h2 className="sidebar__title">Tableaux</h2>

      {boards.map((board) => (
        <div className="board-row" key={board.id}>
          <button
            type="button"
            className="board-row__name"
            onClick={() => goToBoard(board.id)}
            title={board.name}
          >
            {board.name}
          </button>
        </div>
      ))}
    </aside>
  )
}
