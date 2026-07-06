// Logique de la popup (module ES). Deux états :
//   (a) non connecté  → formulaire email/mot de passe → POST /auth/login ;
//   (b) connecté      → extraction de l'offre → formulaire de CORRECTION
//                        pré-rempli → « Ajouter au cockpit ».
//
// Séparation des rôles :
// - la popup fait le login (contexte extension, hors CSP d'un site) et stocke
//   le token via storage.js ;
// - l'extraction et le POST /applications passent par le service worker
//   (messages EXTRACT_OFFER / ADD_OFFER), qui agit hors CSP du site visité.
//
// Point clé de cette version : on ne poste plus l'extraction brute. Elle
// pré-remplit le formulaire ; c'est l'utilisateur qui valide/complète, puis on
// poste les données DU FORMULAIRE.

import { getToken, setToken, clearToken } from "./storage.js";
import { login } from "./api.js";

const loadingEl = document.getElementById("loading");
const loggedOutEl = document.getElementById("logged-out");
const loggedInEl = document.getElementById("logged-in");
const messageEl = document.getElementById("message");

const emailEl = document.getElementById("email");
const passwordEl = document.getElementById("password");
const loginBtn = document.getElementById("login-btn");

const extractStatusEl = document.getElementById("extract-status");
const offerFormEl = document.getElementById("offer-form");
const titleEl = document.getElementById("f-title");
const companyEl = document.getElementById("f-company");
const locationEl = document.getElementById("f-location");
const urlEl = document.getElementById("f-url");
const addBtn = document.getElementById("add-btn");
const logoutBtn = document.getElementById("logout-btn");

// Offre extraite courante : on la conserve pour préserver les champs non éditables
// (source) et l'url même si l'utilisateur ne la touche pas — au moment de l'envoi,
// les valeurs du formulaire sont fusionnées PAR-DESSUS cet objet.
let currentOffer = null;

/** Affiche un message d'info/erreur/succès sous les boutons. */
function showMessage(text, kind = "") {
  messageEl.textContent = text;
  messageEl.className = kind;
}

/** Bascule l'affichage entre les deux états (et efface le message). */
function render(isAuthenticated) {
  loadingEl.style.display = "none";
  loggedOutEl.style.display = isAuthenticated ? "none" : "block";
  loggedInEl.style.display = isAuthenticated ? "block" : "none";
  showMessage("");
}

/** Active « Ajouter » seulement si title et company sont non vides (comme le backend). */
function refreshAddButton() {
  const valid = titleEl.value.trim() !== "" && companyEl.value.trim() !== "";
  addBtn.disabled = !valid;
}

/**
 * Demande l'extraction au service worker et pré-remplit le formulaire.
 * Appelée à chaque entrée dans l'état connecté (ouverture popup / login réussi).
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

  currentOffer = offer;
  titleEl.value = offer.title ?? "";
  companyEl.value = offer.company ?? "";
  locationEl.value = offer.location ?? "";
  urlEl.value = offer.url ?? "";

  extractStatusEl.style.display = "none";
  offerFormEl.style.display = "block";
  refreshAddButton();

  // Ergonomie : focus sur le premier champ pour une correction immédiate au clavier.
  titleEl.focus();
  titleEl.select();
}

// --- État (a) : connexion ---
loggedOutEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  showMessage("");

  const email = emailEl.value.trim();
  const password = passwordEl.value;
  if (!email || !password) {
    showMessage("Renseignez votre email et votre mot de passe.", "error");
    return;
  }

  loginBtn.disabled = true;
  loginBtn.textContent = "Connexion…";
  try {
    const { access_token: token } = await login(email, password);
    await setToken(token);
    passwordEl.value = "";
    render(true);
    startExtraction();
  } catch (err) {
    // 401 : identifiants invalides. Le backend renvoie déjà un message générique.
    showMessage(err.message || "Échec de la connexion.", "error");
  } finally {
    loginBtn.disabled = false;
    loginBtn.textContent = "Se connecter";
  }
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

  // Fusion par-dessus l'offre extraite : conserve l'url (même non modifiée) et
  // marque la source comme « extension » même si l'extraction avait échoué.
  const offer = {
    ...currentOffer,
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
      showMessage("✅ Offre ajoutée au cockpit !", "success");
      // Laisse le message de succès visible un court instant, puis referme la
      // popup : ~900 ms est assez long pour lire le ✅ (perçu comme un accusé de
      // réception) sans faire attendre, et assez court pour que l'ajout reste
      // « en un geste ». On garde le bouton désactivé jusqu'à la fermeture pour
      // éviter un double envoi accidentel pendant ce délai.
      setTimeout(() => window.close(), 900);
      return;
    }

    // Token expiré/invalide : le service worker a déjà purgé le token ; on
    // rebascule la popup vers l'état non connecté. On NE ferme PAS la popup.
    if (result?.status === 401) {
      await clearToken();
      render(false);
      showMessage("Session expirée, reconnectez-vous.", "error");
      return;
    }

    showMessage(`❌ ${result?.error || "Échec de l'ajout."}`, "error");
  } catch (err) {
    showMessage(`❌ ${err.message}`, "error");
  } finally {
    // En cas d'échec seulement : réactive selon la validité courante pour pouvoir
    // réessayer. En cas de succès, on laisse le bouton désactivé (popup en cours
    // de fermeture).
    if (!succeeded) refreshAddButton();
  }
});

// --- Déconnexion ---
logoutBtn.addEventListener("click", async () => {
  await clearToken();
  currentOffer = null;
  render(false);
});

// --- Au chargement de la popup : choisir l'état selon la présence d'un token ---
(async () => {
  const token = await getToken();
  render(Boolean(token));
  if (token) startExtraction();
})();
