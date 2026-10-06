// Registre des adaptateurs d'extraction par site.
//
// Un adaptateur est une fonction AUTONOME, injectée dans la page par
// chrome.scripting.executeScript à la place de l'extraction générique
// (extractOffer, background.js). Il est choisi ICI, dans le service worker, d'après
// le nom d'hôte de l'onglet actif : sur tout autre site, c'est littéralement la même
// fonction qu'avant qui est injectée (aucune régression possible par construction).
//
// Ajouter un site : écrire un fichier dans adapters/ qui exporte une fonction
// SANS dépendance extérieure (elle est sérialisée, cf. francetravail.js), puis
// l'ajouter à ADAPTERS avec les noms d'hôte EXACTS qu'elle couvre.

import { extractFranceTravailOffer } from "./francetravail.js";
import { extractIndeedOffer } from "./indeed.js";

const ADAPTERS = [
  {
    // Les pages de détail d'offre ne vivent que sur ce sous-domaine.
    hostnames: ["candidat.francetravail.fr"],
    extract: extractFranceTravailOffer,
  },
  {
    // Indeed France uniquement : seul domaine relevé (les autres pays ne sont
    // pas vérifiés, l'extraction générique continue de s'y appliquer).
    hostnames: ["fr.indeed.com"],
    extract: extractIndeedOffer,
  },
];

/**
 * Renvoie l'adaptateur dédié à l'URL de l'onglet, ou null (extraction générique).
 * Nom d'hôte EXACT (pas de suffixe) : un domaine voisin ne déclenche rien.
 * `tabUrl` peut être absent (pas d'accès à l'URL de l'onglet) : null aussi.
 */
export function findAdapter(tabUrl) {
  try {
    const { hostname } = new URL(tabUrl);
    return ADAPTERS.find((adapter) => adapter.hostnames.includes(hostname)) ?? null;
  } catch {
    return null;
  }
}
