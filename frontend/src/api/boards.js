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

/**
 * Crée un tableau. POST /boards. Le propriétaire est déduit du token côté serveur.
 * @param {string} name nom du tableau (non vide, validé aussi par le backend).
 * @returns {Promise<Object>} le tableau créé.
 */
export function createBoard(name) {
  return apiFetch('/boards', {
    method: 'POST',
    body: JSON.stringify({ name }),
  })
}

/**
 * Renomme un tableau. PATCH /boards/{id}.
 * @param {number} id   id du tableau.
 * @param {string} name nouveau nom (non vide).
 * @returns {Promise<Object>} le tableau à jour.
 */
export function updateBoard(id, name) {
  return apiFetch(`/boards/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ name }),
  })
}

/**
 * Supprime un tableau ET ses candidatures (cascade backend). DELETE /boards/{id}.
 * Le backend refuse (409) la suppression du dernier tableau de l'utilisateur.
 * @param {number} id id du tableau.
 * @returns {Promise<void>}
 */
export function deleteBoard(id) {
  return apiFetch(`/boards/${id}`, { method: 'DELETE' })
}
