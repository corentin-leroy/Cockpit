// Miroir des bornes de validation du backend (backend/app/limits.py et
// backend/app/schemas.py). Le SERVEUR reste l'autorité (cf. CLAUDE.md,
// « Limites de quantité » : « le front peut les afficher pour l'UX mais ne fait
// pas autorité ») : ces constantes ne servent qu'à bloquer la saisie
// (maxLength) et à afficher un compteur, jamais à décider qu'une valeur est
// valide — l'extension et un appel direct à l'API restent plafonnés côté
// serveur quoi que fasse ce fichier. Une modification des bornes backend doit
// être répercutée ici dans la même passe.
//
// Absent volontairement : le nom de tableau. Il a sa propre borne, PLUS
// STRICTE, déjà définie et commentée localement dans BoardForm.jsx
// (NAME_MAX_LENGTH = 25, contre 100 côté backend) — ce n'est pas un oubli.
//
// Absent aussi : le mot de passe PRÉSENTÉ (connexion, suppression de compte).
// Sa borne backend est de 4096 OCTETS (pas des caractères), et un compte déjà
// existant peut avoir un mot de passe choisi avant une éventuelle baisse de
// cette politique — un maxLength dessus empêcherait de s'authentifier avec un
// mot de passe pourtant valide. PASSWORD_MAX_LENGTH ci-dessous ne concerne que
// le mot de passe CHOISI (inscription, réinitialisation).

export const TITLE_MAX_LENGTH = 255
export const COMPANY_MAX_LENGTH = 255
export const LOCATION_MAX_LENGTH = 255
export const URL_MAX_LENGTH = 2048
export const NOTES_MAX_LENGTH = 5000

// Mot de passe CHOISI uniquement (inscription, réinitialisation) : miroir de
// backend/app/limits.py (MAX_CHOSEN_PASSWORD_BYTES = 72). Côté serveur la borne
// est en OCTETS UTF-8 (bcrypt ignore tout ce qui dépasse 72 octets) ; maxLength
// compte, lui, des caractères. Un mot de passe accentué (« é » = 2 octets) peut
// donc passer ici et être refusé par le backend, avec son message — accepté :
// le serveur fait autorité. Ne JAMAIS l'appliquer au mot de passe de connexion
// ni à celui de suppression de compte — voir la note ci-dessus.
export const PASSWORD_MAX_LENGTH = 72
