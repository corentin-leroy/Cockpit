// Barre de navigation minimale des pages protégées. Pour l'instant : le titre
// de l'app et un bouton de déconnexion.

import { useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/useAuth.js'

const navStyle = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '12px 24px',
  borderBottom: '1px solid var(--border)',
}

const buttonStyle = {
  padding: '6px 12px',
  borderRadius: 8,
  border: '1px solid var(--border)',
  background: 'transparent',
  color: 'inherit',
  font: 'inherit',
  cursor: 'pointer',
}

export default function Navbar() {
  const { logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <nav style={navStyle}>
      <strong style={{ color: 'var(--text-h)' }}>Alternance Cockpit</strong>
      <button type="button" style={buttonStyle} onClick={handleLogout}>
        Déconnexion
      </button>
    </nav>
  )
}
