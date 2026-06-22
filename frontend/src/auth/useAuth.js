// Hook d'accès au contexte d'authentification.

import { useContext } from 'react'

import { AuthContext } from './context.js'

/** Renvoie { isAuthenticated, login, logout }. Garde-fou si hors AuthProvider. */
export function useAuth() {
  const context = useContext(AuthContext)
  if (context === null) {
    throw new Error('useAuth doit être utilisé à l’intérieur d’un <AuthProvider>')
  }
  return context
}
