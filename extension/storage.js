// Session de l'extension (jeton JWT et email du compte) — SEUL endroit qui touche
// chrome.storage (équivalent de auth/token.js côté front, mais on stocke dans
// chrome.storage.local et JAMAIS dans le localStorage d'un site visité).
//
// chrome.storage.local est propre à l'extension, persistant entre les sessions,
// et accessible aussi bien depuis la popup que depuis le service worker — c'est
// ce qui permet à ces deux contextes de partager la même session.
//
// La session est reçue du site (session:set, background.js) : jeton et email sont
// écrits et effacés ENSEMBLE, en un seul appel. L'email sert à l'affichage
// « Connecté en tant que … » de la popup. Il peut manquer (jeton stocké par la
// popup de la 1.1.0, avant l'email) : la popup le tolère.

const TOKEN_KEY = "cockpit_token";
const EMAIL_KEY = "cockpit_email";
// Dernier tableau choisi dans l'extension (équivalent de boards/lastBoard.js côté
// front, même clé « cockpit_last_board »). chrome.storage préserve les types JSON :
// on y stocke/relit un NOMBRE, pas une chaîne comme localStorage côté front.
const LAST_BOARD_KEY = "cockpit_last_board";

/** Lit le token stocké, ou null s'il n'y en a pas. */
export async function getToken() {
  const result = await chrome.storage.local.get(TOKEN_KEY);
  return result[TOKEN_KEY] ?? null;
}

/** Lit l'email du compte connecté, ou null s'il n'y en a pas. */
export async function getEmail() {
  const result = await chrome.storage.local.get(EMAIL_KEY);
  return result[EMAIL_KEY] ?? null;
}

/** Enregistre la session (jeton validé par /auth/me et son email), en un appel. */
export async function setSession(token, email) {
  await chrome.storage.local.set({ [TOKEN_KEY]: token, [EMAIL_KEY]: email });
}

/** Efface la session (session:clear du site, ou purge sur 401), en un appel. */
export async function clearSession() {
  await chrome.storage.local.remove([TOKEN_KEY, EMAIL_KEY]);
}

/** Lit l'id du dernier tableau choisi, ou null. */
export async function getLastBoardId() {
  const result = await chrome.storage.local.get(LAST_BOARD_KEY);
  return result[LAST_BOARD_KEY] ?? null;
}

/** Mémorise le tableau choisi pour le pré-sélectionner au prochain ajout. */
export async function setLastBoardId(id) {
  await chrome.storage.local.set({ [LAST_BOARD_KEY]: id });
}
