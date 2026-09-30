// Hook d'accès à l'état de repli de la sidebar.

import { useContext } from 'react'

import { SidebarContext } from './context.js'

/** Renvoie { collapsed, toggleSidebar }. Garde-fou si utilisé hors SidebarProvider. */
export function useSidebar() {
  const context = useContext(SidebarContext)
  if (context === null) {
    throw new Error('useSidebar doit être utilisé à l’intérieur d’un <SidebarProvider>')
  }
  return context
}
