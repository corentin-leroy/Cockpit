// Hook d'accès au contexte d'authentification.

import { useContext } from 'react'

import { AuthContext } from './context.js'

/**
 * Renvoie { isAuthenticated, user, login, logout, refreshUser }.
 * `user` peut être null même connecté (chargement en cours, ou /auth/me en
 * échec) : toujours tester sa présence avant de lire un champ.
 * Garde-fou si hors AuthProvider.
 */
export function useAuth() {
  const context = useContext(AuthContext)
  if (context === null) {
    throw new Error('useAuth doit être utilisé à l’intérieur d’un <AuthProvider>')
  }
  return context
}
