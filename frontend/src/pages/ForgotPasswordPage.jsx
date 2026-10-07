// Écran « Mot de passe oublié » : saisie de l'email, envoi du lien de
// réinitialisation.
//
// Anti-énumération : le backend renvoie sciemment le même message que le compte
// existe ou non. Le front tient la même ligne — un seul message de confirmation,
// aucune branche conditionnelle qui laisserait deviner l'existence du compte.

import { useState } from 'react'
import { Link } from 'react-router-dom'

import { forgotPassword } from '../api/auth.js'
import { splitFormErrors } from '../api/client.js'
import { useRateLimitCooldown } from '../auth/useRateLimitCooldown.js'
import Alert, { FieldError } from '../components/Alert.jsx'
import AuthLayout from '../components/AuthLayout.jsx'

const FIELD_MAP = { email: 'email' }

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [fieldError, setFieldError] = useState('')
  const [formError, setFormError] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [loading, setLoading] = useState(false)
  const cooldown = useRateLimitCooldown()

  async function handleSubmit(event) {
    event.preventDefault()
    // Pendant un blocage (429), le bouton est désactivé ; ce garde couvre aussi
    // tout envoi qui contournerait le bouton.
    if (cooldown.active) return
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
      // Seuls des échecs TECHNIQUES ou de LIMITATION arrivent ici (réseau, 422
      // email mal formé, 429 de la limite par IP, 5xx) : l'API ne renvoie jamais
      // d'erreur signalant un compte inconnu. Le 429 ne l'enfreint pas : cette
      // limite compte les demandes de l'adresse IP, quel que soit l'email, donc
      // elle est identique que le compte existe ou non. Le plafond PAR COMPTE, lui,
      // reste silencieux côté backend.
      // Un 429 portant un délai lisible est pris en charge par le blocage partagé
      // (message conservé et bouton désactivé le temps d'attente) ; sans délai
      // lisible, il suit le chemin des autres erreurs ci-dessous.
      if (cooldown.handle(err)) return
      // Les messages backend (422, 429…) sont directement affichables.
      const { fieldErrors, generalMessage } = splitFormErrors(err, FIELD_MAP)
      setFieldError(fieldErrors.email || '')
      setFormError(generalMessage)
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthLayout>
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
          {cooldown.active && <Alert className="stack-gap">{cooldown.message}</Alert>}

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
              disabled={loading || cooldown.active}
              className="btn btn--primary btn--block"
            >
              {loading ? 'Envoi…' : cooldown.active ? cooldown.buttonLabel : 'Envoyer le lien'}
            </button>
          </form>

          <p className="auth-card__footer">
            <Link to="/login">Retour à la connexion</Link>
          </p>
        </>
      )}
    </AuthLayout>
  )
}
