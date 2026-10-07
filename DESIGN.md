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
- Page du kanban : la PAGE ne défile pas, c'est la zone des colonnes (`.kanban`) qui
  défile, dans les deux sens (`.board-page`, components.css ; décidé le 2026-10-07).
  - Pourquoi : `.kanban` défile horizontalement, donc c'est un conteneur de défilement.
    Tant que la page défilait verticalement, des en-têtes `sticky` restaient accrochés
    à ce conteneur immobile et ne collaient jamais. Et la barre de défilement
    horizontale était sous la plus longue colonne : 413px sous le bas de l'écran,
    mesuré en 1366px de large.
  - Effets : les en-têtes de colonnes restent collés en haut de la zone, la sidebar
    (cibles de dépôt) et le bouton « Ajouter une candidature » restent visibles, la
    barre horizontale est toujours en bas de l'écran. Nombre de cartes visibles
    inchangé.
  - La zone est focalisable et nommée (« Colonnes du tableau ») : sans cela, le
    clavier ne peut pas la faire défiler. Anneau de focus extérieur (rentrant, son
    bord haut passait sous les en-têtes collés), d'où 4px de marge sous la zone.
  - Hauteurs en chaîne de flex, aucune valeur en dur : le bandeau de vérification
    prend ou rend sa place sans rien casser.
  - Limité à la page du kanban : archives et compte gardent le défilement de page ;
    la landing n'est pas concernée.
- Tableau vide : les cinq colonnes restent affichées (elles montrent les étapes du
  suivi), précédées d'une phrase qui dit comment ajouter une offre : le bouton, ou
  l'extension (lien neutre vers le Chrome Web Store, jamais teal). C'est le premier
  écran d'un nouvel inscrit, dont le tableau « Mes candidatures » est créé vide.

## Typographie
- Une seule famille, celle déjà en place. Pas de police décorative.
- Échelle : 12 / 14 / 16 / 20 / 28px. Aucune valeur hors échelle.
- Exception : la landing page a sa propre échelle d'affichage, au-delà de 28px (cf.
  section « Landing page »). L'application (kanban, formulaires, modales) plafonne à 28px.
- Les glyphes et icônes (croix de fermeture, pictogrammes) ne consomment pas de token
  typographique : leur taille relève de l'icône, pas du texte.
- Icônes : bibliothèque Phosphor (`@phosphor-icons/react`) PARTOUT, graisse normale,
  16px. Aucun caractère Unicode ni emoji servant d'icône dans le frontend (croix de
  fermeture, coche, avertissement, enveloppe compris) : un glyphe dépend de la police
  de secours, change de taille et de graisse d'un système à l'autre. Harmonisation
  terminée le 2026-10-07 ; à revérifier par une recherche dans `frontend/` à chaque
  ajout d'icône.
  - Boutons-icônes des barres (bascule de thème, repli de la sidebar) et croix de
    fermeture des modales : CARRÉS FIXES de 32px (`--space-6`), leur taille ne dépend
    jamais de l'icône.
  - Repli de la sidebar : DEUX boutons, même icône (`SidebarSimple`, un panneau
    latéral, et non `List`, lu comme un menu). Celui de la navbar (seul moyen de
    rouvrir) et celui de l'en-tête de la sidebar, à côté de « TABLEAUX », carré de
    24px : là où l'œil se trouve, le premier seul passait inaperçu. Replier depuis
    l'en-tête rend le focus au bouton de la navbar.
  - Actions d'une ligne de la sidebar (renommer, supprimer) : carrés de 24px
    (`--space-5`).
  - Icône posée devant un texte (alerte, avertissement, bandeau, retour d'action) :
    centrée sur la PREMIÈRE ligne du texte (hauteur `1lh`), qu'il tienne sur une ou
    plusieurs lignes.
- Titre de carte : 14px, poids 500, couleur de texte principale.
- Métadonnées (entreprise, lieu) : 12px, couleur de texte secondaire.
- Titre de colonne : 12px, poids 600, majuscules, couleur de texte PRINCIPALE (12,5:1
  en clair, 14,3:1 en sombre). Écart retenu le 2026-10-07 (auparavant : secondaire) :
  le libellé de colonne structure la zone de travail, mais en secondaire il avait la
  couleur des métadonnées et pesait moins que les titres de cartes. La hiérarchie
  était inversée.
- Compteur de colonne : 12px, couleur discrète (`--color-text-muted`, 5,1:1 / 6,2:1),
  un cran sous le libellé qu'il complète.
- Étiquette « TABLEAUX » de la sidebar : même gabarit que le titre de colonne, mais en
  couleur SECONDAIRE. Rôle différent : c'est une étiquette de catégorie, et ce sont
  les noms de tableaux (14px) qu'elle surmonte qui doivent dominer.
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
- Les ÉTATS sont neutres, jamais teal : tableau courant de la sidebar (fond de carte,
  bordure `--color-border-hover` à 5,1:1 / 5,6:1, nom en semi-gras : il dit où l'on se
  trouve, il doit être évident d'un coup d'œil), cible de dépôt survolée (fond de
  survol, bordure `--color-border-hover`), survols de boutons. Corrigé le 2026-10-07 : ces trois
  éléments étaient teal.
- Bandeau de vérification d'email : NEUTRE, jamais teal (il l'était : deux éléments
  teal à l'écran avec le bouton d'ajout). Il attire l'œil par sa bande et par une
  accroche en gras (« Adresse email non vérifiée. »), pas par la couleur. Fond
  `--color-surface-band`, écart retenu le 2026-10-07 (token jusque-là réservé aux
  bandes de la landing) : c'est le seul fond qui se détache de la page de façon
  comparable dans les deux thèmes (1,20 / 1,19:1). Mesuré : texte 11,3 / 11,4:1,
  retours d'envoi succès 5,1 / 7,9 et erreur 5,7 / 7,2. Limite connue : en sombre, il
  ne se distingue de la navbar qu'à 1,08:1 (deux filets les séparent). Texte EXACT :
  aucune promesse de « sécuriser le compte », la vérification n'est pas bloquante.
- Les colonnes n'ont pas de couleur propre. Le statut est porté par la position et le libellé.
- Fond de colonne : token dédié `--color-surface-column`, en CREUX sous la page dans les
  deux thèmes. Écart retenu le 2026-10-07 (nouvelle nuance) : en sombre,
  `--color-surface-2` est plus claire que la page. La colonne y était en relief (en
  creux en clair) et la carte s'en distinguait à 1,05:1 seulement. Mesuré : carte /
  colonne 1,14 (clair) et 1,16 (sombre), colonne / page 1,08 et 1,05.
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
  Bordure de survol `--color-border-hover` (4,7:1 / 4,6:1 sur le fond de survol) : un
  saut de luminance perceptible quelle que soit la vision des couleurs.
- Le titre reste un lien vers l'offre : couleur de texte principale, `cursor: pointer`,
  pas de soulignement AU REPOS. Souligné (couleur du texte, jamais teal) au survol ou
  au focus du TITRE SEUL, pas de la carte. Écart retenu le 2026-10-07 : la carte a deux
  cibles de clic aux effets opposés (le titre ouvre l'offre externe dans un nouvel
  onglet, le reste de la carte ouvre la modale), elles doivent se distinguer.
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
  - `--color-surface-band` est le token DÉDIÉ aux bandes de section (et, dans
    l'application, au bandeau de vérification d'email, cf. « Couleur ») : il se distingue du
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
  C'est le seul élément ombré de la page, hors bouton principal et hors carte EN COURS
  de glisser dans la démo (élément flottant, `--shadow-md`, cf. « Interaction et
  périmètre »), qui n'existe que le temps du geste.
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
- Pendant un glisser-déposer (décidé le 2026-10-07). Chaque état se distingue par la
  FORME du trait et la LUMINANCE, jamais par la teinte seule ; aucun teal ; aucun
  décalage de mise en page au début ni à la fin du geste :
  - Carte glissée : OPAQUE, `--shadow-md` (élément flottant). Au-dessus d'un tableau de
    la sidebar ou de la zone d'archivage, translucide à 20 % : le nom de la cible se lit
    à travers (son titre tombe pile dessus, à 40 % les deux textes se mêlaient), et
    l'effacement annonce qu'elle va quitter le tableau. Landing : toujours opaque.
  - Sidebar dépliée, dès le début du geste : « TABLEAUX » devient « DÉPLACER VERS »
    (même élément, aucun décalage), actions de ligne masquées.
  - Autre tableau (cible) : trait fin en TIRETS `--color-border-hover` (5,1 / 5,6:1),
    le vocabulaire « déposer ici » de l'application.
  - Cible survolée : trait PLEIN et DOUBLE (bordure + liseré intérieur, sans changer la
    taille), fond `--color-surface-3`, nom en texte principal (11,4 / 10,8:1).
  - Tableau courant (pas une cible) : trait plein fin, atténué à 65 %. Plus bas, son nom
    passerait sous AA (4,75 / 6,05:1 à 65 %, 3,56 à 55 %).
  - Zone d'archivage : MÊME langage que les tableaux cibles (tirets fins au repos,
    trait plein doublé et fond de survol quand elle est visée). Elle apparaît par un
    simple fondu d'opacité, sans glisser (glissement de 12px retiré le 2026-10-07).
  - Sidebar repliée : rien ne change (déplacement vers un autre tableau par la modale).
- Le survol n'est jamais le seul chemin vers une action : la carte est aussi
  activable au clavier (Entrée ou Espace).
- `cursor: grab` sur la carte, `cursor: pointer` sur le titre-lien.
- L'anneau de focus est visible sur tous les éléments interactifs :
  `:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }`
- Ne jamais écrire `outline: none` sans le remplacer immédiatement.

## Interdits
- Pas de dégradé.
- Pas d'ombre décorative. L'ombre sert uniquement aux éléments flottants (modale, menu,
  zone d'archivage, carte en cours de glisser), et au panneau du kanban de la landing
  page, posé sur la page (cf. section « Landing page »).
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
- Exceptions VOLONTAIRES, absentes de la popup, à ajouter le jour où elle en aurait
  l'usage (leur absence n'est pas un oubli de synchronisation) :
  - `--color-surface-band` : ne sert qu'aux bandes de section de la landing ;
  - `--color-surface-column` : ne sert qu'aux colonnes du kanban, la popup n'en a pas.

## Vérification avant de considérer un écran terminé
- Compter les valeurs d'espacement utilisées : toutes doivent être dans l'échelle.
- Compter les éléments teal à l'écran : idéalement un, deux au maximum.
- Passer la capture dans un simulateur de daltonisme : aucune information perdue.
- Mesurer les contrastes au lieu de les juger à l'œil.
- Contrôler qu'aucun token de texte (`--color-text*`) n'est utilisé en `border-color`,
  `background`/`background-color` ou couleur d'icône.