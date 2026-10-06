# Roadmap V1 : historique
Historique des lots. Les points encore OUVERTS sont suivis uniquement dans la
section « Feuille de route » du CLAUDE.md racine.
1. [fait] CRUD candidatures + extension navigateur (extraction générique + JSON-LD)
2. [fait] Auth JWT multi-utilisateurs (inscription, login, protection, ownership)
3. Front React
   - [fait] Setup Vite + structure
   - [fait] Couche API + contexte d'auth
   - [fait] Écrans Login/Register + routes protégées
   - [fait] Kanban en lecture seule
   - [fait] Création / édition / suppression de candidatures (modale)
   - [fait] Drag & drop des cartes entre colonnes
   - [fait] Champ statut dans le formulaire, en mode édition uniquement
4. [fait] Reconnecter l'extension à l'auth (elle ne peut plus créer sans token)
5. Multi-tableaux (Boards)
   - [fait] Backend : modèle Board, CRUD, ownership en chaîne, board par défaut,
     dernier tableau non supprimable, cascade
   - [fait] Front : sélection/gestion des tableaux, board_id à la création
6. Design du site (en cours : ce qui reste est dans la feuille de route du
   CLAUDE.md racine)
   - [fait] DESIGN.md : direction visuelle, échelle typo, espacements, couleur
   - [fait] Refonte du kanban : densité, carte cliquable, tokens, contrastes
   - [fait] Refonte de la landing page : slogan en titre, vrai kanban de démonstration
     déplaçable (sans persistance), section confiance, extension présentée une fois,
     tous types de contrat, anciens styles `.landing-*` supprimés de components.css
   - [fait, committé (274b856)] Rythme visuel de la landing : échelle d'affichage (h1 de 36
     à 56px), fonds de section alternés (token `--color-surface-band` créé), kanban
     posé dans un panneau ombré qui chevauche la bande suivante, teal d'identité,
     sections aux dispositions toutes différentes, barre collée avec bouton
     d'inscription différé. Écarts documentés dans DESIGN.md (section « Landing
     page »). Palier typographique de 30px (`--text-2xl`) supprimé : le h1 par défaut
     passe à 28px (titres de Mon compte et Archives, qui dépassaient la règle)
7. Mot de passe oublié + vérification d'email (Brevo)
   - [fait] Backend : app/email.py, SecurityToken, 4 endpoints, rate limiting
   - [fait] Front : écrans /forgot-password, /reset-password, /verify-email
     (routes PUBLIQUES, sans garde) + bandeau "confirmez votre adresse"
     (is_verified via GET /auth/me) avec renvoi de l'email
8. [fait] Déploiement (backend + PostgreSQL sur Railway)
9. [fait] Archivage des candidatures
   - [fait, déployé le 2026-09-28] Backend : champ archived_at (migration
     0003), statut conservé à l'archivage, endpoints /archive et /unarchive,
     plafond de 2000 archivées, plafond de 300 actives au désarchivage,
     correction du comptage des 300 (n'exclut plus les archivées à tort),
     filtre ?archived= par défaut sur les listes, compteurs sur BoardRead —
     confirmé en production (`alembic current` → 0003 head)
   - [fait] Front : page d'archives (liste, recherche insensible aux accents
     et à la casse, tri par date d'archivage), archivage depuis la modale
     d'édition et par glisser-déposer sur le kanban, ancienneté affichée sur
     les cartes (en bas à droite, sur la ligne du lieu — présente même sans
     lieu), mise en page de la page d'archives (bordures de ligne alignées,
     largeurs de colonnes fixes, page centrée, recherche à 440px, cellules
     plafonnées à deux lignes) — committé et poussé sur origin/main (`git
     log`), déployé comme le reste du front
   - [fait, committé (44b4627)] Filtre par tableau sur la page d'archives
   - [fait, committé (a24bc5c)] Confirmation de suppression d'un tableau
     annonçant le nombre de candidatures concernées, actives et archivées
     (compteurs de BoardRead, `DeleteBoardModal.jsx`)
   - [fait] Suppression du statut "Refusée" : front (2a) déployé ; migration
     0002 + backend (2b) déployés le 2026-09-26 (confirmé : `alembic current`
     → 0002 head, cinq libellés d'enum relus en base) ; textes résiduels de la
     landing, du README et des commentaires nettoyés
10. [fait] Durcissement de la validation des entrées (lots 3a-3e)
    - [fait, déployé] 3a : mini-lot applied_at (bornes 1900-2100, conversion
      UTC) et correctif de la course d'inscription concurrente
    - [fait, déployé] 3b/3c : schémas Pydantic (InputModel, rejet du NUL et du
      surrogate isolé, PydanticCustomError), catalogue de messages d'erreur,
      format de réponse unique (detail + errors), les deux trous corrigés (401
      anonyme, 500 catch-all)
    - [fait, committé] 3d : extension alignée sur les mêmes limites (troncature
      du lieu, nettoyage des URL trop longues, maxLength, ApiError.data).
      Publication sur le Chrome Web Store : suivie dans la feuille de route du
      CLAUDE.md racine
    - [fait] 3e : migration 0004, `notes` passe de
      `Text` à `String(5000)` (longueur tirée de MAX_NOTES_LENGTH) : la borne est
      désormais appliquée par l'API ET par la base, comme tous les autres champs
      texte. Garde-fou explicite si une note dépasse déjà 5000 caractères,
      jamais de troncature. Testée sur PostgreSQL 18.6 jetable (aller-retour avec
      données, échec du garde-fou, échec de conversion sans troncature)
11. [fait, committé (6f9548b, a02a1c4), déployé et vérifié en production :
    migration contrôlée, cinq tests passés en ligne] Réordonnancement des
    cartes du kanban
    (colonne `position`, migration 0005, POST /applications/{id}/move, règle
    d'arrivée en haut, verrou par utilisateur, tri réordonnable côté front et sur
    la landing). Extension non modifiée (elle crée par POST : arrivée en haut).
12. [fait, committé, vérifié à la main dans l'extension chargée] Adaptateurs
    d'extraction par site dans l'extension (détail : extension/CLAUDE.md) :
    - France Travail, hôte `candidat.francetravail.fr` (18b2f95, 2026-10-05)
    - Indeed, hôte `fr.indeed.com` uniquement (committé dans 274b856,
      2026-10-06)
    Publication sur le Chrome Web Store : suivie dans la feuille de route du
    CLAUDE.md racine
