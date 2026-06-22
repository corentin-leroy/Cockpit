// Écran d'inscription. Valide basiquement les champs (miroir de la règle
// backend : email non vide, mot de passe >= 8), appelle register(), puis
// connecte automatiquement l'utilisateur et redirige vers le kanban.

import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { register as apiRegister } from '../api/auth.js'
import { useAuth } from '../auth/useAuth.js'
import { styles } from '../components/ui.js'

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
      navigate('/', { replace: true })
    } catch (err) {
      if (err.status === 409) {
        setFormError('Cet email est déjà utilisé.')
      } else if (err.status === 422) {
        // Validation refusée par le backend (filet de sécurité si la nôtre rate
        // un cas, ex. email mal formé accepté par notre test « contient @ »).
        setFormError('Email ou mot de passe invalide.')
      } else {
        setFormError(err.message || 'Une erreur est survenue. Réessayez.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <h2 style={styles.title}>Créer un compte</h2>

        {formError && <div style={styles.formError}>{formError}</div>}

        <form onSubmit={handleSubmit} noValidate>
          <div style={styles.field}>
            <label style={styles.label} htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              style={styles.input}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            {fieldErrors.email && (
              <span style={styles.fieldError}>{fieldErrors.email}</span>
            )}
          </div>

          <div style={styles.field}>
            <label style={styles.label} htmlFor="password">Mot de passe</label>
            <input
              id="password"
              type="password"
              autoComplete="new-password"
              style={styles.input}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            {fieldErrors.password && (
              <span style={styles.fieldError}>{fieldErrors.password}</span>
            )}
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{ ...styles.button, ...(loading ? styles.buttonDisabled : {}) }}
          >
            {loading ? 'Création…' : 'Créer mon compte'}
          </button>
        </form>

        <p style={styles.footer}>
          Déjà un compte ? <Link to="/login">Se connecter</Link>
        </p>
      </div>
    </div>
  )
}
