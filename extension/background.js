// Service worker de l'extension (Manifest V3).
//
// Flux quand l'utilisateur clique sur l'icône :
//   1. On injecte extractOffer() dans la page active (lecture seule du DOM)
//   2. On récupère le résultat ici, dans le contexte de l'extension
//   3. On POST vers l'API depuis ce contexte → pas soumis à la CSP du site
//
// Pourquoi ce détour ? Un fetch lancé depuis la page elle-même serait soumis
// aux règles de sécurité (CSP/CORS) du site visité. Le service worker, lui,
// n'obéit qu'au manifest (host_permissions).

const API_URL = "http://127.0.0.1:8000/applications";

// --- Étape 1 : la fonction injectée dans la page ---
// ATTENTION : cette fonction est sérialisée puis exécutée DANS la page.
// Elle ne peut donc utiliser aucune variable extérieure (pas de API_URL ici).
function extractOffer() {
  // Extraction générique V1 : titre de page + URL.
  // TODO chantier suivant : extracteurs spécifiques par site, par exemple
  //   if (location.hostname.includes("welcometothejungle.com")) { ... }
  // en lisant les balises structurées (JSON-LD type JobPosting, og:title...)
  const jsonLd = document.querySelector('script[type="application/ld+json"]');
  let structured = null;
  if (jsonLd) {
    try {
      const data = JSON.parse(jsonLd.textContent);
      // Certains sites mettent un tableau, d'autres un objet
      const posting = Array.isArray(data)
        ? data.find((d) => d["@type"] === "JobPosting")
        : data["@type"] === "JobPosting"
          ? data
          : null;
      if (posting) {
        structured = {
          title: posting.title,
          company: posting.hiringOrganization?.name,
          location:
            posting.jobLocation?.address?.addressLocality ??
            posting.jobLocation?.[0]?.address?.addressLocality,
        };
      }
    } catch (_) {
      /* JSON-LD illisible : on retombe sur le générique */
    }
  }

  return {
    title: (structured?.title ?? document.title).slice(0, 255),
    company: (structured?.company ?? "À compléter").slice(0, 255),
    location: structured?.location ?? null,
    url: location.href,
    source: "extension",
  };
}

// --- Étapes 2 et 3 : au clic sur l'icône ---
chrome.action.onClicked.addListener(async (tab) => {
  try {
    const [{ result: offer }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: extractOffer,
    });

    const response = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(offer),
    });

    await notify(tab.id, response.ok ? "✅ Offre ajoutée au cockpit !" : `❌ Erreur API : ${response.status}`);
  } catch (err) {
    await notify(tab.id, `❌ ${err.message} — le backend tourne ?`);
  }
});

// Petit feedback visuel injecté dans la page (toast éphémère).
function notify(tabId, message) {
  return chrome.scripting.executeScript({
    target: { tabId },
    args: [message],
    func: (msg) => {
      const el = document.createElement("div");
      el.textContent = msg;
      el.style.cssText =
        "position:fixed;top:16px;right:16px;z-index:99999;padding:12px 16px;" +
        "background:#1e293b;color:#fff;border-radius:8px;font:14px sans-serif;" +
        "box-shadow:0 4px 12px rgba(0,0,0,.3)";
      document.body.appendChild(el);
      setTimeout(() => el.remove(), 3000);
    },
  });
}
