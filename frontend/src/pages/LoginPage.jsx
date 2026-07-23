// Écran de connexion. Appelle login() du contexte d'auth, qui stocke le token
// et met à jour l'état. Au succès, redirige vers le kanban.

import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/useAuth.js'
import Alert from '../components/Alert.jsx'

// Valeur que React donne à `key` sur son événement synthétique quand
// l'événement clavier natif n'en porte aucun. Mesuré sur le remplissage
// automatique : le natif a `key === undefined`, React expose "Unidentified".
// Ce n'est donc PAS une touche, malgré les apparences.
const UNIDENTIFIED_KEY = 'Unidentified'

export default function LoginPage() {
  const navigate = useNavigate()
  const { login, sessionExpired, clearSessionExpired } = useAuth()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [formError, setFormError] = useState('')
  const [loading, setLoading] = useState(false)

  // Le signal du contexte est RECOPIÉ dans un état local au premier rendu, puis
  // acquitté aussitôt (effet ci-dessous). Ce détour donne les trois
  // comportements attendus sans code de nettoyage supplémentaire :
  //  - quitter la page efface le message, puisque cet état meurt avec le
  //    composant ;
  //  - y revenir plus tard ne le ressort pas, le drapeau du contexte ayant été
  //    consommé ;
  //  - un rechargement repart vierge, l'état n'étant nulle part persisté.
  // Nettoyer plutôt dans un cleanup d'effet serait piégeux : en StrictMode,
  // React monte, démonte puis remonte les effets en développement, et le message
  // disparaîtrait avant même d'être lu.
  const [showExpired, setShowExpired] = useState(sessionExpired)

  useEffect(() => {
    if (sessionExpired) clearSessionExpired()
  }, [sessionExpired, clearSessionExpired])

  // Masquage du message : uniquement sur une SAISIE RÉELLE.
  //
  // C'est le cœur du correctif. L'ancienne version se branchait sur `onChange`,
  // qui se déclenche pour tout changement de valeur — y compris ceux que
  // l'utilisateur n'a pas provoqués. Or le gestionnaire de mots de passe du
  // navigateur garnit les deux champs environ 180 ms après l'affichage du
  // formulaire : le message était effacé avant d'avoir pu être lu, sans que
  // personne n'ait touché au clavier.
  //
  // Se rabattre sur `onKeyDown` ne suffit pas non plus : le remplissage
  // SYNTHÉTISE des `keydown`, et ils portent `isTrusted = true` — tester
  // `isTrusted` ne distinguerait donc rien.
  //
  // Deux différences observables subsistent, toutes deux MESURÉES dans le
  // navigateur, et c'est sur elles qu'on s'appuie :
  //  - le remplissage n'émet AUCUN `beforeinput`, alors qu'une modification
  //    faite par l'utilisateur en émet toujours un — frappe, collage (y compris
  //    au clic droit), saisie via IME ;
  //  - ses `keydown` synthétisés n'ont ni `key`, ni `code`, ni `keyCode`. Piège
  //    à connaître : React NORMALISE son événement synthétique et expose alors
  //    `key === "Unidentified"`, si bien qu'un simple `Boolean(event.key)`
  //    conclut à tort à une frappe (c'est ce qui a fait échouer une première
  //    version de ce correctif).
  //
  // On accepte donc l'un OU l'autre signal. `beforeinput` est le plus juste
  // sémantiquement (« le contenu va être modifié par l'utilisateur ») et couvre
  // le collage à la souris ; le repli sur `key` protège d'un navigateur qui
  // n'émettrait pas `beforeinput`. En cas de doute, le message RESTE affiché :
  // c'est le mode de défaillance sûr — un message qui s'attarde est bénin, un
  // message jamais lu ne sert à rien.
  function dismissExpiredNotice(event) {
    const isRealUserInput =
      event.type === 'beforeinput' ||
      (Boolean(event.key) && event.key !== UNIDENTIFIED_KEY)
    if (isRealUserInput) setShowExpired(false)
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setFormError('')
    // Soumettre vaut acquittement, quel que soit le chemin emprunté pour
    // remplir le formulaire (clavier, collage souris, remplissage automatique).
    setShowExpired(false)

    if (!email.trim() || !password) {
      setFormError('Renseignez votre email et votre mot de passe.')
      return
    }

    setLoading(true)
    try {
      await login(email, password)
      navigate('/', { replace: true })
    } catch (err) {
      // 401 : le backend renvoie volontairement le même message que l'email
      // existe ou non. On reste tout aussi générique côté UI.
      if (err.status === 401) {
        setFormError('Email ou mot de passe incorrect.')
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
        <h1 className="auth-card__title">Connexion</h1>

        {/* Explication de la présence sur cet écran, affichée seulement quand la
            session a réellement été invalidée par le serveur. Ton neutre : une
            session qui arrive à son terme est un fonctionnement normal, pas un
            incident — et surtout pas une faute de l'utilisateur. Masquée dès
            qu'une erreur de connexion survient, pour ne pas empiler deux
            messages dont un devenu caduc. */}
        {showExpired && !formError && (
          <Alert variant="info" className="stack-gap">
            Votre session a expiré, veuillez vous reconnecter.
          </Alert>
        )}

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
              onBeforeInput={dismissExpiredNotice}
              onKeyDown={dismissExpiredNotice}
            />
          </div>

          <div className="field">
            <div className="field__label-row">
              <label className="field__label" htmlFor="password">Mot de passe</label>
              <Link className="field__link" to="/forgot-password">
                Mot de passe oublié ?
              </Link>
            </div>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              className="input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onBeforeInput={dismissExpiredNotice}
              onKeyDown={dismissExpiredNotice}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn btn--primary btn--block"
          >
            {loading ? 'Connexion…' : 'Se connecter'}
          </button>
        </form>

        <p className="auth-card__footer">
          Pas encore de compte ? <Link to="/register">Créer un compte</Link>
        </p>
      </div>
    </div>
  )
}
