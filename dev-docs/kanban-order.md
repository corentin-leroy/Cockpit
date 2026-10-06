# Ordre des cartes du kanban (colonne `position`, migration 0005)
- `Application.position` (INTEGER, nullable) : rang de la carte dans sa COLONNE
  = les candidatures ACTIVES d'un même tableau ayant le même statut. Dans chaque
  colonne, les positions valent exactement 0..n-1 (0 = EN HAUT), sans trou ni
  doublon. Une ARCHIVÉE a toujours `position = NULL` (elle n'est dans aucune
  colonne). Écrite UNIQUEMENT par routers/applications.py, jamais reçue du client ;
  NON exposée dans `ApplicationRead` : le contrat, c'est l'ORDRE de la liste.
- TRI de GET /applications (actives) : `position ASC NULLS FIRST, updated_at DESC,
  id DESC`. Les NULL en tête = lignes créées par l'ANCIENNE version du code pendant
  un déploiement (arrivées, donc en haut) ; à rang égal (doublon de même origine),
  la plus récemment modifiée d'abord. Liste des archivées : inchangée (updated_at
  décroissant ; la page d'archives trie elle-même). Avant ce lot, le tri était
  `updated_at DESC` : modifier une note faisait remonter la carte.
- RÈGLE D'ARRIVÉE, unique : toute carte qui entre dans une colonne AUTREMENT que
  par POST /move arrive EN HAUT (rang 0) : création (formulaire ET extension),
  PATCH qui change RÉELLEMENT le statut ou le tableau (modale, dépôt sur un tableau
  de la sidebar), désarchivage. Seul POST /move choisit un autre rang.
  ⚠ Le PATCH compare aux valeurs STOCKÉES, pas à la présence du champ : le
  formulaire d'édition renvoie TOUJOURS `status` et `board_id`, même inchangés, et
  ce n'est pas une arrivée (test : `test_patch_resending_the_same_status_and_board_
  does_not_move_the_card`).
- QUITTER une colonne (déplacement, archivage, suppression d'une active) la
  compacte. Un PATCH sur une ARCHIVÉE (correction depuis la page d'archives, statut
  ou tableau compris) ne touche à aucune position ; au désarchivage, elle arrive en
  haut de la colonne de son statut et de son tableau ACTUELS.
- POST /applications/{id}/move, corps `{status, position}` (`ApplicationMove`,
  `position` entre 0 et 299) : place la carte au rang `position` de la colonne
  `status` de SON tableau, compté sans la carte déplacée. Rang au-delà de la fin →
  ramené en fin de colonne (onglet en retard ; décision validée, pas un 422).
  Rang déjà occupé par la carte → 200 sans effet (placement absolu, pas une
  bascule). Archivée → 409. Aucun contrôle de plafond (déplacer ne change aucun
  total). Changer de TABLEAU reste un PATCH board_id. Endpoint DÉDIÉ plutôt qu'un
  champ du PATCH : un PATCH pose des valeurs, un rang implique de décaler les
  voisines, et `PATCH {status}` / `PATCH {status, position}` auraient eu deux
  placements implicites différents.
- RENUMÉROTATION : toute écriture qui fait entrer ou sortir une carte d'une colonne
  relit la colonne DANS L'ORDRE AFFICHÉ et la renumérote ENTIÈREMENT (seules les
  lignes dont le rang change sont réécrites ; au plus 300 cartes). Elle SE RÉPARE
  donc d'elle-même : un NULL, un doublon ou un trou (ancien code pendant un
  déploiement, SQL manuel, insertion directe en test) disparaît à la prochaine
  écriture dans la colonne. Les voisines sont réécrites par la TABLE (Core) avec
  `updated_at` reposé à sa propre valeur : décaler une carte n'est pas la modifier
  (la carte déplacée, elle, voit son updated_at changer).
- CONCURRENCE (deux onglets, double clic) : chaque endpoint qui écrit une position
  (création, PATCH, /move, archivage, désarchivage, suppression) appelle d'abord
  `_lock_positions_of`, AVANT toute lecture : `UPDATE users SET id = id WHERE id =
  :uid`, même SQL sur les deux moteurs (comme `_consume_token`). PostgreSQL : verrou
  de ligne jusqu'au commit, la requête suivante relit l'état commité (READ
  COMMITTED). SQLite : première ÉCRITURE de la transaction, qui prend le verrou
  d'écriture avant toute lecture (`FOR UPDATE` y serait ignoré). Par UTILISATEUR,
  pas par tableau : un déplacement vers un autre tableau en touche deux, deux
  requêtes pourraient les verrouiller dans des ordres opposés. Effet de bord : les
  comptages des plafonds (300/2000), faits après le verrou, ne sont plus
  dépassables par des créations simultanées.
  MESURÉ sur PostgreSQL 18.6 jetable (10 manches de 40 écritures simultanées
  mêlées) : avec le verrou, 0 incohérence et 0 erreur ; SANS, 10 manches sur 10
  incohérentes (doublons `[0, 0, 1…]`, archivées numérotées) et 12 à 25
  `DeadlockDetected` (500) par manche.
- AUCUNE CONTRAINTE en base (ni NOT NULL, ni CHECK « archivée ⟺ NULL », ni
  unicité), décision validée : l'ancienne version du code, qui sert encore pendant
  un déploiement, crée sans position et change des statuts sans renuméroter ; une
  contrainte ferait échouer ses écritures. L'unicité de (tableau, statut, position)
  ne serait de toute façon pas déclarable : PostgreSQL et SQLite la vérifient ligne
  par ligne, une renumérotation la violerait en cours d'instruction. Pas de 0006
  prévue : avec une numérotation qui se répare à chaque écriture, son intérêt est
  faible ; à reconsidérer seulement si une incohérence apparaît.
