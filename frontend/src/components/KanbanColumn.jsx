// Une colonne du kanban : un statut, son libellé, le nombre de candidatures
// qu'elle contient, et les cartes correspondantes, DANS L'ORDRE REÇU. Zone droppable
// (@dnd-kit/react) identifiée par la clé technique du statut : elle reçoit une carte
// lâchée dans son espace libre ou dans une colonne VIDE ; le reste du temps, la
// cible est la carte survolée (tri).
//
// Le statut est identifié par son LIBELLÉ (« Repérée », « Entretien »…) : les
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
  // Identifiant droppable = clé technique du statut (saved, applied, …) : c'est
  // aussi la clé de groupe des cartes triables, que le helper `move` de dnd-kit
  // reconnaît pour insérer une carte dans la colonne survolée.
  // collisionPriority 1 = CollisionPriority.Low (@dnd-kit/abstract, dépendance
  // interne de dnd-kit, non importée ici) : la carte survolée l'emporte sur la
  // colonne qui la contient, sinon le rang visé serait toujours le bord.
  const { ref, isDropTarget } = useDroppable({
    id: statusKey,
    type: 'column',
    accept: 'card',
    collisionPriority: 1,
  })

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
          applications.map((application, index) => (
            <ApplicationCard
              key={application.id}
              application={application}
              index={index}
              onEdit={onEditApplication}
            />
          ))
        )}
      </div>
    </section>
  )
}
