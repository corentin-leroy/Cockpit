# Direction visuelle — Cockpit

Outil de travail dense, consulté plusieurs fois par jour. Référence de densité : Notion.
Principe : la couleur et l'espace signalent, ils ne décorent pas.

## Densité
- Padding interne des cartes : 8px.
- Espace entre deux cartes : 8px.
- Espace entre deux colonnes : 12px.
- Largeur de colonne : 280px, fixe.
- Objectif mesurable : 10 cartes visibles sans scroll sur un écran 1080p.

## Typographie
- Une seule famille, celle déjà en place. Pas de police décorative.
- Échelle : 12 / 14 / 16 / 20 / 28px. Aucune valeur hors échelle.
- Exception : la landing page dispose d'un palier supplémentaire à 30px pour son titre
  principal. L'application (kanban, formulaires, modales) plafonne à 28px.
- Les glyphes et icônes (croix de fermeture, pictogrammes) ne consomment pas de token
  typographique : leur taille relève de l'icône, pas du texte.
- Titre de carte : 14px, poids 500, couleur de texte principale.
- Métadonnées (entreprise, lieu) : 12px, couleur de texte secondaire.
- Titre de colonne : 12px, poids 600, majuscules, couleur secondaire.
- Titre de page : 28px, poids 600.
- Interligne : 1.4 pour le texte courant, 1.2 pour les titres.

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
- Pas de bordure quand un espace suffit à séparer.

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