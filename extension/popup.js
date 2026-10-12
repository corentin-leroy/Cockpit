// Logique de la popup (module ES). Deux états :
//   (a) non connecté  → bouton « Se connecter sur Cockpit », qui ouvre la page
//                        de connexion du site dans un nouvel onglet ;
//   (b) connecté      → « Connecté en tant que <email> », extraction de l'offre
//                        → formulaire de CORRECTION pré-rempli → « Ajouter au
//                        cockpit ».
//
// Séparation des rôles :
// - la popup ne se connecte plus : la session vient du site (session:set, reçu
//   et validé par le service worker, cf. background.js), et la déconnexion se fait
//   aussi sur le site. La popup ne fait que LIRE la session (storage.js) ;
// - l'extraction et le POST /applications passent par le service worker
//   (messages EXTRACT_OFFER / GET_BOARDS / ADD_OFFER), qui agit hors CSP du site
//   visité.
//
// On ne poste jamais l'extraction brute. Elle pré-remplit le formulaire ; c'est
// l'utilisateur qui valide/complète, puis on poste les données DU FORMULAIRE.

import { SITE_ORIGIN } from "./config.js";
import {
  getToken,
  getEmail,
  clearSession,
  getLastBoardId,
  setLastBoardId,
} from "./storage.js";
import {
  TITLE_MAX_LENGTH,
  COMPANY_MAX_LENGTH,
  LOCATION_MAX_LENGTH,
  URL_MAX_LENGTH,
} from "./limits.js";

const loadingEl = document.getElementById("loading");
const loggedOutEl = document.getElementById("logged-out");
const loggedInEl = document.getElementById("logged-in");
const messageEl = document.getElementById("message");

const openLoginBtn = document.getElementById("open-login-btn");
const accountEl = document.getElementById("account");

const extractStatusEl = document.getElementById("extract-status");
const offerFormEl = document.getElementById("offer-form");
const titleEl = document.getElementById("f-title");
const companyEl = document.getElementById("f-company");
const locationEl = document.getElementById("f-location");
const urlEl = document.getElementById("f-url");
const boardFieldEl = document.getElementById("board-field");
const boardSelectEl = document.getElementById("f-board");
const addBtn = document.getElementById("add-btn");

// Message commun aux deux 401 (chargement des tableaux, ajout) : la reconnexion
// se fait sur le site, la popup n'a plus de formulaire.
const SESSION_EXPIRED_MESSAGE = "Session expirée : reconnectez-vous sur le site Cockpit.";

// Bornes posées PAR CODE (miroir du backend, cf. limits.js) plutôt qu'en dur
// dans popup.html : un fichier réellement appliqué, pas une documentation qu'on
// pourrait oublier de tenir à jour.
titleEl.maxLength = TITLE_MAX_LENGTH;
companyEl.maxLength = COMPANY_MAX_LENGTH;
locationEl.maxLength = LOCATION_MAX_LENGTH;
urlEl.maxLength = URL_MAX_LENGTH;

// Offre extraite courante : on la conserve pour préserver les champs non éditables
// (source) et l'url même si l'utilisateur ne la touche pas — au moment de l'envoi,
// les valeurs du formulaire sont fusionnées PAR-DESSUS cet objet.
let currentOffer = null;

// Tableaux de l'utilisateur et tableau de destination choisi. board_id part
// TOUJOURS de selectedBoardId (même quand le déroulant est masqué, cas d'un seul
// tableau) : c'est ce qui répare l'ajout (POST /applications exige un board_id).
let boards = [];
let selectedBoardId = null;

/** Affiche un message d'info/erreur/succès sous les boutons. */
function showMessage(text, kind = "") {
  messageEl.textContent = text;
  messageEl.className = kind;
}

/**
 * Affiche « Connecté en tant que <email> », ou masque la ligne si l'email est
 * inconnu (jeton stocké par la popup de la 1.1.0, avant l'email) : jamais de ligne
 * vide ni « undefined ». textContent uniquement, jamais innerHTML.
 */
function renderAccount(email) {
  accountEl.replaceChildren();
  if (typeof email !== "string" || email === "") {
    accountEl.hidden = true;
    return;
  }
  const emailSpan = document.createElement("span");
  emailSpan.className = "account__email";
  emailSpan.textContent = email;
  accountEl.append("Connecté en tant que ", emailSpan);
  accountEl.hidden = false;
}

/** Bascule l'affichage entre les deux états (et efface le message). */
function render(isAuthenticated, email = null) {
  loadingEl.style.display = "none";
  loggedOutEl.style.display = isAuthenticated ? "none" : "block";
  loggedInEl.style.display = isAuthenticated ? "block" : "none";
  renderAccount(isAuthenticated ? email : null);
  showMessage("");
}

/** Active « Ajouter » seulement si title et company sont non vides (comme le backend). */
function refreshAddButton() {
  const valid = titleEl.value.trim() !== "" && companyEl.value.trim() !== "";
  addBtn.disabled = !valid;
}

/**
 * Demande l'extraction au service worker et pré-remplit le formulaire.
 * Appelée à chaque entrée dans l'état connecté (ouverture de la popup).
 */
async function startExtraction() {
  currentOffer = null;
  offerFormEl.style.display = "none";
  extractStatusEl.style.display = "block";
  extractStatusEl.textContent = "Lecture de l'offre…";
  showMessage("");

  let offer;
  try {
    const result = await chrome.runtime.sendMessage({ type: "EXTRACT_OFFER" });
    // Même si l'extraction échoue, on ouvre un formulaire vide : l'utilisateur
    // peut toujours saisir l'offre à la main.
    offer = result?.ok ? result.offer : {};
    if (!result?.ok) {
      showMessage("Extraction impossible : saisie manuelle.", "error");
    }
  } catch (err) {
    offer = {};
    showMessage(`Extraction impossible : ${err.message}`, "error");
  }

  // `notice` (adaptateurs) ne sert qu'à CE message : on ne la garde pas dans
  // currentOffer, qui est fusionné dans ce que l'on envoie à l'API.
  const { notice, ...extractedOffer } = offer;
  currentOffer = extractedOffer;
  offer = extractedOffer;
  titleEl.value = offer.title ?? "";
  companyEl.value = offer.company ?? "";
  locationEl.value = offer.location ?? "";
  urlEl.value = offer.url ?? "";

  // L'extraction a RÉUSSI (title/company/location sont là) ; seule l'URL a dû
  // être écartée (trop longue même après nettoyage — cf. background.js). Pas de
  // variante "error" (pas de ⚠) : ce n'est pas un échec global, la candidature
  // pourra être ajoutée sans son lien, à compléter à la main si l'utilisateur le
  // souhaite.
  if (offer.urlTooLong) {
    showMessage("Lien trop long : collez-le manuellement dans le champ ci-dessus si besoin.");
  }

  // Rien à lire (adaptateur) : formulaire vide, message neutre — ni « error » ni ⚠,
  // ce n'est pas un échec de l'extension. Champs vides plutôt que préremplis avec
  // le titre d'une liste : ce serait enregistrer de fausses données.
  if (notice === "not-an-offer") {
    showMessage("Ouvrez une offre pour l'ajouter.");
  } else if (notice === "timeout") {
    showMessage("L'offre n'a pas fini de s'afficher : rouvrez l'extension dans un instant.");
  }

  extractStatusEl.style.display = "none";
  offerFormEl.style.display = "block";
  refreshAddButton();

  // Ergonomie : focus sur le premier champ pour une correction immédiate au clavier.
  titleEl.focus();
  titleEl.select();
}

/** Remplit le déroulant des tableaux et applique la règle de complexité progressive. */
function populateBoardSelect() {
  boardSelectEl.innerHTML = "";
  for (const board of boards) {
    const option = document.createElement("option");
    option.value = String(board.id);
    option.textContent = board.name;
    boardSelectEl.appendChild(option);
  }
  boardSelectEl.value = String(selectedBoardId);
  // Complexité progressive : on ne propose de CHOISIR que s'il y a plusieurs
  // tableaux. Avec un seul, le déroulant reste masqué (l'offre y va sans choix).
  boardFieldEl.style.display = boards.length > 1 ? "block" : "none";
}

/**
 * Charge les tableaux (via le service worker) et détermine le tableau
 * pré-sélectionné. Renvoie true si tout est prêt, false si l'ajout ne peut pas
 * se faire (401 → état non connecté ; erreur réseau → message). Dans ces deux
 * cas de false, l'UI a déjà été mise à jour ici.
 */
async function loadBoards() {
  const result = await chrome.runtime.sendMessage({ type: "GET_BOARDS" });

  if (result?.ok) {
    boards = result.boards ?? [];
    if (boards.length === 0) {
      // Ne devrait pas arriver (le backend garantit au moins un tableau), mais on
      // évite un POST sans board_id qui échouerait en 422.
      showMessage("Aucun tableau disponible.", "error");
      return false;
    }

    // Pré-sélection (repli inclus) : dernier tableau mémorisé s'il existe ENCORE
    // dans la liste, sinon le premier. Le find neutralise un id périmé (tableau
    // supprimé depuis le dernier ajout).
    const lastId = await getLastBoardId();
    const remembered =
      lastId != null && boards.find((b) => b.id === Number(lastId));
    selectedBoardId = remembered ? remembered.id : boards[0].id;

    populateBoardSelect();
    return true;
  }

  // Token expiré/invalide : le service worker a déjà purgé la session. On
  // rebascule vers l'état non connecté (cohérent avec l'ajout). On NE ferme PAS
  // la popup.
  if (result?.status === 401) {
    await clearSession();
    render(false);
    showMessage(SESSION_EXPIRED_MESSAGE, "error");
    return false;
  }

  showMessage(`${result?.error || "Impossible de charger les tableaux."}`, "error");
  return false;
}

/**
 * Entrée dans l'état connecté : on charge d'abord les tableaux (nécessaires au
 * board_id, et détecte un 401 d'emblée) ; seulement si c'est bon, on lance
 * l'extraction qui affiche le formulaire de correction.
 */
async function enterConnectedState(email) {
  render(true, email);
  const ready = await loadBoards();
  if (!ready) return;
  startExtraction();
}

// Changement de tableau de destination dans le déroulant.
boardSelectEl.addEventListener("change", () => {
  selectedBoardId = Number(boardSelectEl.value);
});

// --- État (a) : ouvrir la connexion du site ---
// Nouvel onglet sur /login (la popup se ferme d'elle-même en perdant le focus).
// Déjà connecté sur le site, /login renvoie vers le kanban, dont le chargement
// transmet la session à l'extension. chrome.tabs.create n'exige pas la
// permission « tabs ».
openLoginBtn.addEventListener("click", () => {
  chrome.tabs.create({ url: `${SITE_ORIGIN}/login` });
});

// Validation cliente en direct : title et company non vides.
titleEl.addEventListener("input", refreshAddButton);
companyEl.addEventListener("input", refreshAddButton);

// --- État (b) : envoi des données DU FORMULAIRE ---
offerFormEl.addEventListener("submit", async (event) => {
  event.preventDefault();

  const title = titleEl.value.trim();
  const company = companyEl.value.trim();
  if (!title || !company) {
    showMessage("L'intitulé et l'entreprise sont obligatoires.", "error");
    return;
  }
  if (selectedBoardId == null) {
    // Garde-fou : sans tableau cible, le POST échouerait (422). En pratique
    // loadBoards a déjà bloqué ce cas avant d'afficher le formulaire.
    showMessage("Aucun tableau sélectionné.", "error");
    return;
  }

  // Fusion par-dessus l'offre extraite : conserve l'url (même non modifiée) et
  // marque la source comme « extension » même si l'extraction avait échoué.
  // board_id : tableau de destination choisi (ou l'unique tableau).
  const offer = {
    ...currentOffer,
    board_id: selectedBoardId,
    title,
    company,
    location: locationEl.value.trim() || null,
    url: urlEl.value.trim() || null,
    source: "extension",
  };

  showMessage("Ajout en cours…");
  addBtn.disabled = true;

  let succeeded = false;
  try {
    const result = await chrome.runtime.sendMessage({ type: "ADD_OFFER", offer });

    if (result?.ok) {
      succeeded = true;
      // Mémorise le tableau choisi pour le pré-sélectionner au prochain ajout.
      await setLastBoardId(selectedBoardId);
      showMessage("Offre ajoutée au cockpit !", "success");
      // Laisse le message de succès visible un court instant, puis referme la
      // popup : ~900 ms est assez long pour lire le message de confirmation
      // (perçu comme un accusé de réception) sans faire attendre, et assez court
      // pour que l'ajout reste « en un geste ». On garde le bouton désactivé
      // jusqu'à la fermeture pour éviter un double envoi accidentel pendant ce
      // délai.
      setTimeout(() => window.close(), 900);
      return;
    }

    // Token expiré/invalide : le service worker a déjà purgé la session ; on
    // rebascule la popup vers l'état non connecté. On NE ferme PAS la popup.
    if (result?.status === 401) {
      await clearSession();
      render(false);
      showMessage(SESSION_EXPIRED_MESSAGE, "error");
      return;
    }

    showMessage(`${result?.error || "Échec de l'ajout."}`, "error");
  } catch (err) {
    showMessage(`${err.message}`, "error");
  } finally {
    // En cas d'échec seulement : réactive selon la validité courante pour pouvoir
    // réessayer. En cas de succès, on laisse le bouton désactivé (popup en cours
    // de fermeture).
    if (!succeeded) refreshAddButton();
  }
});

// --- Au chargement de la popup : choisir l'état selon la présence d'un token ---
// (l'email peut manquer : renderAccount masque alors sa ligne)
(async () => {
  const [token, email] = await Promise.all([getToken(), getEmail()]);
  if (token) {
    enterConnectedState(email);
  } else {
    render(false);
  }
})();
