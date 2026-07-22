// Écran « Mon compte » (protégé) : informations du compte et suppression.
//
// Deux zones nettement séparées, dans cet ordre : les informations (lecture
// seule), puis la zone de suppression. La séparation n'est pas décorative — une
// action irréversible ne doit jamais se trouver à portée de clic d'une action
// courante, ni pouvoir être déclenchée par erreur en parcourant la page.

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { deleteAccount } from '../api/auth.js'
import { useAuth } from '../auth/useAuth.js'
import { useResendVerification } from '../auth/useResendVerification.js'
import Navbar from '../components/Navbar.jsx'
import DeleteAccountModal from '../components/DeleteAccountModal.jsx'

export default function AccountPage() {
  const { user, logout } = useAuth()
  const { resend, loading: resending, feedback } = useResendVerification()
  const navigate = useNavigate()
  const [confirming, setConfirming] = useState(false)

  // Suppression confirmée : l'appel réussi rend le token caduc côté serveur (le
  // compte n'existe plus). On purge la session LOCALEMENT avant de rediriger,
  // sans quoi ProtectedRoute laisserait passer un utilisateur dont chaque appel
  // suivant échouerait en 401. `replace` : la page de compte d'un compte
  // supprimé n'a rien à faire dans l'historique de navigation.
  //
  // Aucun try/catch ici : les erreurs sont volontairement laissées remonter à la
  // modale, qui les affiche en restant ouverte. Les rattraper ici fermerait la
  // modale sur un échec, en laissant croire que la suppression a eu lieu.
  async function handleConfirmDelete(password) {
    await deleteAccount(password)
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <>
      <Navbar />

      <main className="account-page">
        <h1 className="account-page__title">Mon compte</h1>

        <section className="account-card">
          <h2 className="account-card__title">Informations</h2>

          <dl className="account-info">
            <dt className="account-info__label">Adresse email</dt>
            <dd className="account-info__value">
              {user?.email ?? <span className="text-muted">Chargement…</span>}
            </dd>

            <dt className="account-info__label">Statut de l’adresse</dt>
            <dd className="account-info__value">
              {/* Le statut n'est jamais porté par la seule couleur : un
                  pictogramme (✓ / ⚠) et un libellé explicite le disent aussi. */}
              {user ? (
                <span
                  className={`status-tag status-tag--${
                    user.is_verified ? 'success' : 'warning'
                  }`}
                >
                  <span aria-hidden="true">{user.is_verified ? '✓' : '⚠'}</span>
                  {user.is_verified ? 'Vérifiée' : 'Non vérifiée'}
                </span>
              ) : (
                <span className="text-muted">Chargement…</span>
              )}
            </dd>
          </dl>

          {/* Action de vérification proposée ici aussi : l'utilisateur qui vient
              gérer son compte doit pouvoir régler ce point sans retourner au
              kanban chercher le bandeau. */}
          {user && !user.is_verified && (
            <div className="account-card__action">
              <button
                type="button"
                className="btn btn--secondary btn--sm"
                onClick={resend}
                disabled={resending}
              >
                {resending ? 'Envoi…' : 'Renvoyer l’email de vérification'}
              </button>
              {feedback && (
                <span
                  className={`inline-feedback inline-feedback--${feedback.variant}`}
                  role="status"
                >
                  <span aria-hidden="true">
                    {feedback.variant === 'success' ? '✓' : '⚠'}
                  </span>{' '}
                  {feedback.message}
                </span>
              )}
            </div>
          )}
        </section>

        {/* Zone dangereuse : signalée par un intitulé explicite (« Zone de
            danger »), un pictogramme, une bordure marquée ET la couleur. La
            couleur n'est donc qu'un signal parmi quatre (WCAG 1.4.1). */}
        <section className="account-card account-card--danger">
          <h2 className="account-card__title account-card__title--danger">
            <span aria-hidden="true">⚠</span> Zone de danger
          </h2>

          <div className="danger-row">
            <div>
              <p className="danger-row__title">Supprimer mon compte</p>
              <p className="danger-row__text">
                Supprime définitivement votre compte, vos tableaux et toutes vos
                candidatures. Cette action est irréversible.
              </p>
            </div>

            <button
              type="button"
              className="btn btn--danger"
              onClick={() => setConfirming(true)}
            >
              Supprimer mon compte
            </button>
          </div>
        </section>
      </main>

      {confirming && (
        <DeleteAccountModal
          onConfirm={handleConfirmDelete}
          onClose={() => setConfirming(false)}
        />
      )}
    </>
  )
}
