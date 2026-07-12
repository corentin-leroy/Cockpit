// Fournit le thème courant ('light' | 'dark') et la bascule associée.
//
// Au montage, l'état part du thème déjà résolu par initTheme() (choix mémorisé,
// sinon préférence système). Toute bascule : met à jour l'état, applique
// l'attribut data-theme sur <html>, et mémorise le choix.
//
// Tant que l'utilisateur n'a rien choisi, on continue de SUIVRE la préférence
// système en direct (l'OS passe en sombre le soir → l'app suit). Dès qu'il
// bascule manuellement, son choix prime et cet écouteur ne s'applique plus.

import { useCallback, useEffect, useMemo, useState } from 'react'

import { ThemeContext } from './context.js'
import { DARK, LIGHT, getStoredTheme, setStoredTheme } from './storage.js'
import { applyTheme, getSystemTheme, resolveInitialTheme } from './theme.js'

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(resolveInitialTheme)

  // Synchronise le DOM avec l'état (couvre aussi le rendu initial).
  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)')

    function handleSystemChange() {
      // Un choix explicite mémorisé l'emporte toujours sur le système.
      if (getStoredTheme() === null) setTheme(getSystemTheme())
    }

    media.addEventListener('change', handleSystemChange)
    return () => media.removeEventListener('change', handleSystemChange)
  }, [])

  const toggleTheme = useCallback(() => {
    setTheme((current) => {
      const next = current === DARK ? LIGHT : DARK
      setStoredTheme(next)
      return next
    })
  }, [])

  const value = useMemo(() => ({ theme, toggleTheme }), [theme, toggleTheme])

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}
