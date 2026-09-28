// Couche d'accès à l'API backend (FastAPI).
//
// L'URL de base est lue depuis une variable d'environnement Vite (préfixe VITE_
// obligatoire pour être exposée au client), avec une valeur par défaut pointant
// vers le backend en développement, pour que le projet démarre sans config.

import { emitSessionExpired } from '../auth/authEvents.js'
import { getToken, removeToken } from '../auth/token.js'

// Le « / » final est retiré : les endpoints commencent tous par « / » et sont
// concaténés directement (`${API_BASE_URL}${endpoint}`). Une valeur saisie
// « https://api.exemple.app/ » produirait sinon « https://api.exemple.app//auth/login »,
// donc des 404 partout — et uniquement en production, là où la variable est
// renseignée à la main. Même précaution que côté backend sur FRONTEND_URL et
// CORS_ORIGINS.
export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
).replace(/\/+$/, '')

/**
 * Erreur d'API exploitable : expose le code HTTP (`status`) pour permettre à
 * l'appelant de réagir finement — typiquement détecter un 401.
 */
export class ApiError extends Error {
  constructor(message, status, data) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
  }
}

/**
 * Wrapper autour de fetch pour tous les appels à l'API.
 *
 * - préfixe l'endpoint avec API_BASE_URL ;
 * - pose Content-Type: application/json ;
 * - ajoute Authorization: Bearer <token> si un token est présent ;
 * - parse la réponse JSON (gère le 204 sans corps) ;
 * - en cas de statut >= 400, lève une ApiError porteuse du code HTTP ;
 * - sur 401 ET SEULEMENT si un token avait été envoyé, purge le token et signale
 *   l'expiration de session (voir le commentaire détaillé plus bas) — la
 *   redirection vers /login est ensuite assurée par les routes protégées.
 *
 * @param {string} endpoint  chemin commençant par '/', ex. '/auth/login'
 * @param {RequestInit} options  options fetch (method, body...)
 */
export async function apiFetch(endpoint, options = {}) {
  const token = getToken()

  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, { ...options, headers })

  // 204 No Content (ex. DELETE) : pas de corps à parser. Sinon on tente le JSON,
  // en restant tolérant si le corps est vide ou non-JSON.
  const data =
    response.status === 204 ? null : await response.json().catch(() => null)

  if (!response.ok) {
    // Un 401 ne signifie « session expirée » que si l'on avait RÉELLEMENT une
    // session à présenter. La condition est donc `token &&` : on a envoyé un
    // jeton, le serveur l'a refusé. Sans jeton, un 401 est la réponse normale
    // d'un endpoint public à de mauvais identifiants (POST /auth/login) : il n'y
    // a aucune session à purger, et signaler une expiration afficherait « votre
    // session a expiré » à quelqu'un qui vient simplement de se tromper de mot
    // de passe.
    //
    // Ce critère a été préféré à une liste d'endpoints publics à exclure (du
    // type « ne pas émettre pour /auth/* »), pour deux raisons. D'abord parce
    // qu'il serait FAUX : /auth/me et /auth/resend-verification sont
    // authentifiés, et un 401 y est une vraie expiration — l'exclusion par
    // préfixe casserait la détection sur /auth/me, précisément l'appel que
    // AuthContext émet au montage. Ensuite parce qu'une liste se maintient :
    // tout endpoint public ajouté plus tard devrait y être pensé, et l'oubli ne
    // se verrait qu'en production. La présence d'un jeton, elle, décrit
    // exactement la condition qu'on veut tester, et reste juste sans
    // maintenance.
    if (response.status === 401 && token) {
      // Token invalide ou expiré : on le purge pour ne pas le renvoyer en boucle,
      // puis on notifie le contexte d'auth pour qu'il bascule isAuthenticated à
      // false (sinon l'UI resterait « connectée » jusqu'au rechargement).
      removeToken()
      emitSessionExpired()
    }
    // Le backend renvoie `detail` déjà en français, directement affichable
    // (chaîne dans tous les cas, y compris un 422 — cf. app/error_messages.py
    // côté backend). Fallback sur le texte de statut si le corps est illisible.
    const message = data?.detail || response.statusText || 'Erreur API'
    throw new ApiError(message, response.status, data)
  }

  return data
}

/**
 * Répartit les erreurs d'un 422 entre les champs d'un formulaire et un message
 * général, à partir de `err.data.errors` (cf. app/error_messages.py côté
 * backend : `{"field": "title", "message": "..."}`, jamais de `field` pour une
 * erreur qui n'en désigne aucun — corps illisible, paramètre de requête).
 *
 * `fieldMap` associe le nom de champ BACKEND au nom d'état LOCAL du
 * formulaire — ils ne coïncident pas toujours (ex. ResetPasswordPage : `password`
 * localement, `new_password` côté API). Une clé absente de `fieldMap` (ex.
 * `board_id` d'ApplicationForm, dont le sélecteur peut être masqué) est traitée
 * comme si elle n'avait pas de champ : son message ne serait jamais vu s'il
 * était rangé dans un `fieldErrors` que rien n'affiche.
 *
 * `generalMessage` n'est PAS `err.message` par défaut : c'est le message de la
 * PREMIÈRE erreur qui n'a trouvé aucun champ où s'afficher. Si toutes les
 * erreurs ont trouvé un champ, `generalMessage` est vide (pas de doublon entre
 * un bandeau général et le message déjà affiché sous le champ). Pour une
 * réponse SANS `errors` (401, 403, 404, 409, 413… — pas un 422), on retombe sur
 * `err.message`, qui est déjà la bonne phrase française du backend.
 *
 * @param {ApiError} err
 * @param {Record<string, string>} fieldMap
 * @returns {{ fieldErrors: Record<string, string>, generalMessage: string }}
 */
export function splitFormErrors(err, fieldMap) {
  const apiErrors = err.data?.errors
  if (!Array.isArray(apiErrors) || apiErrors.length === 0) {
    return { fieldErrors: {}, generalMessage: err.message }
  }

  const fieldErrors = {}
  let unmatchedMessage = ''
  for (const error of apiErrors) {
    const localKey = error.field && fieldMap[error.field]
    if (localKey) {
      fieldErrors[localKey] = error.message
    } else if (!unmatchedMessage) {
      unmatchedMessage = error.message
    }
  }
  return { fieldErrors, generalMessage: unmatchedMessage }
}
