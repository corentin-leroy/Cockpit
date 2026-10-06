# Archivage des candidatures
- `Application.archived_at` (DateTime nullable, migration 0003) : NULL = active,
  renseignée = archivée à cette date. Le SERVEUR pose la date (`utcnow()`),
  jamais le client : `archived_at` n'est PAS exposé en écriture dans
  `ApplicationUpdate`, seulement en lecture dans `ApplicationRead`. Deux
  endpoints dédiés, `POST /applications/{id}/archive` et `/unarchive` — pas de
  PATCH générique sur ce champ.
- Le STATUT (ApplicationStatus) n'est JAMAIS modifié par l'archivage ou le
  désarchivage : il reste celui qu'il était au moment d'archiver.
- 409 EXPLICITE (pas d'idempotence silencieuse) sur une action redondante :
  archiver une candidature déjà archivée, ou désarchiver une candidature déjà
  active. Un succès sur une action qui n'a rien fait masquerait un bug côté
  client — cohérent avec le reste du projet (ex. le 409 du dernier tableau).
- Deux plafonds DISTINCTS, comptés GLOBALEMENT par utilisateur (même chaîne
  d'ownership que les autres limites), une candidature ne comptant jamais dans
  les deux à la fois :
  - MAX_APPLICATIONS_PER_USER (300) sur les ACTIVES, à la CRÉATION.
  - MAX_ARCHIVED_APPLICATIONS_PER_USER (2000) sur les ARCHIVÉES, à
    l'ARCHIVAGE. 409 : « Limite de 2000 candidatures archivées atteinte.
    Supprimez d'anciennes archives pour en archiver de nouvelles. »
  - Le DÉSARCHIVAGE est lui aussi plafonné par les 300 actives — sans ce
    contrôle, la limite se contournerait en archivant puis désarchivant. 409 :
    « Limite de 300 candidatures actives atteinte. Supprimez ou archivez une
    candidature active pour faire de la place. » La candidature visée est
    encore archivée au moment du contrôle, donc jamais comptée par erreur
    parmi les 300 actives comparées au plafond.
- ⚠ CORRECTION DE COMPORTEMENT (pas un simple ajout) : le comptage des 300
  actives à la CRÉATION (`create_application`) filtrait auparavant TOUTES les
  candidatures, archivées comprises. Sans le filtre `archived_at IS NULL`,
  archiver ne libérait AUCUNE place — l'archivage n'aurait eu aucun intérêt.
  Test de non-régression : `test_creating_application_counts_only_active_towards_the_cap`
  (tests/test_archiving.py), qui aurait échoué avant cette correction.
- Toutes les LECTURES DE LISTE excluent les archivées par défaut, via
  `?archived=` sur `GET /applications` (`bool`, PAS optionnel : vaut `false`
  quand il est absent — un client qui ignore l'archivage, extension comprise,
  reçoit le comportement sûr). `?archived=true` n'affiche QUE les archivées,
  jamais un mélange.
  Le garde-fou vit dans `_visible_applications_query` (routers/applications.py),
  dont le paramètre `archived` n'a PAS de valeur par défaut : tout futur
  endpoint de liste qui la réutiliserait doit choisir explicitement — l'oubli
  lève une `TypeError` immédiate, pas un bug silencieux. Ce n'est PAS la valeur
  par défaut du paramètre de requête qui protège (elle ne protège que CET
  endpoint), c'est celle-ci.
- L'ACCÈS PAR IDENTIFIANT (`_get_owned_application`, donc `GET`/`PATCH`/`DELETE
  /applications/{id}`) N'EST PAS filtré par `archived_at`, décision
  DÉLIBÉRÉE : la correction d'une candidature depuis la page d'archives
  en dépend (un PATCH doit rester possible sur une archivée, sans la
  désarchiver au passage).
- La cascade de suppression d'un tableau (cf. « Cascade de suppression »)
  emporte les candidatures ARCHIVÉES comme les actives — `ON DELETE CASCADE` ne
  distingue pas `archived_at`, aucune logique possible à ce niveau.
- `BoardRead` expose `active_applications_count` et `archived_applications_count`
  (routers/boards.py, `_to_board_read`), pour que le frontend puisse annoncer
  le nombre d'archives concernées avant de confirmer la suppression d'un
  tableau (`DeleteBoardModal.jsx`, commit a24bc5c). Calculés par DEUX requêtes COUNT par tableau
  (pas une agrégation), donc jusqu'à 2×MAX_BOARDS_PER_USER (20) requêtes
  supplémentaires sur `GET /boards`. MESURÉ (pas supposé), le 2026-09-28, sur
  PostgreSQL 18 jetable, 10 tableaux et ~200 candidatures chacun (2000 lignes,
  mélange actif/archivé) : 34 ms médiane sur 20 appels — négligeable à cette
  échelle (MAX_BOARDS_PER_USER = 10). À reconsidérer seulement si ce plafond
  changeait significativement.
