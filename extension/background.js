// Service worker de l'extension (Manifest V3), chargé comme module ES
// ("type": "module" dans le manifest) pour pouvoir importer la couche API.
//
// Deux canaux de messages :
//
// 1. Popup → service worker (chrome.runtime.onMessage). Le clic sur l'icône ouvre
//    la popup (action.default_popup), qui pilote trois opérations :
//    - EXTRACT_OFFER : injecter l'extraction dans la page active et renvoyer le
//      résultat à la popup, SANS rien poster (elle pré-remplit un formulaire) ;
//    - GET_BOARDS    : renvoyer les tableaux de l'utilisateur ;
//    - ADD_OFFER     : poster vers l'API les données VALIDÉES par l'utilisateur.
//    Pourquoi passer par le service worker plutôt que la page ? L'injection et le
//    POST se font depuis le contexte de l'extension → pas soumis à la CSP du site.
//
// 2. Site Cockpit → service worker (chrome.runtime.onMessageExternal), partage de
//    session : session:set et session:clear. Canal à SENS UNIQUE, le jeton ne
//    repart jamais vers une page. Décisions : dev-docs/extension-session-sharing.md.

import { findAdapter } from "./adapters/index.js";
import { getBoards, createApplication, fetchCurrentUser } from "./api.js";
import { SITE_ORIGIN } from "./config.js";
import { URL_MAX_LENGTH } from "./limits.js";
import { getToken, getEmail, setSession, clearSession } from "./storage.js";
import { stripTrackingParams } from "./urlCleanup.js";

// --- La fonction injectée dans la page ---
// ATTENTION : cette fonction est sérialisée puis exécutée DANS la page.
// Elle ne peut donc utiliser aucune variable extérieure.
// Extraction GÉNÉRIQUE : utilisée sur tout site sans adaptateur dédié (cf.
// adapters/index.js, qui choisit l'extracteur d'après l'hôte de l'onglet).
function extractOffer() {
  // Ordre de fallback (inchangé) : JSON-LD JobPosting d'abord, repli générique
  // sur le titre de page ensuite. Ce résultat n'est plus posté tel quel : il
  // PRÉ-REMPLIT le formulaire de la popup, que l'utilisateur corrige avant envoi.

  // Cherche récursivement une entité JobPosting dans une valeur JSON-LD. Une page
  // peut exposer PLUSIEURS blocs (HelloWork : WebSite, Organization, Breadcrumb,
  // puis JobPosting), et un même bloc peut être un objet, un tableau, ou un objet
  // à `@graph` imbriquant plusieurs entités. `@type` est parfois un tableau.
  function findJobPosting(value) {
    if (!value || typeof value !== "object") return null;
    const nodes = Array.isArray(value) ? value : [value];
    for (const node of nodes) {
      if (!node || typeof node !== "object") continue;
      const type = node["@type"];
      if (type === "JobPosting" || (Array.isArray(type) && type.includes("JobPosting"))) {
        return node;
      }
      if (Array.isArray(node["@graph"])) {
        const nested = findJobPosting(node["@graph"]);
        if (nested) return nested;
      }
    }
    return null;
  }

  // Parcourt TOUS les blocs et s'arrête au premier JobPosting trouvé. Un bloc mal
  // formé (JSON.parse qui échoue) est ignoré, sans interrompre les suivants.
  let posting = null;
  for (const block of document.querySelectorAll(
    'script[type="application/ld+json"]',
  )) {
    let data;
    try {
      data = JSON.parse(block.textContent);
    } catch (_) {
      continue;
    }
    posting = findJobPosting(data);
    if (posting) break;
  }

  let structured = null;
  if (posting) {
    // hiringOrganization : objet { name } le plus souvent, parfois une chaîne.
    const org = posting.hiringOrganization;
    // jobLocation : objet unique ou tableau (offre multi-sites) → on prend le 1er.
    const jobLocation = Array.isArray(posting.jobLocation)
      ? posting.jobLocation[0]
      : posting.jobLocation;
    structured = {
      title: posting.title,
      company: typeof org === "string" ? org : org?.name,
      location: jobLocation?.address?.addressLocality,
    };
  }

  // Champs non trouvés → chaîne vide (et non un placeholder « À compléter ») :
  // le formulaire les montre vides et la validation cliente force l'utilisateur
  // à les renseigner, plutôt que d'enregistrer une donnée factice.
  return {
    title: (structured?.title ?? document.title ?? "").slice(0, 255),
    company: (structured?.company ?? "").slice(0, 255),
    location: (structured?.location ?? "").slice(0, 255),
    url: location.href,
    source: "extension",
  };
}

/**
 * Ramène `offer.url` sous URL_MAX_LENGTH si besoin (mutation en place).
 *
 * En dessous de la borne : rien ne change, quels que soient les paramètres
 * portés par l'URL. Au-delà : on retire d'abord les paramètres de suivi connus
 * (urlCleanup.js) ; si ça ne suffit pas — fréquent sur LinkedIn/Indeed, où la
 * longueur vient surtout de la navigation interne (identifiant d'offre, tri,
 * pagination) et non du suivi marketing — on laisse le champ VIDE plutôt que de
 * poster un lien tronqué et cassé. `offer.urlTooLong` signale ce cas à la popup,
 * qui invite alors à coller le lien à la main.
 */
function shortenUrlIfNeeded(offer) {
  if (!offer.url || offer.url.length <= URL_MAX_LENGTH) return;

  const cleaned = stripTrackingParams(offer.url);
  if (cleaned.length <= URL_MAX_LENGTH) {
    offer.url = cleaned;
  } else {
    offer.url = "";
    offer.urlTooLong = true;
  }
}

/**
 * Extrait l'offre de l'onglet actif (sans rien poster).
 * Renvoie { ok: true, offer } ou { ok: false, error } pour l'affichage popup.
 */
async function handleExtractOffer() {
  try {
    const [tab] = await chrome.tabs.query({
      active: true,
      currentWindow: true,
    });
    if (!tab?.id) {
      return { ok: false, error: "Aucun onglet actif." };
    }

    // Extracteur selon le site (cf. adapters/index.js) : un adaptateur dédié si
    // l'hôte de l'onglet en a un, sinon extractOffer, INCHANGÉE. activeTab donne
    // accès à tab.url ; sans lui, findAdapter(undefined) renvoie null → générique.
    const extract = findAdapter(tab.url)?.extract ?? extractOffer;

    // activeTab (accordé à l'ouverture de la popup par clic) autorise l'injection
    // dans l'onglet courant sans host_permission sur chaque site. Une fonction
    // asynchrone est attendue par executeScript (adaptateur France Travail).
    const [{ result: offer }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: extract,
    });
    // Hors du contexte sandboxé (contrairement à extractOffer ci-dessus) : peut
    // importer librement, d'où le nettoyage ICI plutôt que dans extractOffer.
    shortenUrlIfNeeded(offer);
    return { ok: true, offer };
  } catch (err) {
    return { ok: false, error: err.message };
  }
}

/**
 * Récupère les tableaux de l'utilisateur pour alimenter le choix dans la popup.
 * Renvoie { ok: true, boards } ou { ok: false, status, error } ; status permet à
 * la popup de distinguer le 401 (→ reconnexion).
 */
async function handleGetBoards() {
  try {
    const boards = await getBoards();
    return { ok: true, boards };
  } catch (err) {
    return { ok: false, status: err.status, error: err.message };
  }
}

/**
 * Poste au cockpit les données VALIDÉES par l'utilisateur (celles du formulaire,
 * pas l'extraction brute). Renvoie un résultat structuré ; err.status permet à
 * la popup de distinguer le 401 (→ reconnexion).
 */
async function handleCreateApplication(offer) {
  try {
    const application = await createApplication(offer);
    return { ok: true, application };
  } catch (err) {
    return { ok: false, status: err.status, error: err.message };
  }
}

// Canal popup → service worker. On renvoie true pour signaler une réponse
// asynchrone (sendResponse sera appelé après l'opération).
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "EXTRACT_OFFER") {
    handleExtractOffer().then(sendResponse);
    return true;
  }
  if (message?.type === "GET_BOARDS") {
    handleGetBoards().then(sendResponse);
    return true;
  }
  if (message?.type === "ADD_OFFER") {
    handleCreateApplication(message.offer).then(sendResponse);
    return true;
  }
});

// --- Partage de session avec le site (session:set / session:clear) ---

// Compteur de GÉNÉRATION : « le dernier message reçu gagne ». Chaque message du
// site l'incrémente DÈS SON ARRIVÉE (de façon synchrone, avant toute attente).
// Un session:set retient son numéro et, après chaque attente (lecture du stockage,
// appel à /auth/me), abandonne avec { ok: false } si un message plus récent est
// arrivé entre-temps : ni un clear (déconnexion pendant la validation), ni un set
// plus récent (reconnexion rapide) ne peuvent être écrasés par un set dépassé.
// En mémoire : un service worker relancé repart à 0, sans risque, puisqu'aucune
// validation n'est alors en cours.
let sessionGeneration = 0;

/**
 * Valide le jeton reçu du site puis le stocke avec l'email du compte.
 * Renvoie { ok: true } si la session est stockée (ou l'était déjà), sinon
 * { ok: false } : jeton refusé, panne réseau, réponse sans email, ou message
 * dépassé par un plus récent. Dans tous les cas d'échec, RIEN n'est écrit (la
 * session précédente reste intacte) ; le site renverra au prochain chargement.
 */
async function handleSessionSet(token, generation) {
  try {
    const [storedToken, storedEmail] = await Promise.all([getToken(), getEmail()]);
    if (generation !== sessionGeneration) return { ok: false };

    // Raccourci : même jeton ET email déjà là → rien à valider (évite un /auth/me
    // à chaque chargement du site). Sans email (jeton venu de la popup de la 1.1.0),
    // on passe par /auth/me, qui le complète.
    if (token === storedToken && storedEmail) return { ok: true };

    const user = await fetchCurrentUser(token);
    if (generation !== sessionGeneration) return { ok: false };
    if (typeof user?.email !== "string" || user.email === "") return { ok: false };

    // Aucune attente entre le contrôle ci-dessus et cet appel : un message arrivé
    // juste après est mis en file DERRIÈRE cette écriture dans chrome.storage, et
    // c'est donc lui qui s'applique en dernier.
    await setSession(token, user.email);
    return { ok: true };
  } catch {
    // 401 (ApiError) ou panne réseau (TypeError) : rien n'est stocké.
    return { ok: false };
  }
}

/** Efface la session, sans condition. */
async function handleSessionClear() {
  try {
    await clearSession();
    return { ok: true };
  } catch {
    return { ok: false };
  }
}

// Canal site → service worker. Ordre des contrôles, AVANT tout traitement :
// 1. origine EXACTE du site (sender.origin), 2. type parmi les deux attendus,
// 3. pour session:set, jeton en chaîne non vide. Tout autre message est ignoré
// sans réponse. La réponse au site n'est jamais que { ok } : ni jeton, ni email.
chrome.runtime.onMessageExternal.addListener((message, sender, sendResponse) => {
  if (sender.origin !== SITE_ORIGIN) return;

  if (message?.type === "session:clear") {
    sessionGeneration += 1;
    handleSessionClear().then(sendResponse);
    return true;
  }

  if (message?.type === "session:set") {
    if (typeof message.token !== "string" || message.token === "") return;
    sessionGeneration += 1;
    handleSessionSet(message.token, sessionGeneration).then(sendResponse);
    return true;
  }
});
