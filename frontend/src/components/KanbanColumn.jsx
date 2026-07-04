// Une colonne du kanban : un statut, son libellé, le nombre de candidatures
// qu'elle contient, et les cartes correspondantes.

import ApplicationCard from './ApplicationCard.jsx'

const columnStyle = {
  flex: '0 0 240px',
  display: 'flex',
  flexDirection: 'column',
  background: 'var(--social-bg)',
  border: '1px solid var(--border)',
  borderRadius: 10,
  padding: 12,
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

export default function KanbanColumn({ label, applications, onEditApplication }) {
  return (
    <section style={columnStyle}>
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
