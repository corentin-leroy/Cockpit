// Modale réutilisable : superpose une popup centrée au-dessus du contenu.
//
// Accessibilité :
// - role="dialog" + aria-modal, titré par aria-labelledby ;
// - fermeture par la touche Échap, par un clic sur le fond, ou par la croix ;
// - à l'ouverture, le focus est déplacé dans la modale (premier champ focusable) ;
//   à la fermeture, il est rendu à l'élément qui l'avait avant l'ouverture.

import { useEffect, useRef } from 'react'

const overlayStyle = {
  position: 'fixed',
  inset: 0,
  background: 'rgba(0, 0, 0, 0.5)',
  display: 'flex',
  alignItems: 'flex-start',
  justifyContent: 'center',
  padding: 24,
  overflowY: 'auto', // si la modale est plus haute que l'écran
  zIndex: 1000,
}

const dialogStyle = {
  width: '100%',
  maxWidth: 480,
  marginTop: 48,
  background: 'var(--bg)',
  border: '1px solid var(--border)',
  borderRadius: 12,
  boxShadow: 'var(--shadow)',
  padding: 24,
  textAlign: 'left',
}

const headerStyle = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  marginBottom: 16,
}

const titleStyle = { margin: 0, fontSize: 18, color: 'var(--text-h)' }

const closeButtonStyle = {
  border: 'none',
  background: 'transparent',
  color: 'inherit',
  font: 'inherit',
  fontSize: 22,
  lineHeight: 1,
  cursor: 'pointer',
  padding: 4,
}

export default function Modal({ title, onClose, children }) {
  const dialogRef = useRef(null)

  useEffect(() => {
    // Élément focalisé avant l'ouverture : on le restaurera à la fermeture.
    const previouslyFocused = document.activeElement

    // Déplace le focus dans la modale. On vise en priorité le premier champ de
    // SAISIE (input/textarea/select) : dans le DOM, la croix de fermeture précède
    // le contenu, donc un sélecteur générique la choisirait — or démarrer sur la
    // croix fait qu'un appui sur Entrée ferme la modale au lieu de saisir. La
    // croix reste atteignable ensuite au clavier (Tab/Shift+Tab). Fallback sur un
    // autre focusable (ex. modale sans champ), puis sur le dialog lui-même.
    const dialog = dialogRef.current
    const firstInput = dialog?.querySelector('input, textarea, select')
    const focusable =
      firstInput ||
      dialog?.querySelector('button, [href], [tabindex]:not([tabindex="-1"])')
    ;(focusable || dialog)?.focus()

    function handleKeyDown(event) {
      if (event.key === 'Escape') {
        event.stopPropagation()
        onClose()
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      if (previouslyFocused instanceof HTMLElement) previouslyFocused.focus()
    }
  }, [onClose])

  return (
    <div
      style={overlayStyle}
      // onMouseDown plutôt que onClick : évite une fermeture accidentelle si un
      // glissé de sélection démarré dans la modale se termine sur le fond.
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        tabIndex={-1}
        style={dialogStyle}
      >
        <header style={headerStyle}>
          <h2 id="modal-title" style={titleStyle}>
            {title}
          </h2>
          <button
            type="button"
            aria-label="Fermer"
            style={closeButtonStyle}
            onClick={onClose}
          >
            ×
          </button>
        </header>

        {children}
      </div>
    </div>
  )
}
