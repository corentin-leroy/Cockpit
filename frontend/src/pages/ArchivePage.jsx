// Écran « Archives » (protégé) : liste dense des candidatures archivées, tous
// tableaux confondus. Pas un kanban — un tableau HTML, une ligne par
// candidature (cf. DESIGN.md, « densité » : cet écran n'a pas vocation à
// représenter un flux de statuts, seulement à retrouver une candidature).
//
// Chargement UNIQUE au montage : les archives sont ensuite filtrées côté
// CLIENT (recherche) — pas de requête réseau par frappe. Pas de correction
// (édition) depuis cet écran dans ce lot : seulement désarchiver et supprimer
// définitivement (lot dédié prévu pour la correction).

import { useEffect, useMemo, useState } from 'react'

import {
  deleteApplication,
  getArchivedApplications,
  unarchiveApplication,
} from '../api/applications.js'
import Alert from '../components/Alert.jsx'
import ArchiveSidebar from '../components/ArchiveSidebar.jsx'
import ConfirmModal from '../components/ConfirmModal.jsx'
import Navbar from '../components/Navbar.jsx'
import { APPLICATION_STATUSES } from '../constants/applicationStatuses.js'
import { parseUtcDate } from '../utils/dates.js'

// Libellé français du statut, pour l'affichage ET pour la recherche (une seule
// source, comme partout ailleurs dans le front).
const STATUS_LABELS = Object.fromEntries(
  APPLICATION_STATUSES.map((status) => [status.key, status.label]),
)

// Mois abrégé (« 29 sept. 2026 ») plutôt que numérique : sur cette page on
// cherche une archive précise, la lisibilité prime sur les quelques pixels
// gagnés par un format numérique (qui demanderait de décoder le mois).
const DATE_FORMATTER = new Intl.DateTimeFormat('fr-FR', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
})

// Normalisation accents/casse : NFD décompose un caractère accentué en lettre
// de base + diacritique combinant (ex. « é » → « e » + U+0301) ; la plage
// ̀-ͯ couvre tous les diacritiques combinants Unicode, qu'on retire
// ensuite. « developpeur » et « Développeur » produisent alors la même chaîne.
function normalize(text) {
  return text
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
}

export default function ArchivePage() {
  const [archives, setArchives] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  // Erreur d'une action ponctuelle (désarchivage refusé par le plafond de 300
  // actives) : bandeau au-dessus de la liste, distincte de l'erreur de
  // chargement — elle ne doit pas masquer les archives déjà affichées.
  const [actionError, setActionError] = useState('')
  const [query, setQuery] = useState('')
  const [unarchivingId, setUnarchivingId] = useState(null)
  // Candidature ciblée par une suppression définitive : pilote l'ouverture de
  // ConfirmModal. null = fermée.
  const [deleteTarget, setDeleteTarget] = useState(null)

  useEffect(() => {
    let active = true
    getArchivedApplications()
      .then((data) => {
        if (!active) return
        // Le backend ne garantit pas d'ordre particulier sur ce filtre : tri
        // explicite par date d'archivage décroissante, exigé par ce lot.
        // parseUtcDate : archived_at est un datetime NAÏF en UTC (cf.
        // utils/dates.js) — un `new Date()` direct l'interpréterait comme une
        // heure locale et pourrait inverser l'ordre de deux archivages proches.
        const sorted = [...data].sort(
          (a, b) => parseUtcDate(b.archived_at) - parseUtcDate(a.archived_at),
        )
        setArchives(sorted)
        setError('')
      })
      .catch((err) => {
        if (!active) return
        setError(err.message || 'Impossible de charger les archives.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  // Recherche : chaque MOT saisi doit trouver une correspondance quelque part
  // dans l'intitulé, l'entreprise, le lieu OU le libellé de statut (ET entre
  // les mots, OU entre les champs — un mot suffit à matcher n'importe lequel
  // des quatre). Notes et URL sont délibérément exclues (demande explicite).
  const filtered = useMemo(() => {
    const words = normalize(query).split(/\s+/).filter(Boolean)
    if (words.length === 0) return archives

    return archives.filter((application) => {
      const haystack = normalize(
        [
          application.title,
          application.company,
          application.location ?? '',
          STATUS_LABELS[application.status] ?? '',
        ].join(' '),
      )
      return words.every((word) => haystack.includes(word))
    })
  }, [archives, query])

  async function handleUnarchive(application) {
    setActionError('')
    setUnarchivingId(application.id)
    try {
      await unarchiveApplication(application.id)
      setArchives((prev) => prev.filter((item) => item.id !== application.id))
    } catch (err) {
      // 409 si le plafond de 300 actives est atteint : message du backend
      // affiché tel quel, la ligne reste dans la liste (rien n'a changé).
      setActionError(err.message || 'Le désarchivage a échoué.')
    } finally {
      setUnarchivingId(null)
    }
  }

  // Pas de try/catch ici : une erreur doit remonter à ConfirmModal, qui
  // l'affiche et reste ouverte (même principe que DeleteAccountModal).
  async function handleConfirmDelete() {
    await deleteApplication(deleteTarget.id)
    setArchives((prev) => prev.filter((item) => item.id !== deleteTarget.id))
    setDeleteTarget(null)
  }

  return (
    <>
      <Navbar />

      <div className="board-layout">
        <ArchiveSidebar />

        <main className="archive-page">
          <h1 className="archive-page__title">Archives</h1>

          {actionError && <Alert className="stack-gap">{actionError}</Alert>}

          {/* Ligne flex : la recherche prend l'espace disponible (flex:1).
              Emplacement réservé pour le futur filtre par tableau (lot
              suivant) : un <select> ajouté ici comme frère de
              .archive-page__search s'alignera à droite sans restructuration. */}
          <div className="archive-page__filters">
            <div className="field archive-page__search">
              <label className="field__label" htmlFor="archive-search">
                Rechercher
              </label>
              <input
                id="archive-search"
                type="search"
                className="input"
                placeholder="Intitulé, entreprise, lieu, statut…"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </div>
          </div>

          {loading && <p className="text-muted">Chargement des archives…</p>}

          {!loading && error && <Alert>{error}</Alert>}

          {!loading && !error && archives.length === 0 && (
            <p className="text-muted">Aucune candidature archivée.</p>
          )}

          {!loading && !error && archives.length > 0 && filtered.length === 0 && (
            <p className="text-muted">Aucun résultat pour « {query.trim()} ».</p>
          )}

          {!loading && !error && filtered.length > 0 && (
            <div className="archive-table-wrapper">
              <table className="archive-table">
                {/* table-layout:fixed (CSS) s'appuie sur ces largeurs : Intitulé
                    n'en a PAS, il absorbe tout l'espace restant — c'est la
                    colonne qui doit en recevoir le plus (demande explicite). */}
                <colgroup>
                  <col />
                  <col style={{ width: 180 }} />
                  <col style={{ width: 130 }} />
                  <col style={{ width: 110 }} />
                  <col style={{ width: 110 }} />
                  <col style={{ width: 230 }} />
                </colgroup>
                <thead>
                  <tr>
                    <th scope="col">Intitulé</th>
                    <th scope="col">Entreprise</th>
                    <th scope="col">Lieu</th>
                    <th scope="col">Statut</th>
                    <th scope="col">Archivée le</th>
                    <th scope="col">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((application) => (
                    <tr key={application.id}>
                      <td>
                        <span className="archive-table__title">
                          {application.title}
                        </span>
                      </td>
                      <td className="archive-table__ellipsis">
                        {application.company}
                      </td>
                      <td className="archive-table__ellipsis">
                        {application.location || '—'}
                      </td>
                      <td>
                        {STATUS_LABELS[application.status] ?? application.status}
                      </td>
                      <td>
                        {DATE_FORMATTER.format(
                          parseUtcDate(application.archived_at),
                        )}
                      </td>
                      <td>
                        {/* Le flex vit sur ce DIV interne, jamais directement
                            sur le <td> : posé sur le <td>, il le sort du
                            calcul de hauteur de ligne du tableau (mesuré :
                            cette cellule finissait plus courte que les
                            autres, d'où la bordure « décrochée »). */}
                        <div className="archive-table__actions">
                          <button
                            type="button"
                            className="btn btn--secondary btn--sm"
                            onClick={() => handleUnarchive(application)}
                            disabled={unarchivingId === application.id}
                          >
                            {unarchivingId === application.id
                              ? 'Désarchivage…'
                              : 'Désarchiver'}
                          </button>
                          <button
                            type="button"
                            className="btn btn--danger btn--sm"
                            onClick={() => setDeleteTarget(application)}
                          >
                            Supprimer
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </main>
      </div>

      {deleteTarget && (
        <ConfirmModal
          title="Supprimer définitivement"
          warningLead="Cette action est définitive et ne peut pas être annulée."
          warningDetail={`La candidature « ${deleteTarget.title} » chez ${deleteTarget.company} sera supprimée immédiatement.`}
          confirmLabel="Supprimer définitivement"
          confirmingLabel="Suppression…"
          onConfirm={handleConfirmDelete}
          onClose={() => setDeleteTarget(null)}
        />
      )}
    </>
  )
}
