// Service worker de l'extension (Manifest V3), chargé comme module ES
// ("type": "module" dans le manifest) pour pouvoir importer la couche API.
//
// Le clic sur l'icône ouvre la popup (action.default_popup). La popup pilote
// deux opérations, via deux messages distincts :
//   - EXTRACT_OFFER : injecter l'extraction dans la page active et renvoyer le
//     résultat à la popup, SANS rien poster (elle pré-remplit un formulaire) ;
//   - ADD_OFFER     : poster vers l'API les données VALIDÉES par l'utilisateur.
//
// Pourquoi passer par le service worker plutôt que la page ? L'injection et le
// POST se font depuis le contexte de l'extension → pas soumis à la CSP du site.

import { getBoards, createApplication } from "./api.js";

// --- La fonction injectée dans la page ---
// ATTENTION : cette fonction est sérialisée puis exécutée DANS la page.
// Elle ne peut donc utiliser aucune variable extérieure.
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
    location: structured?.location ?? "",
    url: location.href,
    source: "extension",
  };
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

    // activeTab (accordé à l'ouverture de la popup par clic) autorise l'injection
    // dans l'onglet courant sans host_permission sur chaque site.
    const [{ result: offer }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: extractOffer,
    });
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
