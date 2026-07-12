// Objet React Context isolé dans son propre module (même convention que auth/) :
// un fichier de composant ne doit exporter que des composants (règle Fast Refresh).

import { createContext } from 'react'

export const ThemeContext = createContext(null)
