// web/src/pages/ProClaimDetailPage.tsx
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, FileText, CheckCircle2, XCircle } from 'lucide-react'
import { getClaim } from '@/api/claims'
import { Money } from '@/components/Money'
import { StatusBadge } from '@/components/StatusBadge'
import { rejectionReasonLabels, rejectionReasons } from '@/lib/config'

export function ProClaimDetailPage() {
  const { factureId = '' } = useParams()
  const { data: detail, isLoading, isError } = useQuery({
    queryKey: ['pro-claim', factureId],
    queryFn: () => getClaim(factureId),
    enabled: Boolean(factureId),
  })

  if (isError) return <div className="queue-state">Ce dossier n'a pas pu être ouvert.</div>
  if (isLoading || !detail) return <div className="queue-state">Chargement du dossier…</div>

  const isRejected = detail.statut === 'REJETEE'
  const reasonLabel = detail.motif_rejet && rejectionReasons.includes(detail.motif_rejet)
    ? rejectionReasonLabels[detail.motif_rejet]
    : detail.motif_rejet

  return (
    <div className="claim-page">
      <Link className="claim-back" to="/professionnel-sante/dossiers">
        <ArrowLeft size={16} /> Retour à mes dossiers
      </Link>

      <header className="claim-page-heading">
        <div>
          <span className="claim-heading-icon"><FileText size={20} /></span>
          <div>
            <h1>{detail.facture_id}</h1>
            <p>{detail.numero_facture} · {detail.nom_etablissement ?? 'Établissement'} · soin du {detail.date_soin}</p>
          </div>
        </div>
        <StatusBadge status={detail.statut} />
      </header>

      <div className="fiche-stack">
        <section className="claim-section">
          <div className="claim-section-heading">
            <div><h2>Résumé de la facture</h2><p>Détails de la prise en charge.</p></div>
          </div>

          <dl className="fiche-facts">
            <div><dt>Assuré</dt><dd>{detail.assure_id}</dd></div>
            <div><dt>Date d'émission</dt><dd>{detail.date_emission}</dd></div>
            <div><dt>Ordonnance</dt><dd>{detail.ordonnance_id ?? 'Non transmise'}</dd></div>
            <div><dt>Mode de règlement</dt><dd>Tiers payant</dd></div>
          </dl>

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
                    <td className="fiche-number"><Money amount={line.prix_unitaire} /></td>
                    <td className="fiche-number"><Money amount={line.montant_total} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="fiche-totals">
            <div><span>Part de l'assuré</span><Money amount={detail.part_assure} className="fiche-amount" /></div>
            <div><span>Montant demandé</span><Money amount={detail.montant_demande} className="fiche-amount" /></div>
            {detail.montant_pris_en_charge !== null && (
              <div><span>Montant pris en charge</span><Money amount={detail.montant_pris_en_charge} className="fiche-amount" /></div>
            )}
            <div className="fiche-total-main"><span>Montant total</span><Money amount={detail.montant_total} className="fiche-amount" /></div>
          </div>

          {isRejected && reasonLabel && (
            <div className="claim-summary claim-summary-error" style={{ marginTop: '1rem' }}>
              <strong><XCircle size={16} style={{ display: 'inline', marginRight: '6px' }} /> Motif de rejet</strong>
              <span>{reasonLabel}</span>
            </div>
          )}

          {detail.statut === 'PAYEE' && (
            <div className="claim-summary" style={{ marginTop: '1rem', borderLeftColor: 'var(--success)', background: 'var(--success-soft)' }}>
              <strong style={{ color: 'var(--success-soft-foreground)' }}><CheckCircle2 size={16} style={{ display: 'inline', marginRight: '6px' }} /> Dossier validé et payé</strong>
              <span style={{ color: 'var(--success-soft-foreground)' }}>Le remboursement a été effectué.</span>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}