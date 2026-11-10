# Script de remplissage de la base de dev (`backend/scripts/seed_dev.py`)
Recrée en une commande un état connu d'une base SQLite LOCALE : un compte de test
et des données factices. Ajouté le 2026-11-10 (session d'arrière-plan).

## Commandes
Depuis `backend\`, venv activé, schéma à jour :
```powershell
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m scripts.seed_dev            # crée le compte de test
.venv\Scripts\python.exe -m scripts.seed_dev --reset    # le supprime puis le recrée
```
- Toujours `-m scripts.seed_dev` depuis `backend\` : lancé comme fichier
  (`python scripts\seed_dev.py`), le paquet `app` n'est pas importable.
- La base visée est celle de l'application : `DATABASE_URL` du shell, sinon celle du
  `.env` (le script appelle `load_dotenv()` avant d'importer `app.database`, comme
  `app.main` et `alembic/env.py`), sinon `sqlite:///./cockpit.db`, RELATIF AU
  DOSSIER COURANT. Le script affiche le chemin absolu du fichier rempli.
- Codes de sortie : 0 succès ; 1 refus (base non SQLite) ou compte déjà présent.

## Ce qui est créé
- Compte `demo@cockpit.example`, adresse vérifiée (`is_verified`), mot de passe
  `cockpit-demo-dev-only` (constante `DEMO_PASSWORD`).
  - Mot de passe PUBLIC (dépôt public) : il ne protège rien, ne sert NULLE PART
    ailleurs, et le compte ne contient que des données inventées.
  - `.example` et non `.test` (décision initiale) : la validation des emails de
    l'API (`EmailStr`, bibliothèque email-validator 2.3.0) refuse les domaines à
    usage spécial (`.test`, `.localhost`, `.invalid`, `.local`, `.onion`, `.arpa`) ;
    le compte aurait été créé mais la connexion répondait 422. `.example` est
    réservé (RFC 2606), sans boîte réelle. Pas `demo@example.com` : une adresse
    qu'un développeur pourrait inscrire à la main, que `--reset` supprimerait.
- Trois tableaux : Alternance, CDI, Stage (pas de « Mes candidatures » : le compte
  n'est pas créé par l'inscription, cf. plus bas).
- 40 actives : Alternance 12/5/2/2/1, CDI 3/4/2/1/0, Stage 2/3/1/1/1 (Repérée,
  Postulée, Relancée, Entretien, Acceptée). 15 archivées : 6, 5 et 4, statuts variés
  (l'archivage garde le statut).
- Contenu inventé, entreprises comprises ; accents, intitulés longs (jusqu'à
  ~200 caractères), URL France Travail et Indeed (identifiants inventés, `source`
  = `extension`) et de sites quelconques sous le TLD réservé `.example`.
- Déterministe : aucun aléa ; `applied_at` en dates fixes (été-automne 2026). Seuls
  changent d'une exécution à l'autre les identifiants et les horodatages posés par
  le serveur (`created_at`, `updated_at`, `archived_at`).

## Garde-fous
- SQLite uniquement : refus AVANT toute connexion si le moteur réellement utilisé
  (`app.database.engine`) n'est pas SQLite (`engine.url.get_backend_name()`), que
  `DATABASE_URL` soit définie ou non. Le contrôle porte sur le moteur, pas sur la
  variable : absente, elle ne dit rien de la base visée (le `.env` peut en fournir
  une). Le message cite le nom du moteur, JAMAIS l'URL (mot de passe).
- Ne touche qu'au compte `demo@cockpit.example`, cherché par adresse EXACTE :
  - présent sans `--reset` → arrêt, rien n'est écrit ;
  - `--reset` → `db.delete(user)` puis commit : la cascade de la base emporte ses
    tableaux, candidatures et jetons (cf. `dev-docs/deletion-cascade.md`). Même
    opération que DELETE /auth/me, sans sa vérification du mot de passe (qui
    bloquerait le reset si le mot de passe du compte de démo a été changé depuis
    l'application) ;
  - échec en cours de remplissage → le compte de test est supprimé (pas de
    demi-jeu de données, qui bloquerait l'exécution suivante).
- Hors périmètre : remplissage jusqu'aux plafonds, compte sans mot de passe.

## Chemin d'écriture : les fonctions de l'application
- Les endpoints sont des fonctions Python appelées directement (`payload`,
  `current_user`, `db` passés explicitement) : `create_board`, puis par carte
  `create_application` (arrivée en haut de « Repérée »), `update_application`
  (statut et `applied_at` : arrivée en haut de la colonne cible, chemin du PATCH),
  `archive_application`. Verrou `_lock_positions_of`, plafonds et ownership
  s'appliquent donc comme en production ; aucune position n'est écrite à la main
  (cf. `dev-docs/kanban-order.md`).
- Chaque arrivée se fait EN HAUT : `CARDS` liste chaque colonne dans l'ordre
  AFFICHÉ et le script la crée dans l'ordre INVERSE (`reversed(CARDS)`).
- Seul le compte passe par le modèle `User` (+ `hash_password`) : `/auth/register`
  exige une requête HTTP, applique la limite de débit par IP, envoie un email de
  vérification (réel si la clé Brevo du `.env` est chargée) et crée « Mes
  candidatures ».
- Une centaine de petites transactions (chaque endpoint commite) : quelques
  secondes, bcrypt compris.

## Tests : `backend/tests/test_seed_dev.py`
- Base de conftest.py (SQLite en mémoire), passée par le paramètre `engine` de
  `main()`.
- Refus sur un moteur PostgreSQL (substitué à `app.database.engine`, DATABASE_URL
  absente ou annonçant faussement un SQLite) : un écouteur `do_connect` prouve
  qu'aucune connexion n'est tentée ; l'URL, l'utilisateur, l'hôte et le mot de
  passe n'apparaissent pas dans la sortie.
- Comptes par tableau et statut, positions 0..n-1 (archivées NULL), ordre affiché
  par l'API = ordre de `CARDS` puis un POST /move réel, archivées par tableau,
  connexion par l'API, déterminisme, arrêt sans écriture (vidage complet des tables
  comparé), `--reset` qui laisse deux autres comptes (dont
  `copie-demo@cockpit.example`) identiques ligne pour ligne.
- Preuves par mutation (2026-11-10) : garde-fou désactivé → les 4 variantes du test
  de refus échouent ; `--reset` qui supprime tous les comptes → le test du reset
  échoue ; création sans `reversed` → le test d'ordre échoue.
