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

  // Repli depuis le bouton de l'EN-TÊTE de la sidebar. Ce bouton devient inerte
  // avec elle : le focus clavier serait perdu (renvoyé au <body>). On le rend au
  // bouton de la navbar (#sidebar-toggle, Navbar.jsx), qui sert à rouvrir.
  const collapseSidebar = useCallback(() => {
    setCollapsed(true)
    setSidebarCollapsed(true)
    document.getElementById('sidebar-toggle')?.focus()
  }, [])

  const value = useMemo(
    () => ({ collapsed, toggleSidebar, collapseSidebar }),
    [collapsed, toggleSidebar, collapseSidebar],
  )

  return <SidebarContext.Provider value={value}>{children}</SidebarContext.Provider>
}
