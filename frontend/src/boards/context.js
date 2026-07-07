// Objet React Context isolé dans son propre module (même motif que auth/context.js),
// pour respecter la règle Fast Refresh : provider et hook l'importent d'ici.

import { createContext } from 'react'

export const BoardsContext = createContext(null)
