// Écran principal (protégé) : le kanban des candidatures, en lecture seule.
// Charge les candidatures au montage et gère explicitement les trois états :
// chargement, erreur, succès (dont le cas liste vide).

import { useEffect, useMemo, useState } from 'react'
import { DragDropProvider } from '@dnd-kit/react'

import {
  getApplications,
  createApplication,
  updateApplication,
  deleteApplication,
} from '../api/applications.js'
import Navbar from '../components/Navbar.jsx'
import KanbanColumn from '../components/KanbanColumn.jsx'
import Modal from '../components/Modal.jsx'
import ApplicationForm from '../components/ApplicationForm.jsx'
import { APPLICATION_STATUSES } from '../constants/applicationStatuses.js'

const mainStyle = { padding: 24, textAlign: 'left' }

const headerRowStyle = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: 16,
  marginBottom: 16,
}

const addButtonStyle = {
  padding: '8px 14px',
  borderRadius: 8,
  border: '1px solid var(--accent-border)',
  background: 'var(--accent-bg)',
  color: 'var(--text-h)',
  font: 'inherit',
  cursor: 'pointer',
}

const boardStyle = {
  display: 'flex',
  gap: 16,
  alignItems: 'flex-start',
  overflowX: 'auto', // 6 colonnes : défilement horizontal si l'écran est étroit
  paddingBottom: 8,
}

const messageStyle = { opacity: 0.8 }
const errorStyle = {
  color: '#d33',
  padding: '8px 12px',
  borderRadius: 8,
  background: 'rgba(221, 51, 51, 0.08)',
}

export default function BoardPage() {
  const [applications, setApplications] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // État de la modale : null (fermée), { mode: 'create' }, ou
  // { mode: 'edit', application }. Une seule modale ouverte à la fois.
  const [modal, setModal] = useState(null)
  // Id de la candidature en cours de suppression (désactive les actions).
  const [deletingId, setDeletingId] = useState(null)
  // Erreur d'une action ponctuelle (ex. échec du changement de statut). Distincte
  // de `error` (échec de chargement) : elle ne masque pas le board, s'affiche en
  // bannière au-dessus, et est effacée à la prochaine action réussie.
  const [actionError, setActionError] = useState('')

  useEffect(() => {
    // `active` : évite de poser l'état si le composant est démonté avant la
    // réponse (ex. redirection sur 401, ou double-montage StrictMode en dev).
    let active = true

    // Pas de setLoading(true)/setError('') ici : l'état initial les couvre déjà
    // (loading=true, error='') et l'effet ne s'exécute qu'au montage.
    getApplications()
      .then((data) => {
        if (active) setApplications(data)
      })
      .catch((err) => {
        if (active) {
          setError(err.message || 'Impossible de charger les candidatures.')
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [])

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

  // Fin d'un glisser-déposer. La carte porte l'id de la candidature ; la colonne
  // cible porte la clé du statut. On change le statut via PATCH, en optimiste.
  function handleDragEnd(event) {
    const { operation, canceled } = event
    // Drag annulé (Échap) ou relâché hors d'une colonne : rien à faire.
    if (canceled) return

    const source = operation.source
    const target = operation.target
    if (!source || !target) return

    const applicationId = source.id // id de la candidature (nombre)
    const newStatus = target.id // clé du statut de la colonne cible (chaîne)

    // Statut d'origine mémorisé sur la carte (data.status), qui sert à la fois à
    // détecter un dépôt sans changement et de valeur de rollback en cas d'échec.
    const previousStatus = source.data?.status

    // Étape 6 : reposée dans sa colonne d'origine → aucun PATCH.
    if (previousStatus === newStatus) return

    // Étape 4 : mise à jour optimiste immédiate (la carte change de colonne avant
    // la réponse de l'API), via une mise à jour fonctionnelle ciblée sur la carte.
    setActionError('')
    setApplications((prev) =>
      prev.map((item) =>
        item.id === applicationId ? { ...item, status: newStatus } : item,
      ),
    )

    // Étape 5 : PATCH en arrière-plan ; rollback ciblé si l'appel échoue. On ne
    // restaure QUE le statut de cette carte (à previousStatus) plutôt qu'un
    // snapshot complet du tableau : la mise à jour fonctionnelle se compose ainsi
    // proprement avec d'éventuelles autres modifications survenues entre-temps.
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

  // Création : la candidature créée est renvoyée par le backend (statut « saved »).
  // On la préfixe à la liste locale (le backend trie par updated_at décroissant),
  // ce qui la fait apparaître dans la colonne « Repérée » sans rechargement.
  async function handleCreate(data) {
    const created = await createApplication(data)
    setApplications((prev) => [created, ...prev])
    closeModal()
  }

  // Édition : on remplace la candidature par la version à jour renvoyée par l'API.
  async function handleUpdate(data) {
    const updated = await updateApplication(modal.application.id, data)
    setApplications((prev) =>
      prev.map((item) => (item.id === updated.id ? updated : item)),
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

  return (
    <>
      <Navbar />
      <main style={mainStyle}>
        <div style={headerRowStyle}>
          <h1 style={{ margin: 0 }}>Mon kanban</h1>
          <button
            type="button"
            style={addButtonStyle}
            onClick={() => setModal({ mode: 'create' })}
          >
            Ajouter une candidature
          </button>
        </div>

        {actionError && (
          <p role="alert" style={{ ...errorStyle, marginBottom: 16 }}>
            {actionError}
          </p>
        )}

        {loading && <p style={messageStyle}>Chargement des candidatures…</p>}

        {!loading && error && (
          <p role="alert" style={errorStyle}>
            {error}
          </p>
        )}

        {!loading && !error && applications.length === 0 && (
          <p style={messageStyle}>
            Vous n’avez pas encore de candidature. Cliquez sur « Ajouter une
            candidature » pour commencer.
          </p>
        )}

        {!loading && !error && applications.length > 0 && (
          <DragDropProvider onDragEnd={handleDragEnd}>
            <div style={boardStyle}>
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
          </DragDropProvider>
        )}
      </main>

      {modal?.mode === 'create' && (
        <Modal title="Ajouter une candidature" onClose={closeModal}>
          <ApplicationForm
            submitLabel="Ajouter"
            onSubmit={handleCreate}
            onCancel={closeModal}
          />
        </Modal>
      )}

      {modal?.mode === 'edit' && (
        <Modal title="Modifier la candidature" onClose={closeModal}>
          <ApplicationForm
            initialValues={modal.application}
            submitLabel="Enregistrer"
            onSubmit={handleUpdate}
            onCancel={closeModal}
            onDelete={handleDelete}
            deleting={deletingId === modal.application.id}
          />
        </Modal>
      )}
    </>
  )
}
