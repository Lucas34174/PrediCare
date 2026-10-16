import { useQuery } from '@tanstack/react-query'
import { ArrowUpRight, BadgeCheck, CircleAlert, FileText, WalletCards } from 'lucide-react'
import { request } from '@/api/request'
import type { DashboardKpis, DashboardPrediction } from '@/api/types'
import { useAuth } from '@/auth/AuthContext'
import { roleTitles } from '@/components/navigation'
import { normalizeFactors } from '@/lib/normalizeFactors'

const formatMGA = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 })

export function DashboardPage() {
  const { user } = useAuth()
  const { data: kpis } = useQuery({ queryKey: ['kpis'], queryFn: () => request<DashboardKpis>('/dashboard/kpis') })
  const { data: prediction } = useQuery({
    queryKey: ['prediction'],
    queryFn: () => request<DashboardPrediction>('/predictions/latest'),
  })
  const factors = normalizeFactors(prediction?.explanation.top_factors)

  if (!user) return null

  const cards = [
    { label: 'Dossiers reçus', value: kpis?.claims_received ?? '—', note: 'sur la période', icon: FileText },
    { label: 'À examiner', value: kpis?.claims_to_review ?? '—', note: 'vérification recommandée', icon: CircleAlert },
    { label: 'Dossiers traités', value: kpis?.claims_processed ?? '—', note: 'sur la période', icon: BadgeCheck },
    {
      label: 'Remboursements',
      value: kpis ? `${formatMGA.format(kpis.reimbursements_mga)} MGA` : '—',
      note: 'montant total',
      icon: WalletCards,
    },
  ]

  return (
    <div className="dashboard-page">
      <header className="page-heading">
        <div>
          <p className="eyebrow">2026-10-14 <span>·</span> ANTANANARIVO</p>
          <h1>{roleTitles[user.role]}</h1>
          <p className="page-subtitle">Bonjour {user.display_name.split(' ')[0]}, voici le point sur votre espace.</p>
        </div>
        <div className="live-indicator"><span /> Données de démonstration</div>
      </header>

      <section className="metric-grid" aria-label="Indicateurs clés">
        {cards.map(({ label, value, note, icon: Icon }) => (
          <article className="metric-card" key={label}>
            <div className="metric-card-top"><span>{label}</span><Icon aria-hidden="true" size={18} /></div>
            <strong>{value}</strong>
            <small>{note}</small>
          </article>
        ))}
      </section>

      <section className="dashboard-lower">
        <article className="overview-panel">
          <div className="panel-heading">
            <div><span className="section-kicker">VOTRE ACTIVITÉ</span><h2>Un aperçu, en un regard</h2></div>
            <span className="period-tag">Ce mois-ci</span>
          </div>
          <div className="activity-visual" aria-label="Résumé de l’activité">
            <div className="activity-orbit orbit-one" />
            <div className="activity-orbit orbit-two" />
            <div className="activity-core"><span>TPA</span><strong>{kpis?.claims_processed ?? '—'}</strong><small>dossiers suivis</small></div>
            <div className="activity-note note-left"><span className="note-dot green" /> Traitement fluide</div>
            <div className="activity-note note-right"><span className="note-dot amber" /> {kpis?.claims_to_review ?? '—'} à revoir</div>
          </div>
          <div className="panel-footer"><span>Dernière mise à jour</span><strong>2026-10-14 · 09:42</strong></div>
        </article>

        <article className="signal-panel">
          <div className="panel-heading"><div><span className="section-kicker">ANALYSE EXPLICABLE</span><h2>Signal récent</h2></div><span className="signal-badge">À examiner</span></div>
          {prediction ? (
            <div className="signal-content">
              <div className="signal-score"><span>Score de risque</span><strong>{Math.round(prediction.fraud_probability * 100)}<small>%</small></strong><div className="score-track"><span style={{ width: `${Math.round(prediction.fraud_probability * 100)}%` }} /></div></div>
              <p className="claim-reference">Dossier <strong>{prediction.claim_id}</strong><span>Version {prediction.model_version}</span></p>
              <p className="signal-disclaimer">Un score élevé est un signal à examiner, jamais une preuve de fraude.</p>
              <ul className="factor-list">{factors.slice(0, 2).map((factor) => <li key={factor.feature}><ArrowUpRight aria-hidden="true" size={15} />{factor.label}</li>)}</ul>
            </div>
          ) : (
            <div className="empty-signal"><CircleAlert aria-hidden="true" /><strong>Aucun signal à afficher</strong><span>Les nouvelles analyses apparaîtront ici.</span></div>
          )}
        </article>
      </section>
      <p className="rights-note">Les menus facilitent la navigation. Les autorisations sont contrôlées par l’API.</p>
    </div>
  )
}
