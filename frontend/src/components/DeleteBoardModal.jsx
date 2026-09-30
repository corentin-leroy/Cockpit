// Confirmation de suppression d'un tableau, avec le nombre de candidatures
// (actives et archivées) qui disparaîtront avec lui.
//
// Les compteurs sont RECHARGÉS à l'ouverture (GET /boards), jamais lus dans la
// liste du contexte : cette liste est chargée une fois au montage de la page et
// devient périmée dès qu'on archive, supprime ou déplace une carte. Pour un
// message qui précède une suppression définitive, un chiffre périmé est
// inacceptable.
//
// UNE SEULE modale, dont le contenu évolue (chargement → chiffres, ou erreur) :
// échanger deux modales remonterait l'overlay (clignotement, focus rejoué,
// saut de mise en page). Le nom du tableau étant connu d'emblée, la question
// s'affiche tout de suite ; seule la ligne de détail attend les chiffres. Tant
// qu'ils ne sont pas reçus, le bouton de confirmation est désactivé : on ne
// propose JAMAIS la suppression sans chiffres fiables (échec du rechargement
// compris, ou tableau introuvable — supprimé depuis un autre onglet).

import { useEffect, useState } from 'react'

import { getBoards } from '../api/boards.js'
import { describeBoardContent } from '../utils/boardDeletion.js'
import ConfirmModal from './ConfirmModal.jsx'

const LOADING_DETAIL = 'Vérification du contenu du tableau…'
const LOAD_ERROR_DETAIL =
  'Impossible de vérifier le contenu du tableau. Fermez cette fenêtre et réessayez.'
const NOT_FOUND_DETAIL =
  "Ce tableau n'existe plus. Fermez cette fenêtre : la liste sera à jour au prochain chargement."

/**
 * @param {Object} props
 * @param {{id: number, name: string}} props.board  tableau à supprimer.
 * @param {() => Promise<void>} props.onConfirm  suppression effective (async).
 * @param {() => void} props.onClose  fermeture sans supprimer.
 */
export default function DeleteBoardModal({ board, onConfirm, onClose }) {
  // Aucun setState synchrone dans l'effet : tout se joue dans les callbacks.
  const [content, setContent] = useState({ status: 'loading', detail: LOADING_DETAIL })

  useEffect(() => {
    let active = true
    getBoards()
      .then((list) => {
        if (!active) return
        const fresh = list.find((item) => item.id === board.id)
        if (!fresh) {
          setContent({ status: 'error', detail: NOT_FOUND_DETAIL })
          return
        }
        setContent({
          status: 'ready',
          detail: describeBoardContent(
            fresh.active_applications_count,
            fresh.archived_applications_count,
          ),
        })
      })
      .catch(() => {
        if (active) setContent({ status: 'error', detail: LOAD_ERROR_DETAIL })
      })
    return () => {
      active = false
    }
  }, [board.id])

  return (
    <ConfirmModal
      title="Supprimer le tableau"
      warningLead={`Supprimer le tableau « ${board.name} » ?`}
      warningDetail={content.detail}
      confirmLabel="Supprimer le tableau"
      confirmingLabel="Suppression…"
      confirmDisabled={content.status !== 'ready'}
      onConfirm={onConfirm}
      onClose={onClose}
    />
  )
}
