// Adaptateur France Travail : extraction d'une offre depuis candidat.francetravail.fr.
//
// ATTENTION : comme extractOffer (background.js), cette fonction est sérialisée
// puis exécutée DANS la page visitée. Elle ne peut utiliser aucune variable ni
// aucun import extérieur : toutes ses constantes sont déclarées à l'intérieur.
//
// POURQUOI un adaptateur dédié (l'extraction générique échoue sur ce site) :
//  - aucun JSON-LD sur la page : la générique retombe sur document.title, qui
//    vaut « Offre d'emploi <intitulé> - 59 - Lille - 214NYCN | France Travail » en
//    page seule et le titre de la LISTE en mode panneau ;
//  - le bloc de l'offre vit dans le Shadow DOM OUVERT d'un élément personnalisé
//    <descriptif-offre id-offre="…"> : invisible pour document.querySelector ;
//  - son contenu arrive APRÈS le chargement de la page, de façon asynchrone.
//
// Deux modes d'affichage, MÊME bloc : la page de détail seule, ou un panneau
// ouvert par-dessus la liste (l'URL devient alors celle du détail, sans les
// paramètres de recherche). On ne lit QUE le bloc de l'offre ouverte, jamais la
// page entière : en mode panneau, la liste contient d'autres intitulés et
// d'autres entreprises. On ne lit QUE la page : l'API interne du site
// (/api-descriptifoffre) n'est ni documentée ni prévue pour un usage externe, et
// n'est jamais appelée.
//
// ⚠ GARDE ANTI-OFFRE-PÉRIMÉE : le même élément est REMPLACÉ à chaque ouverture, et
// il RESTE dans le DOM, avec le contenu de la dernière offre, quand on ferme le
// panneau. Pendant le chargement d'une nouvelle offre, l'URL a déjà changé mais
// l'élément porte encore l'ancienne. On ne lit donc le contenu que lorsque TROIS
// numéros concordent : celui de l'URL, l'attribut `id-offre` de l'élément et le
// « Offre n° … » affiché dans son contenu. Sans ce contrôle, l'extension pourrait
// enregistrer silencieusement la mauvaise offre.
//
// Résultat : { title, company, location, url, source } comme extractOffer, plus un
// champ `notice` UNIQUEMENT quand il n'y a rien à lire (la popup l'affiche puis
// ne le garde pas) :
//  - "not-an-offer" : page France Travail sans offre ouverte → champs vides, AUCUN
//    lien (l'URL d'une liste de recherche serait une fausse donnée) ;
//  - "timeout" : le contenu n'est pas apparu à temps → champs vides, avec le lien
//    canonique (l'URL de détail est connue et fiable).

export async function extractFranceTravailOffer() {
  // Bornes miroir de backend/app/limits.py (cf. limits.js : extractOffer et cet
  // adaptateur dupliquent ces valeurs en dur, une modification se fait aux deux).
  const FIELD_MAX_LENGTH = 255;
  // Lien enregistré = adresse canonique de la page de détail, construite à partir
  // du numéro. Format VÉRIFIÉ (jamais supposé) : c'est l'URL que le site utilise
  // lui-même en mode panneau, et la page de détail s'ouvre seule à cette adresse.
  // Aucune balise <link rel="canonical"> ni og:url n'existe sur ces pages.
  const DETAIL_PATH = /^\/offres\/recherche\/detail\/([0-9A-Za-z]{5,12})\/?$/;
  const DETAIL_BASE_URL =
    "https://candidat.francetravail.fr/offres/recherche/detail/";
  // Offre anonyme : la carte « L'employeur » existe mais sans nom. Le backend
  // exige une entreprise non vide ; l'utilisateur peut la corriger dans la popup.
  const ANONYMOUS_COMPANY = "Entreprise non communiquée";
  const TIMEOUT_MS = 10000;
  const POLL_INTERVAL_MS = 100;

  const clean = (value) => (value ?? "").replace(/\s+/g, " ").trim();
  const sameId = (a, b) => a.toUpperCase() === b.toUpperCase();
  const empty = (notice, url = "") => ({
    title: "",
    company: "",
    location: "",
    url,
    source: "extension",
    notice,
  });

  // Pas une page de détail (liste sans panneau ouvert, accueil…) : rien à lire.
  const match = DETAIL_PATH.exec(location.pathname);
  if (!match) return empty("not-an-offer");
  const urlId = match[1];

  // Lecture ponctuelle : renvoie l'offre, ou null tant que le contenu n'est pas
  // PRÊT et COHÉRENT avec l'URL.
  function readOffer() {
    const host = document.querySelector("descriptif-offre");
    const attributeId = host?.getAttribute("id-offre") ?? "";
    if (!host || !sameId(attributeId, urlId)) return null;

    // Shadow DOM ouvert : absent tant que le composant n'a pas rendu l'offre.
    const root = host.shadowRoot;
    if (!root) return null;
    const read = (key) =>
      clean(root.querySelector(`[data-cy="${key}"]`)?.textContent);

    const title = read("intituleOffre");
    // « Offre n° 214NYCN » : le dernier mot est le numéro affiché.
    const displayedId = read("numeroOffre").split(" ").pop();
    if (!title || !sameId(displayedId, urlId)) return null;

    // Contenu complet et cohérent. L'employeur absent = offre anonyme (il vient
    // du même rendu que l'intitulé : s'il manquait parce que la page n'est pas
    // finie, l'intitulé manquerait aussi).
    return {
      title: title.slice(0, FIELD_MAX_LENGTH),
      company: (read("nom-etablissement") || ANONYMOUS_COMPANY).slice(
        0,
        FIELD_MAX_LENGTH,
      ),
      location: read("lieuTravail_entete").slice(0, FIELD_MAX_LENGTH),
      url: DETAIL_BASE_URL + attributeId,
      source: "extension",
    };
  }

  // Le contenu arrive après le chargement : on interroge la page jusqu'à ce qu'il
  // soit prêt, dans la limite du délai. executeScript attend la promesse.
  const deadline = Date.now() + TIMEOUT_MS;
  for (;;) {
    const offer = readOffer();
    if (offer) return offer;
    if (Date.now() >= deadline) return empty("timeout", DETAIL_BASE_URL + urlId);
    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
  }
}
