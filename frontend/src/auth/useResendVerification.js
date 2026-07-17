// Hook partagé par les deux endroits qui proposent de renvoyer l'email de
// confirmation : le bandeau des pages protégées et l'écran /verify-email quand
// le lien a expiré. Un seul endroit traduit les réponses du backend (409, 429),
// pour que le message soit identique quel que soit le point d'entrée.

import { useCallback, useState } from 'react'

import { resendVerification } from '../api/auth.js'
import { useAuth } from './useAuth.js'

/**
 * @returns {{ resend: () => Promise<void>, loading: boolean,
 *             feedback: { variant: 'success'|'error', message: string } | null }}
 */
export function useResendVerification() {
  const { refreshUser } = useAuth()
  const [loading, setLoading] = useState(false)
  const [feedback, setFeedback] = useState(null)

  const resend = useCallback(async () => {
    setLoading(true)
    setFeedback(null)
    try {
      const { message } = await resendVerification()
      setFeedback({ variant: 'success', message })
    } catch (err) {
      if (err.status === 409) {
        // L'adresse a été confirmée entre-temps (autre onglet, autre appareil).
        // On recharge l'utilisateur : le bandeau disparaîtra de lui-même.
        refreshUser()
        setFeedback({
          variant: 'success',
          message: 'Votre adresse est déjà confirmée.',
        })
      } else if (err.status === 429) {
        // Plafond horaire d'envois atteint. Le backend fournit déjà un message
        // actionnable (« réessayez dans une heure ou vérifiez vos spams »).
        setFeedback({ variant: 'error', message: err.message })
      } else {
        setFeedback({
          variant: 'error',
          message: err.message || 'L’envoi a échoué. Réessayez.',
        })
      }
    } finally {
      setLoading(false)
    }
  }, [refreshUser])

  return { resend, loading, feedback }
}
