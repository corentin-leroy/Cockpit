# Cockpit

**Le poste de pilotage de votre recherche d'emploi.**

Suivi de candidatures en kanban, multi-tableaux, avec une extension navigateur
qui capture une offre depuis n'importe quel site d'annonces en un clic.

### → [Voir l'application en ligne](https://cockpit-front-production.up.railway.app)

![Le kanban de suivi des candidatures : six colonnes de statuts, de « Repérée » à
« Acceptée », et la barre latérale de sélection des tableaux](docs/kanban-light.png)

---

## Le problème

Une recherche d'emploi se mène sur cinq ou six sites d'annonces à la fois, chacun
avec son propre compte et ses propres offres sauvegardées. Aucun n'a de vue
d'ensemble : on perd le fil de qui a été relancé, de ce qui attend une réponse,
et de l'offre repérée la semaine dernière dont l'onglet a fini par fermer.

Cockpit rassemble tout au même endroit : un kanban qui suit chaque candidature
de « repérée » à « acceptée », plusieurs tableaux pour séparer les recherches, et
une extension navigateur qui enregistre une offre sans quitter la page.

## Fonctionnalités

- Suivi kanban à six statuts (repérée, postulée, relancée, entretien, refusée,
  acceptée) avec déplacement des cartes par glisser-déposer
- Tableaux multiples, pour séparer plusieurs recherches en parallèle
- Extension navigateur (Chrome) : capture d'une offre en un clic depuis
  n'importe quel site
- Comptes utilisateurs : inscription, connexion, réinitialisation de mot de
  passe et vérification d'adresse email, gestion du compte (consultation de
  l'adresse et du statut de vérification, suppression définitive du compte et de
  toutes les données associées)
- Thèmes clair et sombre

## Stack technique

- **Frontend** — React 19, Vite, React Router 7
- **Backend** — FastAPI, SQLAlchemy 2.0, PostgreSQL en production (SQLite en
  développement et pour les tests)
- **Extension** — Chrome, Manifest V3
- **Déploiement** — Railway (front, API et base PostgreSQL en services séparés)
- **Emails transactionnels** — Brevo

## Décisions d'architecture

**Extraction par JSON-LD `JobPosting`, pas d'extracteurs par site.**
L'extension lit les données structurées `schema.org/JobPosting` que la plupart
des sites d'annonces publient déjà pour le référencement, au lieu de cibler le
HTML de chaque site. Un seul extracteur couvre donc immédiatement tout site
conforme, et aucune maintenance n'est nécessaire quand l'un d'eux refond son
interface — un extracteur spécifique casse à la première refonte. Si la page ne
publie rien d'exploitable, l'extension bascule sur une extraction générique puis
sur un formulaire manuel pré-rempli.

**Aucun scraping serveur, aucun stockage d'identifiants tiers.**
Le backend ne visite jamais un site d'annonces et ne demande jamais les
identifiants de l'utilisateur pour un service tiers. L'extraction a lieu dans le
navigateur, sur une page que l'utilisateur a lui-même ouverte, ce qui respecte
les CGU des sites et évite de détenir des secrets qui ne nous appartiennent pas.

**Ownership vérifié en chaîne, et 404 plutôt que 403.**
Une candidature ne porte pas de `user_id` : son propriétaire se déduit par
jointure candidature → tableau → utilisateur, une seule source de vérité qui ne
peut pas se désynchroniser. L'accès à la ressource d'autrui renvoie **404**,
jamais 403 : un 403 confirmerait l'existence de l'identifiant demandé et
permettrait de cartographier les données des autres comptes par simple
énumération.

**Réponses génériques sur l'authentification et le mot de passe oublié.**
Le login renvoie un 401 identique que l'adresse existe ou non, et
`/auth/forgot-password` renvoie toujours le même message de confirmation — y
compris quand le plafond d'envois est atteint, où un 429 trahirait l'existence
du compte. Sans cela, ces endpoints deviennent un oracle pour savoir qui est
inscrit.

**Tokens à usage unique hashés en SHA-256, pas en bcrypt.**
Les liens de réinitialisation et de vérification sont stockés hashés, jamais en
clair. bcrypt est conçu pour ralentir les attaques par dictionnaire sur des
secrets à faible entropie (les mots de passe humains) ; ici le secret vient de
`secrets.token_urlsafe(32)`, soit 256 bits d'aléa, hors de portée de toute force
brute. SHA-256 suffit donc, et reste rapide sur un endpoint public non
authentifié. Les tokens expirent (60 min pour un reset, 24 h pour une
vérification) et sont consommés à la première utilisation.

**Limites de quantité vérifiées côté serveur.**
Le nombre de tableaux et de candidatures par utilisateur, ainsi que la taille des
corps de requête, sont plafonnés dans l'API. Le front peut les afficher pour
l'UX, mais ne fait jamais autorité : l'extension, `curl` ou tout autre client
restent soumis aux mêmes plafonds.

**Droit à l'effacement : mot de passe exigé, cascade au niveau du schéma.**
Supprimer son compte impose de ressaisir le mot de passe courant : un jeton de
session, qui peut fuiter et n'autorise que des actions réversibles, ne doit pas
suffire à détruire définitivement un compte. C'est une ré-authentification, pas
une simple confirmation. La suppression emporte par cascade tableaux,
candidatures et jetons de sécurité, et cette cascade est déclarée au niveau du
schéma PostgreSQL (`ON DELETE CASCADE`), pas seulement dans l'ORM : toute
suppression se comporte de la même façon, y compris en SQL direct ou lors d'une
maintenance qui contourne l'application.

## Accessibilité

- Interface construite sur des **design tokens**
  (`frontend/src/styles/tokens.css`) : couleurs, espacements et typographie sont
  déclarés une fois et dérivés par thème, ce qui rend un écart de contraste
  corrigeable en un point unique.
- **Contrastes vérifiés WCAG AA** dans les deux thèmes, texte comme éléments
  d'interface.
- **Aucune information portée par la couleur seule** : les statuts sont
  identifiés par leur libellé écrit, et les messages d'erreur ou de succès
  portent un pictogramme en plus de leur couleur.

![Le même kanban en thème sombre : les libellés de statuts et la hiérarchie
visuelle sont identiques, seuls les tokens de couleur changent](docs/kanban-dark.png)

## Tests

Suite `pytest` côté backend, ciblée sur les points où une régression serait
silencieuse et coûteuse : authentification (fuite du mot de passe,
anti-énumération), ownership (cloisonnement entre utilisateurs), règles métier
(statut imposé à la création, dernier tableau non supprimable), limites de
quantité, et suppression de compte (mot de passe exigé, cascade sur les données
associées).

```powershell
cd backend
py -m pytest
```

Les tests s'exécutent sur une base SQLite en mémoire, recréée à chaque test :
ils ne touchent jamais la base de développement et n'envoient aucun email.

## Installation locale

Prérequis : Python 3.13, Node 20+.

```powershell
git clone https://github.com/<utilisateur>/cockpit.git
cd cockpit
```

**Backend** — l'API démarre sur http://127.0.0.1:8000 (documentation
interactive auto-générée sur `/docs`) :

```powershell
cd backend
py -m venv .venv
.venv\Scripts\Activate.ps1
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
copy .env.example .env   # renseigner au minimum JWT_SECRET_KEY
py -m uvicorn app.main:app --reload
```

**Frontend** — sur http://localhost:5173 :

```powershell
cd frontend
npm install
npm run dev
```

La configuration est documentée dans `backend/.env.example` et
`frontend/.env.example`. En développement, seul `JWT_SECRET_KEY` est
obligatoire : les autres valeurs ont des défauts locaux, et les emails sont
écrits dans les logs du serveur au lieu d'être envoyés.

**Extension** — `chrome://extensions` → activer le mode développeur → « Charger
l'extension non empaquetée » → dossier `extension/`.

## Structure du dépôt

```
backend/     API FastAPI — modèles, schémas Pydantic, routers, tests
frontend/    Application React (Vite)
extension/   Extension Chrome Manifest V3
```

## Limites connues et suite

- L'extension n'est **pas encore publiée sur le Chrome Web Store** : elle
  s'installe pour l'instant en mode développeur.
- Le schéma de base est créé au démarrage via `create_all()`, qui ne migre rien.
  **Alembic est à mettre en place avant le premier changement de schéma en
  production.**
- L'agrégation d'offres via les API officielles (La Bonne Alternance, France
  Travail) est prévue après la V1.
