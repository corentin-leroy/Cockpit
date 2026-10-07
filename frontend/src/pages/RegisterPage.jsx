// Écran d'inscription. Valide basiquement les champs (miroir de la règle
// backend : email non vide, mot de passe >= 8), appelle register(), puis
// connecte automatiquement l'utilisateur et redirige vers le kanban.

import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { register as apiRegister } from '../api/auth.js'
import { splitFormErrors } from '../api/client.js'
import { useAuth } from '../auth/useAuth.js'
import { useRateLimitCooldown } from '../auth/useRateLimitCooldown.js'
import Alert, { FieldError } from '../components/Alert.jsx'
import AuthLayout from '../components/AuthLayout.jsx'
import { PASSWORD_MAX_LENGTH } from '../constants/limits.js'
import { PRIVACY_URL } from '../constants/links.js'

const FIELD_MAP = { email: 'email', password: 'password' }

export default function RegisterPage() {
  const navigate = useNavigate()
  const { login } = useAuth()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fieldErrors, setFieldErrors] = useState({})
  const [formError, setFormError] = useState('')
  const [loading, setLoading] = useState(false)
  const cooldown = useRateLimitCooldown()

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
    // Pendant un blocage (429), le bouton est désactivé ; ce garde couvre aussi
    // tout envoi qui le contournerait.
    if (cooldown.active) return
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
      try {
        await login(email, password)
      } catch (loginErr) {
        // Le compte EXISTE désormais. Si la connexion automatique est refusée par
        // la limite de débit (429), ce n'est pas un échec d'inscription : afficher
        // « trop de tentatives » ici laisserait croire que rien n'a été créé, et
        // renvoyer l'utilisateur ressaisir ses identifiants le mènerait à un
        // « email déjà pris ». On le renvoie donc sur la connexion, avec la
        // confirmation que le compte est créé et l'heure à partir de laquelle il
        // pourra s'y connecter. Tout autre échec garde le traitement ci-dessous.
        if (loginErr.status === 429) {
          const until = loginErr.retryAfter ? Date.now() + loginErr.retryAfter * 1000 : null
          navigate('/login', { replace: true, state: { accountCreated: { until } } })
          return
        }
        throw loginErr
      }
      navigate('/app', { replace: true })
    } catch (err) {
      // 429 de l'INSCRIPTION elle-même (20 par heure et par IP) : avec un délai
      // lisible, le blocage partagé garde le message affiché et désactive le
      // bouton le temps d'attente ; sans délai lisible, il suit le chemin
      // ci-dessous (message affiché, bouton utilisable).
      if (cooldown.handle(err)) return
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
    <AuthLayout>
      <h1 className="auth-card__title">Créer un compte</h1>

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
            aria-describedby={fieldErrors.password ? undefined : 'register-password-hint'}
          />
          {/* La règle est annoncée AVANT la saisie, pas seulement par l'erreur.
              L'erreur la remplace quand elle s'affiche : les deux à la suite
              répéteraient la même consigne. */}
          {fieldErrors.password ? (
            <FieldError>{fieldErrors.password}</FieldError>
          ) : (
            <span id="register-password-hint" className="field__hint">
              8 caractères minimum.
            </span>
          )}
        </div>

        <button
          type="submit"
          disabled={loading || cooldown.active}
          className="btn btn--primary btn--block"
        >
          {loading ? 'Création…' : cooldown.active ? cooldown.buttonLabel : 'Créer mon compte'}
        </button>
      </form>

      {/* Information, pas consentement : aucune formule du type « vous
          acceptez ». Le pied de page porte aussi ce lien ; il est répété ici,
          au moment où l'adresse est confiée. */}
      <p className="auth-card__legal">
        Ce que Cockpit fait de vos données :{' '}
        <a href={PRIVACY_URL} target="_blank" rel="noopener noreferrer">
          politique de confidentialité
        </a>
        .
      </p>

      <p className="auth-card__footer">
        Déjà un compte ? <Link to="/login">Se connecter</Link>
      </p>
    </AuthLayout>
  )
}
