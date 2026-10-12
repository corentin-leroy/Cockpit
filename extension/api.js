// Couche d'accès à l'API backend, utilisée par le service worker (contexte
// extension, non soumis à la CSP d'un site). Trois appels :
// - getBoards() et
//   createApplication() : ajoutent le Bearer du jeton STOCKÉ et purgent la
//                         session sur 401 (même logique que le front) ;
// - fetchCurrentUser()  : valide un jeton REÇU du site avant de le stocker
//                         (session:set) ; ne purge jamais rien.
// Plus de login() : on se connecte sur le site, qui transmet sa session.
//
// L'URL de l'API (API_BASE_URL) est figée dans config.js : voir ce fichier pour
// son alignement obligatoire avec host_permissions et le développement local.

import { API_BASE_URL } from "./config.js";
import { getToken, clearSession } from "./storage.js";

/**
 * Erreur d'API porteuse du code HTTP (pour détecter un 401) et du corps JSON
 * complet (`data`) — notamment `data.errors`, la liste par champ que le backend
 * fournit sur un 422 (`[{"field": "title", "message": "..."}]`). La popup n'a
 * qu'un seul conteneur de message (`#message`, cf. CLAUDE.md de l'extension :
 * « ne pas en créer un second ») et n'exploite donc PAS `data.errors`
 * aujourd'hui — `message` (déjà la bonne phrase française, cf. plus bas) suffit
 * à ce seul affichage. `data` est conservé pour rester aligné avec ApiError du
 * front (frontend/src/api/client.js), qui l'exploite déjà.
 */
export class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

/**
 * Utilisateur courant pour un jeton DONNÉ. GET /auth/me → { id, email, ... }.
 * Sert à valider le jeton reçu du site AVANT de le stocker (session:set,
 * background.js). Lève une ApiError (status 401 pour un jeton refusé) ; une
 * panne réseau remonte telle quelle (TypeError de fetch).
 *
 * ⚠ Ne purge JAMAIS la session sur 401, contrairement aux deux appels suivants :
 * le jeton refusé n'est pas celui du stockage, qui peut porter une session
 * valide.
 */
export async function fetchCurrentUser(token) {
  const response = await fetch(`${API_BASE_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    // Le backend renvoie `detail` déjà en français — TOUJOURS une chaîne.
    // Fallback générique si le corps est illisible.
    throw new ApiError(data?.detail || `Erreur ${response.status}`, response.status, data);
  }
  return data;
}

/**
 * Récupère les tableaux de l'utilisateur. GET /boards avec Bearer.
 * Sert à alimenter le choix du tableau dans la popup. Même gestion du 401 que
 * createApplication (purge de la session → la popup rebascule vers l'état
 * « non connecté »).
 */
export async function getBoards() {
  const token = await getToken();
  if (!token) {
    throw new ApiError("Session expirée, reconnectez-vous.", 401);
  }

  const response = await fetch(`${API_BASE_URL}/boards`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401) {
      await clearSession();
    }
    throw new ApiError(data?.detail || `Erreur ${response.status}`, response.status, data);
  }
  return data;
}

/**
 * Crée une candidature. POST /applications avec Authorization: Bearer <token>.
 * Sur 401 (token expiré/invalide), purge la session stockée — la popup rebascule
 * alors vers l'état « non connecté ».
 */
export async function createApplication(offer) {
  const token = await getToken();
  if (!token) {
    throw new ApiError("Session expirée, reconnectez-vous.", 401);
  }

  const response = await fetch(`${API_BASE_URL}/applications`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(offer),
  });

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401) {
      await clearSession();
    }
    throw new ApiError(data?.detail || `Erreur ${response.status}`, response.status, data);
  }
  return data;
}
