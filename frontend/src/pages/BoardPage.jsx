// Écran principal (protégé) : le kanban des candidatures du TABLEAU COURANT.
// Recharge les candidatures quand le tableau courant change et gère explicitement
// les trois états : chargement, erreur, succès (dont le cas liste vide).

import { useEffect, useMemo, useState } from 'react'
import { DragDropProvider, useDragOperation } from '@dnd-kit/react'

import {
  getApplications,
  createApplication,
  updateApplication,
  deleteApplication,
  archiveApplication,
  moveApplication,
} from '../api/applications.js'
import { useBoards } from '../boards/useBoards.js'
import { useKanbanDrag } from '../kanban/useKanbanDrag.js'
import { placeCard } from '../utils/kanbanOrder.js'
import Navbar from '../components/Navbar.jsx'
import VerificationBanner from '../components/VerificationBanner.jsx'
import Sidebar from '../components/Sidebar.jsx'
import KanbanColumn from '../components/KanbanColumn.jsx'
import ArchiveDropZone from '../components/ArchiveDropZone.jsx'
import Modal from '../components/Modal.jsx'
import Alert from '../components/Alert.jsx'
import ApplicationForm from '../components/ApplicationForm.jsx'
import BoardForm from '../components/BoardForm.jsx'
import ConfirmModal from '../components/ConfirmModal.jsx'
import DeleteBoardModal from '../components/DeleteBoardModal.jsx'
import { APPLICATION_STATUSES } from '../constants/applicationStatuses.js'
import { EXTENSION_URL } from '../constants/links.js'

// Enveloppe de <main class="board-main"> qui pose board-main--dragging pendant
// un glisser-déposer : cette classe réserve (par padding-bottom de la zone .kanban,
// celle qui défile, cf. components.css) la hauteur d'ArchiveDropZone, plutôt que
// de laisser la barre se superposer au bas des colonnes. DOIT être un composant à part — un hook
// appelé dans BoardPage lui-même n'aurait pas accès au contexte de
// DragDropProvider que BoardPage rend dans le même JSX (le contexte n'est
// fourni qu'à ses DESCENDANTS, pas au composant qui le monte).
//
// Pose aussi board-main--leaving quand la carte survole un tableau de la sidebar
// ou la zone d'archivage : la carte glissée (qui reste dans ce <main> même affichée
// en couche supérieure) devient translucide, elle va QUITTER le tableau (cf.
// components.css). La cible est un signal calculé : ce composant ne se réaffiche
// qu'au changement de cible, pas à chaque mouvement du pointeur.
function BoardMain({ children }) {
  const { source, target } = useDragOperation()
  const isDragging = source != null
  const targetType = target?.data?.type
  const isLeaving = isDragging && (targetType === 'board' || targetType === 'archive')

  const className = [
    'board-main',
    isDragging ? 'board-main--dragging' : '',
    isLeaving ? 'board-main--leaving' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return <main className={className}>{children}</main>
}

export default function BoardPage() {
  // Tableau courant (source de vérité partagée) : pilote quelles candidatures
  // afficher et le titre du kanban.
  const {
    boards,
    currentBoard,
    currentBoardId,
    selectBoard,
    createBoard,
    renameBoard,
    removeBoard,
    loading: boardsLoading,
    error: boardsError,
  } = useBoards()

  const [applications, setApplications] = useState([])
  const [error, setError] = useState('')
  // Tableau auquel correspondent les candidatures actuellement en mémoire. Sert à
  // DÉRIVER l'état de chargement (voir `loading` plus bas) sans setState synchrone
  // dans l'effet : dès que le tableau courant change, `loading` repasse à true.
  const [dataBoardId, setDataBoardId] = useState(null)

  // Chargement dérivé : true tant que les candidatures en mémoire ne correspondent
  // pas au tableau courant (transition, ou premier chargement).
  const loading = dataBoardId !== currentBoardId

  // État de la modale : null (fermée), { mode: 'create' }, ou
  // { mode: 'edit', application }. Une seule modale ouverte à la fois.
  const [modal, setModal] = useState(null)
  // Candidature ciblée par une suppression : pilote ConfirmModal. null = fermée.
  // Jamais ouverte en même temps que `modal` : une seule modale à la fois (deux
  // <Modal> empilées réagiraient toutes deux à Échap, écouteur posé sur document).
  const [applicationToDelete, setApplicationToDelete] = useState(null)
  // Modale de tableau : null, { mode: 'create' }, ou { mode: 'rename', board }.
  const [boardModal, setBoardModal] = useState(null)
  // Tableau ciblé par une suppression : pilote l'ouverture de DeleteBoardModal.
  // null = fermée.
  const [boardToDelete, setBoardToDelete] = useState(null)
  // Erreur d'une action ponctuelle (ex. échec du changement de statut). Distincte
  // de `error` (échec de chargement) : elle ne masque pas le board, s'affiche en
  // bannière au-dessus, et est effacée à la prochaine action réussie.
  const [actionError, setActionError] = useState('')

  useEffect(() => {
    // Tant que le tableau courant n'est pas déterminé (tableaux en cours de
    // chargement), on ne charge rien : l'écran affiche l'état des tableaux.
    if (currentBoardId == null) return

    // `active` : évite de poser l'état si le composant est démonté ou si le
    // tableau change avant la réponse (course entre deux sélections).
    let active = true

    // Aucun setState synchrone ici : tout se joue dans les callbacks async. Le
    // marquage `setDataBoardId(currentBoardId)` (succès comme échec) fait
    // repasser `loading` à false et associe le résultat au bon tableau. Pendant
    // la transition, `loading` (dérivé) masque déjà les candidatures/erreur du
    // tableau précédent.
    getApplications(currentBoardId)
      .then((data) => {
        if (!active) return
        setApplications(data)
        setError('')
        setDataBoardId(currentBoardId)
      })
      .catch((err) => {
        if (!active) return
        setApplications([])
        setError(err.message || 'Impossible de charger les candidatures.')
        setDataBoardId(currentBoardId)
      })

    return () => {
      active = false
    }
  }, [currentBoardId])

  // Répartition des candidatures par statut, en respectant l'ordre des colonnes.
  // Une candidature au statut inconnu (désync backend) est simplement ignorée.
  const byStatus = useMemo(() => {
    const groups = Object.fromEntries(
      APPLICATION_STATUSES.map((status) => [status.key, []]),
    )
    for (const application of applications) {
      if (groups[application.status]) {
        groups[application.status].push(application)
      }
    }
    return groups
  }, [applications])

  function closeModal() {
    setModal(null)
  }

  // Glisser-déposer : début, survol et fin (kanban/useKanbanDrag.js). Pendant le
  // survol, la liste est réordonnée et la carte se déplace réellement dans les
  // colonnes ; le placeholder de dnd-kit montre où elle va s'insérer.
  const kanbanDrag = useKanbanDrag(applications, setApplications)

  // Fin d'un glisser-déposer. Trois familles de cibles partagent le MÊME contexte :
  //  - un TABLEAU de la sidebar (BoardRow, data.type « board » + boardId) →
  //    déplacement vers ce tableau ;
  //  - la ZONE D'ARCHIVAGE (data.type « archive ») → archivage ;
  //  - tout le reste (une carte, une colonne, ou aucune cible : relâchée hors de
  //    tout) → la carte va là où le placeholder la montrait au moment du dépôt.
  // Pour les deux premières, seule compte la place d'ORIGINE (`drag.original`) : une
  // colonne traversée pendant le survol ne change ni le statut envoyé ni le rang de
  // retour en cas d'échec.
  function handleDragEnd(event) {
    const drag = kanbanDrag.endDrag()
    if (!drag) return

    const { operation, canceled } = event
    // Annulé (Échap) : la carte revient à sa place d'origine.
    if (canceled) {
      drag.restore()
      return
    }

    const target = operation.target
    if (target?.data?.type === 'board') {
      moveApplicationToBoard(drag, target.data.boardId)
      return
    }
    if (target?.data?.type === 'archive') {
      archiveViaDrag(drag)
      return
    }

    // Réordonnancement, dans la colonne ou vers une autre. Reposée à sa place
    // d'origine → aucun appel.
    const { from, to } = drag
    if (from.status === to.status && from.index === to.index) return

    // Mise à jour optimiste : l'état montre déjà la carte à sa nouvelle place
    // (survol). POST /move en arrière-plan ; retour ciblé en cas d'échec (seule
    // cette carte revient à sa place d'origine : les autres modifications
    // survenues entre-temps sont conservées).
    setActionError('')
    moveApplication(drag.applicationId, { status: to.status, position: to.index }).catch(
      (err) => {
        drag.restore()
        setActionError(
          err.message || 'Le déplacement de la carte a échoué. Elle a été replacée.',
        )
      },
    )
  }

  // Déplacement d'une candidature vers un AUTRE tableau par dépôt sur la sidebar,
  // via le même chemin que la modale d'édition (updateApplication avec board_id) :
  // le serveur la place EN HAUT de la colonne de même statut dans ce tableau.
  function moveApplicationToBoard(drag, targetBoardId) {
    // Lâchée sur le tableau courant : la candidature y est déjà (le droppable du
    // tableau courant est `disabled`, mais on reste défensif) : elle revient à sa
    // place d'origine, aucun PATCH.
    if (targetBoardId === currentBoardId) {
      drag.restore()
      return
    }

    // Optimiste : la carte quitte le tableau courant → elle disparaît de la vue
    // (on n'affiche que les candidatures du tableau courant). Les compteurs de
    // colonnes se recalculent seuls (byStatus dérivé de `applications`).
    setActionError('')
    setApplications((prev) => prev.filter((item) => item.id !== drag.applicationId))

    updateApplication(drag.applicationId, { board_id: targetBoardId }).catch((err) => {
      // Retour : la carte réapparaît à sa place d'origine.
      drag.restore()
      setActionError(
        err.message ||
          'Le déplacement vers le tableau a échoué. La carte a été restaurée.',
      )
    })
  }

  // Archivage par glisser-déposer sur ArchiveDropZone : même chemin optimiste
  // que moveApplicationToBoard (la carte disparaît immédiatement, la vue
  // courante ne montrant que les candidatures ACTIVES). Retour ciblé si le
  // serveur refuse (409, plafond de 2000 archivées, ou déjà archivée) ;
  // l'erreur va dans la bannière actionError, comme les autres échecs de drag.
  function archiveViaDrag(drag) {
    setActionError('')
    setApplications((prev) => prev.filter((item) => item.id !== drag.applicationId))

    archiveApplication(drag.applicationId).catch((err) => {
      drag.restore()
      setActionError(
        err.message || "L'archivage a échoué. La carte a été restaurée.",
      )
    })
  }

  // Création : la candidature créée est renvoyée par le backend (statut « saved »).
  // Le formulaire y attache un board_id (tableau courant par défaut, ou un autre
  // tableau choisi). On ne l'ajoute au kanban QUE si elle appartient au tableau
  // affiché ; créée dans un autre tableau, elle n'a pas à apparaître ici.
  async function handleCreate(data) {
    const created = await createApplication(data)
    if (created.board_id === currentBoardId) {
      // Préfixée à la liste → elle apparaît EN HAUT de la colonne « Repérée », là
      // où le serveur l'a placée (règle d'arrivée en haut).
      setApplications((prev) => [created, ...prev])
    }
    closeModal()
  }

  // Édition : la version à jour est renvoyée par l'API. Trois cas :
  //  - restée dans le tableau courant, même statut → remplacée sur place ;
  //  - restée dans le tableau courant, statut CHANGÉ → EN HAUT de sa nouvelle
  //    colonne, comme le serveur l'a placée (règle d'arrivée en haut) : l'affichage
  //    ne change pas au rechargement ;
  //  - déplacée vers un AUTRE tableau → elle sort de la vue courante (on ne montre
  //    que les candidatures du tableau affiché), donc on la retire de la liste.
  // Le formulaire renvoie toujours le statut, même inchangé : on compare au statut
  // d'avant, comme le serveur.
  async function handleUpdate(data) {
    const previousStatus = modal.application.status
    const updated = await updateApplication(modal.application.id, data)
    setApplications((prev) => {
      if (updated.board_id !== currentBoardId) {
        return prev.filter((item) => item.id !== updated.id)
      }
      const replaced = prev.map((item) => (item.id === updated.id ? updated : item))
      return updated.status === previousStatus
        ? replaced
        : placeCard(replaced, updated.id, { status: updated.status, index: 0 })
    })
    closeModal()
  }

  // Archivage depuis la modale (alternative au glisser-déposer vers la zone
  // d'archive) : réversible, donc AUCUNE confirmation demandée. La candidature
  // n'est plus active, elle sort de la vue de ce tableau — même sort qu'un
  // déplacement vers un autre tableau (GET /applications ne renvoie que les
  // actives). Aucun try/catch ici : une erreur (409, plafond de 2000
  // archivées) doit remonter au formulaire, qui l'affiche et reste ouvert.
  async function handleArchive() {
    const target = modal.application
    await archiveApplication(target.id)
    setApplications((prev) => prev.filter((item) => item.id !== target.id))
    closeModal()
  }

  // Suppression, en trois temps. « Supprimer » (modale d'édition) ÉCHANGE la
  // modale d'édition contre la confirmation — jamais les deux à la fois.
  // Les modifications non enregistrées du formulaire sont perdues (décision :
  // cliquer sur « Supprimer » signifie qu'on veut jeter la candidature).
  function handleDelete() {
    setApplicationToDelete(modal.application)
    setModal(null)
  }

  // « Annuler » ramène à l'édition de la même candidature (celle d'où l'on
  // venait), formulaire réinitialisé.
  function handleCancelDelete() {
    setModal({ mode: 'edit', application: applicationToDelete })
    setApplicationToDelete(null)
  }

  // Pas de try/catch : une erreur remonte à ConfirmModal, qui l'affiche et reste
  // ouverte (même principe que la suppression d'un tableau ou d'une archive).
  async function handleConfirmDeleteApplication() {
    const target = applicationToDelete
    await deleteApplication(target.id)
    setApplications((prev) => prev.filter((item) => item.id !== target.id))
    setApplicationToDelete(null)
  }

  // --- Gestion des tableaux (création / renommage / suppression) ---
  // Les appels réseau + la mise à jour de la liste vivent dans BoardsProvider ;
  // ici on ne pilote que l'ouverture des modales et la confirmation de suppression.

  function closeBoardModal() {
    setBoardModal(null)
  }

  // Création : createBoard (contexte) crée, ajoute à la liste ET bascule le
  // tableau courant sur le nouveau ; on ferme la modale au succès. Une erreur
  // (réseau/serveur) est propagée à BoardForm, qui l'affiche sans fermer.
  async function handleCreateBoard(name) {
    await createBoard(name)
    closeBoardModal()
  }

  // Renommage : le titre du kanban suit automatiquement (currentBoard dérivé).
  async function handleRenameBoard(name) {
    await renameBoard(boardModal.board.id, name)
    closeBoardModal()
  }

  // Suppression : la confirmation (DeleteBoardModal) annonce ce que la cascade
  // emporte. Pas de try/catch ici : une erreur (ex. 409 dernier tableau, en
  // filet de sécurité malgré l'action masquée) remonte à ConfirmModal, qui
  // l'affiche et reste ouverte. Le contexte rebascule le tableau courant si on
  // supprime celui affiché.
  async function handleConfirmDeleteBoard() {
    await removeBoard(boardToDelete.id)
    setBoardToDelete(null)
  }

  return (
    // .board-page : hauteur de la fenêtre, la PAGE ne défile pas (components.css).
    // C'est la zone .kanban qui défile, dans les deux sens : ses en-têtes de
    // colonnes peuvent alors rester collés, la sidebar et le bouton d'ajout
    // restent visibles, et la barre de défilement horizontale est toujours en bas
    // de l'écran. Les modales, en position fixe, n'en dépendent pas.
    <div className="board-page">
      <Navbar withSidebarToggle />
      {/* Ne rend rien si l'adresse est déjà vérifiée (ou si `user` n'est pas
          encore chargé) : aucun décalage de mise en page dans le cas courant. */}
      <VerificationBanner />

      {boardsLoading && (
        <main className="board-main">
          <p className="text-muted">Chargement des tableaux…</p>
        </main>
      )}

      {!boardsLoading && boardsError && (
        <main className="board-main">
          <Alert>{boardsError}</Alert>
        </main>
      )}

      {!boardsLoading && !boardsError && (
        // DragDropProvider englobe la sidebar ET le kanban : les cartes draggables
        // et les tableaux droppables doivent partager le même contexte de drag &
        // drop pour qu'une carte puisse être déposée sur un tableau. (Il était
        // auparavant limité au kanban ; il remonte ici sans changer le drag entre
        // colonnes, qui reste géré par le même onDragEnd.)
        <DragDropProvider
          onDragStart={kanbanDrag.onDragStart}
          onDragOver={kanbanDrag.onDragOver}
          onDragEnd={handleDragEnd}
        >
        <div className="board-layout">
          <Sidebar
            boards={boards}
            currentBoardId={currentBoardId}
            onSelect={selectBoard}
            onCreate={() => setBoardModal({ mode: 'create' })}
            onRename={(board) => setBoardModal({ mode: 'rename', board })}
            onDelete={setBoardToDelete}
          />

          <BoardMain>
            <div className="board-header">
              <h1
                className="board-header__title"
                title={currentBoard?.name ?? undefined}
              >
                {currentBoard?.name ?? 'Tableau'}
              </h1>
              <button
                type="button"
                className="btn btn--primary"
                onClick={() => setModal({ mode: 'create' })}
              >
                Ajouter une candidature
              </button>
            </div>

            {actionError && <Alert className="stack-gap">{actionError}</Alert>}

            {loading && (
              <p className="text-muted">Chargement des candidatures…</p>
            )}

            {!loading && error && <Alert>{error}</Alert>}

            {/* Tableau vide (premier écran d'un nouvel inscrit : « Mes
                candidatures » est créé vide) : les cinq colonnes restent
                affichées, elles montrent les étapes du suivi ; une phrase dit
                comment ajouter une offre. Lien neutre : le teal reste unique à
                l'écran, sur le bouton d'ajout. */}
            {!loading && !error && applications.length === 0 && (
              <p className="board-empty-hint">
                Ce tableau est vide. Ajoutez une offre avec le bouton « Ajouter
                une candidature », ou directement depuis la page de l’offre
                grâce à{' '}
                <a href={EXTENSION_URL} target="_blank" rel="noreferrer">
                  l’extension Chrome
                </a>
                .
              </p>
            )}

            {!loading && !error && (
              // Zone qui défile (cf. .board-page) : focalisable et nommée, sinon
              // le clavier ne peut pas la faire défiler.
              <div
                className="kanban"
                tabIndex={0}
                role="region"
                aria-label="Colonnes du tableau"
              >
                {APPLICATION_STATUSES.map((status) => (
                  <KanbanColumn
                    key={status.key}
                    statusKey={status.key}
                    label={status.label}
                    applications={byStatus[status.key]}
                    onEditApplication={(application) =>
                      setModal({ mode: 'edit', application })
                    }
                  />
                ))}
              </div>
            )}
          </BoardMain>
        </div>
        <ArchiveDropZone />
        </DragDropProvider>
      )}

      {modal?.mode === 'create' && (
        <Modal title="Ajouter une candidature" onClose={closeModal}>
          <ApplicationForm
            submitLabel="Ajouter"
            boards={boards}
            initialBoardId={currentBoardId}
            onSubmit={handleCreate}
            onCancel={closeModal}
          />
        </Modal>
      )}

      {modal?.mode === 'edit' && (
        <Modal title="Modifier la candidature" onClose={closeModal}>
          <ApplicationForm
            initialValues={modal.application}
            boards={boards}
            initialBoardId={modal.application.board_id}
            submitLabel="Enregistrer"
            onSubmit={handleUpdate}
            onCancel={closeModal}
            onDelete={handleDelete}
            onArchive={handleArchive}
          />
        </Modal>
      )}

      {boardModal?.mode === 'create' && (
        <Modal title="Nouveau tableau" onClose={closeBoardModal}>
          <BoardForm
            submitLabel="Créer"
            onSubmit={handleCreateBoard}
            onCancel={closeBoardModal}
          />
        </Modal>
      )}

      {boardModal?.mode === 'rename' && (
        <Modal title="Renommer le tableau" onClose={closeBoardModal}>
          <BoardForm
            initialName={boardModal.board.name}
            submitLabel="Enregistrer"
            onSubmit={handleRenameBoard}
            onCancel={closeBoardModal}
          />
        </Modal>
      )}

      {applicationToDelete && (
        <ConfirmModal
          title="Supprimer la candidature"
          warningLead="Cette action est définitive et ne peut pas être annulée."
          warningDetail={`La candidature « ${applicationToDelete.title} » chez ${applicationToDelete.company} sera supprimée immédiatement.`}
          confirmLabel="Supprimer la candidature"
          confirmingLabel="Suppression…"
          onConfirm={handleConfirmDeleteApplication}
          onClose={handleCancelDelete}
        />
      )}

      {boardToDelete && (
        <DeleteBoardModal
          board={boardToDelete}
          onConfirm={handleConfirmDeleteBoard}
          onClose={() => setBoardToDelete(null)}
        />
      )}
    </div>
  )
}
