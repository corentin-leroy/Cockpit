// Lecture des datetimes renvoyés par le backend.
//
// Convention du projet (CLAUDE.md, « Base de données ») : toutes les colonnes
// DateTime sont NAÏVES en UTC. Pydantic sérialise un datetime naïf par
// isoformat() brut, SANS 'Z' ni offset (ex. « 2026-09-15T10:23:45.123456 »).
// Or la spec ECMA-262 interprète une chaîne ISO avec heure mais SANS fuseau
// comme une heure LOCALE, pas UTC : sans précaution, `new Date(chaîne)`
// déciderait du mauvais jour calendaire selon le fuseau du visiteur (jusqu'à
// afficher « Hier » pour une candidature créée « Aujourd'hui »).

/**
 * Interprète une chaîne datetime NAÏVE du backend comme un instant UTC.
 * @param {string} isoString  ex. "2026-09-15T10:23:45.123456"
 * @returns {Date}
 */
export function parseUtcDate(isoString) {
  return new Date(`${isoString}Z`)
}

// Numéro de jour calendaire, sur le fuseau LOCAL du visiteur : « Aujourd'hui »
// doit correspondre au jour du visiteur, pas à un jour UTC. On compare les
// composants année/mois/jour locaux plutôt qu'une soustraction brute de
// millisecondes, pour rester exact autour d'un changement d'heure (DST, jour
// de 23h ou 25h).
function localDayNumber(date) {
  return Math.floor(
    Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()) / 86_400_000,
  )
}

/**
 * Formule l'ancienneté d'une candidature depuis son created_at (chaîne ISO
 * naïve UTC). Une SEULE unité, le jour, sans palier semaine/mois/année (choix
 * explicite : un nombre de jours brut se compare directement d'une carte à
 * l'autre, sans arrondi qui masquerait l'écart réel). Seules exceptions, plus
 * lisibles qu'un nombre : « Aujourd'hui » et « Hier ».
 * @param {string} createdAtIso
 * @param {Date} [now]  injectable (tests, ou horloge figée).
 * @returns {string}
 */
export function formatApplicationAge(createdAtIso, now = new Date()) {
  const createdAt = parseUtcDate(createdAtIso)
  const days = localDayNumber(now) - localDayNumber(createdAt)

  // <= 0 couvre aussi une horloge cliente désynchronisée (created_at « dans le
  // futur ») : mieux vaut « Aujourd'hui » qu'un nombre négatif absurde.
  if (days <= 0) return 'Aujourd’hui'
  if (days === 1) return 'Hier'
  return `il y a ${days} j`
}
