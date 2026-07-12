// Résolution et application du thème sur le document.
//
// Le thème effectif est décidé dans cet ordre :
//   1. le choix mémorisé par l'utilisateur (localStorage) ;
//   2. à défaut, la préférence système (prefers-color-scheme).
//
// Il est appliqué via l'attribut data-theme sur <html> : c'est le seul point de
// contact entre le JS et l'apparence. Tout le reste est piloté par les variables
// CSS de styles/tokens.css.

import { DARK, LIGHT, getStoredTheme } from './storage.js'

/** Thème préféré au niveau du système d'exploitation / navigateur. */
export function getSystemTheme() {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? DARK : LIGHT
}

/** Thème à appliquer au chargement : choix mémorisé, sinon préférence système. */
export function resolveInitialTheme() {
  return getStoredTheme() ?? getSystemTheme()
}

/** Pose l'attribut data-theme sur <html>. */
export function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme)
}

/**
 * Applique le thème AVANT le premier rendu de React (appelé depuis main.jsx),
 * pour éviter un flash du mauvais thème quand le choix mémorisé diffère de la
 * préférence système.
 */
export function initTheme() {
  applyTheme(resolveInitialTheme())
}
