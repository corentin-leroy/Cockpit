// Confirmation générique d'une action irréversible : modale stylée, jamais
// window.confirm/window.alert (cf. CLAUDE.md, « Suppression de compte » — une
// boîte native ne respecte ni les tokens ni le thème, et son bouton « OK » ne
// nomme pas l'action réelle). Généralisation de DeleteAccountModal, sans le
// champ mot de passe : les actions qui l'utilisent (suppression définitive
// d'une candidature) n'en exigent pas côté backend.

import { useState } from 'react'
import { Warning } from '@phosphor-icons/react'

import Alert from './Alert.jsx'
import Modal from './Modal.jsx'

/**
 * @param {Object} props
 * @param {string} props.title            titre de la modale.
 * @param {string} props.warningLead      phrase d'avertissement (gras, ton alerte).
 * @param {string} [props.warningDetail]  détail de ce qui va disparaître.
 * @param {string} props.confirmLabel     libellé du bouton de confirmation au repos.
 * @param {string} props.confirmingLabel  libellé du bouton pendant l'action.
 * @param {boolean} [props.confirmDisabled]  désactive le bouton de confirmation
 *   (ex. le temps de charger ce que l'action va détruire) sans fermer la modale.
 * @param {() => Promise<void>} props.onConfirm  action confirmée (async).
 * @param {() => void} props.onClose  fermeture sans confirmer.
 */
export default function ConfirmModal({
  title,
  warningLead,
  warningDetail,
  confirmLabel,
  confirmingLabel,
  confirmDisabled = false,
  onConfirm,
  onClose,
}) {
  const [formError, setFormError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // Pas de try/catch délégué au parent : une erreur reste ici, la modale
  // affiche le message et reste ouverte, comme DeleteAccountModal.
  async function handleConfirm() {
    setFormError('')
    setSubmitting(true)
    try {
      await onConfirm()
      // Succès : le parent ferme la modale (ce composant est démonté).
    } catch (err) {
      setFormError(err.message || "L'action a échoué. Réessayez.")
      setSubmitting(false)
    }
  }

  return (
    <Modal title={title} onClose={onClose}>
      {formError && <Alert className="stack-gap">{formError}</Alert>}

      {/* Sans champ de saisie, Modal porte le focus initial sur le premier
          bouton rencontré dans le DOM : la croix de fermeture, jamais le
          bouton de confirmation — Entrée n'exécute donc jamais l'action
          destructrice par défaut. */}
      <div className="confirm-warning" role="alert">
        <span className="confirm-warning__icon" aria-hidden="true">
          <Warning size={16} />
        </span>
        <div className="confirm-warning__body">
          <p className="confirm-warning__lead">{warningLead}</p>
          {warningDetail && (
            <p className="confirm-warning__detail">{warningDetail}</p>
          )}
        </div>
      </div>

      <div className="form-actions">
        <button
          type="button"
          className="btn btn--secondary"
          onClick={onClose}
          disabled={submitting}
        >
          Annuler
        </button>
        <button
          type="button"
          className="btn btn--danger"
          onClick={handleConfirm}
          disabled={submitting || confirmDisabled}
        >
          {submitting ? confirmingLabel : confirmLabel}
        </button>
      </div>
    </Modal>
  )
}
