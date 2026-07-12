// Formulaire d'un tableau, partagé par la création et le renommage.
//
// Un seul champ : name (requis). Même contrat que ApplicationForm : le formulaire
// gère son propre état (valeur, erreurs, soumission) et délègue l'appel réseau au
// parent via `onSubmit`, qui doit renvoyer une promesse. Si elle rejette, on
// affiche l'erreur et on garde la modale ouverte ; si elle résout, le parent ferme.

import { useState } from 'react'

import Alert, { FieldError } from './Alert.jsx'

// Longueur max du nom côté UX : garde la sidebar et le titre lisibles. Le backend
// borne plus largement (max_length=100) comme garde-fou de cohérence des données.
const NAME_MAX_LENGTH = 25

/**
 * @param {Object}   props
 * @param {string}  [props.initialName]  nom pré-rempli (mode renommage).
 * @param {string}   props.submitLabel   libellé du bouton de validation.
 * @param {(name: string) => Promise<void>} props.onSubmit  soumission (async).
 * @param {() => void} props.onCancel     fermeture sans enregistrer.
 */
export default function BoardForm({
  initialName = '',
  submitLabel,
  onSubmit,
  onCancel,
}) {
  const [name, setName] = useState(initialName)
  const [fieldError, setFieldError] = useState('')
  const [formError, setFormError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setFormError('')

    // Validation cliente : nom non vide (le backend l'exige aussi, min_length=1).
    if (!name.trim()) {
      setFieldError('Le nom du tableau est obligatoire.')
      return
    }
    setFieldError('')

    setSubmitting(true)
    try {
      await onSubmit(name.trim())
      // Succès : le parent ferme la modale (ce composant est démonté).
    } catch (err) {
      setFormError(err.message || 'Une erreur est survenue. Réessayez.')
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      {formError && <Alert className="stack-gap">{formError}</Alert>}

      <div className="field">
        <div className="field__label-row">
          <label className="field__label" htmlFor="board-name">
            Nom du tableau *
          </label>
          <span className="field__counter" aria-hidden="true">
            {name.length}/{NAME_MAX_LENGTH}
          </span>
        </div>
        <input
          id="board-name"
          type="text"
          maxLength={NAME_MAX_LENGTH}
          className="input"
          value={name}
          onChange={(event) => setName(event.target.value)}
          aria-invalid={Boolean(fieldError)}
        />
        {fieldError && <FieldError>{fieldError}</FieldError>}
      </div>

      <div className="form-actions">
        <button
          type="button"
          className="btn btn--secondary"
          onClick={onCancel}
          disabled={submitting}
        >
          Annuler
        </button>
        <button type="submit" className="btn btn--primary" disabled={submitting}>
          {submitting ? 'Enregistrement…' : submitLabel}
        </button>
      </div>
    </form>
  )
}
