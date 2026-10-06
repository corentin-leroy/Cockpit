# Déploiement (Railway)
- Le backend vit dans `backend/`, pas à la racine : le service Railway doit
  avoir son **Root Directory réglé sur `backend`**, sinon ni requirements.txt ni
  railway.json ne sont trouvés. C'est le réglage qu'on oublie en premier.
- `backend/railway.json` porte la config de déploiement (préféré au Procfile :
  il exprime aussi le healthcheck et la politique de redémarrage) :
  - startCommand : `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`.
    Sans `--reload` (dev uniquement : il surveille les fichiers et redémarre).
    `0.0.0.0` et non 127.0.0.1, sinon le conteneur n'accepte aucune connexion
    venue de l'extérieur. `$PORT` est injecté par Railway et doit être respecté.
  - preDeployCommand `alembic upgrade head` : migre la base avant le démarrage
    (cf. plus bas). `alembic` est appelé nu, comme `uvicorn` : trouvé sous
    Nixpacks, confirmé au premier déploiement.
  - healthcheckPath `/health` : Railway attend que l'app réponde avant de
    basculer le trafic — pas de fenêtre d'erreurs au redémarrage.
- `backend/.python-version` épingle Python 3.13 (version de dev). Si le log de
  build montre une autre version, le repli est `runtime.txt` ou la variable
  NIXPACKS_PYTHON_VERSION.
- La base PostgreSQL est un service Railway séparé ; référencer
  `DATABASE_URL=${{Postgres.DATABASE_URL}}` plutôt que copier l'URL en dur.
- Migrations : `preDeployCommand` (`alembic upgrade head`, dans railway.json)
  s'exécute UNE fois par déploiement, avant le démarrage du nouveau conteneur.
  Si elle échoue, le déploiement est en échec et l'ANCIENNE version continue de
  servir ; PostgreSQL exécute le DDL en transaction, donc une migration en échec
  est annulée en bloc (base inchangée). Pas dans startCommand : cela
  s'exécuterait à chaque redémarrage et réplica, et `restartPolicyType:
  ON_FAILURE` (10 essais) rejouerait dix fois la même erreur.
- /health reste un test de vie et n'interroge PAS la base ni alembic_version :
  le coupler ferait tomber le service pour des raisons étrangères au schéma.
- Ordre de mise en place (fait le 2026-09-25) : la prod a été marquée
  `alembic stamp 0001` AVANT le premier déploiement contenant le pre-deploy.
  Sinon `upgrade head` aurait tenté de recréer des tables existantes (échec sans
  gravité mais déploiement rouge). Une NOUVELLE base (autre environnement) n'a
  pas besoin de stamp : `upgrade head` la construit.
