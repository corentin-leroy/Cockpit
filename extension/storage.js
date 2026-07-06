// Gestion du token JWT de l'extension — SEUL endroit qui touche chrome.storage
// pour le token (équivalent de auth/token.js côté front, mais on stocke dans
// chrome.storage.local et JAMAIS dans le localStorage d'un site visité).
//
// chrome.storage.local est propre à l'extension, persistant entre les sessions,
// et accessible aussi bien depuis la popup que depuis le service worker — c'est
// ce qui permet à ces deux contextes de partager le même token.

const TOKEN_KEY = "cockpit_token";

/** Lit le token stocké, ou null s'il n'y en a pas. */
export async function getToken() {
  const result = await chrome.storage.local.get(TOKEN_KEY);
  return result[TOKEN_KEY] ?? null;
}

/** Enregistre le token (après un login réussi). */
export async function setToken(token) {
  await chrome.storage.local.set({ [TOKEN_KEY]: token });
}

/** Efface le token (déconnexion, ou purge sur 401). */
export async function clearToken() {
  await chrome.storage.local.remove(TOKEN_KEY);
}
