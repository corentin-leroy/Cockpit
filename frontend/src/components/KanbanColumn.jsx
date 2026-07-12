// Une colonne du kanban : un statut, son libellé, le nombre de candidatures
// qu'elle contient, et les cartes correspondantes. Zone droppable (@dnd-kit/react)
// identifiée par la clé technique du statut : y déposer une carte la fait changer
// de statut.
//
// Le statut est identifié par son LIBELLÉ (« Repérée », « Refusée »…) : les
// colonnes partagent toutes la même couleur, aucune information n'est portée par
// la teinte seule.

import { useDroppable } from '@dnd-kit/react'

import ApplicationCard from './ApplicationCard.jsx'

export default function KanbanColumn({
  statusKey,
  label,
  applications,
  onEditApplication,
}) {
  // Identifiant droppable = clé technique du statut (saved, applied, …), lue au
  // drop pour déterminer le nouveau statut.
  const { ref, isDropTarget } = useDroppable({ id: statusKey })

  return (
    <section
      ref={ref}
      className={`kanban-column${isDropTarget ? ' kanban-column--drop-target' : ''}`}
    >
      <header className="kanban-column__header">
        <span className="kanban-column__label">{label}</span>
        <span className="kanban-column__count">{applications.length}</span>
      </header>

      <div className="kanban-column__list">
        {applications.length === 0 ? (
          <p className="kanban-column__empty">—</p>
        ) : (
          applications.map((application) => (
            <ApplicationCard
              key={application.id}
              application={application}
              onEdit={onEditApplication}
            />
          ))
        )}
      </div>
    </section>
  )
}
