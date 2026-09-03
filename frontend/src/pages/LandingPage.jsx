// Landing page publique, servie sur "/". Présente le produit avant
// inscription — accessible sans être connecté (garde symétrique : c'est
// GuestRoute, dans routes.jsx, qui renvoie un utilisateur déjà authentifié
// vers /app plutôt que de le laisser voir cette page).
//
// Un seul h1 sur la page (le nom du produit, dans l'en-tête) : la baseline et
// le sous-titre sont des paragraphes stylés en grand, pas des titres — la
// hiérarchie de titres reste donc h1 (page) → h2 (section fonctionnalités) →
// h3 (une fonctionnalité).

import { Link } from 'react-router-dom'

import ThemeToggle from '../components/ThemeToggle.jsx'

const FEATURES = [
  {
    icon: '🗂',
    title: 'Suivi kanban à six statuts',
    text: 'Repérée, postulée, relancée, entretien, refusée, acceptée : chaque candidature avance par glisser-déposer, sans ressaisie.',
  },
  {
    icon: '📋',
    title: 'Tableaux multiples',
    text: 'Séparez vos recherches — par type de contrat, par secteur, par période — dans autant de tableaux que nécessaire.',
  },
  {
    icon: '🧩',
    title: 'Extension de capture d’offres',
    text: 'Ajoutez une offre à votre tableau depuis n’importe quel site d’emploi, sans ressaisir l’intitulé, l’entreprise ou le lien.',
  },
  {
    icon: '🌓',
    title: 'Thèmes clair et sombre',
    text: 'L’interface s’adapte à votre préférence système, ou à votre choix explicite, mémorisé d’une visite à l’autre.',
  },
]

export default function LandingPage() {
  return (
    <div className="landing-page">
      <header className="landing-topbar">
        <span className="landing-topbar__brand">Cockpit</span>
        <ThemeToggle />
      </header>

      <section className="landing-hero">
        <h1 className="landing-hero__title">Cockpit</h1>
        <p className="landing-hero__tagline">
          Le poste de pilotage de votre recherche d’emploi
        </p>
        <p className="landing-hero__subtitle">
          Une recherche d’emploi éclatée entre plusieurs sites, dont on perd le
          fil : Cockpit centralise vos candidatures pour que vous gardiez la
          vue d’ensemble.
        </p>
        <div className="landing-hero__actions">
          <Link to="/register" className="btn btn--primary">
            Créer un compte
          </Link>
          <Link to="/login" className="btn btn--secondary">
            Se connecter
          </Link>
        </div>
      </section>

      <section className="landing-features" aria-labelledby="landing-features-title">
        <h2 id="landing-features-title" className="landing-features__title">
          Fonctionnalités principales
        </h2>
        <div className="landing-features__grid">
          {FEATURES.map((feature) => (
            <article className="feature-card" key={feature.title}>
              <span className="feature-card__icon" aria-hidden="true">
                {feature.icon}
              </span>
              <h3 className="feature-card__title">{feature.title}</h3>
              <p className="feature-card__text">{feature.text}</p>
            </article>
          ))}
        </div>
      </section>

      <footer className="landing-footer">
        <a
          href="https://corentin-leroy.github.io/Cockpit/privacy"
          target="_blank"
          rel="noopener noreferrer"
        >
          Politique de confidentialité
        </a>
      </footer>
    </div>
  )
}
