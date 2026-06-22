// Écran principal (protégé) : le kanban des candidatures, en lecture seule.
// Charge les candidatures au montage et gère explicitement les trois états :
// chargement, erreur, succès (dont le cas liste vide).

import { useEffect, useMemo, useState } from 'react'

import { getApplications } from '../api/applications.js'
import Navbar from '../components/Navbar.jsx'
import KanbanColumn from '../components/KanbanColumn.jsx'
import { APPLICATION_STATUSES } from '../constants/applicationStatuses.js'

const mainStyle = { padding: 24, textAlign: 'left' }

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

  return (
    <>
      <Navbar />
      <main style={mainStyle}>
        <h1>Mon kanban</h1>

        {loading && <p style={messageStyle}>Chargement des candidatures…</p>}

        {!loading && error && (
          <p role="alert" style={errorStyle}>
            {error}
          </p>
        )}

        {!loading && !error && applications.length === 0 && (
          <p style={messageStyle}>
            Vous n’avez pas encore de candidature. Vous pourrez bientôt en
            ajouter ici (formulaire et extension navigateur).
          </p>
        )}

        {!loading && !error && applications.length > 0 && (
          <div style={boardStyle}>
            {APPLICATION_STATUSES.map((status) => (
              <KanbanColumn
                key={status.key}
                label={status.label}
                applications={byStatus[status.key]}
              />
            ))}
          </div>
        )}
      </main>
    </>
  )
}
