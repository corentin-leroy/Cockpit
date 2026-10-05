// Carte d'une candidature dans le kanban. Triable (@dnd-kit/react/sortable) : on la
// glisse à n'importe quel rang de sa colonne ou d'une autre colonne. La carte
// entière ouvre la modale d'édition au clic ou au clavier (Entrée/Espace) ; le lien
// vers l'offre (titre) coexiste avec ce clic global via stopPropagation.

import { useSortable } from '@dnd-kit/react/sortable'

import { formatApplicationAge } from '../utils/dates.js'

export default function ApplicationCard({ application, index, onEdit }) {
  const { title, company, location, url, created_at: createdAt } = application
  const age = formatApplicationAge(createdAt)

  // Identifiant = id de la candidature ; `group` = sa colonne (statut), `index` =
  // son rang dans la colonne. `type`/`accept` : une carte ne se trie qu'avec
  // d'autres cartes. L'ordre lui-même vit dans l'état de la page, réordonné pendant
  // le survol (utils/kanbanOrder.js explique pourquoi dnd-kit ne doit pas déplacer
  // le DOM lui-même).
  const { ref, isDragging } = useSortable({
    id: application.id,
    index,
    group: application.status,
    type: 'card',
    accept: 'card',
  })

  // Équivalent clavier du clic sur la carte (Entrée/Espace). `target !==
  // currentTarget` ignore les touches pressées depuis le lien imbriqué : son
  // activation clavier native (Entrée) suffit déjà, sinon la modale s'ouvrirait
  // en plus de la navigation quand l'événement remonte jusqu'ici.
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
      {/* Ligne du bas TOUJOURS présente, même sans lieu (choix explicite :
          une mise en page cohérente plutôt qu'une économie de hauteur sur les
          cartes sans lieu). Le lieu occupe l'espace disponible à gauche,
          l'ancienneté reste collée à droite — y compris quand le lieu est
          absent (span vide, flex:1 le pousse quand même jusqu'au bord). */}
      <p className="app-card__meta-row">
        <span className="app-card__location">{location}</span>
        <span className="app-card__age">{age}</span>
      </p>
    </article>
  )
}
