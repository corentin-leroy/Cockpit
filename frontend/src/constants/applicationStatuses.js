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
  { key: 'rejected', label: 'Refusée' },
  { key: 'accepted', label: 'Acceptée' },
]
