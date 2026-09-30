// Préférences d'affichage mémorisées : unique point d'accès au stockage pour ces
// clés (même principe que auth/token.js, theme/storage.js et boards/lastBoard.js :
// un module par clé, jamais de localStorage direct dans un composant).
//
// Une préférence d'affichage est FACULTATIVE : le stockage peut être indisponible
// (navigation privée, données de site bloquées) et lever une exception à la
// lecture comme à l'écriture. Dans ce cas la lecture rend la valeur par défaut et
// l'écriture est ignorée, sans erreur : la préférence n'est simplement pas
// retenue d'une visite à l'autre.

export const SIDEBAR_COLLAPSED_KEY = 'cockpit_sidebar_collapsed'

/** Sidebar des tableaux repliée ? Faux (dépliée) par défaut et si la lecture échoue. */
export function getSidebarCollapsed() {
  try {
    return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === 'true'
  } catch {
    return false
  }
}

/** Mémorise l'état de la sidebar ; ignoré si le stockage est indisponible. */
export function setSidebarCollapsed(collapsed) {
  try {
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(collapsed))
  } catch {
    // Stockage indisponible : la préférence ne survivra pas au rechargement.
  }
}
