// Appels à l'API des tableaux (boards).

import { apiFetch } from './client.js'

/**
 * Récupère les tableaux de l'utilisateur connecté. GET /boards.
 * Le cloisonnement par utilisateur est assuré côté backend (filtre user_id) ;
 * apiFetch ajoute déjà le header Bearer et gère le 401.
 * @returns {Promise<Array>} liste des tableaux (au moins un, garanti backend).
 */
export function getBoards() {
  return apiFetch('/boards')
}
