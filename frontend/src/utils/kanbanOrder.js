// Ordre des cartes du kanban pendant un glisser-déposer. Fonctions PURES, partagées
// par BoardPage (avec appel API) et la landing page (démonstration, sans appel).
//
// L'état est une liste PLATE de candidatures ; l'ordre d'affichage d'une colonne est
// l'ordre de ses cartes dans cette liste (BoardPage et la landing les répartissent
// par statut sans retrier). Le serveur renvoie la liste dans l'ordre des positions
// (colonne `position`, cf. CLAUDE.md « Ordre des cartes du kanban »).
//
// POURQUOI l'état suit le survol : dnd-kit fournit un « tri optimiste »
// (OptimisticSortingPlugin) qui déplace LUI-MÊME les nœuds DOM des cartes pendant le
// glisser, à l'insu de React. Si la carte quitte ensuite l'état (dépôt sur la zone
// d'archivage ou sur un tableau de la sidebar) alors que le plugin l'a glissée dans
// une autre colonne, React tente de la retirer de son parent d'ORIGINE, qui ne la
// contient plus (removeChild → NotFoundError). kanban/useKanbanDrag.js appelle donc
// `event.preventDefault()` dans onDragOver (le plugin s'abstient alors) et
// réordonne l'état avec ces fonctions : React reste le seul à déplacer les nœuds.

import { move } from '@dnd-kit/helpers'

import { APPLICATION_STATUSES } from '../constants/applicationStatuses.js'

const STATUS_KEYS = APPLICATION_STATUSES.map((status) => status.key)

/**
 * Réordonne la liste d'après un événement `dragover` de dnd-kit (carte survolée ou
 * colonne survolée). Renvoie la MÊME liste si rien ne change (pas de rendu inutile).
 * Les candidatures au statut inconnu (désync backend) sont conservées, en fin.
 */
export function reorderOnDragOver(applications, event) {
  const groups = Object.fromEntries(STATUS_KEYS.map((key) => [key, []]))
  for (const application of applications) {
    groups[application.status]?.push(application.id)
  }

  const moved = move(groups, event)
  if (moved === groups) return applications

  const byId = new Map(applications.map((application) => [application.id, application]))
  const ordered = []
  for (const key of STATUS_KEYS) {
    for (const id of moved[key]) {
      const application = byId.get(id)
      ordered.push(application.status === key ? application : { ...application, status: key })
    }
  }
  const unknown = applications.filter((application) => !STATUS_KEYS.includes(application.status))
  return [...ordered, ...unknown]
}

/**
 * Place d'une carte : son statut et son rang dans SA colonne (0 = en haut), ou null
 * si elle n'est pas dans la liste. C'est ce qu'attend POST /applications/{id}/move.
 */
export function placeOf(applications, applicationId) {
  const application = applications.find((item) => item.id === applicationId)
  if (!application) return null
  const index = applications
    .filter((item) => item.status === application.status)
    .findIndex((item) => item.id === applicationId)
  return { status: application.status, index }
}

/**
 * Place une carte au rang `index` de la colonne `status` (0 = en haut), les autres
 * cartes gardant leur ordre. Applique à l'ÉTAT un placement déjà calculé : le calcul
 * (reorderOnDragOver) lit la position du pointeur en direct, il ne doit pas être
 * refait plus tard dans une mise à jour d'état différée.
 */
export function placeCard(applications, applicationId, { status, index }) {
  const card = applications.find((item) => item.id === applicationId)
  if (!card) return applications
  const placed = card.status === status ? card : { ...card, status }
  const next = applications.filter((item) => item.id !== applicationId)
  const column = next.filter((item) => item.status === status)
  if (index < column.length) {
    next.splice(next.indexOf(column[index]), 0, placed)
  } else if (column.length > 0) {
    next.splice(next.indexOf(column[column.length - 1]) + 1, 0, placed)
  } else {
    next.push(placed)
  }
  return next
}

/**
 * Remet une carte telle qu'elle était au début du glisser (`original`, à l'index
 * `originalIndex` de la liste d'alors) : retirée de sa place actuelle, réinsérée à
 * son index d'origine. Ciblé sur cette seule carte, comme les autres retours en
 * arrière de BoardPage : se compose avec d'éventuelles autres modifications.
 */
export function restoreCard(applications, original, originalIndex) {
  const next = applications.filter((item) => item.id !== original.id)
  next.splice(Math.min(originalIndex, next.length), 0, original)
  return next
}
