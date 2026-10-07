// Messages d'état, partagés par les formulaires et les écrans.
//
// Accessibilité : un état ne repose JAMAIS sur la seule couleur. Chaque message
// combine trois signaux redondants — un pictogramme (décoratif, aria-hidden), le
// texte du message, et la couleur — et porte role="alert" pour être annoncé par
// un lecteur d'écran. Le couple erreur/succès n'est pas un simple rouge/vert :
// les pictogrammes (triangle d'avertissement, coche) suffisent à les distinguer
// sans percevoir la teinte. Icônes Phosphor (DESIGN.md), 16px.

// La variante `info` porte une information NEUTRE : ni faute de l'utilisateur,
// ni réussite d'une action. Son pictogramme (i) et ses couleurs sobres la
// distinguent de `error` (triangle, rouge tiède), qui dramatiserait un événement
// aussi ordinaire qu'une session arrivée à son terme.
import { Check, Info, Warning } from '@phosphor-icons/react'

const ICONS = { error: Warning, success: Check, info: Info }

/**
 * @param {Object}  props
 * @param {'error'|'success'|'info'} [props.variant='error']  nature du message.
 * @param {string}  [props.className]  classes additionnelles (marges).
 * @param {React.ReactNode} props.children  le texte du message.
 */
export default function Alert({ variant = 'error', className = '', children }) {
  const Icon = ICONS[variant]
  return (
    <div role="alert" className={`alert alert--${variant} ${className}`.trim()}>
      <span className="alert__icon" aria-hidden="true">
        <Icon size={16} />
      </span>
      <span>{children}</span>
    </div>
  )
}

/** Erreur de validation affichée sous un champ de formulaire. */
export function FieldError({ children }) {
  return (
    <span className="field__error">
      <Warning size={16} aria-hidden="true" />
      {children}
    </span>
  )
}
