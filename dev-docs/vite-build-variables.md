# Variables Vite : injectées au BUILD, pas au runtime
- Différence FONDAMENTALE avec le backend, qui lit `os.getenv` au démarrage et
  qu'il suffit donc de redémarrer : Vite ne lit pas d'environnement dans le
  navigateur (il n'y en a pas). `npm run build` REMPLACE textuellement chaque
  `import.meta.env.VITE_X` par sa valeur littérale dans le bundle. Le JS livré
  contient l'URL en dur ; il n'existe plus aucune variable à l'exécution.
- Conséquences pour le déploiement :
  - `VITE_API_BASE_URL` doit être définie AU MOMENT DU BUILD (variable du
    service front sur Railway, pas du service backend).
  - Changer l'URL de l'API impose de REBUILDER et redéployer le front.
    Redémarrer le conteneur ne change rien : le bundle est déjà figé.
  - Une variable ajoutée après coup dans le dashboard n'a AUCUN effet tant
    qu'aucun build n'a été relancé — symptôme classique : le front déployé
    continue d'appeler 127.0.0.1:8000 et échoue chez tous les utilisateurs.
  - Tout ce qui est préfixé VITE_ est PUBLIC (lisible dans le bundle) : jamais
    de secret. Les secrets restent côté backend.
- Valeur de production : `VITE_API_BASE_URL=https://api.cockpitemploi.fr`, le
  domaine personnalisé du service backend (cf. `dev-docs/domain.md`).
- `VITE_EXTENSION_ID` : identifiant de l'extension Chrome à qui le site transmet
  sa session (`frontend/src/auth/extensionSession.js`, cf.
  `dev-docs/extension-session-sharing.md`). DEV UNIQUEMENT, dans
  `frontend/.env.local` (ignoré par Git) : l'ID de l'extension non empaquetée
  chargée depuis `extension/dist/dev/`. Absente, c'est l'ID du Chrome Web Store
  (`EXTENSION_STORE_ID`, `frontend/src/constants/links.js`) qui sert : ne JAMAIS
  la poser dans les variables du service front sur Railway. Pas un secret (un ID
  d'extension est public).
  - ⚠ Vite lit `.env.local` en dev ET pendant `npm run build` : un build fait sur
    le poste embarque l'ID de dev. Seul le build de Railway (qui ne voit pas ce
    fichier) est déployé ; ne jamais déployer un `dist/` construit localement.
