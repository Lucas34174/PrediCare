// web/src/pages/AdminDashboardPage.tsx
import { useQuery } from '@tanstack/react-query'
import { Activity, AlertTriangle, CheckCircle2, Server, ShieldAlert } from 'lucide-react'
import { getAdminMetrics } from '@/api/admin'

export function AdminDashboardPage() {
  const { data: metrics, isLoading } = useQuery({
    queryKey: ['admin-metrics'],
    queryFn: getAdminMetrics,
  })

  if (isLoading || !metrics) {
    return <div className="queue-state">Chargement des métriques de supervision…</div>
  }

  const { api_metrics, ml_drift_monitoring } = metrics
  const isDriftAlert = ml_drift_monitoring.alerte_derive

  return (
    <div className="dashboard-page">
      <header className="page-heading">
        <div>
          <p className="eyebrow">SUPERVISION SYSTÈME</p>
          <h1>Santé de la plateforme</h1>
          <p className="page-subtitle">Surveillance en temps réel de l'API et de la dérive du modèle ML.</p>
        </div>
        <div className="live-indicator">
          <span /> Dernière éval. : {new Date(ml_drift_monitoring.derniere_evaluation).toLocaleString('fr-FR')}
        </div>
      </header>

      <section className="metric-grid" aria-label="Métriques API">
        <article className="metric-card">
          <div className="metric-card-top"><span>Requêtes totales</span><Server size={18} /></div>
          <strong>{api_metrics.requests_total.toLocaleString('fr-FR')}</strong>
          <small>depuis le démarrage</small>
        </article>
        <article className="metric-card">
          <div className="metric-card-top"><span>Taux d'erreur (5xx)</span><ShieldAlert size={18} /></div>
          <strong>{(api_metrics.error_rate_5xx * 100).toFixed(2)} %</strong>
          <small>objectif &lt; 0.1 %</small>
        </article>
        <article className="metric-card">
          <div className="metric-card-top"><span>Latence P95</span><Activity size={18} /></div>
          <strong>{api_metrics.p95_latency_ms} ms</strong>
          <small>objectif &lt; 200 ms</small>
        </article>
        <article className="metric-card">
          <div className="metric-card-top"><span>Statut Dérive (PSI)</span></div>
          <strong style={{ color: isDriftAlert ? 'var(--danger)' : 'var(--success)' }}>
            {ml_drift_monitoring.psi_score}
          </strong>
          <small>{ml_drift_monitoring.statut_derive}</small>
        </article>
      </section>

      <section className="dashboard-lower">
        <article className="overview-panel">
          <div className="panel-heading">
            <div><span className="section-kicker">MODÈLE ML</span><h2>Monitoring de dérive</h2></div>
          </div>
          <div className="signal-content" style={{ marginTop: '2rem' }}>
            <div className={`signal-disclaimer ${isDriftAlert ? 'claim-summary-error' : ''}`} style={{ borderLeftColor: isDriftAlert ? 'var(--red)' : 'var(--success)' }}>
              {isDriftAlert ? <AlertTriangle size={18} /> : <CheckCircle2 size={18} />}
              <span style={{ marginLeft: '8px' }}>
                {isDriftAlert 
                  ? "Alerte : La distribution des données a changé de manière significative. Un réentraînement est recommandé." 
                  : "Le modèle est stable. Aucune dérive majeure détectée sur les dernières 24h."}
              </span>
            </div>
            <div style={{ marginTop: '2rem', display: 'flex', gap: '2rem' }}>
              <div>
                <span className="section-kicker">PSI SCORE</span>
                <strong style={{ fontSize: '2rem', display: 'block' }}>{ml_drift_monitoring.psi_score}</strong>
                <small className="claim-hint">&lt; 0.10 = Stable</small>
              </div>
              <div>
                <span className="section-kicker">STATUT</span>
                <strong style={{ fontSize: '1.2rem', display: 'block', marginTop: '0.5rem' }}>{ml_drift_monitoring.statut_derive}</strong>
              </div>
            </div>
          </div>
        </article>
      </section>
    </div>
  )
}