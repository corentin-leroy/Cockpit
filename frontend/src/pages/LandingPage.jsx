// Landing page publique, servie sur "/". Accessible sans être connecté (garde symétrique : c'est GuestRoute, dans
// routes.jsx, qui renvoie un utilisateur déjà authentifié vers /app).
//
// Hiérarchie de titres : UN seul h1 (le slogan, qui porte le message de la
// page ; le nom du produit est dans l'en-tête), puis un h2 par section et un h3
// par élément. Aucun titre n'est un simple paragraphe stylé.
//
// Le hero montre le VRAI kanban : KanbanColumn et ApplicationCard, les mêmes
// composants que l'application, nourris de candidatures d'exemple codées en dur.
// Un DragDropProvider les rend déplaçables à n'importe quel rang, dans leur colonne
// comme vers une autre, à titre de démonstration : même logique que le kanban
// (kanban/useKanbanDrag.js), mais l'état vit dans un useState, aucun appel à l'API,
// aucune persistance (un rechargement remet les cartes à leur place d'origine). Pas
// de zone d'archivage ni de sidebar ici.
// Aucun `onEdit` n'est fourni : ApplicationCard n'ouvre aucune modale.
//
// Les styles vivent dans landing.css (préfixe `landing-`), importé ci-dessous.

import { useEffect, useRef, useState } from 'react'
import { DragDropProvider } from '@dnd-kit/react'
import { Link } from 'react-router-dom'

import KanbanColumn from '../components/KanbanColumn.jsx'
import ThemeToggle from '../components/ThemeToggle.jsx'
import { APPLICATION_STATUSES } from '../constants/applicationStatuses.js'
import { useKanbanDrag } from '../kanban/useKanbanDrag.js'
import '../styles/landing.css'

const EXTENSION_URL =
  'https://chromewebstore.google.com/detail/cockpit/cabhkfjohddpeigkoijhlidndfkgbpno'
const PRIVACY_URL = 'https://corentin-leroy.github.io/Cockpit/privacy'
const GITHUB_URL = 'https://github.com/corentin-leroy'

// Date de création relative à AUJOURD'HUI : l'ancienneté affichée sur les cartes
// (« il y a 6 j ») reste plausible à chaque visite au lieu de vieillir. Même
// format que le backend : ISO NAÏF en UTC, sans « Z » (cf. utils/dates.js).
const DAY_MS = 86_400_000
function daysAgo(days) {
  return new Date(Date.now() - days * DAY_MS).toISOString().replace('Z', '')
}

// Candidatures d'exemple : entreprises fictives, les quatre types de contrat
// mélangés (c'est ce qui dit « tous les contrats » sans slogan).
const DEMO_APPLICATIONS = [
  { id: 1, status: 'saved', title: 'Stage assistant marketing', company: 'Maison Aubrac', location: 'Nantes', created_at: daysAgo(0) },
  { id: 2, status: 'saved', title: 'Alternance développeur web', company: 'Atelier Verdier', location: 'Lyon', created_at: daysAgo(1) },
  { id: 3, status: 'saved', title: 'CDD technicien de laboratoire', company: 'Institut Valmont', location: 'Toulouse', created_at: daysAgo(2) },
  { id: 4, status: 'applied', title: 'CDI chargé de projet digital', company: 'Studio Pavillon', location: 'Paris', created_at: daysAgo(6) },
  { id: 5, status: 'applied', title: 'Alternance assistant RH', company: 'Groupe Lanternier', location: 'Rennes', created_at: daysAgo(9) },
  { id: 6, status: 'followed_up', title: 'Stage data analyst', company: 'Cabinet Orsay', location: 'Lille', created_at: daysAgo(14) },
  { id: 7, status: 'interview', title: 'CDI comptable', company: 'Fonderie Delmas', location: 'Bordeaux', created_at: daysAgo(18) },
  { id: 8, status: 'interview', title: 'Alternance chef de projet', company: 'Atelier Sorel', location: 'Grenoble', created_at: daysAgo(21) },
  { id: 9, status: 'accepted', title: 'CDD animateur', company: 'Association Rivages', location: 'Strasbourg', created_at: daysAgo(30) },
]

const FEATURES = [
  {
    title: 'Chaque candidature à sa place',
    text: 'Cinq colonnes, de Repérée à Acceptée. Vous faites avancer une candidature en la glissant d’une colonne à l’autre, et chaque carte indique depuis combien de jours elle est dans votre tableau.',
  },
  {
    title: 'Un tableau par recherche',
    text: 'Séparez vos recherches par type de contrat, par secteur ou par période. Chaque tableau garde ses propres candidatures.',
  },
  {
    title: 'Archivez sans rien perdre',
    text: 'Une candidature classée quitte le tableau mais reste consultable et cherchable dans vos archives, avec le statut qu’elle avait.',
  },
]

const EXTENSION_STEPS = [
  'Ouvrez une offre sur n’importe quel site d’emploi, puis cliquez sur l’extension.',
  'L’intitulé, l’entreprise, le lieu et le lien sont pré-remplis : corrigez-les si besoin.',
  'Choisissez le tableau et ajoutez. La candidature arrive dans la colonne Repérée.',
]

const TRUST_POINTS = [
  {
    title: 'Aucune collecte automatique',
    text: 'L’extension ne lit que la page de l’offre que vous choisissez d’ajouter, au moment où vous l’ouvrez. Rien n’est envoyé à Cockpit avant que vous validiez le formulaire.',
  },
  {
    title: 'Aucun mot de passe de vos sites d’emploi',
    text: 'Cockpit ne vous en demande aucun et n’en stocke aucun. Vous ne saisissez que votre mot de passe Cockpit.',
  },
  {
    title: 'Vos données vous appartiennent',
    text: 'Depuis la page Mon compte, vous pouvez supprimer votre compte à tout moment : vos tableaux et vos candidatures sont effacés avec lui.',
  },
]

export default function LandingPage() {
  const [applications, setApplications] = useState(DEMO_APPLICATIONS)
  const kanbanRef = useRef(null)

  // Même réordonnancement que BoardPage : la carte se déplace dans l'état pendant
  // le survol. À la fin, rien à enregistrer ; seule une annulation (Échap) la
  // remet à sa place d'origine.
  const kanbanDrag = useKanbanDrag(applications, setApplications)

  function handleDragEnd(event) {
    const drag = kanbanDrag.endDrag()
    if (drag && event.canceled) drag.restore()
  }

  // Cartes HORS de l'ordre de tabulation : le déplacement est une interaction
  // au pointeur (cf. DESIGN.md), neuf arrêts de tabulation sans action utile
  // gêneraient la navigation au clavier. dnd-kit ne pose tabindex="0" que si
  // l'attribut est absent, mais il le fait de façon différée : l'observateur
  // corrige le cas où il passerait après nous (et à chaque nouveau rendu).
  useEffect(() => {
    const root = kanbanRef.current
    if (!root) return undefined

    function removeFromTabOrder() {
      for (const card of root.querySelectorAll('.app-card')) {
        if (card.getAttribute('tabindex') !== '-1') {
          card.setAttribute('tabindex', '-1')
        }
      }
    }

    removeFromTabOrder()
    const observer = new MutationObserver(removeFromTabOrder)
    observer.observe(root, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ['tabindex'],
    })
    return () => observer.disconnect()
  }, [])

  return (
    <div className="landing">
      <header className="landing-topbar">
        <div className="landing-container landing-topbar__inner">
          <span className="landing-topbar__brand">Cockpit</span>
          <div className="landing-topbar__actions">
            <Link to="/login" className="btn btn--ghost btn--sm">
              Se connecter
            </Link>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main>
        <section className="landing-hero">
          <div className="landing-container landing-hero__intro">
            <h1 className="landing-hero__title">
              Le poste de pilotage de votre recherche d’emploi
            </h1>
            <p className="landing-hero__lead">
              Alternance, CDI, CDD ou stage : Cockpit rassemble toutes vos
              candidatures dans un tableau que vous faites avancer, de l’offre
              repérée à la réponse reçue.
            </p>
            <div className="landing-actions">
              <Link to="/register" className="btn btn--primary">
                Créer un compte
              </Link>
            </div>
          </div>

          <div className="landing-container">
            <figure className="landing-board">
              {/* Fenêtre étroite : le conteneur défile horizontalement et reste
                  focusable pour que le clavier puisse le faire défiler. */}
              <div
                className="landing-board__scroll"
                tabIndex={0}
                role="region"
                aria-label="Tableau d’exemple, défilement horizontal"
              >
                <DragDropProvider
                  onDragStart={kanbanDrag.onDragStart}
                  onDragOver={kanbanDrag.onDragOver}
                  onDragEnd={handleDragEnd}
                >
                  <div
                    ref={kanbanRef}
                    className="kanban landing-board__kanban"
                  >
                    {APPLICATION_STATUSES.map(({ key, label }) => (
                      <KanbanColumn
                        key={key}
                        statusKey={key}
                        label={label}
                        applications={applications.filter(
                          (application) => application.status === key,
                        )}
                      />
                    ))}
                  </div>
                </DragDropProvider>
              </div>
              <figcaption className="landing-board__caption">
                Essayez : glissez une carte d’une colonne à l’autre. Ces
                candidatures sont fictives, rien n’est enregistré et un
                rechargement remet tout en place.
              </figcaption>
            </figure>
          </div>
        </section>

        <section className="landing-section" aria-labelledby="landing-features-title">
          <div className="landing-container">
            <h2 id="landing-features-title" className="landing-section__title">
              Gardez la vue d’ensemble
            </h2>
            <div className="landing-features">
              {FEATURES.map((feature) => (
                <div className="landing-feature" key={feature.title}>
                  <h3>{feature.title}</h3>
                  <p>{feature.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="landing-section" aria-labelledby="landing-extension-title">
          <div className="landing-container">
            <div className="landing-extension">
              <div className="landing-extension__intro">
                <h2 id="landing-extension-title" className="landing-section__title">
                  Ajoutez une offre depuis le site où vous la trouvez
                </h2>
                <p>
                  L’extension Chrome de Cockpit évite de recopier l’intitulé,
                  l’entreprise et le lien de chaque offre.
                </p>
                <a
                  href={EXTENSION_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn--secondary"
                >
                  Installer l’extension Chrome
                </a>
              </div>
              <ol className="landing-steps">
                {EXTENSION_STEPS.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
            </div>
          </div>
        </section>

        <section
          className="landing-section landing-trust"
          aria-labelledby="landing-trust-title"
        >
          <div className="landing-container">
            <h2 id="landing-trust-title" className="landing-section__title">
              Ce que Cockpit fait de vos données
            </h2>
            <div className="landing-features">
              {TRUST_POINTS.map((point) => (
                <div className="landing-feature" key={point.title}>
                  <h3>{point.title}</h3>
                  <p>{point.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="landing-section landing-closing">
          <div className="landing-container">
            <p className="landing-closing__text">
              Votre prochaine candidature a sa colonne qui l’attend.
            </p>
            <div className="landing-actions">
              <Link to="/register" className="btn btn--primary">
                Créer un compte
              </Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="landing-footer">
        <div className="landing-container landing-footer__inner">
          <a href={PRIVACY_URL} target="_blank" rel="noopener noreferrer">
            Politique de confidentialité
          </a>
          <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer">
            GitHub
          </a>
        </div>
      </footer>
    </div>
  )
}
