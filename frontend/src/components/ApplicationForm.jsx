// Formulaire d'une candidature, partagé par la création et l'édition.
//
// Champs : title (requis), company (requis), location, url, notes.
// PAS de champ status : à la création le backend démarre en « saved » (Repérée),
// et le changement de statut se fera via le drag & drop du kanban.
//
// Le formulaire possède son propre état (valeurs, erreurs de champ, état de
// soumission), à l'image des écrans Login/Register. Il délègue l'appel réseau au
// parent via `onSubmit`, qui doit renvoyer une promesse : si elle rejette, on
// affiche le message d'erreur ; si elle résout, le parent ferme la modale.

import { useState } from 'react'

import { styles } from './ui.js'

const textareaStyle = { ...styles.input, minHeight: 80, resize: 'vertical' }

const actionsStyle = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: 8,
  marginTop: 8,
}

const rightActionsStyle = { display: 'flex', gap: 8, marginLeft: 'auto' }

const primaryButtonStyle = {
  padding: '10px 14px',
  borderRadius: 8,
  border: '1px solid var(--accent-border)',
  background: 'var(--accent-bg)',
  color: 'var(--text-h)',
  font: 'inherit',
  cursor: 'pointer',
}

const secondaryButtonStyle = {
  padding: '10px 14px',
  borderRadius: 8,
  border: '1px solid var(--border)',
  background: 'transparent',
  color: 'inherit',
  font: 'inherit',
  cursor: 'pointer',
}

const dangerButtonStyle = {
  padding: '10px 14px',
  borderRadius: 8,
  border: '1px solid rgba(221, 51, 51, 0.5)',
  background: 'transparent',
  color: '#d33',
  font: 'inherit',
  cursor: 'pointer',
}

/**
 * @param {Object}   props
 * @param {Object}  [props.initialValues]  valeurs pré-remplies (mode édition).
 * @param {Array}   [props.boards]         tableaux de l'utilisateur (pour le déroulant).
 * @param {number}  [props.initialBoardId] tableau pré-sélectionné (courant à la
 *   création, tableau actuel de la candidature à l'édition).
 * @param {string}   props.submitLabel      libellé du bouton de validation.
 * @param {(data: Object) => Promise<void>} props.onSubmit  soumission (async).
 * @param {() => void} props.onCancel        fermeture sans enregistrer.
 * @param {() => void} [props.onDelete]      si fourni, affiche « Supprimer ».
 * @param {boolean}  [props.deleting]        désactive les actions pendant la suppression.
 */
export default function ApplicationForm({
  initialValues,
  boards = [],
  initialBoardId,
  submitLabel,
  onSubmit,
  onCancel,
  onDelete,
  deleting = false,
}) {
  // On ne conserve que les champs éditables ; les valeurs manquantes (null côté
  // API) sont normalisées en chaîne vide pour des <input> contrôlés. board_id est
  // toujours dans l'état (requis à la création) même si le déroulant n'est pas
  // affiché — il vaut alors le tableau pré-sélectionné.
  const [values, setValues] = useState(() => ({
    title: initialValues?.title ?? '',
    company: initialValues?.company ?? '',
    location: initialValues?.location ?? '',
    url: initialValues?.url ?? '',
    notes: initialValues?.notes ?? '',
    board_id: initialBoardId ?? null,
  }))

  // Complexité progressive : on ne propose de CHOISIR un tableau que si
  // l'utilisateur en a plusieurs. Avec un seul tableau, aucun choix à faire.
  const showBoardSelect = boards.length > 1
  const [fieldErrors, setFieldErrors] = useState({})
  const [formError, setFormError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const busy = submitting || deleting

  function update(field) {
    return (event) => {
      const { value } = event.target
      setValues((prev) => ({ ...prev, [field]: value }))
    }
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setFormError('')

    // Validation cliente : title et company non vides (le backend l'exige aussi).
    const errors = {}
    if (!values.title.trim()) errors.title = 'Le titre est obligatoire.'
    if (!values.company.trim()) errors.company = "L'entreprise est obligatoire."
    setFieldErrors(errors)
    if (Object.keys(errors).length > 0) return

    // Normalisation : trim des champs ; champs optionnels vides → null (le backend
    // accepte null pour location/url/notes). board_id part toujours : requis à la
    // création, et à l'édition il permet le déplacement (inchangé s'il est égal).
    const payload = {
      board_id: values.board_id,
      title: values.title.trim(),
      company: values.company.trim(),
      location: values.location.trim() || null,
      url: values.url.trim() || null,
      notes: values.notes.trim() || null,
    }

    setSubmitting(true)
    try {
      await onSubmit(payload)
      // Succès : le parent ferme la modale (ce composant est démonté).
    } catch (err) {
      setFormError(err.message || 'Une erreur est survenue. Réessayez.')
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      {formError && (
        <div role="alert" style={styles.formError}>
          {formError}
        </div>
      )}

      <div style={styles.field}>
        <label style={styles.label} htmlFor="app-title">
          Intitulé du poste *
        </label>
        <input
          id="app-title"
          type="text"
          style={styles.input}
          value={values.title}
          onChange={update('title')}
          aria-invalid={Boolean(fieldErrors.title)}
        />
        {fieldErrors.title && (
          <span style={styles.fieldError}>{fieldErrors.title}</span>
        )}
      </div>

      <div style={styles.field}>
        <label style={styles.label} htmlFor="app-company">
          Entreprise *
        </label>
        <input
          id="app-company"
          type="text"
          style={styles.input}
          value={values.company}
          onChange={update('company')}
          aria-invalid={Boolean(fieldErrors.company)}
        />
        {fieldErrors.company && (
          <span style={styles.fieldError}>{fieldErrors.company}</span>
        )}
      </div>

      <div style={styles.field}>
        <label style={styles.label} htmlFor="app-location">
          Lieu
        </label>
        <input
          id="app-location"
          type="text"
          style={styles.input}
          value={values.location}
          onChange={update('location')}
        />
      </div>

      <div style={styles.field}>
        <label style={styles.label} htmlFor="app-url">
          Lien vers l'offre
        </label>
        <input
          id="app-url"
          type="url"
          placeholder="https://…"
          style={styles.input}
          value={values.url}
          onChange={update('url')}
        />
      </div>

      <div style={styles.field}>
        <label style={styles.label} htmlFor="app-notes">
          Notes
        </label>
        <textarea
          id="app-notes"
          style={textareaStyle}
          value={values.notes}
          onChange={update('notes')}
        />
      </div>

      {showBoardSelect && (
        <div style={styles.field}>
          <label style={styles.label} htmlFor="app-board">
            Tableau
          </label>
          <select
            id="app-board"
            style={styles.input}
            value={values.board_id ?? ''}
            // La valeur d'un <select> est une chaîne : on reconvertit en nombre
            // pour rester cohérent avec les ids côté API.
            onChange={(event) =>
              setValues((prev) => ({
                ...prev,
                board_id: Number(event.target.value),
              }))
            }
          >
            {boards.map((board) => (
              <option key={board.id} value={board.id}>
                {board.name}
              </option>
            ))}
          </select>
        </div>
      )}

      <div style={actionsStyle}>
        {onDelete && (
          <button
            type="button"
            style={{ ...dangerButtonStyle, ...(busy ? styles.buttonDisabled : {}) }}
            onClick={onDelete}
            disabled={busy}
          >
            {deleting ? 'Suppression…' : 'Supprimer'}
          </button>
        )}

        <div style={rightActionsStyle}>
          <button
            type="button"
            style={{ ...secondaryButtonStyle, ...(busy ? styles.buttonDisabled : {}) }}
            onClick={onCancel}
            disabled={busy}
          >
            Annuler
          </button>
          <button
            type="submit"
            style={{ ...primaryButtonStyle, ...(busy ? styles.buttonDisabled : {}) }}
            disabled={busy}
          >
            {submitting ? 'Enregistrement…' : submitLabel}
          </button>
        </div>
      </div>
    </form>
  )
}
