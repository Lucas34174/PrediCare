import { useQuery } from '@tanstack/react-query'
import { ArrowUpRight, BadgeCheck, CircleAlert, FileText, WalletCards, Database, Zap } from 'lucide-react'
import { request } from '@/api/request'
import { useAuth } from '@/auth/AuthContext'
import { roleTitles } from '@/components/navigation'
import { normalizeFactors } from '@/lib/normalizeFactors'

const formatMGA = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 })

export function DashboardPage() {
  const { user } = useAuth()
  
  // 1. On active la requête (enabled: true)
  const { data: apiKpis, isLoading } = useQuery({ 
    queryKey: ['kpis'], 
    queryFn: () => request<any>('/dashboard/kpis'),
    enabled: !!user && user.role !== 'assure', // Uniquement pour gestionnaires/admins
  })
  
  const { data: prediction } = useQuery({
    queryKey: ['prediction'],
    queryFn: () => request<any>('/predictions/latest'),
    retry: false,
    enabled: !!user,
  })

  if (!user) return null

  const factors = normalizeFactors(prediction?.explanation?.top_factors)

  // 2. On extrait les vraies données de l'API
    const kpis = apiKpis?.kpis_metier ? {
    total_factures: apiKpis.kpis_metier.total_factures ?? 0,
    en_attente: apiKpis.kpis_metier.en_attente ?? 0,
    montant: apiKpis.kpis_metier.montant_total_demande ?? 0,
    montant_economise: apiKpis.kpis_metier.montant_economise ?? 0,
    taux_fraude: apiKpis.kpis_metier.taux_detection_fraude ?? 0,
    cache_hits: apiKpis.kpis_finops?.cache_hits ?? 0,
    tokens_economises: apiKpis.kpis_finops?.tokens_economises ?? 0,
  } : null

  // 3. On ajoute les KPIs FinOps
  const cards = [
    { label: 'Dossiers traités', value: kpis ? formatMGA.format(kpis.total_factures) : '—', note: 'sur la période', icon: FileText },
    { label: 'À examiner', value: kpis ? formatMGA.format(kpis.en_attente) : '—', note: 'vérification recommandée', icon: CircleAlert },
    { label: 'Économies (Fraude)', value: kpis ? `${formatMGA.format(kpis.montant_economise)} Ar` : '—', note: 'montant évité', icon: WalletCards },
    { label: 'Cache FinOps', value: kpis ? formatMGA.format(kpis.tokens_economises) : '—', note: 'tokens économisés', icon: Zap },
  ]

  return (
    <div className="dashboard-page">
      <header className="page-heading">
        <div>
          <p className="eyebrow">2026-10-22 <span>·</span> ANTANANARIVO</p>
          <h1>{roleTitles[user.role]}</h1>
          <p className="page-subtitle">Bonjour {user.display_name.split(' ')[0]}, voici le point sur votre espace.</p>
        </div>
        <div className="live-indicator"><span /> Données en direct</div>
      </header>

      <section className="metric-grid" aria-label="Indicateurs clés">
        {cards.map(({ label, value, note, icon: Icon }) => (
          <article className="metric-card" key={label}>
            <div className="metric-card-top"><span>{label}</span><Icon aria-hidden="true" size={18} /></div>
            <strong>{isLoading ? '...' : value}</strong>
            <small>{note}</small>
          </article>
        ))}
      </section>
      
      {/* Le reste de ton composant avec les graphiques (activity-visual, etc.) */}
            <section className="dashboard-lower">
        <article className="overview-panel">
          <div className="panel-heading">
            <div><span className="section-kicker">VOTRE ACTIVITÉ</span><h2>Un aperçu, en un regard</h2></div>
            <span className="period-tag">Ce mois-ci</span>
          </div>
          <div className="activity-visual" aria-label="Résumé de l’activité">
            <div className="activity-orbit orbit-one" />
            <div className="activity-orbit orbit-two" />
            <div className="activity-core"><span>TPA</span><strong>{kpis?.total_factures ?? '—'}</strong><small>dossiers suivis</small></div>
            <div className="activity-note note-left"><span className="note-dot green" /> Taux de fraude: {kpis ? (kpis.taux_fraude * 100).toFixed(1) : 0}%</div>
            <div className="activity-note note-right"><span className="note-dot amber" /> {kpis?.cache_hits ?? '—'} requêtes en cache</div>
          </div>
          <div className="panel-footer"><span>Dernière mise à jour</span><strong>À l'instant</strong></div>
        </article>

        <article className="signal-panel">
          <div className="panel-heading"><div><span className="section-kicker">ANALYSE EXPLICABLE</span><h2>Signal récent</h2></div><span className="signal-badge">À examiner</span></div>
          {prediction ? (
             // ... ton code existant pour l'affichage du signal ...
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
