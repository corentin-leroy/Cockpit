// Configuration de base des appels à l'API backend (FastAPI).
//
// L'URL est lue depuis une variable d'environnement Vite. Seules les variables
// préfixées par VITE_ sont exposées au code client (sécurité Vite). On fournit
// une valeur par défaut pointant vers le backend en développement, pour que le
// projet démarre sans configuration.
export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
