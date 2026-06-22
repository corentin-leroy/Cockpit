// Garde symétrique de ProtectedRoute : réserve son contenu aux visiteurs NON
// authentifiés (écrans Login/Register). Un utilisateur déjà connecté qui tente
// d'y accéder est renvoyé vers le kanban.

import { Navigate } from 'react-router-dom'

import { useAuth } from '../auth/useAuth.js'

export default function GuestRoute({ children }) {
  const { isAuthenticated } = useAuth()

  if (isAuthenticated) {
    return <Navigate to="/" replace />
  }
  return children
}
