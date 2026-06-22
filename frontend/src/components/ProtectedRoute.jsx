// Garde de route : réserve son contenu aux utilisateurs authentifiés.
// Sinon, redirige vers /login (`replace` pour ne pas empiler l'historique).

import { Navigate } from 'react-router-dom'

import { useAuth } from '../auth/useAuth.js'

export default function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuth()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  return children
}
