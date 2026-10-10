// Couche d'accès à l'API backend, partagée par la popup et le service worker.
//
// Trois appels :
// - login()             : utilisé par la popup (contexte extension, non soumis
//                         à la CSP d'un site) ;
// - getBoards() et
//   createApplication() : utilisés par le service worker, qui ajoute le Bearer
//                         et purge le token sur 401 (même logique que le front).
//
// L'URL de l'API (API_BASE_URL) est figée dans config.js : voir ce fichier pour
// son alignement obligatoire avec host_permissions et le développement local.

import { API_BASE_URL } from "./config.js";
import { getToken, clearToken } from "./storage.js";

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
 * Connexion. POST /auth/login → { access_token, token_type }.
 * Ne stocke PAS le token : le stockage est décidé par la popup (via storage.js),
 * qui bascule ensuite vers l'état connecté.
 */
export async function login(email, password) {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    // Le backend renvoie `detail` déjà en français, directement affichable —
    // TOUJOURS une chaîne, y compris sur un 422 (401 ici : « Email ou mot de
    // passe incorrect. »). Fallback générique si le corps est illisible.
    throw new ApiError(data?.detail || `Erreur ${response.status}`, response.status, data);
  }
  return data;
}

/**
 * Récupère les tableaux de l'utilisateur. GET /boards avec Bearer.
 * Sert à alimenter le choix du tableau dans la popup. Même gestion du 401 que
 * createApplication (purge du token → la popup rebascule vers la connexion).
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
      await clearToken();
    }
    throw new ApiError(data?.detail || `Erreur ${response.status}`, response.status, data);
  }
  return data;
}

/**
 * Crée une candidature. POST /applications avec Authorization: Bearer <token>.
 * Sur 401 (token expiré/invalide), purge le token stocké — la popup rebascule
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
      await clearToken();
    }
    throw new ApiError(data?.detail || `Erreur ${response.status}`, response.status, data);
  }
  return data;
}
