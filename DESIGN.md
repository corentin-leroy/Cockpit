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
- Titre de carte : 14px, poids 500, couleur de texte principale.
- Métadonnées (entreprise, lieu) : 12px, couleur de texte secondaire.
- Titre de colonne : 12px, poids 600, majuscules, couleur secondaire.
- Titre de page : 28px, poids 600.
- Interligne : 1.4 pour le texte courant, 1.2 pour les titres.

## Espacement
- Échelle unique : 4 / 8 / 12 / 16 / 24 / 32px. Aucune valeur intermédiaire.
- L'espace entre deux groupes est toujours supérieur à l'espace interne d'un groupe.

## Couleur
- L'accent teal est réservé à une seule fonction : l'action principale de l'écran
  (bouton « Ajouter une candidature ») et les états de focus.
- Aucun texte de contenu en accent. Les titres de cartes sont en neutre.
- Les colonnes n'ont pas de couleur propre. Le statut est porté par la position et le libellé.
- Aucune information ne repose sur la couleur seule.
- Contraste minimum WCAG AA : 4.5:1 pour le texte, 3:1 pour les bordures et icônes.

## Cartes
- La carte entière est cliquable et ouvre le détail de la candidature.
- Aucun bouton d'action affiché en permanence sur la carte.
- Les actions (éditer, supprimer) apparaissent au survol, en haut à droite, en icônes.
- Le survol n'est jamais le seul chemin vers une action : l'édition et la suppression
  sont également accessibles depuis la vue détail.
- Pas de soulignement sur les titres. La zone cliquable est signalée par le survol.
- Bordure 1px, rayon 6px, pas d'ombre portée.

## Interaction et périmètre
- Cible : desktop, pointeur. Le tactile est hors périmètre pour l'instant.
- Le glisser-déposer entre colonnes est une interaction pointeur uniquement.
  Choix assumé, à documenter dans le README.
- Une alternative existe pour changer de statut sans glisser-déposer :
  le champ statut dans la vue détail.
- L'anneau de focus est visible sur tous les éléments interactifs :
  `:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }`
- Ne jamais écrire `outline: none` sans le remplacer immédiatement.
- L'accent teal a donc deux usages, et seulement ceux-là :
  l'action principale de l'écran, et le focus.

## Interdits
- Pas de dégradé.
- Pas d'ombre décorative. L'ombre sert uniquement aux éléments flottants (modale, menu).
- Pas d'emoji dans l'interface.
- Pas d'animation au-delà de 150ms, et uniquement sur opacité et couleur.
- Pas de bordure quand un espace suffit à séparer.

## Vérification avant de considérer un écran terminé
- Compter les valeurs d'espacement utilisées : toutes doivent être dans l'échelle.
- Compter les éléments teal à l'écran : idéalement un, deux au maximum.
- Passer la capture dans un simulateur de daltonisme : aucune information perdue.
- Mesurer les contrastes au lieu de les juger à l'œil.