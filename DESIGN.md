# Direction visuelle — Cockpit

Outil de travail dense, consulté plusieurs fois par jour. Référence de densité : Notion.
Principe : la couleur et l'espace signalent, ils ne décorent pas.

## Densité
- Padding interne des cartes : 8px.
- Espace entre deux cartes : 8px.
- Espace entre deux colonnes : 12px.
- Largeur de colonne : 280px, fixe.
- Objectif mesurable : 10 cartes visibles sans scroll sur un écran 1080p.

## Mise en page des écrans
- Les pages de CONTENU (Archives, Mon compte) sont centrées dans l'espace
  disponible à droite de la sidebar : `max-width` + `margin: 0 auto` sur le
  conteneur. Sur un grand écran, le contenu ne doit jamais rester collé à
  gauche avec du vide asymétrique à droite.
- Le KANBAN reste aligné à gauche, jamais centré : ses colonnes s'étendent et
  défilent horizontalement, un centrage n'a pas de sens sur un contenu qui
  déborde par construction.

## Typographie
- Une seule famille, celle déjà en place. Pas de police décorative.
- Échelle : 12 / 14 / 16 / 20 / 28px. Aucune valeur hors échelle.
- Exception : la landing page a sa propre échelle d'affichage, au-delà de 28px (cf.
  section « Landing page »). L'application (kanban, formulaires, modales) plafonne à 28px.
- Les glyphes et icônes (croix de fermeture, pictogrammes) ne consomment pas de token
  typographique : leur taille relève de l'icône, pas du texte.
- Icônes : bibliothèque Phosphor (`@phosphor-icons/react`), graisse normale, 16px dans
  les boutons-icônes des barres. Les boutons-icônes des barres (bascule de thème, repli
  de la sidebar) sont des CARRÉS FIXES de 32px (`--space-6`) : leur taille ne dépend
  jamais de l'icône. Jamais de SVG et de caractère Unicode mêlés dans une même barre.
  Le reste de l'application utilise encore des caractères Unicode (dont deux emoji,
  contraires aux interdits) : leur passage à Phosphor est un lot d'harmonisation prévu.
- Titre de carte : 14px, poids 500, couleur de texte principale.
- Métadonnées (entreprise, lieu) : 12px, couleur de texte secondaire.
- Titre de colonne : 12px, poids 600, majuscules, couleur secondaire.
- Titre de page : 28px, poids 600.
- Interligne : 1.55 pour le texte courant (token `--leading-body`, source unique :
  `html` et la hauteur minimale de `.input` le lisent), 1.2 pour les titres.
- Un texte qui dépasse son espace est plafonné à DEUX lignes avec ellipse
  au-delà (titre de carte, cellule de tableau dense) — jamais coupé sur une
  seule ligne, et jamais laissé libre d'allonger indéfiniment la carte ou la
  ligne du tableau qui le contient.

## Espacement
- Échelle unique : 4 / 8 / 12 / 16 / 24 / 32px. Aucune valeur intermédiaire.
- L'espace entre deux groupes est toujours supérieur à l'espace interne d'un groupe.
- Exception : les espacements entre sections de la landing page, multiples de cette
  échelle (cf. section « Landing page »).

## Couleur
- L'accent teal est réservé à deux usages, et seulement ceux-là : l'action principale
  de l'écran (bouton « Ajouter une candidature ») et l'anneau de focus.
- Aucun texte de contenu en accent. Les titres de cartes sont en neutre.
- Les colonnes n'ont pas de couleur propre. Le statut est porté par la position et le libellé.
- Aucune information ne repose sur la couleur seule.
- Contraste minimum WCAG AA : 4.5:1 pour le texte, 3:1 pour les bordures et icônes.
- Les tokens `--color-text*` ne servent qu'au texte. Une bordure, un fond ou une icône
  passent par un token dédié (`--color-border*`, `--color-surface*`…), jamais par un
  token de texte détourné — même si la valeur hexadécimale coïncide au départ.
- La landing page fait du teal une couleur d'identité, alterne les fonds de section et
  admet des filets décoratifs sous 3:1 : ces écarts, et eux seuls, sont décrits dans la
  section « Landing page ».

## Cartes
- La carte entière est cliquable et ouvre la modale d'édition.
- Aucune action n'est affichée sur la carte, ni en permanence ni au survol.
  Éditer, supprimer et changer de statut se font depuis la modale.
- Le survol modifie le fond et renforce la bordure. C'est le seul signal d'interactivité.
- Le titre reste un lien vers l'offre, mais sans style de lien : couleur de texte
  principale, pas de soulignement, `cursor: pointer`.
- Bordure 1px, rayon 6px, pas d'ombre portée.

## Landing page
Fichiers : `pages/LandingPage.jsx`, `styles/landing.css` (classes préfixées
`landing-`), route `/`.

Pourquoi une zone de liberté : ce document est écrit pour un outil de travail dense, où
la retenue est une qualité. Appliquées telles quelles à une page de présentation, ses
règles la rendent plate : tout a la même intensité, rien ne guide l'œil. La landing
s'écarte donc du reste du document, mais SEULEMENT sur les points listés ci-dessous.
Tout ce qui n'y figure pas reste soumis aux autres sections.

### Intangible
- La palette de `tokens.css` : aucune couleur propre à la landing, pour qu'elle
  ressemble à l'application. Les tailles et espacements propres sont des variables
  locales de `landing.css`, dérivées des tokens quand c'est possible.
- Aucune information portée par la couleur seule. Contrastes AA MESURÉS, pas jugés à
  l'œil (valeurs en tête de `landing.css`, à remesurer à chaque nouveau couple).
- Les deux thèmes, clair et sombre, vérifiés tous les deux.
- Le kanban interactif : les vrais composants, aucun style propre aux cartes, aucun appel
  à l'API.
- Pas d'emoji, pas de dégradé (le chevauchement du kanban se fait par une marge
  négative, pas par un dégradé).

### Écarts retenus
- Typographie : échelle d'affichage propre, au-delà du plafond de 28px de l'application.
  - `h1` (slogan) : de 36px (fenêtre étroite) à 56px (écran large), poids 700,
    interlettrage resserré (-0,025em), interligne 1.08. Deux lignes au plus sur écran
    large (largeur bornée à 24ch).
  - Phrase de l'appel final et numéros des étapes : de 28px à 40px, poids 700.
  - Titres de section (`h2`) : 28px. Titres d'élément (`h3`) : 20px. Chapeau du hero :
    20px. Texte courant : 16px.
- Espacement : l'air entre deux sections est nettement supérieur à l'air dans une
  section. Sections : 96px de padding vertical (64px à 768px et moins). Hero : 64px en
  haut (48px), 48px entre le texte et le kanban. Appel final : 128px. Tous multiples de
  l'échelle (`--space-6`, `--space-7`). La règle « pas de 48px » de l'ancienne landing
  est levée.
- Fonds alternés, cinq temps : page, bande teal pâle (bas du kanban et « Gardez la vue
  d'ensemble », `--color-accent-soft`), page (extension), bande neutre (confiance,
  `--color-surface-band`), page (appel final).
  - `--color-surface-band` est le token DÉDIÉ aux bandes de section : il se distingue du
    fond de page de façon comparable dans les deux thèmes (1,20:1 en clair comme en
    sombre). Aucune surface existante ne le permettait : `--color-surface-2` est plus
    sombre que le fond en clair mais plus claire en sombre, à peine visible (1,08 /
    1,05) ; `--color-surface-3` (1,18 / 1,26), emprunté un temps, a le rôle de survol.
    Textes dessus, mesurés : `--color-text` 11,25 / 11,35, `--color-text-secondary`
    7,23 / 7,42, `--color-text-muted` 4,61 / 4,89.
  - Aucun texte `--color-text-muted` sur la bande teal : 4,23:1 en sombre, sous AA. La
    légende du kanban y est en `--color-text-secondary` (7,90 / 6,43).
- Mise en scène du kanban : un panneau (fond de surface, bordure, `--shadow-lg`) posé
  sur la page, qui chevauche de 160px (96px en fenêtre étroite) la bande teal suivante.
  Rayon concentrique : celui des colonnes plus le padding du panneau (14 + 12 = 26px).
  C'est le seul élément ombré de la page, hors bouton principal.
- Teal comme couleur d'identité, plus seulement comme signal : « poste de pilotage »
  dans le `h1` (`--color-accent-text`, 6,87 / 9,06), la bande teal pâle, les filets de la
  vue d'ensemble (`--color-accent-border`), les numéros des étapes. Partout il double un
  texte ou une forme, jamais il ne porte seul une information.
- L'ACTION principale teal reste unique à l'écran : « Créer un compte » du hero, répété
  une fois en fin de page (jamais visibles ensemble). Partout ailleurs, l'inscription est
  en style secondaire. Au comptage du teal (« Vérification », plus bas), seules les
  actions comptent ; les usages d'identité ci-dessus n'en sont pas.
- Filets DÉCORATIFS sous 3:1 admis : un filet qui ne porte aucune information (l'espace
  et les titres séparent déjà les blocs) peut rester sous le seuil des bordures, comme
  `--color-border` dans l'application. Mesurés : teal sur bande teal 1,49 / 1,94,
  neutre sur bande neutre 1,31 / 1,51.
- Logo (le favicon) dans l'en-tête, à côté du nom.

### Mise en page des sections
- Deux sections ne partagent JAMAIS la même disposition. C'était la principale cause de
  l'uniformité de l'ancienne landing (vue d'ensemble et confiance dans la même grille).
  - Hero : centré. Le kanban, dans son panneau, reste aligné à gauche.
  - Vue d'ensemble : trois colonnes coiffées d'un filet teal (une colonne à 900px et
    moins, où chacune tomberait sous ~200px).
  - Extension : introduction à gauche, étapes à droite en liste verticale, numéros grands
    et teal, filet entre les étapes (introduction au-dessus à 1024px et moins).
  - Confiance : en LIGNES, titre du point à gauche, explication à droite, filet entre
    les lignes (titre au-dessus du texte à 768px et moins).
  - Appel final : centré, la phrase est un `h2`.
- Largeur unique : tous les blocs ont la largeur du panneau du kanban (cinq colonnes de
  280px et quatre espaces de 12px, plus le padding et la bordure du panneau, soit 1474px)
  plus les marges : conteneur de 1522px au plus.
- La numérotation n'apparaît que pour une vraie séquence (les trois étapes de
  l'extension). Pas de numéros ni d'icônes décoratifs.

### Barre du haut
- Balisage propre à la landing (pas `Navbar.jsx`). Collée en haut pendant le défilement
  (`position: sticky`, sans JavaScript), fond opaque `--color-bg`, filet en bas, au-dessus
  du panneau du kanban (z-index 2 contre 1 ; ce sont les deux seuls calques de la page).
- Contenu : logo et « Cockpit », changement de thème, « Se connecter » (fantôme),
  « Créer un compte » (SECONDAIRE, jamais teal). Compacte à 768px et moins (49px au lieu
  de 57px). Sous 480px, le nom est masqué visuellement (toujours lu par les lecteurs
  d'écran) pour que la barre tienne sur une ligne.
- « Créer un compte » de la barre n'apparaît qu'une fois celui du hero ENTIÈREMENT sorti
  de l'écran, y compris caché derrière la barre ; il disparaît quand on remonte.
  - Détection par `IntersectionObserver` (marge haute négative de la hauteur de la
    barre), recréé par un `ResizeObserver` quand cette hauteur change (le seuil de
    768px, traversé en faisant pivoter une tablette). Aucun écouteur de défilement,
    aucun état React (un attribut `data-signup` sur l'en-tête).
  - ÉCART VOLONTAIRE (animation de mise en page, cf. « Interdits ») : en haut de page,
    l'emplacement du bouton a une largeur NULLE, et « Se connecter » touche le bord
    droit, symétrique du logo. Un emplacement réservé vide (l'ancien comportement)
    passait pour un défaut d'alignement aux yeux d'un visiteur qui ne sait pas qu'un
    bouton va apparaître. Quand le bouton du hero sort de l'écran, l'emplacement
    s'élargit en 180ms : le thème et « Se connecter » GLISSENT vers la gauche, le
    bouton reste immobile au bord droit et apparaît en fondu ; mouvement inverse en
    remontant. C'est le seul déplacement d'éléments de la barre, et il est voulu :
    rien d'autre n'y bouge, ni n'y saute (la hauteur de la barre ne change jamais).
  - Technique, CSS seul : grille d'une colonne, `minmax(0, 0fr)` ↔ `minmax(0, 1fr)`,
    l'écart de la barre replié avec elle ; le bouton, qui ne passe jamais à la ligne,
    est rogné (`overflow: clip`) pendant l'élargissement, anneau de focus préservé.
    Détail et mesures : `dev-docs/landing-page.md`.
  - Masqué : ni cliquable, ni atteignable au clavier, ni annoncé (`visibility: hidden`).
    Il reste affiché, emplacement ouvert, tant qu'il a le focus clavier, sinon le focus
    serait perdu.
  - Glissement et fondu de 180ms, activés seulement après le premier verdict (ni
    fondu ni glissement au chargement, même sur une page rechargée déjà défilée).
    Instantanés sous `prefers-reduced-motion`, par une règle EXPLICITE : la règle
    globale de `base.css` réduit les durées, pas les délais (celui de `visibility`
    aurait survécu).
  - Repli sûr : sans observateur, ou avant le premier calcul, il est VISIBLE.
    L'inscription n'est jamais inaccessible au milieu de la page.
- Focus jamais masqué par la barre : `scroll-margin-top` de 72px sur le CONTENU (`main`,
  pied de page). Jamais `scroll-padding-top` sur `<html>` : les éléments de la barre,
  toujours dans les 72px du haut, passeraient pour masqués et chaque tabulation dans la
  barre ferait remonter la page (mesuré : de 1500 à 1047px).

### Mouvement
- Aucune animation d'entrée ni d'apparition au défilement : le kanban déplaçable est
  l'élément animé de la page, rien ne doit lui faire concurrence. Seules exceptions,
  toutes deux dans la barre : le fondu du bouton d'inscription et le glissement qui lui
  fait place (cf. « Barre du haut » et « Interdits »).
- Une bibliothèque d'animation (Motion) n'est envisageable que pour un effet que le CSS
  ne sait pas produire proprement (ressort physique, réorganisation animée), chargée
  sur la landing seulement, et après accord. Fondus, survols et apparitions restent en
  CSS.

### Contenu et interaction
- Le hero montre le PRODUIT : le vrai kanban (`KanbanColumn` et `ApplicationCard`), pas
  un dessin. Candidatures fictives, entreprises inventées, les quatre types de contrat
  mélangés (alternance, CDI, CDD, stage). Toute évolution du kanban se répercute
  d'elle-même sur la landing.
- Démonstration interactive : les cartes se déplacent à n'importe quel rang, mais rien
  n'est enregistré (un rechargement remet tout en place) et il n'y a pas de zone
  d'archivage. La légende sous le tableau le dit. Comme dans l'application, le
  glisser-déposer est une interaction au POINTEUR ; les cartes sont hors de l'ordre de
  tabulation (neuf arrêts sans action utile), seul le panneau du tableau est focusable
  pour le défilement horizontal en fenêtre étroite. Son rayon est conservé au focus
  (`base.css` impose sinon `--radius-sm` à tout `:focus-visible`).
- Les liens du pied de page sont neutres (texte discret, survol en couleur de texte),
  jamais en accent.
- Contenu : la page décrit ce qui existe. Aucune promesse sur l'avenir (fonctionnalité
  à venir, durée de gratuité, offre payante). Chaque affirmation de la section
  « Ce que Cockpit fait de vos données » doit rester exacte (cf. CLAUDE.md).

## Interaction et périmètre
- Cible : desktop, pointeur. Le tactile est hors périmètre pour l'instant.
- Le glisser-déposer entre colonnes est une interaction pointeur uniquement.
  Choix assumé, à documenter dans le README.
- Le survol n'est jamais le seul chemin vers une action : la carte est aussi
  activable au clavier (Entrée ou Espace).
- `cursor: grab` sur la carte, `cursor: pointer` sur le titre-lien.
- L'anneau de focus est visible sur tous les éléments interactifs :
  `:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }`
- Ne jamais écrire `outline: none` sans le remplacer immédiatement.

## Interdits
- Pas de dégradé.
- Pas d'ombre décorative. L'ombre sert uniquement aux éléments flottants (modale, menu),
  et au panneau du kanban de la landing page, posé sur la page (cf. section « Landing
  page »).
- Pas d'emoji dans l'interface.
- Pas d'animation au-delà de 180ms, et uniquement sur opacité, fond et couleur.
  DEUX EXCEPTIONS, écrites et limitées chacune à son seul élément, toutes deux à
  180ms au maximum et INSTANTANÉES sous `prefers-reduced-motion: reduce` (aucune
  transition, délai de visibilité compris) :
  - le repli de la sidebar des tableaux (`.sidebar`, propriété `margin-left`,
    `--sidebar-slide`, components.css) ;
  - l'emplacement du bouton « Créer un compte » de la barre de la landing
    (`.landing-topbar__signup-slot`, `grid-template-columns` et `margin-left`,
    `--transition-base`, landing.css), pour éviter l'asymétrie de la barre en haut de
    page (cf. « Landing page », « Barre du haut »).
  Aucun autre élément ne peut se réclamer de ces exceptions : toute autre animation
  de mise en page reste interdite, et toute nouvelle exige une décision explicite,
  inscrite ici.
- Pas de bordure quand un espace suffit à séparer.
- **Jamais `display: flex` ni `display: -webkit-box` directement sur un `<td>`.**
  Un `<td>` doit garder son `display: table-cell` implicite pour participer au
  calcul de hauteur de ligne du tableau (toutes les cellules d'une ligne sont
  normalement étirées à la même hauteur). Lui poser un autre `display` le sort
  de ce calcul : la cellule se retrouve avec sa propre hauteur, plus courte que
  les autres, et sa bordure basse se décale visiblement au-dessus de celle du
  reste de la ligne. Le flex (boutons d'action) ou le plafond à deux lignes
  (ellipse) vivent toujours sur un élément INTERNE à la cellule (`<div>` ou
  `<span>`), jamais sur le `<td>` lui-même. Piège rencontré deux fois sur la
  page d'archives (colonne Actions, puis intitulé/entreprise/lieu) avant
  d'être documenté ici — vérifier ce point en premier si des cellules d'un
  même tableau finissent à des hauteurs différentes.

## Duplication à surveiller
- Le bloc `<style>` de `extension/popup.html` duplique volontairement les tokens de
  `tokens.css` (couleurs, espacements, rayons, typo). Toute modification de la palette
  ou de l'échelle typographique doit y être répercutée dans la même passe.
- Exception VOLONTAIRE : `--color-surface-band` n'est PAS dans la popup. Il ne sert
  qu'aux bandes de section de la landing, et la popup n'en a pas. Son absence n'est pas
  un oubli de synchronisation ; à ajouter le jour où la popup en aurait l'usage.

## Vérification avant de considérer un écran terminé
- Compter les valeurs d'espacement utilisées : toutes doivent être dans l'échelle.
- Compter les éléments teal à l'écran : idéalement un, deux au maximum.
- Passer la capture dans un simulateur de daltonisme : aucune information perdue.
- Mesurer les contrastes au lieu de les juger à l'œil.
- Contrôler qu'aucun token de texte (`--color-text*`) n'est utilisé en `border-color`,
  `background`/`background-color` ou couleur d'icône.