// Formulaire d'une candidature, partagé par la création et l'édition.
//
// Champs : title (requis), company (requis), location, url, notes.
// Champ status : ABSENT à la création (le backend impose toujours « saved »,
// Repérée) ; visible seulement en édition, comme alternative au drag & drop
// du kanban pour corriger un statut.
//
// Le formulaire possède son propre état (valeurs, erreurs de champ, état de
// soumission), à l'image des écrans Login/Register. Il délègue l'appel réseau au
// parent via `onSubmit`, qui doit renvoyer une promesse : si elle rejette, on
// affiche le message d'erreur ; si elle résout, le parent ferme la modale.

import { useState } from 'react'

import { splitFormErrors } from '../api/client.js'
import Alert, { FieldError } from './Alert.jsx'
import { APPLICATION_STATUSES } from '../constants/applicationStatuses.js'
import { formatApplicationAge } from '../utils/dates.js'
import {
  COMPANY_MAX_LENGTH,
  LOCATION_MAX_LENGTH,
  NOTES_MAX_LENGTH,
  TITLE_MAX_LENGTH,
  URL_MAX_LENGTH,
} from '../constants/limits.js'

// board_id et status sont volontairement ABSENTS de cette table : leur erreur
// (rarissime, jamais déclenchée par l'usage normal du sélecteur/du menu) irait
// dans un champ parfois masqué (un seul tableau : le sélecteur ne s'affiche
// pas) où le message ne serait jamais vu. Elle remonte donc en message général
// via splitFormErrors, jamais perdue.
const FIELD_MAP = {
  title: 'title',
  company: 'company',
  location: 'location',
  url: 'url',
  notes: 'notes',
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
 * @param {() => Promise<void>} [props.onArchive]  si fourni, affiche « Archiver ».
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
  onArchive,
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
    status: initialValues?.status ?? null,
  }))

  // Complexité progressive : on ne propose de CHOISIR un tableau que si
  // l'utilisateur en a plusieurs. Avec un seul tableau, aucun choix à faire.
  const showBoardSelect = boards.length > 1
  // Champ status réservé à l'édition (initialValues présent) : à la création,
  // le backend impose toujours « saved », ce champ n'a donc pas lieu d'être.
  const showStatusSelect = Boolean(initialValues)
  // Ancienneté en lecture seule, réservée à l'édition (created_at n'existe pas
  // encore à la création). Première lettre mise en minuscule pour s'insérer
  // dans la phrase (« Ajoutée aujourd'hui », « Ajoutée il y a 12 j » — déjà en
  // minuscule, l'opération est sans effet).
  const ageLabel = initialValues
    ? formatApplicationAge(initialValues.created_at)
    : null
  const [fieldErrors, setFieldErrors] = useState({})
  const [formError, setFormError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [archiving, setArchiving] = useState(false)

  const busy = submitting || deleting || archiving

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
    // status seulement en édition : jamais envoyé à la création (le backend
    // n'a pas ce champ dans ApplicationCreate, et l'imposer resterait ambigu).
    if (showStatusSelect) {
      payload.status = values.status
    }

    setSubmitting(true)
    try {
      await onSubmit(payload)
      // Succès : le parent ferme la modale (ce composant est démonté).
    } catch (err) {
      const { fieldErrors: apiFieldErrors, generalMessage } = splitFormErrors(err, FIELD_MAP)
      setFieldErrors(apiFieldErrors)
      setFormError(generalMessage)
      setSubmitting(false)
    }
  }

  // Archivage : réversible, donc aucune confirmation demandée (contrairement à
  // la suppression). Erreur gérée ICI, pas déléguée au parent : un 409 (plafond
  // de 2000 archivées) doit s'afficher dans la modale, qui reste ouverte,
  // exactement comme un échec de handleSubmit.
  async function handleArchive() {
    setFormError('')
    setArchiving(true)
    try {
      await onArchive()
      // Succès : le parent ferme la modale (ce composant est démonté).
    } catch (err) {
      setFormError(err.message || "L'archivage a échoué.")
      setArchiving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      {formError && <Alert className="stack-gap">{formError}</Alert>}

      {ageLabel && (
        <p className="form-meta">
          {`Ajoutée ${ageLabel[0].toLowerCase()}${ageLabel.slice(1)}`}
        </p>
      )}

      <div className="field">
        <label className="field__label" htmlFor="app-title">
          Intitulé du poste *
        </label>
        <input
          id="app-title"
          type="text"
          className="input"
          maxLength={TITLE_MAX_LENGTH}
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
          maxLength={COMPANY_MAX_LENGTH}
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
          maxLength={LOCATION_MAX_LENGTH}
          value={values.location}
          onChange={update('location')}
        />
        {fieldErrors.location && <FieldError>{fieldErrors.location}</FieldError>}
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
          maxLength={URL_MAX_LENGTH}
          value={values.url}
          onChange={update('url')}
          aria-invalid={Boolean(fieldErrors.url)}
        />
        {fieldErrors.url && <FieldError>{fieldErrors.url}</FieldError>}
      </div>

      <div className="field">
        <div className="field__label-row">
          <label className="field__label" htmlFor="app-notes">
            Notes
          </label>
          {/* Pas de variante de couleur : avec maxLength, dépasser la limite est
              IMPOSSIBLE (le navigateur bloque la saisie) — il n'y a donc rien à
              signaler comme erreur, seulement une information neutre. */}
          <span className="field__counter" aria-hidden="true">
            {values.notes.length}/{NOTES_MAX_LENGTH}
          </span>
        </div>
        <textarea
          id="app-notes"
          className="input textarea"
          maxLength={NOTES_MAX_LENGTH}
          value={values.notes}
          onChange={update('notes')}
          aria-invalid={Boolean(fieldErrors.notes)}
        />
        {fieldErrors.notes && <FieldError>{fieldErrors.notes}</FieldError>}
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

      {showStatusSelect && (
        <div className="field">
          <label className="field__label" htmlFor="app-status">
            Statut
          </label>
          <select
            id="app-status"
            className="input"
            value={values.status ?? ''}
            onChange={(event) =>
              setValues((prev) => ({ ...prev, status: event.target.value }))
            }
          >
            {APPLICATION_STATUSES.map((s) => (
              <option key={s.key} value={s.key}>
                {s.label}
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="form-actions">
        {onArchive && (
          <button
            type="button"
            className="btn btn--secondary"
            onClick={handleArchive}
            disabled={busy}
          >
            {archiving ? 'Archivage…' : 'Archiver'}
          </button>
        )}

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
