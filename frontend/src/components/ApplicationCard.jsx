// Carte d'une candidature dans le kanban. Draggable (@dnd-kit/react) pour changer
// de statut en la glissant vers une autre colonne.

import { useDraggable } from '@dnd-kit/react'

const cardStyle = {
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '10px 12px',
  background: 'var(--bg)',
  boxShadow: 'var(--shadow)',
  cursor: 'grab',
  // touchAction none : évite que le navigateur interprète le glissé tactile comme
  // un défilement, ce qui empêcherait le drag sur mobile.
  touchAction: 'none',
}

// Retour visuel de la carte en cours de déplacement (étape 7) : atténuée et
// légèrement estompée, pendant qu'un clone suit le curseur (feedback dnd-kit).
const draggingStyle = { opacity: 0.4, cursor: 'grabbing' }

const titleStyle = { margin: 0, fontSize: 15, color: 'var(--text-h)' }
const companyStyle = { margin: '4px 0 0', fontSize: 14 }
const locationStyle = { margin: '2px 0 0', fontSize: 13, opacity: 0.8 }

const footerStyle = { marginTop: 8, display: 'flex', justifyContent: 'flex-end' }

const editButtonStyle = {
  border: '1px solid var(--border)',
  borderRadius: 6,
  background: 'transparent',
  color: 'inherit',
  font: 'inherit',
  fontSize: 12,
  padding: '2px 8px',
  cursor: 'pointer',
}

export default function ApplicationCard({ application, onEdit }) {
  const { title, company, location, url } = application

  // Identifiant draggable = id de la candidature. On mémorise le statut courant
  // dans `data` : il sert de « colonne d'origine » pour détecter un no-op au drop.
  const { ref, isDragging } = useDraggable({
    id: application.id,
    data: { status: application.status },
  })

  return (
    <article
      ref={ref}
      style={{ ...cardStyle, ...(isDragging ? draggingStyle : {}) }}
    >
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

      {onEdit && (
        // Bouton explicite plutôt que carte entière cliquable : préserve le lien
        // vers l'offre et reste accessible au clavier.
        <div style={footerStyle}>
          <button
            type="button"
            style={editButtonStyle}
            onClick={() => onEdit(application)}
          >
            Éditer
          </button>
        </div>
      )}
    </article>
  )
}
