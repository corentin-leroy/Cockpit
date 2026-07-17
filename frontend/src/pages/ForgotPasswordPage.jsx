// Écran « Mot de passe oublié » : saisie de l'email, envoi du lien de
// réinitialisation.
//
// Anti-énumération : le backend renvoie sciemment le même message que le compte
// existe ou non. Le front tient la même ligne — un seul message de confirmation,
// aucune branche conditionnelle qui laisserait deviner l'existence du compte.

import { useState } from 'react'
import { Link } from 'react-router-dom'

import { forgotPassword } from '../api/auth.js'
import Alert, { FieldError } from '../components/Alert.jsx'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [fieldError, setFieldError] = useState('')
  const [formError, setFormError] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setFormError('')
    setFieldError('')

    if (!email.trim()) {
      setFieldError('Email requis.')
      return
    }

    setLoading(true)
    try {
      await forgotPassword(email)
      // Le message affiché est celui du backend, identique dans tous les cas.
      setSubmitted(true)
    } catch (err) {
      // Seuls des échecs TECHNIQUES arrivent ici (réseau, 422 email mal formé,
      // 5xx) : l'API ne renvoie jamais d'erreur signalant un compte inconnu.
      if (err.status === 422) {
        setFieldError('Format d’email invalide.')
      } else {
        setFormError(err.message || 'Une erreur est survenue. Réessayez.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1 className="auth-card__title">Mot de passe oublié</h1>

        {submitted ? (
          <>
            <Alert variant="success">
              Si un compte existe avec cette adresse, un email vient d’être
              envoyé. Le lien reste valable une heure.
            </Alert>
            <p className="auth-card__hint">
              Pensez à regarder dans vos spams si vous ne le voyez pas arriver.
            </p>
            <p className="auth-card__footer">
              <Link to="/login">Retour à la connexion</Link>
            </p>
          </>
        ) : (
          <>
            <p className="auth-card__intro">
              Saisissez l’adresse de votre compte : nous vous enverrons un lien
              pour choisir un nouveau mot de passe.
            </p>

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
                  aria-invalid={Boolean(fieldError)}
                />
                {fieldError && <FieldError>{fieldError}</FieldError>}
              </div>

              <button
                type="submit"
                disabled={loading}
                className="btn btn--primary btn--block"
              >
                {loading ? 'Envoi…' : 'Envoyer le lien'}
              </button>
            </form>

            <p className="auth-card__footer">
              <Link to="/login">Retour à la connexion</Link>
            </p>
          </>
        )}
      </div>
    </div>
  )
}
