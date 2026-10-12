// Transmission de la session du site à l'extension Chrome : SEUL module du front
// qui parle à l'extension, appelé uniquement par le contexte d'auth (AuthContext).
//
// Canal à sens unique (cf. dev-docs/extension-session-sharing.md) : le site pousse
// `session:set` (jeton que GET /auth/me vient d'accepter) et `session:clear`
// (déconnexion explicite ou 401). L'extension ne renvoie que `{ok}`, que le site
// ignore : rien ici n'attend sa réponse.
//
// Échec TOUJOURS silencieux, sans erreur ni message à l'utilisateur : extension
// absente, désactivée, ancienne version (la 1.1.0 n'écoute pas le site) ou autre
// navigateur. C'est ce qui permet de déployer le site avant l'extension 1.2.0.

import { EXTENSION_STORE_ID } from '../constants/links.js'

// ID du Store par défaut. VITE_EXTENSION_ID ne sert qu'en dev (frontend/.env.local),
// pour viser l'extension non empaquetée ; jamais posée en production.
const EXTENSION_ID = import.meta.env.VITE_EXTENSION_ID || EXTENSION_STORE_ID

function postToExtension(message) {
  // `chrome.runtime` n'existe sur la page que si une extension installée accepte
  // les messages de ce site (externally_connectable) : sans elle, rien à faire.
  if (typeof window.chrome?.runtime?.sendMessage !== 'function') return
  try {
    window.chrome.runtime.sendMessage(EXTENSION_ID, message, () => {
      // Lecture obligatoire : sans elle, Chrome journalise « Unchecked
      // runtime.lastError » quand l'extension visée est absente.
      void window.chrome.runtime.lastError
    })
  } catch {
    // ID mal formé (VITE_EXTENSION_ID erronée) : sendMessage lève immédiatement.
  }
}

/** Transmet à l'extension un jeton que le backend vient d'accepter. */
export function sendSessionToExtension(token) {
  if (!token) return
  postToExtension({ type: 'session:set', token })
}

/** Demande à l'extension d'effacer sa session (déconnexion ou jeton refusé). */
export function clearExtensionSession() {
  postToExtension({ type: 'session:clear' })
}
