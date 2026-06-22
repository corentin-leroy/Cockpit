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
