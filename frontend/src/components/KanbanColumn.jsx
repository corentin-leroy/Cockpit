// Une colonne du kanban : un statut, son libellé, le nombre de candidatures
// qu'elle contient, et les cartes correspondantes. Zone droppable (@dnd-kit/react)
// identifiée par la clé technique du statut : y déposer une carte la fait changer
// de statut.

import { useDroppable } from '@dnd-kit/react'

import ApplicationCard from './ApplicationCard.jsx'

const columnStyle = {
  flex: '0 0 240px',
  display: 'flex',
  flexDirection: 'column',
  background: 'var(--social-bg)',
  border: '1px solid var(--border)',
  borderRadius: 10,
  padding: 12,
  transition: 'border-color 120ms, background 120ms',
}

// Surbrillance de la colonne survolée pendant un drag (étape 7).
const dropTargetStyle = {
  borderColor: 'var(--accent-border)',
  background: 'var(--accent-bg)',
}

const headerStyle = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  marginBottom: 12,
  color: 'var(--text-h)',
  fontWeight: 500,
}

const countStyle = {
  fontSize: 13,
  fontWeight: 400,
  background: 'var(--accent-bg)',
  border: '1px solid var(--accent-border)',
  borderRadius: 999,
  padding: '1px 8px',
}

const listStyle = { display: 'flex', flexDirection: 'column', gap: 8 }

const emptyColumnStyle = { fontSize: 13, opacity: 0.6, padding: '4px 0' }

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
      style={{ ...columnStyle, ...(isDropTarget ? dropTargetStyle : {}) }}
    >
      <header style={headerStyle}>
        <span>{label}</span>
        <span style={countStyle}>{applications.length}</span>
      </header>

      <div style={listStyle}>
        {applications.length === 0 ? (
          <p style={emptyColumnStyle}>—</p>
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
