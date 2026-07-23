// Provider du contexte d'authentification : détient l'état de session et
// l'expose à toute l'app via AuthContext.
//
// Ce fichier ne connaît ni le stockage (il passe par le module token) ni le
// transport HTTP (il passe par api/auth). Il ne gère que l'ÉTAT React.

import { useCallback, useEffect, useState } from 'react'

import { getMe, login as apiLogin } from '../api/auth.js'
import { onSessionExpired } from './authEvents.js'
import { AuthContext } from './context.js'
import { getToken, removeToken, setToken, TOKEN_KEY } from './token.js'

export function AuthProvider({ children }) {
  // Initialisation synchrone depuis le token présent au démarrage : si un token
  // est déjà stocké (rechargement de page, onglet rouvert), on démarre connecté.
  // Initializer paresseux (fonction) pour ne lire le stockage qu'une seule fois.
  const [isAuthenticated, setIsAuthenticated] = useState(() => Boolean(getToken()))

  // Utilisateur courant (id, email, is_verified…), ou null tant qu'on ne l'a pas
  // (pas connecté, chargement en cours, ou récupération en échec).
  //
  // Pourquoi un appel réseau plutôt que de lire le JWT ? Le token ne porte que
  // l'id (claim `sub`) et il vit 60 min : un `is_verified` qui y serait figé
  // resterait faux pendant une heure après la confirmation de l'adresse. GET
  // /auth/me donne l'état RÉEL du compte, et le backend reste la seule source
  // de vérité (un token, même déchiffrable côté client, ne se fait pas confiance).
  const [user, setUser] = useState(null)

  // Une session a-t-elle été invalidée par le serveur (par opposition à une
  // déconnexion volontaire) ? Sert uniquement à expliquer à l'utilisateur
  // pourquoi il se retrouve sur /login.
  //
  // L'état vit ICI et non dans LoginPage parce que l'événement arrive AVANT que
  // cette page n'existe : l'expiration est détectée pendant l'utilisation de
  // l'app, la redirection monte LoginPage ensuite. Il faut donc un état qui
  // survive à ce changement de page, et le contexte d'auth est déjà exactement
  // cela — il est déjà abonné au bus, et LoginPage le consomme déjà pour login().
  // Aucun module ni contexte supplémentaire n'est nécessaire.
  //
  // EN MÉMOIRE, jamais en stockage : un rechargement de page doit repartir
  // vierge. Persister ce drapeau ferait réapparaître « votre session a expiré »
  // au chargement suivant, longtemps après l'événement.
  const [sessionExpired, setSessionExpired] = useState(false)

  // Chaîne de promesses (et non async/await) pour que les setState arrivent dans
  // des callbacks, jamais dans le corps synchrone de l'effet appelant.
  const loadUser = useCallback(() => {
    getMe()
      .then(setUser)
      .catch(() => {
        // Échec NON BLOQUANT, volontairement : un 401 aurait déjà été traité par
        // apiFetch (qui purge le token et émet sessionExpired), donc on est ici
        // face à un incident réseau/serveur. On laisse `user` à null : l'app
        // fonctionne, seul le bandeau de vérification ne s'affiche pas. Casser la
        // session pour un /auth/me raté serait pire que le symptôme.
        setUser(null)
      })
  }, [])

  // Chargement de l'utilisateur courant dès qu'une session existe : au montage si
  // un token est déjà en stockage (rechargement de page), et après une connexion
  // (login fait passer isAuthenticated à true). La remise à null, elle, se fait
  // dans les callbacks qui ferment la session (voir plus bas) plutôt qu'ici : un
  // setState synchrone dans un effet provoquerait un rendu en cascade.
  useEffect(() => {
    if (isAuthenticated) loadUser()
  }, [isAuthenticated, loadUser])

  // Synchronisation MÊME ONGLET : apiFetch émet cet événement quand il purge le
  // token sur un 401. On bascule alors l'état, ce qui fait réagir les routes
  // protégées (redirection vers /login).
  useEffect(
    () =>
      onSessionExpired(() => {
        setIsAuthenticated(false)
        setUser(null)
        // apiFetch n'émet cet événement que pour un 401 SUR UNE REQUÊTE PORTANT
        // UN JETON : arriver ici signifie donc bien qu'une session existait et
        // qu'elle a été refusée, jamais qu'une connexion a échoué.
        setSessionExpired(true)
      }),
    [],
  )

  // Synchronisation ENTRE ONGLETS : l'événement `storage` se déclenche dans les
  // AUTRES onglets quand le token change ici (login/logout). On aligne l'état ;
  // une déconnexion ailleurs doit aussi purger l'utilisateur de cet onglet.
  useEffect(() => {
    function handleStorage(event) {
      if (event.key === TOKEN_KEY) {
        setIsAuthenticated(Boolean(event.newValue))
        if (!event.newValue) setUser(null)
      }
    }
    window.addEventListener('storage', handleStorage)
    return () => window.removeEventListener('storage', handleStorage)
  }, [])

  async function login(email, password) {
    const data = await apiLogin(email, password)
    setToken(data.access_token)
    setIsAuthenticated(true) // déclenche l'effet ci-dessus → chargement de `user`
    setSessionExpired(false) // la session précédente n'a plus à être expliquée
    return data
  }

  // Déconnexion VOLONTAIRE : elle ne passe pas par apiFetch et n'émet donc aucun
  // événement d'expiration. C'est ce qui fait qu'un utilisateur qui clique
  // « Déconnexion » ne voit pas « votre session a expiré » — il sait pourquoi il
  // est sur /login. La remise à false couvre le cas d'une déconnexion manuelle
  // faisant suite à une expiration non encore affichée.
  function logout() {
    removeToken()
    setIsAuthenticated(false)
    setUser(null)
    setSessionExpired(false)
  }

  // Recharge l'utilisateur courant depuis l'API. Appelée après une action qui
  // change son état côté serveur (confirmation d'adresse) pour que l'UI suive
  // sans rechargement de page.
  const refreshUser = useCallback(() => {
    if (getToken()) loadUser()
  }, [loadUser])

  // Acquitte le signal d'expiration : appelé par LoginPage dès qu'elle l'a
  // recopié pour affichage. Le drapeau est ainsi consommé UNE fois — revenir sur
  // /login plus tard (ou recharger) ne le ressort pas.
  const clearSessionExpired = useCallback(() => setSessionExpired(false), [])

  const value = {
    isAuthenticated,
    user,
    sessionExpired,
    clearSessionExpired,
    login,
    logout,
    refreshUser,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
