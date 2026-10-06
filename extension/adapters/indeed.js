// Adaptateur Indeed : extraction d'une offre depuis fr.indeed.com.
//
// ATTENTION : comme extractOffer (background.js), cette fonction est sérialisée
// puis exécutée DANS la page visitée. Elle ne peut utiliser aucune variable ni
// aucun import extérieur : toutes ses constantes sont déclarées à l'intérieur.
//
// POURQUOI un adaptateur dédié : deux modes d'affichage, et la générique échoue
// sur le plus courant.
//  - page d'offre seule (/viewjob?jk=<id>) : un JSON-LD JobPosting existe, la
//    générique y fonctionnerait ;
//  - panneau ouvert à droite d'une liste de résultats (/jobs?…&vjk=<id>) : AUCUN
//    JSON-LD, et document.title est celui de la RECHERCHE (« Emplois : Alternance
//    Développeur, Lille (59) - … | Indeed ») : la générique enregistre une fausse
//    donnée.
// Les deux modes partagent le MÊME en-tête d'offre : un seul chemin de lecture,
// plutôt que JSON-LD d'un côté et en-tête de l'autre.
//
// Sélecteurs : attributs data-testid uniquement. Les classes CSS sont générées
// (`css-g5y9jx r-…`) et changent sans prévenir. On ne lit QUE l'en-tête de
// l'offre ouverte (`desktop-job-header`) : les testids `company-name` et
// `text-location` appartiennent aux CARTES de la liste, jamais à l'offre ouverte.
//
// ⚠ GARDE ANTI-OFFRE-PÉRIMÉE : on ne lit l'en-tête que si le lien entreprise qu'il
// contient porte `fromjk=<id>` ÉGAL à l'identifiant de l'URL. Mesuré au changement
// d'offre en mode panneau : Indeed vide le panneau puis remplit URL et contenu dans
// la même mutation (aucun mélange observé), mais la garde rend ce comportement
// indifférent. Une offre dont l'en-tête n'aurait pas ce lien expire (message
// neutre) au lieu d'être lue : on préfère un formulaire vide à une mauvaise offre.
//
// Résultat : { title, company, location, url, source } comme extractOffer, plus un
// champ `notice` UNIQUEMENT quand il n'y a rien à lire (la popup l'affiche puis
// ne le garde pas) :
//  - "not-an-offer" : pas d'identifiant d'offre dans l'URL → champs vides, AUCUN
//    lien (l'URL d'une recherche serait une fausse donnée). Y compris quand le
//    panneau montre déjà l'offre PAR DÉFAUT (première de la liste) : au chargement
//    de l'accueil ou d'une recherche, elle s'affiche sans `vjk` dans l'URL (sur
//    l'accueil, `vjk` n'apparaît qu'au premier clic). DÉCISION (2026-10-05) : on ne
//    lit pas cette offre en se fiant au seul en-tête, la garde reste stricte ; le
//    message invite à cliquer l'offre, ce qui ajoute `vjk` ;
//  - "timeout" : l'en-tête n'est pas apparu, ou pas cohérent, à temps → champs
//    vides, avec le lien canonique (l'identifiant est connu et fiable).

export async function extractIndeedOffer() {
  // Bornes miroir de backend/app/limits.py (cf. limits.js : extractOffer et chaque
  // adaptateur dupliquent ces valeurs en dur, une modification se fait partout).
  const FIELD_MAX_LENGTH = 255;
  // Identifiant d'offre : 16 caractères hexadécimaux (tous ceux observés).
  const JOB_ID = /^[0-9a-f]{16}$/i;
  // Lien enregistré = page d'offre seule, construite depuis l'identifiant. VÉRIFIÉ :
  // elle s'ouvre seule à cette adresse. En mode panneau, location.href rouvrirait la
  // recherche (et dépasse souvent la borne de longueur des URL).
  const VIEWJOB_BASE_URL = "https://fr.indeed.com/viewjob?jk=";
  const TIMEOUT_MS = 10000;
  const POLL_INTERVAL_MS = 100;

  const clean = (value) => (value ?? "").replace(/\s+/g, " ").trim();
  const empty = (notice, url = "") => ({
    title: "",
    company: "",
    location: "",
    url,
    source: "extension",
    notice,
  });

  // Page seule : `jk` ; partout ailleurs (liste, accueil), l'offre ouverte dans le
  // panneau est `vjk`. Absent → aucune offre CHOISIE (cf. "not-an-offer" ci-dessus).
  const params = new URLSearchParams(location.search);
  const urlId =
    (location.pathname === "/viewjob" ? params.get("jk") : params.get("vjk")) ?? "";
  if (!JOB_ID.test(urlId)) return empty("not-an-offer");

  // Premier texte non vide d'un élément, dans l'ordre du document. Le rang du lieu
  // vaut soit le lieu seul, soit « <lieu> • Télétravail partiel » en sous-éléments :
  // le lieu est toujours le premier texte.
  function firstText(element) {
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const text = clean(node.textContent);
      if (text) return text;
    }
    return "";
  }

  // Lecture ponctuelle : renvoie l'offre, ou null tant que l'en-tête n'est pas
  // PRÊT et COHÉRENT avec l'URL.
  function readOffer() {
    const header = document.querySelector('[data-testid="desktop-job-header"]');
    const metadata = header?.querySelector('[data-testid="company-info-metadata"]');
    // Le lien vers la page entreprise : garde ET source du nom de l'entreprise (son
    // texte est le nom seul, sans la note « · 3.7 » affichée à côté).
    const companyLink = metadata?.querySelector('a[href*="fromjk="]');
    if (!companyLink) return null;
    const linkedId = new URL(companyLink.href).searchParams.get("fromjk") ?? "";
    if (linkedId.toLowerCase() !== urlId.toLowerCase()) return null;

    const title = clean(
      header.querySelector('[data-testid="vj-job-title"]')?.textContent,
    );
    const company = clean(companyLink.textContent);
    if (!title || !company) return null;

    // Deux rangs : entreprise (avec le lien), puis lieu. Lieu absent → vide (champ
    // facultatif côté backend).
    const rows = [...(metadata.firstElementChild?.children ?? [])];
    const locationRow = rows.find((row) => !row.contains(companyLink));

    return {
      title: title.slice(0, FIELD_MAX_LENGTH),
      company: company.slice(0, FIELD_MAX_LENGTH),
      location: (locationRow ? firstText(locationRow) : "").slice(
        0,
        FIELD_MAX_LENGTH,
      ),
      url: VIEWJOB_BASE_URL + urlId,
      source: "extension",
    };
  }

  // L'en-tête peut ne pas être rendu, ou pas encore celui de l'offre de l'URL, à
  // l'ouverture de la popup : on interroge la page jusqu'à ce qu'il soit prêt, dans
  // la limite du délai. executeScript attend la promesse.
  const deadline = Date.now() + TIMEOUT_MS;
  for (;;) {
    const offer = readOffer();
    if (offer) return offer;
    if (Date.now() >= deadline) return empty("timeout", VIEWJOB_BASE_URL + urlId);
    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
  }
}
