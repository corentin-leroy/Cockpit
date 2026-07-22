// Confirmation de suppression de compte : modale exigeant le mot de passe.
//
// Pourquoi une modale stylée plutôt que window.confirm/window.alert : les boîtes
// natives ne peuvent pas contenir de champ de saisie (donc pas de confirmation
// par mot de passe), ne respectent ni les tokens ni le thème, ne sont pas
// stylables, et leur libellé de bouton (« OK ») ne dit pas ce qui va se passer.
// Ici le bouton porte l'action réelle, « Supprimer définitivement ».
//
// Le mot de passe est exigé par le BACKEND (403 sinon) : ce champ n'est pas un
// garde-fou d'interface qu'on pourrait contourner en appelant l'API directement.

import { useState } from 'react'

import Alert, { FieldError } from './Alert.jsx'
import Modal from './Modal.jsx'

/**
 * @param {Object} props
 * @param {(password: string) => Promise<void>} props.onConfirm  suppression (async).
 * @param {() => void} props.onClose  fermeture sans supprimer.
 */
export default function DeleteAccountModal({ onConfirm, onClose }) {
  const [password, setPassword] = useState('')
  const [fieldError, setFieldError] = useState('')
  const [formError, setFormError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setFormError('')

    if (!password) {
      setFieldError('Saisissez votre mot de passe pour confirmer.')
      return
    }
    setFieldError('')

    setSubmitting(true)
    try {
      await onConfirm(password)
      // Succès : le parent purge la session et redirige (composant démonté).
    } catch (err) {
      // 403 = mot de passe incorrect ; tout autre code = incident réseau/serveur.
      // Dans les deux cas le compte est intact et la modale reste ouverte.
      setFormError(err.message || 'La suppression a échoué. Réessayez.')
      setSubmitting(false)
    }
  }

  return (
    <Modal title="Supprimer votre compte" onClose={onClose}>
      <form onSubmit={handleSubmit} noValidate>
        {formError && <Alert className="stack-gap">{formError}</Alert>}

        {/* L'avertissement énumère ce qui disparaît, plutôt qu'un « êtes-vous
            sûr ? » abstrait : on ne peut consentir qu'à ce qu'on a compris. */}
        <div className="confirm-warning" role="alert">
          <span className="confirm-warning__icon" aria-hidden="true">
            ⚠
          </span>
          <div>
            <p className="confirm-warning__lead">
              Cette action est définitive et ne peut pas être annulée.
            </p>
            <p className="confirm-warning__detail">
              Vos tableaux, toutes vos candidatures et votre compte seront
              supprimés immédiatement. Aucune récupération n’est possible.
            </p>
          </div>
        </div>

        <div className="field">
          <label className="field__label" htmlFor="delete-account-password">
            Mot de passe *
          </label>
          <input
            id="delete-account-password"
            type="password"
            autoComplete="current-password"
            className="input"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            aria-invalid={Boolean(fieldError)}
            aria-describedby="delete-account-hint"
          />
          {fieldError && <FieldError>{fieldError}</FieldError>}
          <span id="delete-account-hint" className="field__hint">
            Votre mot de passe est demandé pour confirmer qu’il s’agit bien de
            vous.
          </span>
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
          <button type="submit" className="btn btn--danger" disabled={submitting}>
            {submitting ? 'Suppression…' : 'Supprimer définitivement'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
