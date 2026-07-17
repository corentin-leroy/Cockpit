// Appels à l'API d'authentification du backend.

import { apiFetch } from './client.js'

/**
 * Inscription. POST /auth/register → renvoie l'utilisateur créé (sans le hash).
 */
export function register(email, password) {
  return apiFetch('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
}

/**
 * Connexion. POST /auth/login → renvoie { access_token, token_type }.
 * Le stockage du token est géré par le AuthContext, pas ici.
 */
export function login(email, password) {
  return apiFetch('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
}

/**
 * Utilisateur courant. GET /auth/me → { id, email, is_verified, created_at }.
 * Authentifié : apiFetch joint le Bearer. 401 si le token est absent/expiré.
 */
export function getMe() {
  return apiFetch('/auth/me')
}

/**
 * Demande un lien de réinitialisation. POST /auth/forgot-password.
 * Public. Répond TOUJOURS le même message, que le compte existe ou non :
 * l'appelant ne doit rien déduire de la réponse.
 */
export function forgotPassword(email) {
  return apiFetch('/auth/forgot-password', {
    method: 'POST',
    body: JSON.stringify({ email }),
  })
}

/**
 * Change le mot de passe via le lien reçu par email. POST /auth/reset-password.
 * Public (le token EST la preuve d'identité). 400 si le lien est invalide,
 * expiré ou déjà utilisé.
 */
export function resetPassword(token, newPassword) {
  return apiFetch('/auth/reset-password', {
    method: 'POST',
    body: JSON.stringify({ token, new_password: newPassword }),
  })
}

/**
 * Confirme l'adresse email via le lien reçu. POST /auth/verify-email.
 * Public : l'utilisateur peut cliquer depuis sa boîte mail sans être connecté.
 */
export function verifyEmail(token) {
  return apiFetch('/auth/verify-email', {
    method: 'POST',
    body: JSON.stringify({ token }),
  })
}

/**
 * Renvoie un email de confirmation. POST /auth/resend-verification.
 * Authentifié : le backend peut être explicite (409 déjà vérifié, 429 plafond
 * horaire atteint).
 */
export function resendVerification() {
  return apiFetch('/auth/resend-verification', { method: 'POST' })
}
