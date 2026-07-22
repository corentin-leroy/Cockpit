// Barre de navigation minimale des pages protégées : le titre de l'app, l'accès
// au compte, la bascule de thème et un bouton de déconnexion.

import { Link, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/useAuth.js'
import ThemeToggle from './ThemeToggle.jsx'

export default function Navbar() {
  const { logout } = useAuth()
  const navigate = useNavigate()
  const { pathname } = useLocation()

  const onAccountPage = pathname === '/account'

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <nav className="navbar">
      {/* La marque ramène au kanban : sur la page de compte, c'est le chemin de
          retour attendu. Un <Link> plutôt qu'un bouton — c'est une navigation,
          donc ouvrable dans un nouvel onglet et annonçable comme lien. */}
      <Link to="/" className="navbar__brand">
        Cockpit
      </Link>

      <div className="navbar__actions">
        {/* Masqué quand on y est déjà : un lien vers la page courante n'apporte
            rien et brouille le repérage. */}
        {!onAccountPage && (
          <Link to="/account" className="btn btn--ghost btn--sm">
            Mon compte
          </Link>
        )}
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
