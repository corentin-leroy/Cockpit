// Hook d'accès au contexte des tableaux.

import { useContext } from 'react'

import { BoardsContext } from './context.js'

/**
 * Renvoie { boards, currentBoard, currentBoardId, selectBoard, loading, error }.
 * Garde-fou si utilisé hors d'un <BoardsProvider>.
 */
export function useBoards() {
  const context = useContext(BoardsContext)
  if (context === null) {
    throw new Error('useBoards doit être utilisé à l’intérieur d’un <BoardsProvider>')
  }
  return context
}
