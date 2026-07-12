// Écran principal (protégé) : le kanban des candidatures du TABLEAU COURANT.
// Recharge les candidatures quand le tableau courant change et gère explicitement
// les trois états : chargement, erreur, succès (dont le cas liste vide).

import { useEffect, useMemo, useState } from 'react'
import { DragDropProvider } from '@dnd-kit/react'

import {
  getApplications,
  createApplication,
  updateApplication,
  deleteApplication,
} from '../api/applications.js'
import { useBoards } from '../boards/useBoards.js'
import Navbar from '../components/Navbar.jsx'
import Sidebar from '../components/Sidebar.jsx'
import KanbanColumn from '../components/KanbanColumn.jsx'
import Modal from '../components/Modal.jsx'
import Alert from '../components/Alert.jsx'
import ApplicationForm from '../components/ApplicationForm.jsx'
import BoardForm from '../components/BoardForm.jsx'
import { APPLICATION_STATUSES } from '../constants/applicationStatuses.js'

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
  // Id de la candidature en cours de suppression (désactive les actions).
  const [deletingId, setDeletingId] = useState(null)
  // Modale de tableau : null, { mode: 'create' }, ou { mode: 'rename', board }.
  const [boardModal, setBoardModal] = useState(null)
  // Id du tableau en cours de suppression (désactive son action dans la sidebar).
  const [deletingBoardId, setDeletingBoardId] = useState(null)
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

  // Fin d'un glisser-déposer. La carte (source) porte l'id de la candidature.
  // Deux familles de cibles partagent le MÊME contexte de drag & drop :
  //  - une COLONNE du kanban → change le statut (KanbanColumn, id = clé de statut,
  //    sans data.type) ;
  //  - un TABLEAU de la sidebar → déplace la candidature (BoardRow, data.type
  //    « board » + boardId).
  // On distingue les deux par `target.data.type` : le seul discriminant explicite,
  // posé uniquement par les tableaux ; toute cible sans ce marqueur est une colonne.
  function handleDragEnd(event) {
    const { operation, canceled } = event
    // Drag annulé (Échap) ou relâché hors d'une cible valide : rien à faire.
    if (canceled) return

    const source = operation.source
    const target = operation.target
    if (!source || !target) return

    const applicationId = source.id // id de la candidature (nombre)

    if (target.data?.type === 'board') {
      moveApplicationToBoard(applicationId, target.data.boardId)
      return
    }

    // Cible « colonne » : changement de statut (comportement existant, inchangé).
    const newStatus = target.id // clé du statut de la colonne cible (chaîne)

    // Statut d'origine mémorisé sur la carte (data.status), qui sert à la fois à
    // détecter un dépôt sans changement et de valeur de rollback en cas d'échec.
    const previousStatus = source.data?.status

    // Reposée dans sa colonne d'origine → aucun PATCH.
    if (previousStatus === newStatus) return

    // Mise à jour optimiste immédiate (la carte change de colonne avant la réponse
    // de l'API), via une mise à jour fonctionnelle ciblée sur la carte.
    setActionError('')
    setApplications((prev) =>
      prev.map((item) =>
        item.id === applicationId ? { ...item, status: newStatus } : item,
      ),
    )

    // PATCH en arrière-plan ; rollback ciblé si l'appel échoue. On ne restaure QUE
    // le statut de cette carte (à previousStatus) plutôt qu'un snapshot complet du
    // tableau : la mise à jour fonctionnelle se compose ainsi proprement avec
    // d'éventuelles autres modifications survenues entre-temps.
    updateApplication(applicationId, { status: newStatus }).catch((err) => {
      setApplications((prev) =>
        prev.map((item) =>
          item.id === applicationId ? { ...item, status: previousStatus } : item,
        ),
      )
      setActionError(
        err.message ||
          'Le changement de statut a échoué. La carte a été replacée.',
      )
    })
  }

  // Déplacement d'une candidature vers un AUTRE tableau, via le même chemin que la
  // modale d'édition (updateApplication avec board_id). Réutilisée par le drag vers
  // la sidebar.
  function moveApplicationToBoard(applicationId, targetBoardId) {
    // Lâchée sur le tableau courant : la candidature y est déjà (le droppable du
    // tableau courant est `disabled`, mais on reste défensif). Aucun PATCH.
    if (targetBoardId === currentBoardId) return

    // Mémorise la carte ET sa position pour un rollback fidèle en cas d'échec :
    // contrairement au changement de statut (une seule propriété à restaurer), un
    // déplacement RETIRE la carte de la vue courante et doit pouvoir la réinsérer.
    const index = applications.findIndex((item) => item.id === applicationId)
    if (index === -1) return
    const moved = applications[index]

    // Optimiste : la carte quitte le tableau courant → elle disparaît de la vue
    // (on n'affiche que les candidatures du tableau courant). Les compteurs de
    // colonnes se recalculent seuls (byStatus dérivé de `applications`).
    setActionError('')
    setApplications((prev) => prev.filter((item) => item.id !== applicationId))

    updateApplication(applicationId, { board_id: targetBoardId }).catch((err) => {
      // Rollback : on réinsère la carte à sa position d'origine (si elle n'y est
      // pas déjà revenue entre-temps).
      setApplications((prev) => {
        if (prev.some((item) => item.id === applicationId)) return prev
        const next = [...prev]
        next.splice(Math.min(index, next.length), 0, moved)
        return next
      })
      setActionError(
        err.message ||
          'Le déplacement vers le tableau a échoué. La carte a été restaurée.',
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
      // Préfixée à la liste (le backend trie par updated_at décroissant) → elle
      // apparaît en tête de la colonne « Repérée » sans rechargement.
      setApplications((prev) => [created, ...prev])
    }
    closeModal()
  }

  // Édition : la version à jour est renvoyée par l'API. Deux cas selon le tableau
  // de destination :
  //  - restée dans le tableau courant → on remplace la carte sur place ;
  //  - déplacée vers un AUTRE tableau → elle sort de la vue courante (on ne montre
  //    que les candidatures du tableau affiché), donc on la retire de la liste.
  async function handleUpdate(data) {
    const updated = await updateApplication(modal.application.id, data)
    setApplications((prev) =>
      updated.board_id === currentBoardId
        ? prev.map((item) => (item.id === updated.id ? updated : item))
        : prev.filter((item) => item.id !== updated.id),
    )
    closeModal()
  }

  // Suppression : confirmation, puis retrait de la carte de l'affichage.
  async function handleDelete() {
    const target = modal.application
    if (!window.confirm(`Supprimer la candidature « ${target.title} » ?`)) {
      return
    }

    setDeletingId(target.id)
    try {
      await deleteApplication(target.id)
      setApplications((prev) => prev.filter((item) => item.id !== target.id))
      closeModal()
    } catch (err) {
      // Erreur réseau/serveur : on garde la modale ouverte et on signale l'échec.
      window.alert(err.message || 'La suppression a échoué. Réessayez.')
    } finally {
      setDeletingId(null)
    }
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

  // Suppression : confirmation explicite (la cascade supprime aussi les
  // candidatures), puis appel. Le contexte rebascule le tableau courant si on
  // supprime celui affiché. Un échec (ex. 409 dernier tableau, en filet de
  // sécurité malgré l'action masquée) est signalé sans planter.
  async function handleDeleteBoard(board) {
    const confirmed = window.confirm(
      `Supprimer le tableau « ${board.name} » et toutes ses candidatures ?`,
    )
    if (!confirmed) return

    setDeletingBoardId(board.id)
    try {
      await removeBoard(board.id)
    } catch (err) {
      window.alert(err.message || 'La suppression du tableau a échoué. Réessayez.')
    } finally {
      setDeletingBoardId(null)
    }
  }

  return (
    <>
      <Navbar />

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
        <DragDropProvider onDragEnd={handleDragEnd}>
        <div className="board-layout">
          <Sidebar
            boards={boards}
            currentBoardId={currentBoardId}
            onSelect={selectBoard}
            onCreate={() => setBoardModal({ mode: 'create' })}
            onRename={(board) => setBoardModal({ mode: 'rename', board })}
            onDelete={handleDeleteBoard}
            deletingBoardId={deletingBoardId}
          />

          <main className="board-main">
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

            {!loading && !error && applications.length === 0 && (
              <p className="text-muted">
                Ce tableau n’a pas encore de candidature.
              </p>
            )}

            {!loading && !error && applications.length > 0 && (
              <div className="kanban">
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
          </main>
        </div>
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
            deleting={deletingId === modal.application.id}
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
    </>
  )
}
