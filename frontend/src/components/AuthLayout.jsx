// Mise en page commune des cinq écrans d'authentification (connexion,
// inscription, mot de passe oublié, réinitialisation, vérification d'email) :
// barre du haut, carte centrée, pied de page.
//
// Barre : les classes de la navbar de l'application (.navbar, .navbar__brand),
// réutilisées telles quelles, pour une marque identique partout. Elle ne
// contient que la marque et la bascule de thème : ni sidebar, ni liens de
// l'application, qui n'ont pas de sens ici.
//
// Cible de la marque CALCULÉE : la landing (/) pour un visiteur, le kanban
// (/app) pour un connecté. Connexion et inscription ne reçoivent que des
// visiteurs (GuestRoute) ; les trois autres pages, atteintes depuis un lien
// email, peuvent recevoir un connecté. La landing lui est fermée (GuestRoute) :
// le lien mène directement au tableau, sans passer par la redirection.
//
// Pied de page : la politique de confidentialité, accessible depuis chacun de
// ces écrans (même traitement neutre que le pied de page de la landing).

import { Link } from 'react-router-dom'

import { useAuth } from '../auth/useAuth.js'
import { PRIVACY_URL } from '../constants/links.js'
import BrandLogo from './BrandLogo.jsx'
import ThemeToggle from './ThemeToggle.jsx'

/**
 * @param {Object} props
 * @param {React.ReactNode} props.children  contenu de la carte.
 */
export default function AuthLayout({ children }) {
  const { isAuthenticated } = useAuth()

  return (
    <>
      <nav className="navbar">
        <div className="navbar__start">
          <Link to={isAuthenticated ? '/app' : '/'} className="navbar__brand">
            <BrandLogo />
            Cockpit
          </Link>
        </div>
        <div className="navbar__actions">
          <ThemeToggle />
        </div>
      </nav>

      <main className="auth-page">
        <div className="auth-card">{children}</div>
      </main>

      <footer className="auth-footer">
        <a href={PRIVACY_URL} target="_blank" rel="noopener noreferrer">
          Politique de confidentialité
        </a>
      </footer>
    </>
  )
}
