// web/src/pages/ProDossierPage.tsx
// Page liste des dossiers pour les professionnels de santé
// Les liens pointent vers /professionnel-sante/dossiers/:factureId (pas vers /assure/*)

import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Search, ChevronRight, ArrowLeft, FileText, CheckCircle2, XCircle, Building2 } from 'lucide-react'
import { listClaims, getClaim } from '@/api/claims'
import { Money } from '@/components/Money'
import { StatusBadge } from '@/components/StatusBadge'
import { ServerPagination } from '@/components/ServerPagination'
import type { ClaimsQuery } from '@/api/types'
import { useAuth } from '@/auth/AuthContext'

/* ────────────────────────────────────────────────────────────
   ProDossierListPage — /professionnel-sante/dossiers
───────────────────────────────────────────────────────────── */
export function ProDossierListPage() {
  const { user } = useAuth()
  const [page, setPage] = useState(1)
  const query: ClaimsQuery = { page, page_size: 10 }

  const { data, isLoading, isError } = useQuery({
    queryKey: ['pro-dossiers', query],
    queryFn: () => listClaims(query),
    enabled: !!user,
  })

  if (isError)
    return <div className="queue-state">Erreur lors du chargement de vos dossiers.</div>

  return (
    <div className="queue-page">
      <header className="page-heading">
        <div>
          <h1>Mes dossiers transmis</h1>
          <p className="page-subtitle">
            Factures télétransmises par votre établissement — {user?.display_name ?? 'Établissement'}
          </p>
        </div>
      </header>

      {isLoading ? (
        <div className="queue-state">Chargement de vos dossiers…</div>
      ) : data?.items.length === 0 ? (
        <div className="queue-state">
          <Search size={22} />
          <strong>Aucun dossier transmis</strong>
          <span>Vos télétransmissions apparaîtront ici dès qu'elles seront enregistrées.</span>
        </div>
      ) : (
        <section className="queue-panel">
          <div className="queue-scroll">
            <table className="queue-table">
              <thead>
                <tr>
                  <th>Facture</th>
                  <th className="queue-col-secondary">Date de soin</th>
                  <th className="queue-col-secondary">Assuré</th>
                  <th className="queue-amount">Montant total</th>
                  <th className="queue-amount">Montant demandé</th>
                  <th>Statut</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data?.items.map((item) => (
                  <tr key={item.facture_id} className="queue-row">
                    <th scope="row">
                      <Link to={`/professionnel-sante/dossiers/${item.facture_id}`}>
                        {item.facture_id}
                      </Link>
                      <small>{item.numero_facture}</small>
                    </th>
                    <td className="queue-col-secondary queue-date">{item.date_soin}</td>
                    <td className="queue-col-secondary">
                      <code style={{ fontSize: '0.75rem' }}>{item.assure_id}</code>
                    </td>
                    <td className="queue-amount">
                      <Money amount={item.montant_total} />
                    </td>
                    <td className="queue-amount">
                      <Money amount={item.montant_demande} />
                    </td>
                    <td>
                      <StatusBadge status={item.statut} />
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <Link
                        to={`/professionnel-sante/dossiers/${item.facture_id}`}
                        className="nav-item"
                        style={{ display: 'inline-flex', minHeight: 'auto', padding: '4px' }}
                      >
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
            pageSize={data?.page_size ?? 10}
            total={data?.total ?? 0}
            onPageChange={setPage}
            label="Dossiers"
          />
        </section>
      )}
    </div>
  )
}

/* ────────────────────────────────────────────────────────────
   ProDossierDetailPage — /professionnel-sante/dossiers/:factureId
───────────────────────────────────────────────────────────── */
export function ProDossierDetailPage() {
  const { factureId = '' } = useParams()
  const {
    data: detail,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ['pro-dossier', factureId],
    queryFn: () => getClaim(factureId),
    enabled: Boolean(factureId),
  })

  if (isError)
    return <div className="queue-state">Ce dossier n'a pas pu être ouvert ou vous n'y avez pas accès.</div>
  if (isLoading || !detail)
    return <div className="queue-state">Chargement du dossier…</div>

  const isRejected = detail.statut === 'REJETEE'

  return (
    <div className="claim-page">
      <Link className="claim-back" to="/professionnel-sante/dossiers">
        <ArrowLeft size={16} /> Retour à mes dossiers
      </Link>

      <header className="claim-page-heading">
        <div>
          <span className="claim-heading-icon">
            <FileText size={20} />
          </span>
          <div>
            <h1>{detail.facture_id}</h1>
            <p>
              {detail.numero_facture} · soin du {detail.date_soin}
            </p>
          </div>
        </div>
        <StatusBadge status={detail.statut} />
      </header>

      <div className="fiche-stack">
        {/* Infos assuré */}
        <section className="claim-section">
          <div className="claim-section-heading">
            <div>
              <h2>Informations générales</h2>
              <p>Récapitulatif de la facture transmise.</p>
            </div>
          </div>

          <dl className="fiche-facts">
            <div>
              <dt>Date d'émission</dt>
              <dd>{detail.date_emission}</dd>
            </div>
            <div>
              <dt>Établissement</dt>
              <dd>
                <Building2
                  size={14}
                  style={{ display: 'inline', marginRight: 4, verticalAlign: 'middle' }}
                />
                {detail.nom_etablissement ?? detail.prestataire_id}
              </dd>
            </div>
            <div>
              <dt>Assuré</dt>
              <dd>
                <code style={{ fontSize: '0.8rem' }}>{detail.assure_id}</code>
              </dd>
            </div>
            <div>
              <dt>Ordonnance</dt>
              <dd>{detail.ordonnance_id ?? 'Non transmise'}</dd>
            </div>
          </dl>
        </section>

        {/* Lignes de facturation */}
        <section className="claim-section">
          <div className="claim-section-heading">
            <div>
              <h2>Lignes de facturation</h2>
            </div>
          </div>

          <div className="fiche-lines-scroll">
            <table className="fiche-lines">
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Type</th>
                  <th className="fiche-number">Qté</th>
                  <th className="fiche-number">Prix unitaire</th>
                  <th className="fiche-number">Montant</th>
                </tr>
              </thead>
              <tbody>
                {detail.lignes.map((line) => (
                  <tr key={line.num_ligne}>
                    <td>{line.code}</td>
                    <td>{line.type_ligne === 'ACTE' ? 'Acte' : 'Médicament'}</td>
                    <td className="fiche-number">{line.quantite}</td>
                    <td className="fiche-number">
                      <Money amount={line.prix_unitaire} />
                    </td>
                    <td className="fiche-number">
                      <Money amount={line.montant_total} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="fiche-totals">
            <div>
              <span>Part de l'assuré</span>
              <Money amount={detail.part_assure} className="fiche-amount" />
            </div>
            <div>
              <span>Montant demandé à l'assurance</span>
              <Money amount={detail.montant_demande} className="fiche-amount" />
            </div>
            {detail.montant_pris_en_charge !== null && (
              <div>
                <span>Montant pris en charge</span>
                <Money amount={detail.montant_pris_en_charge} className="fiche-amount" />
              </div>
            )}
            <div className="fiche-total-main">
              <span>Montant total</span>
              <Money amount={detail.montant_total} className="fiche-amount" />
            </div>
          </div>

          {isRejected && detail.motif_rejet && (
            <div className="claim-summary claim-summary-error" style={{ marginTop: '1rem' }}>
              <strong>
                <XCircle size={16} style={{ display: 'inline', marginRight: '6px' }} /> Motif de
                rejet
              </strong>
              <span>{detail.motif_rejet}</span>
            </div>
          )}

          {detail.statut === 'PAYEE' && (
            <div
              className="claim-summary"
              style={{
                marginTop: '1rem',
                borderLeftColor: 'var(--success)',
                background: 'var(--success-soft)',
              }}
            >
              <strong style={{ color: 'var(--success-soft-foreground)' }}>
                <CheckCircle2 size={16} style={{ display: 'inline', marginRight: '6px' }} />{' '}
                Remboursement effectué
              </strong>
              <span style={{ color: 'var(--success-soft-foreground)' }}>
                Ce dossier a été traité et le paiement a été effectué.
              </span>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
