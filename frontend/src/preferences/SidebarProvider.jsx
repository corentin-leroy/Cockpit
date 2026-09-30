// État de repli de la sidebar des tableaux, PARTAGÉ par le kanban (Sidebar) et la
// page d'archives (ArchiveSidebar), ainsi que par le bouton de la navbar.
//
// Monté dans main.jsx, AU-DESSUS du routeur : l'état n'appartient à aucune page,
// donc changer de page ne le réinitialise jamais. Initialisé de façon synchrone
// depuis le stockage (pas d'effet) : la sidebar est repliée dès le premier rendu,
// sans flash d'une sidebar dépliée au rechargement.

import { useCallback, useMemo, useState } from 'react'

import { SidebarContext } from './context.js'
import { getSidebarCollapsed, setSidebarCollapsed } from './storage.js'

export function SidebarProvider({ children }) {
  const [collapsed, setCollapsed] = useState(getSidebarCollapsed)

  const toggleSidebar = useCallback(() => {
    const next = !collapsed
    setCollapsed(next)
    setSidebarCollapsed(next)
  }, [collapsed])

  const value = useMemo(() => ({ collapsed, toggleSidebar }), [collapsed, toggleSidebar])

  return <SidebarContext.Provider value={value}>{children}</SidebarContext.Provider>
}
