// Provider du contexte d'authentification : détient l'état de session et
// l'expose à toute l'app via AuthContext.
//
// Ce fichier ne connaît ni le stockage (il passe par le module token) ni le
// transport HTTP (il passe par api/auth). Il ne gère que l'ÉTAT React.

import { useState } from 'react'

import { login as apiLogin } from '../api/auth.js'
import { AuthContext } from './context.js'
import { getToken, removeToken, setToken } from './token.js'

export function AuthProvider({ children }) {
  // Initialisation synchrone depuis le token présent au démarrage : si un token
  // est déjà stocké (rechargement de page, onglet rouvert), on démarre connecté.
  // Initializer paresseux (fonction) pour ne lire le stockage qu'une seule fois.
  const [isAuthenticated, setIsAuthenticated] = useState(() => Boolean(getToken()))

  async function login(email, password) {
    const data = await apiLogin(email, password)
    setToken(data.access_token)
    setIsAuthenticated(true)
    return data
  }

  function logout() {
    removeToken()
    setIsAuthenticated(false)
  }

  const value = { isAuthenticated, login, logout }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
