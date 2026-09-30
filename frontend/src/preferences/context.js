import { createContext } from 'react'

// Contexte de l'état de repli de la sidebar. Vit dans son propre fichier (comme
// theme/context.js) pour que le fichier du provider n'exporte que des composants.
export const SidebarContext = createContext(null)
