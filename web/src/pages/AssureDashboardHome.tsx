// web/src/pages/AssureDashboardHome.tsx
import { useAuth } from '@/auth/AuthContext'
import { FileHeart, MessageSquare, ShieldCheck } from 'lucide-react'
import { Link } from 'react-router-dom'

export function AssureDashboardHome() {
  const { user } = useAuth()
  return (
    <div className="dashboard-page">
      <header className="page-heading">
        <div>
          <p className="eyebrow">ESPACE ASSURÉ</p>
          <h1>Suivi de votre couverture</h1>
          <p className="page-subtitle">Bonjour {user?.display_name}, voici un résumé de votre dossier.</p>
        </div>
      </header>
      <section className="metric-grid">
        <article className="metric-card">
          <div className="metric-card-top"><span>Mes dossiers</span><FileHeart size={18} /></div>
          <strong><Link to="/assure" style={{ color: 'var(--green)' }}>Consulter</Link></strong>
          <small>Voir l'historique de vos soins</small>
        </article>
        <article className="metric-card">
          <div className="metric-card-top"><span>Assistant PrediCare</span><MessageSquare size={18} /></div>
          <strong><Link to="/assure/chat" style={{ color: 'var(--green)' }}>Discuter</Link></strong>
          <small>Posez vos questions sur vos garanties</small>
        </article>
        <article className="metric-card">
          <div className="metric-card-top"><span>Ma couverture</span><ShieldCheck size={18} /></div>
          <strong>Active</strong>
          <small>Contrat en cours de validité</small>
        </article>
      </section>
    </div>
  )
}