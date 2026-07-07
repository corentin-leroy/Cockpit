// Mémorisation du dernier tableau consulté : unique point d'accès au stockage
// pour cette clé (même principe que auth/token.js pour le token). Les composants
// et le contexte passent par ces fonctions, jamais par localStorage directement.

export const LAST_BOARD_KEY = 'cockpit_last_board'

/** Renvoie l'id (chaîne) du dernier tableau consulté, ou null. */
export function getLastBoardId() {
  return localStorage.getItem(LAST_BOARD_KEY)
}

/** Mémorise le tableau courant pour le restaurer au prochain chargement. */
export function setLastBoardId(id) {
  localStorage.setItem(LAST_BOARD_KEY, String(id))
}
