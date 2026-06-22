import { Routes, Route } from 'react-router-dom'

import GuestRoute from '../components/GuestRoute.jsx'
import ProtectedRoute from '../components/ProtectedRoute.jsx'
import BoardPage from '../pages/BoardPage.jsx'
import LoginPage from '../pages/LoginPage.jsx'
import RegisterPage from '../pages/RegisterPage.jsx'

// Routing de l'application :
// - / (kanban) est protégé : accessible uniquement authentifié.
// - /login et /register sont réservés aux visiteurs : un utilisateur déjà
//   connecté y est renvoyé vers le kanban.
export default function AppRoutes() {
  return (
    <Routes>
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <BoardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/login"
        element={
          <GuestRoute>
            <LoginPage />
          </GuestRoute>
        }
      />
      <Route
        path="/register"
        element={
          <GuestRoute>
            <RegisterPage />
          </GuestRoute>
        }
      />
    </Routes>
  )
}
