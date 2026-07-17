// Écran « Nouveau mot de passe » : consomme le lien reçu par email (?token=…)
// et fixe un nouveau mot de passe.
//
// Route PUBLIQUE : le token EST la preuve d'identité. On n'exige pas d'être
// connecté (celui qui a oublié son mot de passe ne l'est justement pas).

import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { resetPassword } from '../api/auth.js'
import { useAuth } from '../auth/useAuth.js'
import Alert, { FieldError } from '../components/Alert.jsx'

// Délai avant la redirection automatique vers /login : laisse le temps de lire
// le message de succès, sans obliger à cliquer.
const REDIRECT_DELAY_MS = 2500

export default function ResetPasswordPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { isAuthenticated, logout } = useAuth()

  const token = searchParams.get('token') ?? ''

  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [fieldErrors, setFieldErrors] = useState({})
  const [formError, setFormError] = useState('')
  // `true` quand le lien lui-même est en cause (absent, invalide, expiré, déjà
  // utilisé) : le formulaire n'a alors plus de sens, on propose de redemander un
  // email plutôt que de laisser resaisir un mot de passe dans le vide.
  const [linkInvalid, setLinkInvalid] = useState(!token)
  const [success, setSuccess] = useState(false)
  const [loading, setLoading] = useState(false)

  // Redirection après succès. Le timer est nettoyé au démontage : si l'utilisateur
  // clique sur le lien avant la fin du délai, aucune navigation ne se déclenche
  // sur un composant démonté.
  useEffect(() => {
    if (!success) return
    const timer = setTimeout(() => navigate('/login', { replace: true }), REDIRECT_DELAY_MS)
    return () => clearTimeout(timer)
  }, [success, navigate])

  /** Validation côté client, miroir de la règle backend (min 8 caractères). */
  function validate() {
    const errors = {}
    if (password.length < 8) {
      errors.password = 'Au moins 8 caractères.'
    }
    if (confirmation !== password) {
      errors.confirmation = 'Les deux mots de passe ne correspondent pas.'
    }
    return errors
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setFormError('')

    const errors = validate()
    setFieldErrors(errors)
    if (Object.keys(errors).length > 0) return

    setLoading(true)
    try {
      await resetPassword(token, password)

      // Le mot de passe a changé : une session ouverte dans cet onglet repose sur
      // l'ancien (un JWT déjà émis reste techniquement valable jusqu'à son
      // expiration). On la ferme pour que l'utilisateur reprenne proprement au
      // login — sans quoi la redirection vers /login serait d'ailleurs renvoyée
      // vers l'app par GuestRoute.
      if (isAuthenticated) logout()

      setSuccess(true)
    } catch (err) {
      if (err.status === 400) {
        // Lien invalide, expiré ou déjà consommé : le backend ne distingue pas
        // les trois (inutile pour le client, l'action à faire est la même).
        setLinkInvalid(true)
      } else if (err.status === 422) {
        setFieldErrors({ password: 'Mot de passe invalide (8 caractères minimum).' })
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
        <h1 className="auth-card__title">Nouveau mot de passe</h1>

        {success && (
          <>
            <Alert variant="success">
              Votre mot de passe a été mis à jour. Vous pouvez vous connecter.
            </Alert>
            <p className="auth-card__footer">
              Redirection en cours… <Link to="/login">Aller à la connexion</Link>
            </p>
          </>
        )}

        {!success && linkInvalid && (
          <>
            <Alert>
              Ce lien est invalide, expiré ou a déjà été utilisé. Les liens de
              réinitialisation ne sont valables qu’une heure et ne servent qu’une
              fois.
            </Alert>
            <p className="auth-card__footer">
              <Link to="/forgot-password">Demander un nouveau lien</Link>
            </p>
          </>
        )}

        {!success && !linkInvalid && (
          <>
            {formError && <Alert className="stack-gap">{formError}</Alert>}

            <form onSubmit={handleSubmit} noValidate>
              <div className="field">
                <label className="field__label" htmlFor="password">
                  Nouveau mot de passe
                </label>
                <input
                  id="password"
                  type="password"
                  autoComplete="new-password"
                  className="input"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  aria-invalid={Boolean(fieldErrors.password)}
                />
                {fieldErrors.password && (
                  <FieldError>{fieldErrors.password}</FieldError>
                )}
              </div>

              <div className="field">
                <label className="field__label" htmlFor="confirmation">
                  Confirmation
                </label>
                <input
                  id="confirmation"
                  type="password"
                  autoComplete="new-password"
                  className="input"
                  value={confirmation}
                  onChange={(e) => setConfirmation(e.target.value)}
                  aria-invalid={Boolean(fieldErrors.confirmation)}
                />
                {fieldErrors.confirmation && (
                  <FieldError>{fieldErrors.confirmation}</FieldError>
                )}
              </div>

              <button
                type="submit"
                disabled={loading}
                className="btn btn--primary btn--block"
              >
                {loading ? 'Enregistrement…' : 'Changer mon mot de passe'}
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
