// Barre de navigation minimale des pages protégées : le titre de l'app, l'accès
// au compte, la bascule de thème et un bouton de déconnexion.

import { Link, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/useAuth.js'
import { useSidebar } from '../preferences/useSidebar.js'
import ThemeToggle from './ThemeToggle.jsx'

/**
 * @param {Object} props
 * @param {boolean} [props.withSidebarToggle]  affiche le bouton de repli de la
 *   sidebar : seulement sur les pages qui en ont une (kanban, archives), pas sur
 *   « Mon compte ».
 */
export default function Navbar({ withSidebarToggle = false }) {
  const { logout } = useAuth()
  const { collapsed, toggleSidebar } = useSidebar()
  const navigate = useNavigate()
  const { pathname } = useLocation()

  const onAccountPage = pathname === '/account'
  const onArchivesPage = pathname === '/archives'

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  // Classe d'un lien de nav : même traitement pour Archives et Mon compte,
  // qu'il s'agisse de la page courante ou non — harmonisé sur demande, pas de
  // cas particulier entre les deux. `aria-current="page"` porte le sens pour
  // un lecteur d'écran, le style (texte pleine intensité + semi-gras) le porte
  // visuellement, jamais la couleur seule (DESIGN.md) : même principe que
  // .board-row--active dans la sidebar du kanban.
  function navLinkClass(active) {
    return `btn btn--ghost btn--sm${active ? ' navbar__link--active' : ''}`
  }

  return (
    <nav className="navbar">
      {/* La marque ramène au kanban : sur la page de compte, c'est le chemin de
          retour attendu. Un <Link> plutôt qu'un bouton — c'est une navigation,
          donc ouvrable dans un nouvel onglet et annonçable comme lien. */}
      <div className="navbar__start">
        {/* Dans la navbar et NON dans la sidebar : sidebar repliée, elle
            disparaît entièrement, le bouton doit rester atteignable. Le glyphe
            est constant ; c'est le libellé (et aria-expanded) qui porte l'état,
            jamais le pictogramme ni la couleur seuls. */}
        {withSidebarToggle && (
          <button
            type="button"
            className="btn btn--ghost btn--icon sidebar-toggle"
            onClick={toggleSidebar}
            aria-expanded={!collapsed}
            aria-controls="board-sidebar"
            aria-label={collapsed ? 'Afficher les tableaux' : 'Replier les tableaux'}
            title={collapsed ? 'Afficher les tableaux' : 'Replier les tableaux'}
          >
            <span aria-hidden="true">☰</span>
          </button>
        )}

        <Link to="/app" className="navbar__brand">
          Cockpit
        </Link>
      </div>

      <div className="navbar__actions">
        {/* TOUJOURS visibles, y compris sur leur propre page : c'est la page
            courante qui se marque comme active, elle ne disparaît plus. */}
        <Link
          to="/archives"
          className={navLinkClass(onArchivesPage)}
          aria-current={onArchivesPage ? 'page' : undefined}
        >
          Archives
        </Link>
        <Link
          to="/account"
          className={navLinkClass(onAccountPage)}
          aria-current={onAccountPage ? 'page' : undefined}
        >
          Mon compte
        </Link>
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
