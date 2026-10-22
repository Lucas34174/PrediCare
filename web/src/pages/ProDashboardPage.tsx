// web/src/pages/ProDashboardPage.tsx
import { useQuery } from '@tanstack/react-query'
import { FileText, Clock, CheckCircle2, WalletCards } from 'lucide-react'
import { useAuth } from '@/auth/AuthContext'
import { request } from '@/api/request'

interface ProKpis {
  prestataire_id: string
  total_factures: number
  en_attente: number
  remboursements_recus: number
  total_facture_mga: number
  montant_rembourse_mga: number
}

const formatMGA = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 })
const today = new Date().toLocaleDateString('fr-FR', {
  year: 'numeric',
  month: 'long',
  day: 'numeric',
})

export function ProDashboardPage() {
  const { user } = useAuth()

  const { data: kpis, isLoading, isError } = useQuery<ProKpis>({
    queryKey: ['pro-kpis'],
    queryFn: () => request<ProKpis>('/dashboard/pro-kpis'),
    enabled: !!user,
    staleTime: 60_000,
  })

  const fmt = (n: number | undefined) =>
    n === undefined || isLoading ? '…' : formatMGA.format(n)

  const count = (n: number | undefined) =>
    n === undefined || isLoading ? '…' : n.toLocaleString('fr-FR')

  return (
    <div className="dashboard-page">
      <header className="page-heading">
        <div>
          <p className="eyebrow">
            {today} <span>·</span> Données en temps réel (PostgreSQL)
          </p>
          <h1>Activité de votre établissement</h1>
          <p className="page-subtitle">
            Bonjour {user?.display_name}, voici un résumé de vos télétransmissions.
          </p>
        </div>
        <div className="live-indicator">
          <span /> Données en direct
        </div>
      </header>

      {isError && (
        <div
          style={{
            padding: '1rem 1.5rem',
            background: 'var(--danger-soft, #fee2e2)',
            color: 'var(--danger, #dc2626)',
            borderRadius: '8px',
            marginBottom: '1.5rem',
            fontSize: '0.875rem',
          }}
        >
          Impossible de charger les données. Veuillez rafraîchir la page.
        </div>
      )}

      <section className="metric-grid">
        <article className="metric-card">
          <div className="metric-card-top">
            <span>Factures transmises</span>
            <FileText size={18} />
          </div>
          <strong>{count(kpis?.total_factures)}</strong>
          <small>au total</small>
        </article>

        <article className="metric-card">
          <div className="metric-card-top">
            <span>En attente de traitement</span>
            <Clock size={18} />
          </div>
          <strong>{count(kpis?.en_attente)}</strong>
          <small>par l'assurance</small>
        </article>

        <article className="metric-card">
          <div className="metric-card-top">
            <span>Remboursements reçus</span>
            <CheckCircle2 size={18} />
          </div>
          <strong>{count(kpis?.remboursements_recus)}</strong>
          <small>factures payées</small>
        </article>

        <article className="metric-card">
          <div className="metric-card-top">
            <span>Total facturé</span>
            <WalletCards size={18} />
          </div>
          <strong>{fmt(kpis?.total_facture_mga)}</strong>
          <small>en MGA</small>
        </article>
      </section>

      {kpis && (
        <div
          style={{
            marginTop: '1.5rem',
            padding: '1.25rem 1.5rem',
            background: 'var(--surface)',
            border: '1px solid var(--line)',
            borderRadius: '12px',
            fontSize: '0.875rem',
            color: 'var(--text-muted)',
          }}
        >
          💰 Montant remboursé :{' '}
          <strong style={{ color: 'var(--text)' }}>
            {fmt(kpis.montant_rembourse_mga)} MGA
          </strong>{' '}
          sur {fmt(kpis.total_facture_mga)} MGA facturés —{' '}
          Réf. prestataire : <code>{kpis.prestataire_id}</code>
        </div>
      )}

      {!kpis && !isLoading && !isError && (
        <div
          style={{
            marginTop: '2rem',
            padding: '2rem',
            background: 'var(--surface)',
            border: '1px solid var(--line)',
            borderRadius: '12px',
            textAlign: 'center',
          }}
        >
          <p className="claim-hint">
            Utilisez le menu "Nouvelle facture" pour télétransmettre un nouveau dossier.
          </p>
        </div>
      )}
    </div>
  )
}
