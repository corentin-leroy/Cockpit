// Mémorisation du dernier tableau consulté : unique point d'accès au stockage
// pour cette clé (même principe que auth/token.js pour le token). Les composants
// et le contexte passent par ces fonctions, jamais par localStorage directement.
//
// Le stockage peut être indisponible (navigation privée, données de site
// bloquées) et lever une exception. En cas d'échec : lecture = aucun tableau
// mémorisé (le contexte retombe sur le premier), écriture ignorée.

export const LAST_BOARD_KEY = 'cockpit_last_board'

/** Renvoie l'id (chaîne) du dernier tableau consulté, ou null. */
export function getLastBoardId() {
  try {
    return localStorage.getItem(LAST_BOARD_KEY)
  } catch {
    return null
  }
}

/** Mémorise le tableau courant pour le restaurer au prochain chargement. */
export function setLastBoardId(id) {
  try {
    localStorage.setItem(LAST_BOARD_KEY, String(id))
  } catch {
    // Le tableau courant vaut pour la session, mais ne sera pas retenu.
  }
}
