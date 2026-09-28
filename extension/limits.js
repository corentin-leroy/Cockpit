// Miroir des bornes de validation du backend (backend/app/limits.py). Paquet
// indépendant du reste du projet : ne peut pas importer frontend/src/constants
// (même raison que la duplication des tokens de couleur dans popup.html —
// cf. CLAUDE.md de l'extension). Le SERVEUR reste l'autorité (cf. CLAUDE.md
// racine, « Limites de quantité ») : ces constantes ne servent qu'à bloquer la
// saisie et nettoyer une URL trop longue, jamais à décider qu'une valeur est
// valide. Une modification des bornes backend doit être répercutée ici dans la
// même passe.
//
// N'inclut PAS la borne appliquée à l'EXTRACTION (title/company/location coupés
// à 255 dans background.js, fonction extractOffer) : ce code est SÉRIALISÉ puis
// exécuté dans la page visitée et ne peut importer aucun module — ces valeurs y
// restent nécessairement dupliquées en dur, au même endroit que le reste de
// cette fonction.

export const TITLE_MAX_LENGTH = 255
export const COMPANY_MAX_LENGTH = 255
export const LOCATION_MAX_LENGTH = 255
export const URL_MAX_LENGTH = 2048
