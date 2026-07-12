// Carte d'une candidature dans le kanban. Draggable (@dnd-kit/react) pour changer
// de statut en la glissant vers une autre colonne.

import { useDraggable } from '@dnd-kit/react'

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
      className={`app-card${isDragging ? ' app-card--dragging' : ''}`}
    >
      <h3 className="app-card__title">
        {url ? (
          // Lien vers l'offre d'origine. rel="noreferrer" par sécurité avec _blank.
          <a href={url} target="_blank" rel="noreferrer">
            {title}
          </a>
        ) : (
          title
        )}
      </h3>
      <p className="app-card__company">{company}</p>
      {location && <p className="app-card__location">{location}</p>}

      {onEdit && (
        // Bouton explicite plutôt que carte entière cliquable : préserve le lien
        // vers l'offre et reste accessible au clavier.
        <div className="app-card__footer">
          <button
            type="button"
            className="btn btn--secondary btn--sm"
            onClick={() => onEdit(application)}
          >
            Éditer
          </button>
        </div>
      )}
    </article>
  )
}
