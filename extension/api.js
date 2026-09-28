// Couche d'accès à l'API backend, partagée par la popup et le service worker.
//
// Deux appels seulement pour l'instant :
// - login()             : utilisé par la popup (contexte extension, non soumis
//                         à la CSP d'un site) ;
// - createApplication() : utilisé par le service worker, qui ajoute le Bearer et
//                         purge le token sur 401 (même logique que le front).

import { getToken, clearToken } from "./storage.js";

// API de PRODUCTION. Cette valeur doit rester STRICTEMENT alignée sur l'entrée
// host_permissions du manifest : c'est cette permission d'hôte qui exempte la
// popup et le service worker du contrôle CORS. Les deux désynchronisées, les
// appels retombent sous le régime CORS ordinaire (préflight compris) et
// échouent, sans que le code ne signale quoi que ce soit d'anormal.
//
// Pour développer contre un backend local, modifier CES DEUX valeurs sans les
// committer (procédure dans README.md). Volontairement PAS de page d'options :
// une URL d'API configurable par l'utilisateur permettrait de diriger le token
// d'authentification vers un serveur arbitraire.
export const API_BASE_URL = "https://cockpit-production-6afb.up.railway.app";

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
