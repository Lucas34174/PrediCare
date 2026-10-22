import { useEffect, useMemo, useState, type MouseEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { CircleAlert, RotateCcw, Search, TriangleAlert } from 'lucide-react'
import { listManagerClaims } from '@/api/claims'
import type { ClaimsQuery, ManagerClaimListItem } from '@/api/types'
import { Money } from '@/components/Money'
import { RiskBadge } from '@/components/RiskBadge'
import { ServerPagination } from '@/components/ServerPagination'
import { StatusBadge } from '@/components/StatusBadge'

const PAGE_SIZE = 8
/** Tri demandé par l'écran ; format à confirmer avec M2. */
const SORT_BY_SCORE_DESC = 'score_fraude:desc'

type SignalFilter = 'alert' | 'all'
type DecisionFilter = 'all' | 'pending' | 'decided'

function useDebouncedValue<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay)
    return () => window.clearTimeout(timer)
  }, [value, delay])
  return debounced
}

function scoreLabel(score: number | null): string {
  return score === null ? 'Score non disponible' : `Score ${Math.round(score * 100)} %`
}

export function ManagerQueuePage() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [signal, setSignal] = useState<SignalFilter>('alert')
  const [decision, setDecision] = useState<DecisionFilter>('all')
  const [sortBy, setSortBy] = useState<'score' | 'date'>('score')
  const debouncedSearch = useDebouncedValue(search)
  const navigate = useNavigate()

  const query = useMemo<ClaimsQuery>(
    () => ({
      page,
      page_size: PAGE_SIZE,
      sort: sortBy === 'score' ? SORT_BY_SCORE_DESC : undefined,
      fraud_alert_only: signal === 'alert' ? true : undefined,
      q: debouncedSearch.trim() || undefined,
      decision_enregistree: decision === 'all' ? undefined : decision === 'decided',
    }),
    [page, signal, debouncedSearch, decision, sortBy],
  )

  const { data, error, isPending, isFetching, isError, refetch } = useQuery({
    queryKey: ['manager-queue', query],
    queryFn: () => listManagerClaims(query),
    placeholderData: keepPreviousData,
  })

  const items = data?.items ?? []
  const filtersActive =
    Boolean(search.trim()) ||
    signal !== 'alert' ||
    decision !== 'all' ||
    sortBy !== 'score'
  const openClaim = (factureId: string) =>
    navigate(`/gestionnaire/dossiers/${encodeURIComponent(factureId)}`)

  function changeFilter(update: () => void) {
    update()
    setPage(1)
  }

  function handleSignalChange(newSignal: SignalFilter) {
    changeFilter(() => {
      setSignal(newSignal)
      setSortBy(newSignal === 'all' ? 'date' : 'score')
    })
  }

  function resetFilters() {
    changeFilter(() => {
      setSearch('')
      setSignal('alert')
      setDecision('all')
      setSortBy('score')
    })
  }

  function handleRowClick(event: MouseEvent<HTMLTableRowElement>, factureId: string) {
    // Le lien interne reste la commande accessible ; le clic de ligne est un confort souris.
    if ((event.target as HTMLElement).closest('a')) return
    if (window.getSelection()?.toString()) return
    openClaim(factureId)
  }
      
  return (
    <div className="queue-page">
      <header className="page-heading">
        <div>
          <h1>Dossiers à examiner</h1>
          <p className="page-subtitle">
            Classés par score décroissant. Le score est une aide à la décision, jamais une preuve de fraude.
          </p>
        </div>
        <div className="live-indicator">
          <span /> {isFetching ? 'Actualisation…' : 'Données de démonstration'}
        </div>
      </header>

      <div className="queue-filters" role="search" aria-label="Filtrer les dossiers à examiner">
        <div className="queue-field">
          <label htmlFor="queue-search">Identifiant de facture</label>
          <input
            id="queue-search"
            type="search"
            value={search}
            placeholder="FAC-00005637"
            autoComplete="off"
            onChange={(event) => changeFilter(() => setSearch(event.target.value))}
          />
        </div>
        <div className="queue-field">
          <label htmlFor="queue-signal">Signal</label>
          <select
            id="queue-signal"
            value={signal}
            onChange={(event) => handleSignalChange(event.target.value as SignalFilter)}
          >
            <option value="alert">Signal à examiner</option>
            <option value="all">Tous les dossiers</option>
          </select>
        </div>
        <div className="queue-field">
          <label htmlFor="queue-sort">Tri</label>
          <select
            id="queue-sort"
            value={sortBy}
            onChange={(event) => changeFilter(() => setSortBy(event.target.value as 'score' | 'date'))}
          >
            <option value="score">Score de risque (décroissant)</option>
            <option value="date">Date de soumission (plus récentes)</option>
          </select>
        </div>
        <div className="queue-field">
          <label htmlFor="queue-decision">État de décision</label>
          <select
            id="queue-decision"
            value={decision}
            onChange={(event) => changeFilter(() => setDecision(event.target.value as DecisionFilter))}
          >
            <option value="all">Tous</option>
            <option value="pending">En attente d’arbitrage</option>
            <option value="decided">Décision enregistrée</option>
          </select>
        </div>
        <button type="button" className="queue-reset" onClick={resetFilters} disabled={!filtersActive}>
          <RotateCcw aria-hidden="true" size={15} /> Réinitialiser
        </button>
      </div>

      {isError && (
        <div className="queue-state" role="alert">
          <TriangleAlert aria-hidden="true" size={22} />
          <strong>La liste n’a pas pu être chargée</strong>
          <span>{error instanceof Error ? error.message : 'Réessayez dans un instant.'}</span>
          <button type="button" onClick={() => void refetch()}>Réessayer</button>
        </div>
      )}

      {!isError && isPending && (
        <div className="queue-state" aria-live="polite">
          <CircleAlert aria-hidden="true" size={22} />
          <strong>Chargement des dossiers…</strong>
          <span>Les dossiers filtrés sont récupérés depuis le serveur.</span>
        </div>
      )}

      {!isError && !isPending && items.length === 0 && (
        <div className="queue-state" aria-live="polite">
          <Search aria-hidden="true" size={22} />
          <strong>Aucun dossier ne correspond</strong>
          <span>Élargissez la recherche ou revenez à tous les dossiers.</span>
          {filtersActive && <button type="button" onClick={resetFilters}>Réinitialiser les filtres</button>}
        </div>
      )}

      {!isError && !isPending && items.length > 0 && (
        <section className="queue-panel" aria-label="Dossiers à examiner" aria-busy={isFetching}>
          <div className="queue-scroll">
            <table className="queue-table">
              <caption className="sr-only">
                Dossiers à examiner, classés par score décroissant. Chaque identifiant ouvre la fiche du dossier.
              </caption>
              <thead>
                <tr>
                  <th scope="col">Facture</th>
                  <th scope="col" className="queue-col-secondary">Assuré</th>
                  <th scope="col" className="queue-col-secondary">Prestataire</th>
                  <th scope="col" className="queue-col-secondary">Date de soumission</th>
                  <th scope="col" className="queue-amount">Montant total</th>
                  <th scope="col">Statut</th>
                  <th scope="col">Signal</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item: ManagerClaimListItem) => (
                  <tr
                    key={item.facture_id}
                    className="queue-row"
                    onClick={(event) => handleRowClick(event, item.facture_id)}
                  >
                    <th scope="row">
                      <Link to={`/gestionnaire/dossiers/${encodeURIComponent(item.facture_id)}`}>{item.facture_id}</Link>
                      <small>{item.numero_facture}</small>
                    </th>
                    <td className="queue-col-secondary">{item.assure_id}</td>
                    <td className="queue-col-secondary">{item.prestataire_id}</td>
                    <td className="queue-col-secondary queue-date">
                      {item.date_reception || item.date_soin}
                    </td>
                    <td className="queue-amount"><Money amount={item.montant_total} /></td>
                    <td><StatusBadge status={item.statut} /></td>
                    <td>
                      <div className="queue-signal">
                        <RiskBadge anomaly={item.est_anomalie} />
                        <small>{scoreLabel(item.score_fraude)}</small>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ServerPagination
            page={data.page}
            pageSize={data.page_size}
            total={data.total}
            onPageChange={setPage}
            label="Dossiers"
          />
        </section>
      )}

      <p className="rights-note">
        Seuls les dossiers autorisés par votre rôle sont transmis par l’API. Le score ne déclenche aucune décision automatique.
      </p>
    </div>
  )
}