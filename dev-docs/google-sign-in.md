# Connexion avec Google (site et backend)
Mécanisme PRÉVU, pas encore implémenté au-delà du lot 1 : le code actuel ne connaît
que les comptes sans mot de passe et la révocation par `token_version`, rien de
propre à Google (ni endpoint, ni bouton). Avancement : feuille de route du CLAUDE.md
racine. Une fois livré, ce document reste la référence du mécanisme : retirer alors
ce paragraphe.

# Principe
- Bouton Google Identity Services (GIS) sur le site ; le backend vérifie le jeton
  d'identité Google et délivre le JWT Cockpit habituel (même session que la
  connexion par mot de passe, cf. `dev-docs/jwt-session.md`).
- Site et backend uniquement : l'extension reflète la session du site
  (`dev-docs/extension-session-sharing.md`), elle n'a rien à faire.

# Décisions
- Données gardées : le `sub` Google (`users.google_sub`) et l'email, RIEN d'autre
  (ni nom, ni photo, ni jeton Google).
- Liaison AUTOMATIQUE d'un compte existant seulement si Google FAIT AUTORITÉ sur
  l'adresse : adresse `@gmail.com`, ou claim `hd` présent (domaine Google
  Workspace). Autre adresse :
  - un compte Cockpit existe déjà avec cet email → refus ;
  - aucun compte → création d'un compte Google.
- Compte NON VÉRIFIÉ lié par Google : son mot de passe est SUPPRIMÉ (n'importe qui
  a pu créer ce compte avec l'adresse d'autrui), et il n'en retrouve JAMAIS ; un
  message l'en informe après la connexion ; `token_version` est incrémenté (les
  sessions ouvertes par le mot de passe sont révoquées). Refus si ce compte porte
  déjà un AUTRE `google_sub`.
- Compte créé par Google : jamais de mot de passe. Aucun mot de passe ne peut être
  ajouté à un compte Google, par aucun chemin :
  - /auth/forgot-password : même réponse à l'écran ; un email (sans lien de
    réinitialisation ni jeton) indique de se connecter avec Google, avec un bouton
    « Se connecter » vers la page de connexion ; plafonné en silence à 3 par heure
    et par compte (lot 1) ;
  - /auth/reset-password : un lien en attente renvoie le 400 « lien invalide »
    (lot 1).
- Connexion par mot de passe sur un compte sans mot de passe : échec EXACTEMENT
  comme un mot de passe faux (même 401, même coût bcrypt par le hash leurre, même
  compteur d'échecs) (lot 1).
- Inscription par formulaire sur une adresse déjà prise par un compte Google : le 409
  actuel, inchangé.
- PAS d'association ni de dissociation de Google dans « Mon compte » : ni
  `/auth/google/link`, ni `DELETE /auth/google`.
- Suppression d'un compte Google : reconfirmée par Google (jeton d'identité dont
  l'`iat` date de moins de 5 minutes), au lot 3. D'ici là : 409 explicite (lot 1).
- Vérification du jeton Google : PyJWT (déjà présent) + `cryptography` épinglée en
  dépendance directe (lot 2). Pas de `nonce`, pas de contrôle de `g_csrf_token`.
- Interface :
  - bouton EN PREMIER sur la connexion et l'inscription, puis « ou », puis le
    formulaire ; libellé « Continuer avec Google » ;
  - thème `outline` en clair, `filled_black` en sombre ; largeur alignée sur celle
    des champs ;
  - script GIS chargé SEULEMENT sur la connexion, l'inscription et « Mon compte ».
- En-têtes : le frontend de production ne sert aucun en-tête CSP, COOP ni
  Referrer-Policy (vérifié) : rien à adapter pour GIS. En ajouter un plus tard impose
  de revérifier GIS.

# Lots
- Lot 1 (backend seul, rien de propre à Google, déployable seul et compatible avec
  le code précédent) : migration 0006 (`hashed_password` nullable, `google_sub`,
  `token_version`) et garde SQLite d'`alembic/env.py` ; comptes sans mot de passe
  traités sur la connexion, le mot de passe oublié, la réinitialisation et la
  suppression ; révocation par `token_version` ; `has_password` dans UserRead
  (`google_sub` jamais exposé). Après ce lot, aucun compte sans mot de passe
  n'existe encore en production.
- Lot 2 (backend) : connexion avec Google (vérification du jeton, liaison, création).
- Lot 3 (backend) : reconfirmation de la suppression par Google, qui remplace le 409.
- ⚠ Les lots 2 et 3 sont DÉPLOYÉS ENSEMBLE : entre les deux, un compte créé par Google
  ne pourrait pas se supprimer (409), alors que `docs/privacy.md` promet la
  suppression à tout moment.
- Puis le site (bouton, page « Mon compte »), au plus tôt avec les lots 2 et 3.
