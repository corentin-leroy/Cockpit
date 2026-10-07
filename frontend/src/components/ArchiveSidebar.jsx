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
import { SidebarSimple } from '@phosphor-icons/react'

import { useBoards } from '../boards/useBoards.js'
import { useSidebar } from '../preferences/useSidebar.js'

export default function ArchiveSidebar() {
  const { boards, selectBoard } = useBoards()
  const { collapsed, collapseSidebar } = useSidebar()
  const navigate = useNavigate()

  function goToBoard(boardId) {
    selectBoard(boardId)
    navigate('/app')
  }

  return (
    // Même état de repli que la sidebar du kanban (contexte partagé) ; `inert` et
    // id : voir Sidebar.jsx.
    <aside
      id="board-sidebar"
      className={`sidebar${collapsed ? ' sidebar--collapsed' : ''}`}
      inert={collapsed}
    >
      {/* Même en-tête que Sidebar.jsx : le repli est partagé, son bouton aussi. */}
      <div className="sidebar__header">
        <h2 className="sidebar__title">Tableaux</h2>
        <button
          type="button"
          className="btn btn--ghost btn--icon sidebar__collapse"
          onClick={collapseSidebar}
          aria-label="Replier les tableaux"
          title="Replier les tableaux"
        >
          <SidebarSimple size={16} aria-hidden="true" />
        </button>
      </div>

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
