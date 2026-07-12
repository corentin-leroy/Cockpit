// Bouton de bascule clair / sombre (navbar).
//
// Accessibilité : l'icône est décorative (aria-hidden) ; c'est l'aria-label du
// bouton qui annonce l'action, et aria-pressed qui expose l'état du mode sombre.
// Aucune information ne repose donc sur la seule couleur ou le seul pictogramme.

import { useTheme } from '../theme/useTheme.js'
import { DARK } from '../theme/storage.js'

export default function ThemeToggle() {
  const { theme, toggleTheme } = useTheme()
  const isDark = theme === DARK

  const label = isDark ? 'Passer en thème clair' : 'Passer en thème sombre'

  return (
    <button
      type="button"
      className="btn btn--ghost btn--icon theme-toggle"
      onClick={toggleTheme}
      aria-label={label}
      aria-pressed={isDark}
      title={label}
    >
      <span aria-hidden="true">{isDark ? '☀' : '☾'}</span>
    </button>
  )
}
