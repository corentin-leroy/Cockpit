// Carte d'une candidature dans le kanban (lecture seule pour l'instant).

const cardStyle = {
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '10px 12px',
  background: 'var(--bg)',
  boxShadow: 'var(--shadow)',
}

const titleStyle = { margin: 0, fontSize: 15, color: 'var(--text-h)' }
const companyStyle = { margin: '4px 0 0', fontSize: 14 }
const locationStyle = { margin: '2px 0 0', fontSize: 13, opacity: 0.8 }

export default function ApplicationCard({ application }) {
  const { title, company, location, url } = application

  return (
    <article style={cardStyle}>
      <h3 style={titleStyle}>
        {url ? (
          // Lien vers l'offre d'origine. rel="noreferrer" par sécurité avec _blank.
          <a href={url} target="_blank" rel="noreferrer">
            {title}
          </a>
        ) : (
          title
        )}
      </h3>
      <p style={companyStyle}>{company}</p>
      {location && <p style={locationStyle}>{location}</p>}
    </article>
  )
}
