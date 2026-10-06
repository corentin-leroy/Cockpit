# Migrations (Alembic)
- Le schéma est géré par Alembic (`alembic==1.20.0`, backend/alembic/), en dev
  comme en prod. `main.py` n'appelle PLUS `create_all()` : un `create_all`
  ne modifie jamais une table existante, c'est ce qui l'a fait remplacer.
  Les tests créent leur propre schéma (fixture `client`).
- Commandes (depuis backend/, toujours via le venv) :
  - `.venv\Scripts\python.exe -m alembic upgrade head` : applique les migrations
    (crée une base neuve).
  - `... -m alembic revision --autogenerate -m "description"` : génère une
    migration d'après models.py. TOUJOURS la relire : l'autogénération ne voit
    pas tout (renommage = drop + create, enums PostgreSQL, données).
  - `... -m alembic check` : liste les écarts modèles/base (code de sortie ≠ 0).
  - `... -m alembic current` / `history` : état et historique.
- Changer models.py exige une migration DANS LE MÊME lot : test_migrations.py
  échoue sinon.
- `alembic/env.py` prend l'URL dans `app.database.DATABASE_URL` (jamais dans
  alembic.ini, qui n'en contient aucune), donc normalisée comme celle de l'app.
  Il charge le .env, puis DATABASE_URL posée dans le shell PRIME. Il affiche
  `[alembic] cible : ...` à chaque commande : LIRE cette ligne avant d'écrire.
- Viser la PROD depuis le poste : poser `$env:DATABASE_URL` (valeur de
  `DATABASE_PUBLIC_URL` de Railway, l'URL interne n'est pas joignable) dans la
  SESSION shell uniquement, jamais dans .env, puis la retirer
  (`Remove-Item Env:DATABASE_URL`) ou fermer la fenêtre. Une session restée
  configurée vise la prod à la commande suivante.
- Historique : la révision 0001 (« baseline ») décrit le schéma tel que créé par
  l'ancien create_all. Elle a été marquée appliquée en prod et sur cockpit.db
  par `alembic stamp 0001` (2026-09-25), après comparaison en lecture seule
  (0 écart, `ON DELETE CASCADE` présents, libellés d'enum identiques). Elle ne
  s'exécute que pour bâtir une base neuve.
- Révision 0002 (« remove rejected status ») : retire `REJECTED` de l'enum
  `applicationstatus`. Voir la procédure ci-dessous, qui sert de modèle pour tout
  retrait de valeur d'enum.
- Révision 0003 (« archive applications ») : ajoute `applications.archived_at`
  (DateTime nullable, sans valeur par défaut). À l'opposé de 0002 : une SEULE
  instruction `ADD COLUMN`, aucun ajustement manuel du fichier généré. Mesuré
  (pas supposé), PostgreSQL 18, table de 50 000 lignes : 68 ms — une opération
  de métadonnées, pas une réécriture de table. Toutes les lignes existantes
  valent NULL après la migration (donc actives) : aucune donnée réinterprétée.
- Révision 0004 (« notes string 5000 ») : passe `applications.notes` de `Text` à
  `String(5000)`. Dans UNE transaction : `LOCK TABLE ... ACCESS EXCLUSIVE`, puis
  garde-fou qui échoue explicitement (nombre de notes et longueur maximale dans
  le message) si une note dépasse déjà 5000 caractères — il ne TRONQUE JAMAIS —,
  puis `ALTER COLUMN ... TYPE VARCHAR(5000)`. La valeur 5000 est en dur dans la
  migration (état figé du schéma), pas importée de limits.py. MESURÉ (pas
  supposé) sur PostgreSQL 18.6 jetable, 50 000 lignes, 18 Mo :
  - `text` → `varchar(5000)` RÉÉCRIT TOUTE LA TABLE (`relfilenode` change) :
    ~950 ms sous verrou exclusif. Négligeable pour cette base (quelques
    lignes), mais à savoir : sur une grosse table les écritures seraient
    bloquées pendant la réécriture.
  - Une valeur trop longue FAIT ÉCHOUER la conversion (« value too long for type
    character varying(5000) »), la transaction est annulée et rien n'est
    tronqué : même sans le garde-fou, aucune donnée n'est perdue. Le garde-fou
    sert à rendre l'échec lisible et actionnable.
  - Le downgrade (`varchar(5000)` → `text`) ne réécrit pas la table et ne perd
    rien (md5 du contenu identique dans les deux sens).
  Compatible avec la version précédente du code (elle n'écrit déjà que des notes
  de 5000 caractères au plus) : si le déploiement échoue, l'ancienne version
  continue de servir sur le schéma migré.
- Révision 0005 (« application positions ») : ajoute `applications.position`
  (INTEGER nullable, SANS contrainte, cf. « Ordre des cartes du kanban ») et
  numérote chaque colonne active par `ROW_NUMBER() OVER (PARTITION BY board_id,
  status ORDER BY updated_at DESC, id DESC) - 1` : exactement l'ancien ordre
  affiché, rien ne bouge à l'écran au déploiement (`id DESC` ne fait que départager
  des updated_at égaux, que l'ancien tri laissait au hasard). Archivées à NULL ;
  updated_at intact (SQL brut). `LOCK TABLE ... ACCESS EXCLUSIVE` sous PostgreSQL,
  une transaction. `UPDATE ... FROM` : SQLite >= 3.33. Downgrade : DROP COLUMN, rien
  d'autre n'est touché (seul l'ordre choisi est perdu). VÉRIFIÉ, sur une copie de
  cockpit.db, un SQLite jetable et un PostgreSQL 18.6 jetable peuplés de 900
  candidatures (8 tableaux, 40 colonnes, égalités d'updated_at, ~30 % d'archivées) :
  ordre identique à l'ancienne requête, empreinte md5 des autres colonnes
  identique après upgrade, après downgrade et après re-upgrade, positions
  identiques au second passage, `alembic check` propre. MESURÉ sur PostgreSQL 18.6,
  50 900 lignes : ~350 ms sous verrou exclusif (1,3 s commande alembic comprise).
  Compatible avec la version précédente du code : elle ignore la colonne ; ses
  créations (NULL) s'affichent en haut et se réparent ensuite.
- Enums : SQLAlchemy stocke les NOMS des membres (`APPLIED`), pas les valeurs
  (`applied`) — à retenir pour toute requête SQL manuelle. Sous PostgreSQL ce
  sont des types natifs (`applicationstatus`, `tokenpurpose`) : on n'y retire
  pas une valeur (pas de `DROP VALUE`), il faut recréer le type, et l'opération
  échoue s'il reste une ligne portant la valeur retirée.
- Procédure de retrait d'une valeur d'enum (celle de 0002), dans UNE transaction :
  `LOCK TABLE ... ACCESS EXCLUSIVE` (aucune écriture concurrente entre contrôle
  et DDL), garde-fou qui échoue explicitement s'il reste une ligne portant la
  valeur, `ALTER TYPE ... RENAME TO ..._old`, `CREATE TYPE` à la nouvelle liste,
  `ALTER COLUMN ... TYPE ... USING col::text::type`, `DROP TYPE ..._old`. Un
  échec annule tout (vérifié : aucun type `_old` orphelin). Les valeurs sont
  écrites EN DUR dans la migration, jamais importées de app.models (une migration
  décrit un état figé du schéma). Le downgrade fait l'inverse et ne perd aucune
  ligne.
- ORDRE de déploiement pour RETIRER une valeur de statut : (1) le FRONT d'abord
  (retirer une colonne est compatible avec l'ancien backend, l'inverse ne l'est
  pas) ; vérifier en prod qu'aucune ligne ne porte la valeur (comptage en
  MAJUSCULES) et recharger tous les onglets ouverts (un ancien bundle peut encore
  écrire la valeur) ; (2) ensuite migration + backend. Une ligne restée avec la
  valeur retirée deviendrait invisible dans l'interface (BoardPage ignore un
  statut inconnu) et ne se corrigerait que par SQL ou par l'API.
- Migrations 0001 et 0002 testées sur un PostgreSQL 18.6 jetable (Docker) :
  upgrade/downgrade/upgrade, contenu des lignes identique (md5), libellés du type
  lus, cas d'échec, verrou face à une transaction concurrente, et
  `downgrade base` puis remontée depuis le vide (le `downgrade` de la baseline,
  qui supprime les types enum, fonctionne sur PostgreSQL).
- Une migration doit rester COMPATIBLE AVEC LA VERSION PRÉCÉDENTE DU CODE : si le
  nouveau code échoue son healthcheck, l'ancienne version continue de servir sur
  le schéma déjà migré (ajout de colonne nullable : oui ; renommage ou
  suppression : en deux déploiements).
