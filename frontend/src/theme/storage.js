// Persistance du thème choisi : unique point d'accès au stockage pour cette clé
// (même principe que auth/token.js pour le JWT). Le reste du code passe par ces
// fonctions et n'appelle jamais localStorage directement.

export const THEME_KEY = 'cockpit_theme'

export const LIGHT = 'light'
export const DARK = 'dark'

/**
 * Renvoie le thème mémorisé ('light' | 'dark'), ou null si l'utilisateur n'a
 * jamais choisi (on suivra alors la préférence système).
 */
export function getStoredTheme() {
  const stored = localStorage.getItem(THEME_KEY)
  return stored === LIGHT || stored === DARK ? stored : null
}

/** Mémorise le choix de l'utilisateur. */
export function setStoredTheme(theme) {
  localStorage.setItem(THEME_KEY, theme)
}
