# Suppression de compte (droit à l'effacement, RGPD)
- DELETE /auth/me (authentifié) supprime définitivement le compte courant et,
  par cascade, ses tableaux, leurs candidatures et ses jetons de sécurité. C'est
  un EFFACEMENT, pas une désactivation : aucune donnée personnelle ne subsiste.
- Le corps de la requête porte le MOT DE PASSE courant, vérifié avant toute
  suppression. Le JWT ne suffit délibérément pas : il prouve la session, pas
  l'identité. Un token peut fuiter et vit 12 h ; il autorise des actions
  réversibles, jamais la destruction définitive du compte. C'est une
  ré-authentification, pas une case à cocher.
- Mot de passe faux → 403, et non 401. L'appelant est DÉJÀ authentifié comme cet
  utilisateur : on ne lui apprend rien sur l'existence du compte (pas de sujet
  d'énumération ici). Un 401 signifierait « session invalide » et ferait purger
  le token côté front alors que la session est parfaitement valide.
- Front : page /account (protégée, atteignable depuis la navbar), avec une zone
  de suppression nettement séparée et une modale de confirmation exigeant le mot
  de passe. Ni window.confirm ni window.alert : une boîte native ne peut pas
  porter de champ de saisie, ignore les tokens et le thème, et son bouton « OK »
  ne nomme pas l'action. Après succès : purge du token local puis redirection
  vers /login (replace).
- Anti-énumération : /auth/forgot-password renvoie TOUJOURS le même message, que
  le compte existe ou non — y compris quand le plafond d'envois est atteint (pas
  de 429, qui trahirait l'existence du compte). Même principe que le 401
  générique du login.
- Rate limiting des emails sortants : 3 par heure et par (utilisateur, usage),
  compté sur `security_tokens.created_at` — pas de compteur dédié, pas de Redis,
  et le plafond survit à un redémarrage. /auth/resend-verification, lui, est
  authentifié : il peut répondre explicitement 429. Ce plafond par COMPTE reste
  inchangé et silencieux ; les limites par IP de /auth/forgot-password s'y ajoutent
  (cf. « Limites de débit »).
