// web/src/pages/AssureDashboardPage.tsx
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Search, ChevronRight } from 'lucide-react'
import { listClaims } from '@/api/claims'
import { Money } from '@/components/Money'
import { StatusBadge } from '@/components/StatusBadge'
import { ServerPagination } from '@/components/ServerPagination'
import type { ClaimsQuery } from '@/api/types'

export function AssureDashboardPage() {
  const [page, setPage] = useState(1)
  const query: ClaimsQuery = { page, page_size: 8 }
  
  const { data, isLoading, isError } = useQuery({
    queryKey: ['assure-claims', query],
    queryFn: () => listClaims(query),
  })

  if (isError) return <div className="queue-state">Erreur lors du chargement de vos dossiers.</div>

  return (
    <div className="queue-page">
      <header className="page-heading">
        <div>
          <h1>Mes dossiers de soins</h1>
          <p className="page-subtitle">Suivez l'état de vos remboursements et consultez vos factures.</p>
        </div>
      </header>

      {isLoading ? (
        <div className="queue-state">Chargement de vos dossiers…</div>
      ) : data?.items.length === 0 ? (
        <div className="queue-state">
          <Search size={22} />
          <strong>Aucun dossier pour le moment</strong>
          <span>Vos futures demandes de remboursement apparaîtront ici.</span>
        </div>
      ) : (
        <section className="queue-panel">
          <div className="queue-scroll">
            <table className="queue-table">
              <thead>
                <tr>
                  <th>Facture</th>
                  <th className="queue-col-secondary">Date de soumission</th>
                  <th className="queue-amount">Montant total</th>
                  <th className="queue-amount">Part assuré</th>
                  <th>Statut</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data?.items.map((item) => (
                  <tr key={item.facture_id} className="queue-row">
                    <th scope="row">
                      <Link to={`/assure/dossiers/${item.facture_id}`}>{item.facture_id}</Link>
                      <small>{item.numero_facture}</small>
                    </th>
                    <td className="queue-col-secondary queue-date">
                      {item.date_reception || item.date_soin}
                    </td>
                    <td className="queue-amount"><Money amount={item.montant_total} /></td>
                    <td className="queue-amount"><Money amount={item.part_assure} /></td>
                    <td><StatusBadge status={item.statut} /></td>
                    <td style={{ textAlign: 'right' }}>
                      <Link to={`/assure/dossiers/${item.facture_id}`} className="nav-item" style={{ display: 'inline-flex', minHeight: 'auto', padding: '4px' }}>
                        <ChevronRight size={16} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
            <ServerPagination 
                page={data?.page ?? 1} 
                pageSize={data?.page_size ?? 8} 
                total={data?.total ?? 0} 
                onPageChange={setPage} 
                label="Dossiers" 
            />
        </section>
      )}
    </div>
  )
}