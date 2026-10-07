// Menu latéral listant les tableaux de l'utilisateur. Le tableau courant est mis
// en évidence ; cliquer sur un tableau le définit comme courant. Chaque tableau
// expose au survol, ou quand le clavier est dans sa ligne, deux actions :
// renommer et supprimer (affichage piloté en CSS, .board-row__action). Un bouton
// « Nouveau tableau » termine la liste.
//
// Chaque tableau est aussi une CIBLE de dépôt (@dnd-kit/react) : glisser une carte
// du kanban sur un tableau y déplace la candidature. Le tableau courant n'est PAS
// une cible (la carte y est déjà) : il est marqué `disabled` côté droppable.
//
// Présentationnel côté données (liste, tableau courant, mutations viennent de
// BoardsProvider via props) ; seule l'intégration drag & drop est locale.
// L'apparence vit dans styles/components.css (.sidebar, .board-row…).

import { useDroppable } from '@dnd-kit/react'
import { PencilSimple, Plus, Trash } from '@phosphor-icons/react'

import { useSidebar } from '../preferences/useSidebar.js'

// Une ligne de tableau. Extraite en composant pour pouvoir appeler le hook
// useDroppable (interdit dans un callback .map) : chaque tableau devient une cible
// de dépôt. L'identifiant du droppable est préfixé `board:` et porte dans `data`
// le type (« board ») et le boardId : c'est ce qui permet à onDragEnd de
// distinguer un dépôt sur un tableau d'un dépôt sur une colonne (cf. BoardPage).
function BoardRow({ board, active, collapsed, canDelete, onSelect, onRename, onDelete }) {
  // Le tableau courant n'est pas une cible : la carte glissée en provient déjà.
  // `disabled` empêche à la fois la détection de collision et la surbrillance.
  // Sidebar REPLIÉE : aussi désactivée. Repliée, elle est décalée hors de l'écran
  // mais ses lignes gardent des rectangles ; sans ce `disabled`, un dépôt sur la
  // zone qu'elles occupaient encore dans la mise en page pourrait déplacer une
  // carte vers un autre tableau sans que rien ne soit visible.
  const { ref, isDropTarget } = useDroppable({
    id: `board:${board.id}`,
    data: { type: 'board', boardId: board.id },
    disabled: active || collapsed,
  })

  const className = [
    'board-row',
    active ? 'board-row--active' : '',
    isDropTarget ? 'board-row--drop-target' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div ref={ref} className={className}>
      <button
        type="button"
        aria-current={active ? 'true' : undefined}
        className="board-row__name"
        onClick={() => onSelect(board.id)}
        title={board.name}
      >
        {board.name}
      </button>

      {/* Toujours rendues : masquées en CSS hors survol et hors focus clavier
          (.board-row__action). Rendues seulement au survol, elles n'existaient
          pas pour le clavier. */}
      <button
        type="button"
        aria-label={`Renommer le tableau ${board.name}`}
        title="Renommer"
        className="btn btn--ghost btn--icon board-row__action"
        onClick={() => onRename(board)}
      >
        <PencilSimple size={16} aria-hidden="true" />
      </button>
      {canDelete && (
        <button
          type="button"
          aria-label={`Supprimer le tableau ${board.name}`}
          title="Supprimer"
          className="btn btn--ghost btn--icon board-row__action"
          onClick={() => onDelete(board)}
        >
          <Trash size={16} aria-hidden="true" />
        </button>
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
}) {
  // Règle métier « pas le dernier tableau » côté UX : sans au moins deux tableaux,
  // on masque l'action supprimer (le backend renverrait 409 de toute façon).
  const canDelete = boards.length > 1
  const { collapsed } = useSidebar()

  return (
    // `inert` : repliée, la sidebar sort du parcours de Tab et de l'arbre
    // d'accessibilité IMMÉDIATEMENT (aussi pendant l'animation), sans dépendre de
    // la visibilité CSS. id : cible de aria-controls du bouton de la navbar.
    <aside
      id="board-sidebar"
      className={`sidebar${collapsed ? ' sidebar--collapsed' : ''}`}
      inert={collapsed}
    >
      <h2 className="sidebar__title">Tableaux</h2>

      {boards.map((board) => (
        <BoardRow
          key={board.id}
          board={board}
          active={board.id === currentBoardId}
          collapsed={collapsed}
          canDelete={canDelete}
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
        <Plus size={16} aria-hidden="true" />
        Nouveau tableau
      </button>
    </aside>
  )
}
