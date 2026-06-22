// Écran de connexion. Appelle login() du contexte d'auth, qui stocke le token
// et met à jour l'état. Au succès, redirige vers le kanban.

import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/useAuth.js'
import { styles } from '../components/ui.js'

export default function LoginPage() {
  const navigate = useNavigate()
  const { login } = useAuth()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [formError, setFormError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setFormError('')

    if (!email.trim() || !password) {
      setFormError('Renseignez votre email et votre mot de passe.')
      return
    }

    setLoading(true)
    try {
      await login(email, password)
      navigate('/', { replace: true })
    } catch (err) {
      // 401 : le backend renvoie volontairement le même message que l'email
      // existe ou non. On reste tout aussi générique côté UI.
      if (err.status === 401) {
        setFormError('Email ou mot de passe incorrect.')
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
        <h2 style={styles.title}>Connexion</h2>

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
          </div>

          <div style={styles.field}>
            <label style={styles.label} htmlFor="password">Mot de passe</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              style={styles.input}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{ ...styles.button, ...(loading ? styles.buttonDisabled : {}) }}
          >
            {loading ? 'Connexion…' : 'Se connecter'}
          </button>
        </form>

        <p style={styles.footer}>
          Pas encore de compte ? <Link to="/register">Créer un compte</Link>
        </p>
      </div>
    </div>
  )
}
