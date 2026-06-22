// Bus d'événements minimal pour signaler une invalidation de session détectée
// HORS de React — typiquement un 401 intercepté par apiFetch, qui purge le token
// sans pouvoir toucher à l'état du contexte (apiFetch n'est pas un composant).
//
// Ce module découple la couche API (non-React) du AuthContext : la couche API
// émet, le contexte s'abonne et se resynchronise. Aucune dépendance au DOM.

const listeners = new Set()

/**
 * Abonne un listener à l'expiration de session.
 * @returns {() => void} fonction de désabonnement (à appeler au cleanup).
 */
export function onSessionExpired(listener) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** Notifie tous les abonnés qu'une session a été invalidée (token purgé). */
export function emitSessionExpired() {
  listeners.forEach((listener) => listener())
}
