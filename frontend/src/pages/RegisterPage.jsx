// Écran d'inscription. Valide basiquement les champs (miroir de la règle
// backend : email non vide, mot de passe >= 8), appelle register(), puis
// connecte automatiquement l'utilisateur et redirige vers le kanban.

import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { register as apiRegister } from '../api/auth.js'
import { splitFormErrors } from '../api/client.js'
import { useAuth } from '../auth/useAuth.js'
import Alert, { FieldError } from '../components/Alert.jsx'
import { PASSWORD_MAX_LENGTH } from '../constants/limits.js'

const FIELD_MAP = { email: 'email', password: 'password' }

export default function RegisterPage() {
  const navigate = useNavigate()
  const { login } = useAuth()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fieldErrors, setFieldErrors] = useState({})
  const [formError, setFormError] = useState('')
  const [loading, setLoading] = useState(false)

  /** Validation côté client, miroir de la règle backend. */
  function validate() {
    const errors = {}
    if (!email.trim()) {
      errors.email = 'Email requis.'
    } else if (!email.includes('@')) {
      errors.email = 'Format d’email invalide.'
    }
    if (password.length < 8) {
      errors.password = 'Au moins 8 caractères.'
    }
    return errors
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setFormError('')

    const errors = validate()
    setFieldErrors(errors)
    if (Object.keys(errors).length > 0) {
      return
    }

    setLoading(true)
    try {
      await apiRegister(email, password)
      // Inscription réussie : on enchaîne sur une connexion automatique pour
      // éviter à l'utilisateur de ressaisir ses identifiants juste après.
      await login(email, password)
      navigate('/app', { replace: true })
    } catch (err) {
      // Le 409 (email déjà pris) comme le 422 (ex. email mal formé accepté par
      // notre test « contient @ », filet de sécurité) portent déjà un message
      // backend directement affichable — plus besoin de le deviner par code
      // HTTP ni de le reformuler ici.
      const { fieldErrors: apiFieldErrors, generalMessage } = splitFormErrors(err, FIELD_MAP)
      setFieldErrors(apiFieldErrors)
      setFormError(generalMessage)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1 className="auth-card__title">Créer un compte</h1>

        {formError && <Alert className="stack-gap">{formError}</Alert>}

        <form onSubmit={handleSubmit} noValidate>
          <div className="field">
            <label className="field__label" htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              className="input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              aria-invalid={Boolean(fieldErrors.email)}
            />
            {fieldErrors.email && <FieldError>{fieldErrors.email}</FieldError>}
          </div>

          <div className="field">
            <label className="field__label" htmlFor="password">Mot de passe</label>
            <input
              id="password"
              type="password"
              autoComplete="new-password"
              className="input"
              maxLength={PASSWORD_MAX_LENGTH}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              aria-invalid={Boolean(fieldErrors.password)}
            />
            {fieldErrors.password && (
              <FieldError>{fieldErrors.password}</FieldError>
            )}
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn btn--primary btn--block"
          >
            {loading ? 'Création…' : 'Créer mon compte'}
          </button>
        </form>

        <p className="auth-card__footer">
          Déjà un compte ? <Link to="/login">Se connecter</Link>
        </p>
      </div>
    </div>
  )
}
