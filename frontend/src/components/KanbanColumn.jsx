// Une colonne du kanban : un statut, son libellé, le nombre de candidatures
// qu'elle contient, et les cartes correspondantes, DANS L'ORDRE REÇU.
//
// Le statut est identifié par son LIBELLÉ (« Repérée », « Entretien »…) : les
// colonnes partagent toutes la même couleur, aucune information n'est portée par
// la teinte seule.
//
// STRUCTURE (DESIGN.md, « Mise en page des écrans » ; dev-docs/frontend-kanban-dnd.md) :
//  - l'ENVELOPPE (section.kanban-column), invisible, étirée à la hauteur de la
//    colonne la plus longue du tableau (.kanban est une grille d'une rangée). C'est
//    le parent de l'en-tête collant : un élément collant ne sort jamais de son
//    parent, et le parent était le cadre, si bien que l'en-tête d'une colonne courte
//    disparaissait avec elle. Flex en colonne : en-tête, liste, espace vide ;
//  - la LISTE est le CADRE visible (fond, bordure, arrondis) : elle remonte SOUS
//    l'en-tête (marge négative de la hauteur de l'en-tête) et garde la hauteur de ses
//    cartes ;
//  - l'en-tête, par-dessus ; sa forme propre (.kanban-column__heading) est
//    transparente au repos et n'apparaît qu'accroché.
//
// DEUX zones de dépôt (@dnd-kit/react) :
//  - le CADRE (la liste, id = clé technique du statut) : une carte lâchée dans son
//    espace libre, ou dans une colonne VIDE. Même rectangle que l'ancienne colonne. `move` (@dnd-kit/helpers) la place en haut ou
//    en bas selon que le pointeur est au-dessus ou au-dessous du CENTRE de la zone :
//    c'est pourquoi cette zone reste le cadre, et non l'enveloppe, dont le centre
//    serait à mi-hauteur de la colonne la plus longue ;
//  - l'espace VIDE sous le cadre (`column-end`) : la carte va toujours à la FIN de la
//    colonne (utils/kanbanOrder.js, moveToColumnEnd).
// Le reste du temps, la cible est la carte survolée (tri).

import { useEffect, useRef, useState } from 'react'
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
  const { ref: frameRef, isDropTarget: frameTargeted } = useDroppable({
    id: statusKey,
    type: 'column',
    accept: 'card',
    collisionPriority: 1,
  })

  // Espace vide sous le cadre : fin de colonne. `data.type` est lu par
  // reorderOnDragOver (comme 'board' et 'archive' par useKanbanDrag).
  const { ref: endRef, isDropTarget: endTargeted } = useDroppable({
    id: `${statusKey}:end`,
    type: 'column',
    accept: 'card',
    collisionPriority: 1,
    data: { type: 'column-end', status: statusKey },
  })

  // En-tête ACCROCHÉ : un témoin de 1px en haut de l'enveloppe, observé par rapport
  // à la zone qui défile (.kanban). Passé au-dessus de son bord haut, l'en-tête est
  // collé et prend sa forme complète (data-stuck, components.css). Même rendu dans
  // tous les navigateurs (les requêtes de conteneur scroll-state ne sont pas
  // supportées par Firefox ni Safari) ; aucun écouteur de défilement.
  // rootMargin horizontal immense : seul compte le bord HAUT. Sans lui, une colonne
  // hors de l'écran à droite ne déclencherait aucun rappel en revenant à l'écran
  // alors que la page est déjà défilée, et son état resterait faux.
  // Landing : son .kanban ne défile pas, le témoin y reste toujours visible.
  const sentinelRef = useRef(null)
  const [stuck, setStuck] = useState(false)

  useEffect(() => {
    const sentinel = sentinelRef.current
    const root = sentinel?.closest('.kanban')
    if (!sentinel || !root || typeof IntersectionObserver === 'undefined') return undefined
    const observer = new IntersectionObserver(
      ([entry]) => {
        setStuck(
          !entry.isIntersecting &&
            entry.rootBounds !== null &&
            entry.boundingClientRect.top < entry.rootBounds.top,
        )
      },
      { root, rootMargin: '0px 100000px' },
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [])

  const className = [
    'kanban-column',
    frameTargeted || endTargeted ? 'kanban-column--drop-target' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <section className={className} data-stuck={stuck ? '' : undefined}>
      <span ref={sentinelRef} className="kanban-column__sentinel" aria-hidden="true" />

      {/* L'en-tête (collant) ne dessine rien lui-même ; sa forme visible est
          portée par .kanban-column__heading, qui a une VRAIE bordure de 1px :
          arrondie par le navigateur exactement comme celle du cadre, au même
          endroit, quel que soit le zoom (components.css, « Kanban »). */}
      <header className="kanban-column__header">
        <div className="kanban-column__heading">
          <span className="kanban-column__label">{label}</span>
          <span className="kanban-column__count">{applications.length}</span>
        </div>
      </header>

      <div ref={frameRef} className="kanban-column__list">
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

      <div ref={endRef} className="kanban-column__end" aria-hidden="true" />
    </section>
  )
}
