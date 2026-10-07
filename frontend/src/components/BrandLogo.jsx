// Logo de Cockpit (le favicon), PARTAGÉ par la barre de la landing et celle de
// l'application : une seule source, pour que la marque soit identique sur la
// vitrine et dans l'outil. Seule l'image est partagée ; le nom « Cockpit », écrit
// à côté, garde la typographie propre à chaque barre.
//
// Décoratif : alt vide, le nom est toujours présent à côté (lu par les lecteurs
// d'écran, même masqué visuellement en fenêtre étroite sur la landing).
//
// Thème : le SVG choisit ses couleurs par @media (prefers-color-scheme). Affiché
// par un <img>, cette requête suit le `color-scheme` de la PAGE, que tokens.css
// pose selon le thème choisi sur le site (data-theme) : le logo suit donc le
// thème du site, pas celui du système. Un <img> plutôt qu'un SVG en ligne : un
// seul fichier sert d'icône d'onglet et de logo, sans copie qui divergerait.

/**
 * @param {Object} props
 * @param {string} [props.className]  classes additionnelles (placement).
 */
export default function BrandLogo({ className = '' }) {
  return (
    <img
      src="/favicon.svg"
      alt=""
      width="24"
      height="24"
      className={`brand-logo ${className}`.trim()}
    />
  )
}
