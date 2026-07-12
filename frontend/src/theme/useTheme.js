// Hook d'accès au contexte de thème.

import { useContext } from 'react'

import { ThemeContext } from './context.js'

/** Renvoie { theme, toggleTheme }. Garde-fou si utilisé hors ThemeProvider. */
export function useTheme() {
  const context = useContext(ThemeContext)
  if (context === null) {
    throw new Error('useTheme doit être utilisé à l’intérieur d’un <ThemeProvider>')
  }
  return context
}
