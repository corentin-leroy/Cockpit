// Provider du contexte des tableaux : détient la liste des tableaux et le
// « tableau courant » (source de vérité unique, partagée par le kanban, la
// sidebar, et plus tard l'ajout/édition).
//
// Monté UNIQUEMENT dans la zone authentifiée (voir router/routes.jsx) : getBoards
// exige un token, donc on ne charge les tableaux qu'une fois connecté.
//
// Comme le contexte d'auth, ce fichier ne connaît ni le transport HTTP (api/boards)
// ni le stockage (boards/lastBoard) : il ne gère que l'ÉTAT React.

import { useEffect, useState } from 'react'

import {
  getBoards,
  createBoard as apiCreateBoard,
  updateBoard as apiUpdateBoard,
  deleteBoard as apiDeleteBoard,
} from '../api/boards.js'
import { BoardsContext } from './context.js'
import { getLastBoardId, setLastBoardId } from './lastBoard.js'

export function BoardsProvider({ children }) {
  const [boards, setBoards] = useState([])
  const [currentBoardId, setCurrentBoardId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    // `active` : ignore la réponse si le composant est démonté avant (déconnexion,
    // ou double-montage StrictMode en dev).
    let active = true

    getBoards()
      .then((list) => {
        if (!active) return
        setBoards(list)

        // Détermination du tableau courant :
        // - on lit l'id mémorisé (dernier tableau consulté) ;
        // - s'il correspond encore à un tableau de la liste, on le restaure ;
        // - sinon (jamais consulté, ou tableau supprimé depuis) on retombe sur le
        //   premier tableau. Ce repli couvre le cas d'un id périmé en localStorage.
        const stored = getLastBoardId()
        const remembered =
          stored != null && list.find((b) => String(b.id) === String(stored))
        setCurrentBoardId(remembered ? remembered.id : (list[0]?.id ?? null))
      })
      .catch((err) => {
        if (active) setError(err.message || 'Impossible de charger les tableaux.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [])

  /** Change le tableau courant et mémorise son id pour le prochain chargement. */
  function selectBoard(id) {
    setCurrentBoardId(id)
    setLastBoardId(id)
  }

  // Les mutations vivent ICI, sur la source de vérité : après l'appel réseau,
  // elles ajustent la liste locale sans re-fetch, comme le kanban le fait pour ses
  // candidatures. Elles renvoient (ou propagent l'erreur de) la promesse d'apiFetch,
  // pour que le formulaire appelant affiche l'échec et ne ferme pas la modale.

  /** Crée un tableau, l'ajoute à la liste et en fait le tableau courant. */
  async function createBoard(name) {
    const created = await apiCreateBoard(name)
    setBoards((prev) => [...prev, created])
    setCurrentBoardId(created.id)
    setLastBoardId(created.id)
    return created
  }

  /** Renomme un tableau et met à jour la liste (le titre du kanban suit via currentBoard). */
  async function renameBoard(id, name) {
    const updated = await apiUpdateBoard(id, name)
    setBoards((prev) => prev.map((b) => (b.id === id ? updated : b)))
    return updated
  }

  /**
   * Supprime un tableau. Si c'était le tableau courant, bascule sur le premier
   * tableau restant pour ne jamais laisser l'app sur un tableau inexistant.
   */
  async function removeBoard(id) {
    await apiDeleteBoard(id)
    setBoards((prev) => prev.filter((b) => b.id !== id))
    if (id === currentBoardId) {
      // `boards` (closure du rendu courant) reflète l'état avant retrait : on y
      // cherche le premier tableau différent de celui supprimé.
      const fallbackId = boards.find((b) => b.id !== id)?.id ?? null
      setCurrentBoardId(fallbackId)
      if (fallbackId != null) setLastBoardId(fallbackId)
    }
  }

  // Objet complet du tableau courant, dérivé de l'id (pour le titre, etc.).
  const currentBoard = boards.find((b) => b.id === currentBoardId) ?? null

  const value = {
    boards,
    currentBoard,
    currentBoardId,
    selectBoard,
    createBoard,
    renameBoard,
    removeBoard,
    loading,
    error,
  }

  return <BoardsContext.Provider value={value}>{children}</BoardsContext.Provider>
}
