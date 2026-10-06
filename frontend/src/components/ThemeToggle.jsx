// Bouton de bascule clair / sombre (navbar de l'app et barre de la landing).
//
// L'icône montre le thème vers lequel on BASCULE (la lune en clair, le soleil en
// sombre), comme le libellé (« Passer en thème sombre »).
//
// Accessibilité : l'icône est décorative (aria-hidden) ; c'est l'aria-label du
// bouton qui annonce l'action. PAS d'aria-pressed : combiné à un libellé qui
// change, il produisait une annonce contradictoire (« Passer en thème clair,
// bouton, enfoncé »). Le libellé seul dit l'action et, par elle, l'état.
//
// Icônes SVG Phosphor, et non des caractères Unicode : dessinées par des polices
// de secours différentes, ☀ et ☾ n'avaient ni la même largeur (le bouton passait
// de 29 à 35px selon le thème) ni la même graisse. Le gabarit fixe du bouton
// (.theme-toggle, components.css) ne dépend plus du glyphe.

import { Moon, Sun } from '@phosphor-icons/react'

import { useTheme } from '../theme/useTheme.js'
import { DARK } from '../theme/storage.js'

export default function ThemeToggle() {
  const { theme, toggleTheme } = useTheme()
  const isDark = theme === DARK

  const label = isDark ? 'Passer en thème clair' : 'Passer en thème sombre'
  const Icon = isDark ? Sun : Moon

  return (
    <button
      type="button"
      className="btn btn--ghost btn--icon theme-toggle"
      onClick={toggleTheme}
      aria-label={label}
      title={label}
    >
      <Icon size={16} aria-hidden="true" />
    </button>
  )
}
