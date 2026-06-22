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
