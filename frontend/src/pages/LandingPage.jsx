// Landing page publique, servie sur "/". Accessible sans être connecté :
// GuestRoute (routes.jsx) renvoie un utilisateur déjà authentifié vers /app.
// Règles de style et écarts au reste de l'application : section « Landing page »
// de DESIGN.md.
//
// Hiérarchie de titres : UN seul h1 (le slogan), puis un h2 par section et un h3
// par élément. La phrase de l'appel final est un h2 : elle en a le poids visuel.
//
// Le hero montre le VRAI kanban : KanbanColumn et ApplicationCard, les mêmes
// composants que l'application, nourris de candidatures d'exemple codées en dur.
// Un DragDropProvider les rend déplaçables à n'importe quel rang (même logique
// que le kanban, kanban/useKanbanDrag.js), l'état vit dans un useState : aucun
// appel à l'API, aucune persistance. Pas de zone d'archivage ni de sidebar, et
// aucun `onEdit` : ApplicationCard n'ouvre aucune modale.
//
// En-tête : balisage PROPRE à cette page (pas components/Navbar.jsx, la navbar de
// l'application, qui n'est pas concernée). Il reste collé en haut pendant le
// défilement, cf. landing.css.
//
// Les styles vivent dans landing.css (classes préfixées `landing-`). Une feuille
// importée par Vite s'applique à toute l'application : ce préfixe ne doit servir
// nulle part ailleurs.

import { useEffect, useLayoutEffect, useRef, useState } from 'react'
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
// reste plausible à chaque visite. Même format que le backend : ISO NAÏF en UTC,
// sans « Z » (cf. utils/dates.js).
const DAY_MS = 86_400_000
function daysAgo(days) {
  return new Date(Date.now() - days * DAY_MS).toISOString().replace('Z', '')
}

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
  const headerRef = useRef(null)
  const heroCtaRef = useRef(null)

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

  // « Créer un compte » de la barre : affiché seulement quand celui du HERO n'est
  // plus visible (doublon sinon), masqué de nouveau quand on remonte jusqu'à lui.
  //
  // Aucun état React : l'effet pose ou retire `data-signup="hidden"` sur l'en-tête
  // et landing.css en tire l'apparence. Un setState ferait réafficher toute la
  // page, kanban compris, à chaque bascule.
  //
  // REPLI SÛR : sans l'attribut, le bouton est VISIBLE. C'est l'état si
  // IntersectionObserver manque, si quoi que ce soit échoue ici, et avant toute
  // détermination : l'inscription n'est jamais inaccessible.
  //
  // useLayoutEffect : le premier calcul a lieu AVANT le premier affichage (en haut
  // de page, le bouton n'apparaît pas pour disparaître aussitôt).
  useLayoutEffect(() => {
    const header = headerRef.current
    const heroCta = heroCtaRef.current
    if (!header || !heroCta || typeof IntersectionObserver === 'undefined') {
      return undefined
    }

    function hideSignup(hidden) {
      if (hidden) header.dataset.signup = 'hidden'
      else delete header.dataset.signup
    }

    // Premier calcul, synchrone, même règle que l'observateur ci-dessous : le
    // bouton du hero est visible s'il dépasse SOUS la barre collée et n'est pas
    // sous le bas de la fenêtre.
    const rect = heroCta.getBoundingClientRect()
    hideSignup(rect.bottom > header.offsetHeight && rect.top < window.innerHeight)

    // Marge haute NÉGATIVE de la hauteur de la barre : un bouton du hero caché
    // derrière elle compte comme sorti de l'écran. Seuil 0 : « sorti » veut dire
    // entièrement invisible.
    let intersectionObserver = null
    let observedHeight = 0
    function observe(barHeight) {
      intersectionObserver?.disconnect()
      observedHeight = barHeight
      intersectionObserver = new IntersectionObserver(
        ([entry]) => {
          hideSignup(entry.isIntersecting)
          // Transitions activées seulement APRÈS le premier verdict : une page
          // chargée déjà défilée (ou dont le navigateur rétablit la position)
          // affiche le bouton directement, sans fondu. La lecture d'offsetHeight
          // force le calcul du style AVANT l'ajout de l'attribut : sans elle, les
          // deux changements seraient calculés ensemble et le fondu jouerait.
          if (!('signupReady' in header.dataset)) {
            void header.offsetHeight
            header.dataset.signupReady = ''
          }
        },
        { rootMargin: `-${barHeight}px 0px 0px 0px` },
      )
      intersectionObserver.observe(heroCta)
    }
    observe(header.offsetHeight)

    // La hauteur de la barre change au seuil de 768px (une tablette qu'on fait
    // pivoter le traverse) : l'observateur est recréé avec la nouvelle marge.
    // Seule la HAUTEUR compte : un changement de largeur seul est ignoré.
    const resizeObserver =
      typeof ResizeObserver === 'undefined'
        ? null
        : new ResizeObserver(() => {
            if (header.offsetHeight !== observedHeight) observe(header.offsetHeight)
          })
    resizeObserver?.observe(header)

    return () => {
      resizeObserver?.disconnect()
      intersectionObserver?.disconnect()
      delete header.dataset.signup
      delete header.dataset.signupReady
    }
  }, [])

  return (
    <div className="landing">
      {/* Barre COLLÉE en haut pendant le défilement (position: sticky, aucun
          JavaScript) : un visiteur convaincu en cours de lecture s'inscrit ou se
          connecte sans remonter. « Créer un compte » y est en style SECONDAIRE :
          en haut de page il est visible en même temps que celui du hero, et
          l'action principale (teal) doit rester unique à l'écran. Il n'apparaît
          d'ailleurs qu'une fois celui du hero sorti de l'écran (effet ci-dessus). */}
      <header ref={headerRef} className="landing-topbar">
        <div className="landing-container landing-topbar__inner">
          {/* Le favicon sert de marque : alt vide, le nom est écrit juste à côté
              (masqué visuellement en fenêtre étroite, toujours lu). */}
          <span className="landing-topbar__brand">
            <img
              src="/favicon.svg"
              alt=""
              width="24"
              height="24"
              className="landing-topbar__logo"
            />
            <span className="landing-topbar__name">Cockpit</span>
          </span>
          <div className="landing-topbar__actions">
            <ThemeToggle />
            <Link to="/login" className="btn btn--ghost btn--sm">
              Se connecter
            </Link>
            <Link
              to="/register"
              className="btn btn--secondary btn--sm landing-topbar__signup"
            >
              Créer un compte
            </Link>
          </div>
        </div>
      </header>

      <main>
        <section className="landing-hero">
          <div className="landing-container landing-hero__intro">
            <h1 className="landing-hero__title">
              Le <span className="landing-hero__accent">poste de pilotage</span>{' '}
              de votre recherche d’emploi
            </h1>
            <p className="landing-hero__lead">
              Alternance, CDI, CDD ou stage : Cockpit rassemble toutes vos
              candidatures dans un tableau que vous faites avancer, de l’offre
              repérée à la réponse reçue.
            </p>
            <Link
              ref={heroCtaRef}
              to="/register"
              className="btn btn--primary landing-cta"
            >
              Créer un compte
            </Link>
          </div>

          {/* Scène : le panneau déborde sur la bande teal de la section
              suivante (marge négative, cf. landing.css). */}
          <div className="landing-container landing-stage">
            <figure className="landing-board">
              {/* Le panneau défile horizontalement en fenêtre étroite et reste
                  focusable pour que le clavier puisse le faire défiler. */}
              <div
                className="landing-board__panel"
                tabIndex={0}
                role="region"
                aria-label="Tableau d’exemple, défilement horizontal"
              >
                <DragDropProvider
                  onDragStart={kanbanDrag.onDragStart}
                  onDragOver={kanbanDrag.onDragOver}
                  onDragEnd={handleDragEnd}
                >
                  <div ref={kanbanRef} className="kanban landing-board__kanban">
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

        <section
          className="landing-section landing-features"
          aria-labelledby="landing-features-title"
        >
          <div className="landing-container">
            <h2 id="landing-features-title" className="landing-section__title">
              Gardez la vue d’ensemble
            </h2>
            <div className="landing-features__grid">
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
          <div className="landing-container landing-extension">
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
            {/* role="list" : sans puce native (list-style: none), Safari retire
                la sémantique de liste. Les numéros affichés sont décoratifs
                (aria-hidden) : le rang est déjà annoncé par l'<ol>. */}
            <ol className="landing-steps" role="list">
              {EXTENSION_STEPS.map((step, index) => (
                <li className="landing-step" key={step}>
                  <span className="landing-step__number" aria-hidden="true">
                    {index + 1}
                  </span>
                  <span className="landing-step__text">{step}</span>
                </li>
              ))}
            </ol>
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
            <div className="landing-trust__rows">
              {TRUST_POINTS.map((point) => (
                <div className="landing-trust__row" key={point.title}>
                  <h3>{point.title}</h3>
                  <p>{point.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section
          className="landing-section landing-closing"
          aria-labelledby="landing-closing-title"
        >
          <div className="landing-container">
            <h2 id="landing-closing-title" className="landing-closing__title">
              Votre prochaine candidature a sa colonne qui l’attend.
            </h2>
            <Link to="/register" className="btn btn--primary landing-cta">
              Créer un compte
            </Link>
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
