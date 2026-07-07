// Couche d'accès à l'API backend, partagée par la popup et le service worker.
//
// Deux appels seulement pour l'instant :
// - login()             : utilisé par la popup (contexte extension, non soumis
//                         à la CSP d'un site) ;
// - createApplication() : utilisé par le service worker, qui ajoute le Bearer et
//                         purge le token sur 401 (même logique que le front).

import { getToken, clearToken } from "./storage.js";

// Même base que host_permissions du manifest. En dur pour la V1 (backend local) ;
// une page d'options configurable est notée dans les pistes d'amélioration.
export const API_BASE_URL = "http://127.0.0.1:8000";

/** Erreur d'API porteuse du code HTTP, pour que l'appelant détecte un 401. */
export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
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
    // FastAPI renvoie le motif dans `detail` (401 : « Email ou mot de passe
    // incorrect. »). Fallback générique si le corps est illisible.
    throw new ApiError(data?.detail || `Erreur ${response.status}`, response.status);
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
    throw new ApiError(data?.detail || `Erreur ${response.status}`, response.status);
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
    throw new ApiError(data?.detail || `Erreur ${response.status}`, response.status);
  }
  return data;
}
