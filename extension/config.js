// Adresses figées de l'extension : SEUL fichier du code où elles sont écrites
// (avec host_permissions et externally_connectable, dans manifest.json).
//
// API_BASE_URL : API de PRODUCTION. Elle doit rester STRICTEMENT alignée sur
// l'entrée host_permissions du manifest : c'est cette permission d'hôte qui
// exempte la popup et le service worker du contrôle CORS. Les deux
// désynchronisées, les appels retombent sous le régime CORS ordinaire (préflight
// compris) et échouent, sans que le code ne signale quoi que ce soit d'anormal.
// package_extension.py refuse de construire un paquet dans ce cas.
//
// SITE_ORIGIN : origine exacte du site. Seule origine dont background.js accepte
// la session (contrôle de sender.origin), et site dont la popup ouvre la page de
// connexion. Alignée sur externally_connectable du manifest (contrôlé par
// package_extension.py). Cf. dev-docs/extension-session-sharing.md.
//
// Volontairement PAS de page d'options : une URL d'API configurable par
// l'utilisateur permettrait de diriger le token d'authentification vers un
// serveur arbitraire. Pour développer contre un backend local, ne JAMAIS modifier
// ce fichier : `package_extension.py dev` en produit une copie réécrite dans
// dist/dev/ (procédure dans README.md).
//
// ⚠ Deux contraintes imposées par package_extension.py :
// - chaque constante tient sur UNE ligne, de la forme exacte
//   `export const NOM = "valeur";` : c'est la seule forme que le script sait
//   réécrire (il échoue sinon, plutôt que de livrer une copie non réécrite) ;
// - aucune valeur locale ni ancien domaine dans ce fichier, commentaires
//   compris : le paquet Store les refuse partout (cf. README.md).

export const API_BASE_URL = "https://api.cockpitemploi.fr";
export const SITE_ORIGIN = "https://cockpitemploi.fr";
