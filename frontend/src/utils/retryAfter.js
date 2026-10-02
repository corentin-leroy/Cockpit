// Fonctions PURES autour du délai d'attente d'un 429 (en-tête Retry-After).
// Aucune dépendance à React ni à Vite : testables telles quelles avec node.
//
// Principe : on n'affiche jamais une durée INVENTÉE. Un Retry-After absent ou
// illisible donne `null`, et l'appelant laisse alors le bouton utilisable (le
// serveur, lui, continue de refuser tant qu'il le faut).

// Plafond de crédibilité : au-delà de 24 h, la valeur est traitée comme illisible.
// Les fenêtres du backend vont jusqu'à 1 h ; une valeur démesurée (en-tête corrompu
// ou hostile) ne doit pas désactiver un bouton pour des jours.
export const MAX_RETRY_AFTER_SECONDS = 24 * 60 * 60

const MS_PER_MINUTE = 60_000

/**
 * Lit la valeur brute de l'en-tête Retry-After.
 *
 * Seul le format « secondes entières » est accepté, celui qu'envoie le backend
 * (RFC 9110 prévoit aussi une date HTTP). Une date n'est PAS interprétée : la
 * convertir en durée demanderait de comparer à l'horloge du poste, et un poste
 * déréglé produirait une durée fausse.
 *
 * @param {string|null|undefined} raw
 * @returns {number|null} secondes (entier >= 1, <= 24 h), ou null si illisible.
 */
export function parseRetryAfterSeconds(raw) {
  if (typeof raw !== 'string') return null
  const trimmed = raw.trim()
  if (!/^\d+$/.test(trimmed)) return null
  const seconds = Number(trimmed)
  if (!Number.isSafeInteger(seconds) || seconds < 1 || seconds > MAX_RETRY_AFTER_SECONDS) {
    return null
  }
  return seconds
}

/**
 * Minutes restantes avant l'échéance, ARRONDIES À LA MINUTE SUPÉRIEURE : 14 min 01 s
 * s'affiche « 15 », 30 s s'affiche « 1 ». 0 uniquement quand l'échéance est passée.
 */
export function minutesLeft(deadlineMs, nowMs) {
  const remaining = deadlineMs - nowMs
  return remaining <= 0 ? 0 : Math.ceil(remaining / MS_PER_MINUTE)
}

/**
 * Délai (ms) avant que l'affichage change : le moment où `minutesLeft` diminue d'une
 * unité (ou le blocage prend fin). Un minuteur à ce délai exact suit l'échéance sans
 * dérive, contrairement à un intervalle fixe de 60 s armé à un instant quelconque.
 * Toujours dans ]0, 60000] tant que l'échéance n'est pas passée, 0 ensuite.
 */
export function msUntilNextChange(deadlineMs, nowMs) {
  const remaining = deadlineMs - nowMs
  if (remaining <= 0) return 0
  const minutes = Math.ceil(remaining / MS_PER_MINUTE)
  return remaining - (minutes - 1) * MS_PER_MINUTE
}

/** Libellé du bouton pendant le blocage : « Réessayer dans 14 min ». */
export function cooldownLabel(minutes) {
  return `Réessayer dans ${minutes} min`
}

/**
 * Heure locale (« 14:32 ») à partir de laquelle le blocage est levé, arrondie à la
 * minute supérieure : à cet instant précis la tentative est permise.
 */
export function formatClockTime(deadlineMs) {
  const roundedUp = Math.ceil(deadlineMs / MS_PER_MINUTE) * MS_PER_MINUTE
  return new Intl.DateTimeFormat('fr-FR', { hour: '2-digit', minute: '2-digit' }).format(
    roundedUp,
  )
}
