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
- Exception : la landing page dispose d'un palier supplémentaire à 30px pour son titre
  principal (le `h1`, qui porte le slogan). L'application (kanban, formulaires, modales)
  plafonne à 28px. Les titres de section de la landing (`h2`) restent à 20px.
- Les glyphes et icônes (croix de fermeture, pictogrammes) ne consomment pas de token
  typographique : leur taille relève de l'icône, pas du texte.
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

## Cartes
- La carte entière est cliquable et ouvre la modale d'édition.
- Aucune action n'est affichée sur la carte, ni en permanence ni au survol.
  Éditer, supprimer et changer de statut se font depuis la modale.
- Le survol modifie le fond et renforce la bordure. C'est le seul signal d'interactivité.
- Le titre reste un lien vers l'offre, mais sans style de lien : couleur de texte
  principale, pas de soulignement, `cursor: pointer`.
- Bordure 1px, rayon 6px, pas d'ombre portée.

## Landing page
Fichiers : `pages/LandingPage.jsx`, `styles/landing.css` (classes préfixées `landing-`).
Elle suit toutes les règles de ce document ; ce qui suit précise les points propres à
une page de présentation.
- Le hero montre le PRODUIT : le vrai kanban (`KanbanColumn` et `ApplicationCard`), pas
  un dessin. Candidatures fictives, entreprises inventées, les quatre types de contrat
  mélangés (alternance, CDI, CDD, stage). Aucun style propre aux cartes ici : toute
  évolution du kanban se répercute d'elle-même sur la landing.
- Largeur unique : tous les blocs occupent la largeur du kanban (cinq colonnes de 280px
  et quatre espaces de 12px, soit 1448px, plus les marges ; conteneur de 1496px au
  plus). Aucun bloc n'est nettement plus large ou plus étroit que les autres.
- Alignement : le hero et l'appel final sont CENTRÉS. Les sections intermédiaires ont
  leur titre à gauche, au-dessus d'une grille de trois colonnes qui occupe toute la
  largeur (la section extension s'y cale : intro en colonne 1, étapes dès la colonne 2).
  Le kanban de démonstration reste aligné à gauche, comme dans l'application.
- Pas de bordure ni d'ombre sur les blocs de contenu : les fonctionnalités sont du texte
  séparé par l'espace ; la section confiance se détache par un fond de surface
  (`--color-surface-2`).
- Teal : un seul bouton, « Créer un compte », répété une fois en fin de page (jamais
  visible en même temps que le premier). « Installer l'extension » est un bouton
  secondaire, pour ne jamais concurrencer l'action principale. Les liens du pied de page
  sont neutres (texte discret, survol en couleur de texte), jamais en accent.
- Espacements dans l'échelle : l'air entre deux sections vient de deux paddings de 32px.
  Pas de 48px.
- La numérotation n'apparaît que pour une vraie séquence (les trois étapes de
  l'extension). Pas de numéros ni d'icônes décoratifs.
- Démonstration interactive : les cartes se déplacent d'une colonne à l'autre, mais rien
  n'est enregistré (un rechargement remet tout en place) et il n'y a pas de zone
  d'archivage. La légende sous le tableau le dit. Comme dans l'application, le
  glisser-déposer est une interaction au POINTEUR ; les cartes sont hors de l'ordre de
  tabulation (neuf arrêts sans action utile), seul le conteneur du tableau est
  focusable pour le défilement horizontal en fenêtre étroite.
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
- Pas d'ombre décorative. L'ombre sert uniquement aux éléments flottants (modale, menu).
- Pas d'emoji dans l'interface.
- Pas d'animation au-delà de 180ms, et uniquement sur opacité, fond et couleur.
  EXCEPTION UNIQUE, écrite et limitée à ce seul cas : le repli de la sidebar des
  tableaux (`.sidebar`, propriété `margin-left`, propriété de mise en page).
  180ms au maximum (`--sidebar-slide`, components.css), jamais davantage. Sous
  `prefers-reduced-motion: reduce`, le basculement est INSTANTANÉ (aucune
  transition, délai de visibilité compris). Aucun autre élément ne peut
  invoquer cette exception : toute autre animation de mise en page reste
  interdite.
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

## Vérification avant de considérer un écran terminé
- Compter les valeurs d'espacement utilisées : toutes doivent être dans l'échelle.
- Compter les éléments teal à l'écran : idéalement un, deux au maximum.
- Passer la capture dans un simulateur de daltonisme : aucune information perdue.
- Mesurer les contrastes au lieu de les juger à l'œil.
- Contrôler qu'aucun token de texte (`--color-text*`) n'est utilisé en `border-color`,
  `background`/`background-color` ou couleur d'icône.