// Gestion du token JWT : unique point d'accès au stockage.
//
// Tout le reste du code passe par ces fonctions et n'appelle JAMAIS localStorage
// directement. Avantage : si l'on change de stratégie de stockage (sessionStorage,
// cookie httpOnly via le backend, mémoire...), un seul fichier est à modifier.

const TOKEN_KEY = 'cockpit_token'

/** Renvoie le token stocké, ou null s'il n'y en a pas. */
export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

/** Stocke le token. */
export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

/** Efface le token (déconnexion, ou token invalide/expiré). */
export function removeToken() {
  localStorage.removeItem(TOKEN_KEY)
}
