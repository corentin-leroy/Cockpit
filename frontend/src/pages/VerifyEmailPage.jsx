// Écran de confirmation d'adresse email : consomme le lien reçu (?token=…) dès
// le chargement, sans action de l'utilisateur — il vient de cliquer, c'était son
// action.
//
// Route PUBLIQUE (ni ProtectedRoute ni GuestRoute) : le token porte l'identité.
// Un utilisateur DÉJÀ connecté qui clique sur le lien depuis sa boîte mail doit
// atterrir ici, pas être renvoyé vers l'app par une garde de route.

import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { verifyEmail } from '../api/auth.js'
import { useAuth } from '../auth/useAuth.js'
import { useResendVerification } from '../auth/useResendVerification.js'
import Alert from '../components/Alert.jsx'

export default function VerifyEmailPage() {
  const [searchParams] = useSearchParams()
  const { isAuthenticated, refreshUser } = useAuth()
  const { resend, loading: resending, feedback } = useResendVerification()

  const token = searchParams.get('token') ?? ''

  // 'pending' (appel en cours) | 'success' | 'error'.
  const [status, setStatus] = useState(token ? 'pending' : 'error')
  const [message, setMessage] = useState(
    token ? '' : 'Ce lien de confirmation est incomplet : le token est absent.',
  )

  // Le token est à USAGE UNIQUE : un second appel le trouverait déjà consommé et
  // afficherait un échec. Ce garde-fou empêche le double déclenchement de l'effet
  // en StrictMode (dev), qui produirait exactement ce faux négatif.
  const consumed = useRef(false)

  useEffect(() => {
    if (!token || consumed.current) return
    consumed.current = true

    let active = true

    verifyEmail(token)
      .then((data) => {
        if (!active) return
        setStatus('success')
        setMessage(data.message)
        // Si l'utilisateur est connecté dans cet onglet, son `user` en contexte
        // porte encore is_verified: false — on le recharge pour que le bandeau
        // ait disparu quand il reviendra sur l'app.
        if (isAuthenticated) refreshUser()
      })
      .catch((err) => {
        if (!active) return
        setStatus('error')
        setMessage(
          err.status === 400
            ? 'Ce lien est invalide, expiré ou a déjà été utilisé.'
            : err.message || 'La confirmation a échoué. Réessayez plus tard.',
        )
      })

    return () => {
      active = false
    }
  }, [token, isAuthenticated, refreshUser])

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1 className="auth-card__title">Confirmation de votre adresse</h1>

        {status === 'pending' && (
          <p className="text-muted" role="status">
            Vérification en cours…
          </p>
        )}

        {status === 'success' && (
          <>
            <Alert variant="success">{message}</Alert>
            <p className="auth-card__footer">
              <Link to="/">Retour à mes candidatures</Link>
            </p>
          </>
        )}

        {status === 'error' && (
          <>
            <Alert>{message}</Alert>

            {isAuthenticated ? (
              <>
                <p className="auth-card__hint">
                  Vous pouvez vous faire renvoyer un lien de confirmation.
                </p>

                {feedback && (
                  <Alert variant={feedback.variant} className="stack-gap">
                    {feedback.message}
                  </Alert>
                )}

                <button
                  type="button"
                  className="btn btn--primary btn--block"
                  onClick={resend}
                  disabled={resending}
                >
                  {resending ? 'Envoi…' : 'Renvoyer l’email de confirmation'}
                </button>

                <p className="auth-card__footer">
                  <Link to="/">Retour à mes candidatures</Link>
                </p>
              </>
            ) : (
              // Non connecté : impossible de renvoyer un lien (l'endpoint est
              // authentifié — et il le reste, sinon il deviendrait un oracle
              // d'énumération des comptes). On invite donc à se connecter, d'où
              // le bandeau proposera le renvoi.
              <p className="auth-card__footer">
                Connectez-vous pour demander un nouveau lien.{' '}
                <Link to="/login">Se connecter</Link>
              </p>
            )}
          </>
        )}
      </div>
    </div>
  )
}
