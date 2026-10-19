// web/src/pages/ProDashboardPage.tsx
import { useAuth } from '@/auth/AuthContext'
import { FileText, Clock, CheckCircle2 } from 'lucide-react'

export function ProDashboardPage() {
  const { user } = useAuth()

  return (
    <div className="dashboard-page">
      <header className="page-heading">
        <div>
          <p className="eyebrow">2026-10-14 <span>·</span> ANTANANARIVO</p>
          <h1>Activité de votre établissement</h1>
          <p className="page-subtitle">Bonjour {user?.display_name}, voici un résumé de vos télétransmissions.</p>
        </div>
        <div className="live-indicator"><span /> Données de démonstration</div>
      </header>

      <section className="metric-grid">
        <article className="metric-card">
          <div className="metric-card-top"><span>Factures transmises</span><FileText size={18} /></div>
          <strong>—</strong>
          <small>ce mois-ci</small>
        </article>
        <article className="metric-card">
          <div className="metric-card-top"><span>En attente de traitement</span><Clock size={18} /></div>
          <strong>—</strong>
          <small>par l'assurance</small>
        </article>
        <article className="metric-card">
          <div className="metric-card-top"><span>Remboursements reçus</span><CheckCircle2 size={18} /></div>
          <strong>—</strong>
          <small>sur la période</small>
        </article>
        <article className="metric-card">
          <div className="metric-card-top"><span>Total facturé</span><FileText size={18} /></div>
          <strong>—</strong>
          <small>en MGA</small>
        </article>
      </section>
      
      <div style={{ marginTop: '2rem', padding: '2rem', background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: '12px', textAlign: 'center' }}>
        <p className="claim-hint">Utilisez le menu "Nouvelle facture" pour télétransmettre un nouveau dossier.</p>
      </div>
    </div>
  )
}
