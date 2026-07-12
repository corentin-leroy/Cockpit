// Modale réutilisable : superpose une popup centrée au-dessus du contenu.
//
// Accessibilité :
// - role="dialog" + aria-modal, titré par aria-labelledby ;
// - fermeture par la touche Échap, par un clic sur le fond, ou par la croix ;
// - à l'ouverture, le focus est déplacé dans la modale (premier champ focusable) ;
//   à la fermeture, il est rendu à l'élément qui l'avait avant l'ouverture.

import { useEffect, useRef } from 'react'

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
      className="modal-overlay"
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
        className="modal"
      >
        <header className="modal__header">
          <h2 id="modal-title" className="modal__title">
            {title}
          </h2>
          <button
            type="button"
            aria-label="Fermer"
            className="btn btn--ghost btn--icon modal__close"
            onClick={onClose}
          >
            <span aria-hidden="true">×</span>
          </button>
        </header>

        {children}
      </div>
    </div>
  )
}
