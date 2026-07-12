// Barre de navigation minimale des pages protégées : le titre de l'app, la
// bascule de thème et un bouton de déconnexion.

import { useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/useAuth.js'
import ThemeToggle from './ThemeToggle.jsx'

export default function Navbar() {
  const { logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <nav className="navbar">
      <strong className="navbar__brand">Alternance Cockpit</strong>

      <div className="navbar__actions">
        <ThemeToggle />
        <button
          type="button"
          className="btn btn--secondary btn--sm"
          onClick={handleLogout}
        >
          Déconnexion
        </button>
      </div>
    </nav>
  )
}
