// ⚠ DIVERGENCE VOLONTAIRE ET TEMPORAIRE avec le backend (sous-lot 2a de la
// suppression du statut « rejected ») : ce fichier n'a PLUS « rejected », alors
// que l'enum ApplicationStatus du backend le garde comme valeur valide jusqu'au
// sous-lot 2b (migration + backend). Le front est retiré EN PREMIER pour qu'on ne
// puisse plus créer de ligne « rejected » (par glisser-déposer ou par le menu de
// statut) qui bloquerait la migration. Ne PAS y remettre « rejected » pour
// « réaligner ». À SUPPRIMER en 2b, quand le backend aura lui aussi retiré la
// valeur et que le miroir exact sera rétabli.
//
// Définition unique des statuts de candidature : clé technique (alignée sur
// l'enum ApplicationStatus du backend) + libellé français. L'ORDRE de ce tableau
// définit l'ordre des colonnes du kanban.
//
// Source de vérité réutilisée par l'affichage (ce kanban) ET, à venir, par la
// création/édition (menu de statuts) et le drag & drop (colonne cible → status).
// Si le backend ajoute un statut, on le répercute ICI et nulle part ailleurs.

export const APPLICATION_STATUSES = [
  { key: 'saved', label: 'Repérée' },
  { key: 'applied', label: 'Postulée' },
  { key: 'followed_up', label: 'Relancée' },
  { key: 'interview', label: 'Entretien' },
  { key: 'accepted', label: 'Acceptée' },
]
