// Persistance du thème choisi : unique point d'accès au stockage pour cette clé
// (même principe que auth/token.js pour le JWT). Le reste du code passe par ces
// fonctions et n'appelle jamais localStorage directement.
//
// Le stockage peut être indisponible (navigation privée, données de site
// bloquées) et LEVER à la lecture comme à l'écriture. La lecture a lieu dans
// initTheme(), avant le premier rendu : sans garde, l'application ne
// s'afficherait pas du tout. En cas d'échec : lecture = « jamais choisi » (on
// suit alors la préférence système), écriture ignorée.

export const THEME_KEY = 'cockpit_theme'

export const LIGHT = 'light'
export const DARK = 'dark'

/**
 * Renvoie le thème mémorisé ('light' | 'dark'), ou null si l'utilisateur n'a
 * jamais choisi (on suivra alors la préférence système) ou si le stockage est
 * indisponible.
 */
export function getStoredTheme() {
  try {
    const stored = localStorage.getItem(THEME_KEY)
    return stored === LIGHT || stored === DARK ? stored : null
  } catch {
    return null
  }
}

/** Mémorise le choix de l'utilisateur ; ignoré si le stockage est indisponible. */
export function setStoredTheme(theme) {
  try {
    localStorage.setItem(THEME_KEY, theme)
  } catch {
    // Le choix vaut pour la session en cours, mais ne sera pas retenu.
  }
}
