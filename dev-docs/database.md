# Base de données : SQLite (dev) et PostgreSQL (prod)
- Le MÊME code tourne sur les deux : seule DATABASE_URL change. Tout ce qui
  dépend du moteur est concentré dans `app/database.py`, nulle part ailleurs.
  - dev/tests : `sqlite:///./cockpit.db` (défaut si la variable est absente)
  - prod : `postgresql+psycopg://user:mdp@hote:5432/base`
- Driver PostgreSQL : psycopg v3 (`psycopg[binary]`), pas psycopg2. C'est le
  driver maintenu, supporté nativement par SQLAlchemy 2.0 via le dialecte
  `postgresql+psycopg`. L'extra [binary] évite toute compilation C.
- `normalize_database_url()` réécrit l'URL au démarrage :
  - `postgres://` (fourni tel quel par Railway, Heroku, Render…) est un alias
    que SQLAlchemy REFUSE depuis la 1.4 → réécrit en `postgresql+psycopg://`.
  - `postgresql://` nu est aussi réécrit, sinon SQLAlchemy chercherait psycopg2,
    qui n'est pas installé.
  - Une URL déjà explicite n'est jamais touchée.
- Options de connexion branchées sur le moteur : `check_same_thread=False` est
  une option du module sqlite3 et ferait ÉCHOUER psycopg → SQLite uniquement.
  `pool_pre_ping=True` ne sert qu'en PostgreSQL (les hébergeurs managés coupent
  les connexions inactives ; sans ping, la première requête après une période
  creuse échoue sur une connexion morte).
- Convention datetime : toutes les colonnes DateTime sont NAIVES en UTC, via le
  helper `utcnow()` (security.py) — y compris les `default`/`onupdate` des
  modèles. Ne JAMAIS y mettre un `datetime.now(timezone.utc)` « aware » : SQLite
  laisse tomber le fuseau en silence, PostgreSQL le convertit vers le fuseau de
  la session avant stockage. Le même code écrirait des heures différentes selon
  le moteur, et fausserait le rate limiting des emails (comparaison sur
  created_at).
- Les tests restent sur SQLite en mémoire (cf. conftest.py) : rapides, isolés,
  aucune dépendance à un PostgreSQL local.
- Session SQLAlchemy par requête (`get_db`, database.py) : ouverte, puis fermée
  dans un `finally` (`db.close()`) ; aucun `rollback` explicite dans l'application,
  et il n'en faut pas : `Session.close()` termine la transaction en cours. Un
  EMPOISONNEMENT DE SESSION (une transaction non annulée qui ferait échouer les
  requêtes suivantes sur la même connexion) a été soupçonné après une DataError et
  ÉCARTÉ, preuve à l'appui, le 2026-09-26 : sur un vrai uvicorn et un PostgreSQL 18
  jetable, pool réduit à UNE connexion, la même connexion (un seul pid, 56
  emprunts) a servi toutes les requêtes ; juste après l'erreur, lectures et
  écritures du même compte et d'un autre compte réussissent, et aucune connexion
  n'est restée `idle in transaction`. Témoin : un `get_db` qui ne ferme jamais la
  session épuise le pool (`QueuePool ... timed out`, 500 en 6 s), donc le test sait
  détecter une session qui fuit. Ce qui ressemblait à un empoisonnement était un
  empoisonnement de DONNÉES (cf. `applied_at`, section « Validation des entrées »).
  Ne pas refaire ce diagnostic ; le pool n'est pas configurable dans l'app
  (database.py : `create_engine` sans `pool_size`), le montage d'essai remplaçait
  `sqlalchemy.create_engine` avant l'import de l'app.
