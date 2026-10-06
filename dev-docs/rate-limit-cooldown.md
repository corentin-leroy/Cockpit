# Blocage après un 429 (extrait de « Architecture frontend »)
- Blocage après un 429 (limites de débit, cf. « Limites de débit ») : connexion,
  inscription et mot de passe oublié partagent UNE logique, pas trois copies.
  - `ApiError.retryAfter` (api/client.js) : délai du serveur en SECONDES ENTIÈRES lu
    dans l'en-tête `Retry-After`, ou `null`. `utils/retryAfter.js` (fonctions pures,
    sans React ni Vite) : seul le format « secondes entières » est accepté, plafonné à
    24 h ; une date HTTP, du texte, 0, un négatif ou une valeur démesurée donnent
    `null`. Aucune date n'est interprétée : la comparer à l'horloge du poste
    produirait une durée fausse sur un poste déréglé.
  - `auth/useRateLimitCooldown.js` : le hook. `handle(err)` renvoie true si c'est un
    429 AVEC un délai lisible ; le message du serveur reste alors affiché pendant tout
    le blocage (même si l'utilisateur modifie les champs), le bouton est désactivé et
    indique le temps restant arrondi à la minute SUPÉRIEURE (« Réessayer dans 14
    min »), mis à jour chaque minute par UN `setTimeout` calé sur le prochain
    changement de minute (pas de `setInterval`, pas de compte à la seconde). À
    l'échéance, le message disparaît et le bouton redevient actif. `handleSubmit`
    refuse aussi d'envoyer pendant le blocage. L'heure courante vit dans un état
    (jamais lue pendant le rendu : règles du compilateur React du lint). Un onglet
    masqué voit ses minuteurs ralentis par le navigateur : `visibilitychange`
    recalcule au retour.
  - SANS délai lisible (en-tête absent ou illisible), `handle` renvoie false : la page
    traite le 429 comme une erreur ordinaire (message affiché, bouton utilisable). On
    ne bloque jamais l'utilisateur sur une durée inventée ; le serveur continue de
    refuser tant qu'il le faut.
  - AUCUNE mémorisation, aucun accès à localStorage : un rechargement oublie le blocage,
    la tentative suivante renvoie un 429 avec le délai à jour.
  - Inscription réussie puis connexion automatique refusée en 429 : le compte EXISTE.
    RegisterPage redirige vers /login avec `state: { accountCreated: { until } }` ;
    LoginPage affiche « Votre compte est créé. … vous pourrez vous connecter à partir
    de HH:MM » (heure d'échéance arrondie à la minute supérieure) et désactive le
    bouton. Contrairement aux autres messages de blocage, celui-ci porte une
    information durable : à l'échéance il NE disparaît PAS, il devient « Votre compte
    est créé, vous pouvez maintenant vous connecter. » (variante succès) et ne
    disparaît qu'à l'envoi suivant. Sans délai lisible : « …connexion momentanément
    limitée : réessayez dans quelques minutes », bouton actif. L'état de navigation
    est recopié dans un état local puis effacé de l'historique (même schéma que
    `sessionExpired`) : un rechargement repart vierge.
  - Vérifié dans le navigateur (backend local aux fenêtres raccourcies, Vite sur un
    autre port, donc en cross-origin réel) : message conservé pendant la saisie,
    bouton et libellé « 2 min » puis « 1 min », levée à l'échéance, envoi forcé sans
    appel réseau, `Retry-After` absent ou en date HTTP (bouton utilisable), inscription
    puis connexion bloquée, 429 sur l'inscription et sur /forgot-password. Le frontend
    n'a pas de lanceur de tests : les fonctions pures ont été vérifiées par un script
    node jetable, pas par un test du dépôt.
