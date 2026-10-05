// Réordonnancement des cartes par glisser-déposer, partagé par le kanban (BoardPage,
// avec appel API) et la démonstration de la landing page (sans appel).
//
// En trois temps :
//  - DÉBUT : on mémorise la carte, son index dans la liste et sa place (statut, rang
//    dans la colonne). C'est la référence de la décision finale et du retour en
//    arrière, la liste changeant pendant le survol ;
//  - SURVOL : la liste est réordonnée (utils/kanbanOrder.js) et React déplace la
//    carte ; le placeholder de dnd-kit, qui la suit dans le DOM, montre où elle va
//    s'insérer. `event.preventDefault()` empêche le tri optimiste de dnd-kit de
//    déplacer LUI-MÊME les nœuds DOM (cf. kanbanOrder.js : sans cela, un dépôt sur
//    l'archive ou un tableau après le survol d'une autre colonne casse React) ;
//  - FIN : `endDrag` renvoie la place d'origine et la place finale ; la page décide.
//
// L'ordre en cours de glisser est tenu dans une REF, mise à jour de façon
// synchrone : dnd-kit exécute onDragOver dans un startTransition (rendu différé,
// interruptible) mais émet dragend immédiatement au relâchement. Lire la place
// finale dans l'état React pourrait donc renvoyer celle d'un survol précédent.

import { useRef } from 'react'

import { placeCard, placeOf, reorderOnDragOver, restoreCard } from '../utils/kanbanOrder.js'

// Cibles qui ne sont pas un rang dans une colonne : leur survol ne réordonne rien.
const NON_SORTING_TARGETS = new Set(['board', 'archive'])

export function useKanbanDrag(applications, setApplications) {
  const drag = useRef(null)

  function onDragStart(event) {
    const id = event.operation.source?.id
    const index = applications.findIndex((item) => item.id === id)
    drag.current =
      index === -1
        ? null
        : {
            applicationId: id,
            original: applications[index],
            originalIndex: index,
            from: placeOf(applications, id),
            order: applications,
          }
  }

  function onDragOver(event) {
    event.preventDefault()
    const current = drag.current
    if (!current) return
    if (NON_SORTING_TARGETS.has(event.operation.target?.data?.type)) return

    const next = reorderOnDragOver(current.order, event)
    if (next === current.order) return
    current.order = next
    const place = placeOf(next, current.applicationId)
    setApplications((prev) => placeCard(prev, current.applicationId, place))
  }

  /**
   * À appeler en tête de onDragEnd. Renvoie null si aucun glisser de carte n'était
   * en cours ; sinon { applicationId, original, originalIndex, from, to, restore },
   * où `from`/`to` = { status, index } (rang dans la colonne) et `restore()` remet la
   * carte à sa place d'origine dans l'état (annulation, échec de l'API).
   */
  function endDrag() {
    const current = drag.current
    drag.current = null
    if (!current) return null
    const { applicationId, original, originalIndex, from, order } = current
    return {
      applicationId,
      original,
      originalIndex,
      from,
      to: placeOf(order, applicationId),
      restore: () => setApplications((prev) => restoreCard(prev, original, originalIndex)),
    }
  }

  return { onDragStart, onDragOver, endDrag }
}
