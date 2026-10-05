// Appels à l'API des candidatures.

import { apiFetch } from './client.js'

/**
 * Récupère les candidatures de l'utilisateur connecté. GET /applications.
 * Le cloisonnement par utilisateur est assuré côté backend (jointure board →
 * user) ; apiFetch ajoute déjà le header Bearer et gère le 401.
 * @param {number} [boardId] filtre optionnel : ne renvoyer que les candidatures
 *   de ce tableau (GET /applications?board_id=...).
 * @returns {Promise<Array>} liste des candidatures.
 */
export function getApplications(boardId) {
  const query = boardId != null ? `?board_id=${encodeURIComponent(boardId)}` : ''
  return apiFetch(`/applications${query}`)
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
 * Déplace une carte par glisser-déposer. POST /applications/{id}/move.
 * Le serveur la place au rang `position` (0 = en haut) de la colonne `status` de
 * SON tableau et renumérote les autres ; un rang au-delà de la fin est ramené en
 * fin de colonne. 409 si la candidature est archivée. Seul ce chemin choisit un
 * rang : toute autre arrivée dans une colonne (création, changement de statut ou
 * de tableau par PATCH, désarchivage) place la carte EN HAUT.
 * @param {number} id  identifiant de la candidature.
 * @param {{status: string, position: number}} target  colonne et rang visés.
 * @returns {Promise<Object>} la candidature à jour.
 */
export function moveApplication(id, { status, position }) {
  return apiFetch(`/applications/${id}/move`, {
    method: 'POST',
    body: JSON.stringify({ status, position }),
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

/**
 * Récupère les candidatures ARCHIVÉES de l'utilisateur connecté, tous tableaux
 * confondus. GET /applications?archived=true (jamais un mélange actif/archivé,
 * cf. CLAUDE.md « Archivage des candidatures »).
 * @returns {Promise<Array>} liste des candidatures archivées.
 */
export function getArchivedApplications() {
  return apiFetch('/applications?archived=true')
}

/**
 * Archive une candidature. POST /applications/{id}/archive.
 * Le statut n'est pas modifié ; le serveur pose archived_at. 409 si le plafond
 * de 2000 archivées est atteint, ou si elle est déjà archivée.
 * @param {number} id  identifiant de la candidature.
 * @returns {Promise<Object>} la candidature à jour.
 */
export function archiveApplication(id) {
  return apiFetch(`/applications/${id}/archive`, { method: 'POST' })
}

/**
 * Désarchive une candidature. POST /applications/{id}/unarchive.
 * 409 si le plafond de 300 actives est atteint, ou si elle est déjà active.
 * @param {number} id  identifiant de la candidature.
 * @returns {Promise<Object>} la candidature à jour.
 */
export function unarchiveApplication(id) {
  return apiFetch(`/applications/${id}/unarchive`, { method: 'POST' })
}
