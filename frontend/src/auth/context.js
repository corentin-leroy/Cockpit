// Objet React Context isolé dans son propre module.
//
// Séparé du provider et du hook pour respecter la règle Fast Refresh de React
// (un fichier de composant ne doit exporter que des composants). Provider
// (AuthContext.jsx) et hook (useAuth.js) importent tous deux ce contexte d'ici.

import { createContext } from 'react'

export const AuthContext = createContext(null)
