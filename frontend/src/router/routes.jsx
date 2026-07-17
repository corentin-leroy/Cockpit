import { Routes, Route } from 'react-router-dom'

import GuestRoute from '../components/GuestRoute.jsx'
import ProtectedRoute from '../components/ProtectedRoute.jsx'
import { BoardsProvider } from '../boards/BoardsProvider.jsx'
import BoardPage from '../pages/BoardPage.jsx'
import ForgotPasswordPage from '../pages/ForgotPasswordPage.jsx'
import LoginPage from '../pages/LoginPage.jsx'
import RegisterPage from '../pages/RegisterPage.jsx'
import ResetPasswordPage from '../pages/ResetPasswordPage.jsx'
import VerifyEmailPage from '../pages/VerifyEmailPage.jsx'

// Routing de l'application, en trois familles :
// - / (kanban) est protégé : accessible uniquement authentifié.
// - /login et /register sont réservés aux visiteurs : un utilisateur déjà
//   connecté y est renvoyé vers le kanban.
// - /forgot-password, /reset-password et /verify-email sont PUBLIQUES, sans
//   aucune garde. Elles sont atteintes depuis un lien reçu par email, et l'état
//   de session de celui qui clique est imprévisible : un utilisateur connecté
//   qui ouvre son lien de vérification doit voir la page de vérification, pas
//   être redirigé vers l'app par GuestRoute ; un utilisateur déconnecté doit
//   pouvoir réinitialiser son mot de passe sans être renvoyé au login par
//   ProtectedRoute. C'est le token de l'URL qui fait autorité, pas la session.
export default function AppRoutes() {
  return (
    <Routes>
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <BoardsProvider>
              <BoardPage />
            </BoardsProvider>
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
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/verify-email" element={<VerifyEmailPage />} />
    </Routes>
  )
}
