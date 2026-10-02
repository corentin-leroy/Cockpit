// Blocage temporaire après un 429 (limite de débit), partagé par les trois écrans
// concernés : connexion, inscription, mot de passe oublié. La logique du délai
// vit ICI et dans utils/retryAfter.js ; aucune page ne la recopie.
//
// Comportement décidé :
//  - après un 429 AVEC un Retry-After lisible, le message du serveur reste affiché
//    pendant toute la durée du blocage (quoi que l'utilisateur modifie dans les
//    champs), le bouton est désactivé et indique le temps restant à la minute
//    supérieure (« Réessayer dans 14 min »), mis à jour chaque minute ;
//  - à l'échéance, le blocage prend fin tout seul : le bouton redevient actif ;
//  - Retry-After absent ou illisible : `handle` renvoie false et la page traite le
//    429 comme n'importe quelle erreur (message affiché, bouton utilisable). On ne
//    bloque jamais l'utilisateur sur une durée inventée ;
//  - AUCUNE mémorisation : un rechargement oublie le blocage (le serveur le
//    maintient, et la tentative suivante renverra un 429 au délai à jour). Rien
//    n'est écrit dans localStorage.
//
// L'heure courante vit dans un état mis à jour par un minuteur (jamais lue pendant
// le rendu) : un seul setTimeout, calé sur le prochain changement de minute.

import { useCallback, useEffect, useState } from 'react'

import { cooldownLabel, minutesLeft, msUntilNextChange } from '../utils/retryAfter.js'

/**
 * @param {Object} [options]
 * @param {number|null} [options.initialDeadline]  échéance (ms epoch) d'un blocage
 *   déjà connu à l'arrivée sur la page (inscription réussie, connexion bloquée).
 * @returns {{
 *   active: boolean,
 *   message: string,
 *   buttonLabel: string|null,
 *   handle: (err: Error & { status?: number, retryAfter?: number|null }) => boolean,
 *   startUntil: (deadlineMs: number, message?: string) => void,
 * }}
 */
export function useRateLimitCooldown({ initialDeadline = null } = {}) {
  const [cooldown, setCooldown] = useState(() =>
    initialDeadline ? { message: '', deadline: initialDeadline } : null,
  )
  const [now, setNow] = useState(() => Date.now())

  const minutes = cooldown ? minutesLeft(cooldown.deadline, now) : 0
  const active = minutes > 0

  useEffect(() => {
    if (!active) return undefined
    const timer = setTimeout(
      () => setNow(Date.now()),
      msUntilNextChange(cooldown.deadline, now),
    )
    return () => clearTimeout(timer)
  }, [active, cooldown, now])

  // Un onglet masqué voit ses minuteurs ralentis par le navigateur : au retour,
  // on recalcule tout de suite plutôt que d'attendre un minuteur en retard.
  useEffect(() => {
    if (!active) return undefined
    function refresh() {
      if (document.visibilityState === 'visible') setNow(Date.now())
    }
    document.addEventListener('visibilitychange', refresh)
    return () => document.removeEventListener('visibilitychange', refresh)
  }, [active])

  const startUntil = useCallback((deadlineMs, message = '') => {
    setNow(Date.now())
    setCooldown({ message, deadline: deadlineMs })
  }, [])

  const handle = useCallback(
    (err) => {
      if (err?.status !== 429 || !err.retryAfter) return false
      startUntil(Date.now() + err.retryAfter * 1000, err.message)
      return true
    },
    [startUntil],
  )

  return {
    active,
    message: active ? cooldown.message : '',
    buttonLabel: active ? cooldownLabel(minutes) : null,
    handle,
    startUntil,
  }
}
