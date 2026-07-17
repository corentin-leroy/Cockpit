// Bandeau d'invitation à confirmer son adresse email, affiché sur les pages
// protégées tant que le compte n'est pas vérifié.
//
// NON BLOQUANT, par décision produit (cf. CLAUDE.md) : un compte non vérifié
// utilise l'app normalement. Le bandeau se contente donc de rappeler et de
// proposer l'action — il ne masque rien, ne modale rien, et n'est pas fermable
// (le fermer n'apporterait rien : il disparaît dès que l'adresse est confirmée,
// et le rappel serait sinon perdu au prochain rechargement).
//
// Il ne s'affiche pas non plus tant que `user` est absent : au premier rendu,
// /auth/me est encore en vol — l'afficher « au cas où » ferait clignoter un
// avertissement chez un utilisateur déjà vérifié.

import { useAuth } from '../auth/useAuth.js'
import { useResendVerification } from '../auth/useResendVerification.js'

export default function VerificationBanner() {
  const { user } = useAuth()
  const { resend, loading, feedback } = useResendVerification()

  if (!user || user.is_verified) return null

  return (
    <div className="banner" role="status">
      <span className="banner__icon" aria-hidden="true">
        ✉
      </span>

      <p className="banner__text">
        Vérifiez votre adresse email <strong>{user.email}</strong> pour
        sécuriser votre compte.
        {/* Le retour de l'envoi (succès, 429, erreur) s'affiche ici même, à côté
            de l'action : pas de bandeau supplémentaire empilé au-dessus. */}
        {feedback && (
          <span className={`banner__feedback banner__feedback--${feedback.variant}`}>
            <span aria-hidden="true">{feedback.variant === 'success' ? '✓' : '⚠'}</span>{' '}
            {feedback.message}
          </span>
        )}
      </p>

      <button
        type="button"
        className="btn btn--secondary btn--sm"
        onClick={resend}
        disabled={loading}
      >
        {loading ? 'Envoi…' : 'Renvoyer l’email'}
      </button>
    </div>
  )
}
