// Phrase annonçant ce que la suppression d'un tableau emporte avec lui (cascade
// backend : candidatures actives ET archivées). Fonction pure, sans React, pour
// que l'accord (singulier/pluriel) se vérifie isolément.

function plural(count, singular, pluralForm) {
  return count > 1 ? pluralForm : singular
}

/**
 * @param {number} active    candidatures actives du tableau.
 * @param {number} archived  candidatures archivées du tableau.
 * @returns {string} la phrase, ou '' si le tableau est vide (rien à annoncer).
 */
export function describeBoardContent(active, archived) {
  if (active === 0 && archived === 0) return ''

  const parts = []
  if (active > 0) {
    parts.push(
      `${active} ${plural(active, 'candidature active', 'candidatures actives')}`,
    )
  }
  if (archived > 0) {
    // Après un premier groupe, le nom « candidature » n'est pas répété :
    // « 12 candidatures actives et 3 archivées ».
    const noun = active > 0 ? '' : `${plural(archived, 'candidature ', 'candidatures ')}`
    parts.push(`${archived} ${noun}${plural(archived, 'archivée', 'archivées')}`)
  }

  // Le verbe s'accorde avec l'ENSEMBLE annoncé : « sera » seulement s'il n'y a
  // qu'une candidature au total (« 1 active et 1 archivée » = deux → « seront »).
  const isPlural = active + archived > 1
  const verb = isPlural ? 'seront définitivement supprimées' : 'sera définitivement supprimée'
  return `${parts.join(' et ')} ${verb}.`
}
