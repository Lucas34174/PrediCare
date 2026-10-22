import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowUpRight, BadgeCheck, CircleAlert, FileText, WalletCards } from 'lucide-react'
import { request } from '@/api/request'
import { useAuth } from '@/auth/AuthContext'
import { roleTitles } from '@/components/navigation'
import { normalizeFactors } from '@/lib/normalizeFactors'

const formatMGA = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 })

export function DashboardPage() {
  const { user } = useAuth()
  const [periode, setPeriode] = useState<'7d' | '30d' | 'all'>('30d')
  
  const { data: apiKpis } = useQuery({ 
    queryKey: ['kpis', periode], 
    queryFn: () => request<any>(`/dashboard/kpis?periode=${periode}`),
  })
  
  const { data: latestClaimData } = useQuery({
    queryKey: ['latest-alert-claim'],
    queryFn: () => request<any>('/claims?fraud_alert_only=true&page_size=1'),
    enabled: !!user && (user.role === 'gestionnaire' || user.role === 'admin'),
  })

  const latestClaimId = latestClaimData?.items?.[0]?.facture_id

  const { data: predictionData } = useQuery({
    queryKey: ['prediction', latestClaimId],
    queryFn: () => request<any>(`/claims/${latestClaimId}/prediction`),
    enabled: Boolean(latestClaimId),
    retry: false,
  })

  if (!user) return null

  const prediction = predictionData ? {
    claim_id: predictionData.facture_id,
    fraud_probability: predictionData.prediction.score_fraude,
    model_version: predictionData.prediction.version_modele,
    explanation: {
      top_factors: predictionData.explicabilite?.top_facteurs?.map((f: any) => ({
        feature: f.feature,
        shap_value: f.impact_shap,
        direction: f.impact_shap > 0 ? 'increases' : 'decreases',
      })) ?? [],
    },
  } : null

  const factors = normalizeFactors(prediction?.explanation?.top_factors)

  // Indicateurs extraits dynamiquement de la base PostgreSQL
  const kpis = apiKpis ? {
    received: apiKpis.kpis?.total_factures_traitees ?? 0,
    to_review: apiKpis.kpis?.dossiers_en_attente_arbitrage ?? 0,
    processed: apiKpis.kpis?.total_factures_traitees ?? 0,
    amount: apiKpis.kpis?.montant_total_demande ?? 0,
  } : null

  const periodNote = periode === '7d' ? 'sur 7 jours' : periode === '30d' ? 'sur 30 jours' : 'tout l’historique'
  const periodTagLabel = periode === '7d' ? '7 derniers jours' : periode === '30d' ? '30 derniers jours' : 'Tout l’historique'

  // Date et heure actuelles calculées dynamiquement sans codage en dur
  const now = new Date()
  const todayStr = now.toISOString().slice(0, 10)
  const timeStr = now.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
  const lastUpdateStr = `${todayStr} · ${timeStr}`

  const cards = [
    { label: 'Dossiers reçus', value: kpis ? formatMGA.format(kpis.received) : '—', note: periodNote, icon: FileText },
    { label: 'À examiner', value: kpis ? formatMGA.format(kpis.to_review) : '—', note: 'vérification recommandée', icon: CircleAlert },
    { label: 'Dossiers traités', value: kpis ? formatMGA.format(kpis.processed) : '—', note: periodNote, icon: BadgeCheck },
    {
      label: 'Remboursements',
      value: kpis ? `${formatMGA.format(kpis.amount)} MGA` : '—',
      note: 'montant total',
      icon: WalletCards,
    },
  ]

  return (
    <div className="dashboard-page">
      <header className="page-heading">
        <div>
          <p className="eyebrow">{todayStr} <span>·</span> ANTANANARIVO</p>
          <h1>{roleTitles[user.role]}</h1>
          <p className="page-subtitle">Bonjour {user.display_name.split(' ')[0]}, voici le point sur votre espace.</p>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '8px' }}>
          <div className="live-indicator"><span /> Données en temps réel (PostgreSQL)</div>
          <div className="period-selector" role="group" aria-label="Filtrer par période">
            <button
              type="button"
              className={`period-btn ${periode === '7d' ? 'active' : ''}`}
              onClick={() => setPeriode('7d')}
            >
              7 jours
            </button>
            <button
              type="button"
              className={`period-btn ${periode === '30d' ? 'active' : ''}`}
              onClick={() => setPeriode('30d')}
            >
              30 jours
            </button>
            <button
              type="button"
              className={`period-btn ${periode === 'all' ? 'active' : ''}`}
              onClick={() => setPeriode('all')}
            >
              Tout
            </button>
          </div>
        </div>
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
            <span className="period-tag">{periodTagLabel}</span>
          </div>
          <div className="activity-visual" aria-label="Résumé de l’activité">
            <div className="activity-orbit orbit-one" />
            <div className="activity-orbit orbit-two" />
            <div className="activity-core"><span>TPA</span><strong>{kpis ? formatMGA.format(kpis.processed) : '—'}</strong><small>dossiers suivis</small></div>
            <div className="activity-note note-left"><span className="note-dot green" /> Traitement fluide</div>
            <div className="activity-note note-right"><span className="note-dot amber" /> {kpis ? formatMGA.format(kpis.to_review) : '—'} à revoir</div>
          </div>
          <div className="panel-footer"><span>Dernière mise à jour</span><strong>{lastUpdateStr}</strong></div>
        </article>

        <article className="signal-panel">
          <div className="panel-heading"><div><span className="section-kicker">ANALYSE EXPLICABLE</span><h2>Signal récent</h2></div><span className="signal-badge">À examiner</span></div>
          {prediction ? (
            <div className="signal-content">
              <div className="signal-score"><span>Score de risque</span><strong>{Math.round(prediction.fraud_probability * 100)}<small>%</small></strong><div className="score-track"><span style={{ width: `${Math.round(prediction.fraud_probability * 100)}%` }} /></div></div>
              <p className="claim-reference">Dossier <strong>{prediction.claim_id}</strong><span>Version {prediction.model_version}</span></p>
              <p className="signal-disclaimer">Un score élevé est un signal à examiner, jamais une preuve de fraude.</p>
              <ul className="factor-list">{factors.slice(0, 2).map((factor) => <li key={factor.feature}><ArrowUpRight aria-hidden="true" size={19} />{factor.label}</li>)}</ul>
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
