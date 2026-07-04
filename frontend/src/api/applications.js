// Appels à l'API des candidatures.

import { apiFetch } from './client.js'

/**
 * Récupère les candidatures de l'utilisateur connecté. GET /applications.
 * Le cloisonnement par utilisateur est assuré côté backend (filtre user_id) ;
 * apiFetch ajoute déjà le header Bearer et gère le 401.
 * @returns {Promise<Array>} liste des candidatures.
 */
export function getApplications() {
  return apiFetch('/applications')
}

/**
 * Crée une candidature. POST /applications → renvoie la candidature créée (201).
 * Le statut n'est PAS transmis : le backend démarre toujours en « saved »
 * (Repérée). Le propriétaire (user_id) est déduit du token côté serveur.
 * @param {{title: string, company: string, location?: string|null,
 *   url?: string|null, notes?: string|null}} data
 * @returns {Promise<Object>} la candidature créée.
 */
export function createApplication(data) {
  return apiFetch('/applications', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

/**
 * Modifie une candidature. PATCH /applications/{id} → renvoie la version à jour.
 * Sémantique PATCH : seuls les champs fournis sont mis à jour côté backend.
 * @param {number} id  identifiant de la candidature.
 * @param {Object} data  champs à modifier.
 * @returns {Promise<Object>} la candidature mise à jour.
 */
export function updateApplication(id, data) {
  return apiFetch(`/applications/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

/**
 * Supprime une candidature. DELETE /applications/{id} → 204 (apiFetch renvoie null).
 * @param {number} id  identifiant de la candidature.
 * @returns {Promise<null>}
 */
export function deleteApplication(id) {
  return apiFetch(`/applications/${id}`, { method: 'DELETE' })
}
