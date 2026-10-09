# Partage de session site → extension (`externally_connectable`)
Mécanisme PRÉVU pour l'extension 1.2.0, pas encore implémenté : le code actuel
(popup avec formulaire de connexion, URL de l'API sur le domaine Railway) ne suit
pas encore ce document. Avancement : feuille de route du CLAUDE.md racine. Une fois
livré, ce document reste la référence du mécanisme : retirer alors ce paragraphe.

# Principe
- L'extension est un REFLET de la session du site : on se connecte et se déconnecte
  sur le site, qui transmet sa session à l'extension. L'extension n'a plus aucun
  écran de connexion.

# Décisions
- Manifeste : `externally_connectable` limité à l'hôte EXACT du frontend
  (`cockpitemploi.fr`), sans joker (ni sous-domaines, ni `<all_urls>`) et SANS champ
  `ids` (aucune autre extension ne peut s'y connecter). Toute page autorisée là
  pourrait pousser une session : la liste reste réduite au seul site.
- Canal à SENS UNIQUE : le site pousse, l'extension ne renvoie JAMAIS le jeton
  (aucun message ne permet de le lire depuis une page).
- Deux messages seulement : `session:set` (le site transmet le jeton) et
  `session:clear` (le site signale la déconnexion). Format exact des messages : à
  fixer à l'audit du code.
- Écouteur dans le service worker EXISTANT (`background.js`), pas dans un nouveau
  script. Avant tout traitement : vérifier `sender.origin` (origine exacte du
  frontend) ; le jeton est VALIDÉ avant d'être stocké (forme de la validation : à
  fixer à l'audit du code).
- Popup : formulaire de connexion et bouton de déconnexion SUPPRIMÉS, remplacés par
  un bouton qui ouvre la page de connexion du site.
- Manifeste construit avec les seuls domaines DÉFINITIFS : `host_permissions` vers
  `api.cockpitemploi.fr` (et l'URL d'`api.js` alignée, cf. extension/CLAUDE.md).
  Le changement d'hôte déclenchera un avertissement de permission à la mise à jour :
  accepté, car il n'y a pas encore d'utilisateurs.
- Script d'empaquetage Python à deux cibles :
  - `dev` : sortie dans un dossier ignoré par Git, valeurs `localhost` (remplace la
    bascule manuelle d'URL, jamais committée, décrite dans extension/CLAUDE.md) ;
  - `store` : paquet construit à partir d'une liste EXPLICITE de fichiers ; échec
    s'il reste une occurrence de `localhost` ou de `railway`.

# Conséquence sur le domaine
- La publication de la 1.2.0 conditionne le retrait du domaine Railway de l'API
  (cf. `dev-docs/domain.md`, « Transition »).
