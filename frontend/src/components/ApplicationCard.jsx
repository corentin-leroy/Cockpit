// Carte d'une candidature dans le kanban. Draggable (@dnd-kit/react) pour changer
// de statut en la glissant vers une autre colonne. La carte entière ouvre la
// modale d'édition au clic ; le lien vers l'offre (titre) et l'icône « éditer »
// (visible au survol) coexistent avec ce clic global via stopPropagation.

import { useDraggable } from '@dnd-kit/react'

export default function ApplicationCard({ application, onEdit }) {
  const { title, company, location, url } = application

  // Identifiant draggable = id de la candidature. On mémorise le statut courant
  // dans `data` : il sert de « colonne d'origine » pour détecter un no-op au drop.
  const { ref, isDragging } = useDraggable({
    id: application.id,
    data: { status: application.status },
  })

  // Équivalent clavier du clic sur la carte (Entrée/Espace). `target !==
  // currentTarget` ignore les touches pressées depuis le lien ou le bouton
  // imbriqués : leur propre activation clavier native suffit déjà, sinon
  // onEdit serait appelé deux fois (une fois par l'élément imbriqué, une fois
  // par ce gestionnaire au moment où l'événement remonte).
  function handleKeyDown(event) {
    if (event.target !== event.currentTarget) return
    if (event.key !== 'Enter' && event.key !== ' ') return
    event.preventDefault() // Espace ne doit pas faire défiler la page.
    onEdit(application)
  }

  return (
    <article
      ref={ref}
      className={`app-card${isDragging ? ' app-card--dragging' : ''}`}
      // Carte entière cliquable seulement si onEdit est fourni (dégradation
      // gracieuse, comme l'ancien `{onEdit && (...)}` sur le bouton).
      {...(onEdit && {
        onClick: () => onEdit(application),
        role: 'button',
        tabIndex: 0,
        onKeyDown: handleKeyDown,
      })}
    >
      <h3 className="app-card__title">
        {url ? (
          // Lien vers l'offre d'origine. stopPropagation : un clic ici ne doit
          // pas AUSSI déclencher l'ouverture de la modale (la navigation, elle,
          // doit avoir lieu normalement — pas de preventDefault).
          <a
            href={url}
            target="_blank"
            rel="noreferrer"
            onClick={(event) => event.stopPropagation()}
          >
            {title}
          </a>
        ) : (
          title
        )}
      </h3>
      <p className="app-card__company">{company}</p>
      {location && <p className="app-card__location">{location}</p>}

      {onEdit && (
        // Icône seule, révélée au survol/focus via CSS (voir .app-card__edit) :
        // aucune insertion/retrait du DOM, donc aucun saut de mise en page.
        <button
          type="button"
          className="btn btn--ghost btn--icon app-card__edit"
          aria-label="Éditer la candidature"
          title="Éditer"
          onClick={(event) => {
            event.stopPropagation()
            onEdit(application)
          }}
        >
          <span aria-hidden="true">✎</span>
        </button>
      )}
    </article>
  )
}
