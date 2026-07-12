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

import Alert, { FieldError } from './Alert.jsx'

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
      {formError && <Alert className="stack-gap">{formError}</Alert>}

      <div className="field">
        <label className="field__label" htmlFor="app-title">
          Intitulé du poste *
        </label>
        <input
          id="app-title"
          type="text"
          className="input"
          value={values.title}
          onChange={update('title')}
          aria-invalid={Boolean(fieldErrors.title)}
        />
        {fieldErrors.title && <FieldError>{fieldErrors.title}</FieldError>}
      </div>

      <div className="field">
        <label className="field__label" htmlFor="app-company">
          Entreprise *
        </label>
        <input
          id="app-company"
          type="text"
          className="input"
          value={values.company}
          onChange={update('company')}
          aria-invalid={Boolean(fieldErrors.company)}
        />
        {fieldErrors.company && <FieldError>{fieldErrors.company}</FieldError>}
      </div>

      <div className="field">
        <label className="field__label" htmlFor="app-location">
          Lieu
        </label>
        <input
          id="app-location"
          type="text"
          className="input"
          value={values.location}
          onChange={update('location')}
        />
      </div>

      <div className="field">
        <label className="field__label" htmlFor="app-url">
          Lien vers l'offre
        </label>
        <input
          id="app-url"
          type="url"
          placeholder="https://…"
          className="input"
          value={values.url}
          onChange={update('url')}
        />
      </div>

      <div className="field">
        <label className="field__label" htmlFor="app-notes">
          Notes
        </label>
        <textarea
          id="app-notes"
          className="input textarea"
          value={values.notes}
          onChange={update('notes')}
        />
      </div>

      {showBoardSelect && (
        <div className="field">
          <label className="field__label" htmlFor="app-board">
            Tableau
          </label>
          <select
            id="app-board"
            className="input"
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

      <div className="form-actions">
        {onDelete && (
          <button
            type="button"
            className="btn btn--danger"
            onClick={onDelete}
            disabled={busy}
          >
            {deleting ? 'Suppression…' : 'Supprimer'}
          </button>
        )}

        <div className="form-actions__right">
          <button
            type="button"
            className="btn btn--secondary"
            onClick={onCancel}
            disabled={busy}
          >
            Annuler
          </button>
          <button type="submit" className="btn btn--primary" disabled={busy}>
            {submitting ? 'Enregistrement…' : submitLabel}
          </button>
        </div>
      </div>
    </form>
  )
}
