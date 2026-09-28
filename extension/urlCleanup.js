// Nettoyage d'une URL d'offre TROP LONGUE (> MAX_URL_LENGTH, cf. limits.js — le
// miroir de backend/app/limits.py). Appelé UNIQUEMENT au-delà de cette borne :
// une URL déjà sous la limite n'est jamais modifiée, quels que soient les
// paramètres qu'elle porte.
//
// Liste EXPLICITE et RESTRICTIVE : jamais une règle générale du type « tout ce
// qui suit un ? ». Seuls les noms listés ci-dessous sont retirés, tout le reste
// de l'URL (chemin, autres paramètres) reste intact.

// Volontairement MINIMALE : uniquement les paramètres dont on est CERTAIN
// qu'ils sont du suivi marketing pur, sans aucun effet sur la page ciblée
// (attribution publicitaire/email, jamais lus par le rendu ou le routage) —
// vérifié pour ces neuf-là, pas supposé.
//
// Volontairement ABSENTS : tout paramètre spécifique à LinkedIn ou Indeed
// (ex. trackingId, refId, currentJobId). Pas par oubli : sur ces deux sites, une
// URL longue vient surtout de la NAVIGATION INTERNE (identifiant d'offre, tri,
// pagination) et non du suivi marketing — certains de ces paramètres sont
// NÉCESSAIRES pour atteindre l'offre, les retirer casserait le lien plutôt que
// de le raccourcir sans risque. Deviner leurs noms sans les avoir vus sur une
// URL réelle aurait un coût (un lien cassé) largement supérieur au bénéfice
// (quelques dizaines de caractères). Sur ces deux sites, le repli « champ vide
// + message invitant à coller le lien à la main » sera donc probablement le
// comportement le plus fréquent — c'est un résultat ACCEPTÉ, pas un défaut à
// corriger ici.
//
// Pour ÉTENDRE cette liste plus tard (après avoir constaté le problème en
// conditions réelles, pas avant) : n'ajouter qu'un nom de paramètre dont on est
// certain qu'il est un identifiant de suivi PUR, jamais lu par le site pour
// afficher ou router quoi que ce soit. Dans le doute, ne pas l'ajouter — un
// champ vide avec message est un filet de sécurité sans risque ; une URL
// mutilée qui a l'air valide n'en est pas un.
export const TRACKING_PARAMS = [
  "utm_source",
  "utm_medium",
  "utm_campaign",
  "utm_term",
  "utm_content",
  "gclid",
  "fbclid",
  "mc_cid",
  "mc_eid",
];

/**
 * Retire les paramètres de TRACKING_PARAMS d'une URL, sans toucher au reste
 * (chemin, autres paramètres, fragment). Renvoie l'URL telle quelle si elle
 * n'est pas parsable (ne devrait pas arriver : `url` vient de `location.href`
 * dans une page déjà chargée par le navigateur).
 */
export function stripTrackingParams(url) {
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    return url;
  }
  for (const param of TRACKING_PARAMS) {
    parsed.searchParams.delete(param);
  }
  return parsed.toString();
}
