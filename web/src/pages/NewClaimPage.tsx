// web/src/pages/NewClaimPage.tsx
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, ArrowRight, ShieldCheck } from 'lucide-react'
import { ClaimForm } from '@/features/claims/ClaimForm'
import { getStoredSession } from '@/api/session'

export function NewClaimPage() {
  const navigate = useNavigate()
  return (
    <div className="claim-page">
      <button
        className="claim-back"
        type="button"
        onClick={() => navigate('/app')}
      >
        <ArrowLeft aria-hidden="true" size={16} /> Retour à la vue d’ensemble
      </button>
      <ClaimForm profile="gestionnaire" />
    </div>
  )
}

export function NewProClaimPage() {
  const navigate = useNavigate()
  const session = getStoredSession()
  const providerId = session?.user?.prestataire_id ?? undefined
  return (
    <div className="claim-page">
      <button
        className="claim-back"
        type="button"
        onClick={() => navigate('/app')}
      >
        <ArrowLeft aria-hidden="true" size={16} /> Retour à la vue d’ensemble
      </button>
      <ClaimForm profile="professionnel_sante" providerId={providerId} />
    </div>
  )
}

export function ClaimReceiptPage() {
  const { claimId = '' } = useParams()
  const navigate = useNavigate()
  return (
    <section className="claim-receipt" aria-live="polite">
      <span className="claim-heading-icon">
        <ShieldCheck aria-hidden="true" size={20} />
      </span>
      <h1>Facture enregistrée</h1>
      <p>
        Le dossier <strong>{claimId}</strong> a été transmis. Son résultat
        explicable sera affiché ici.
      </p>
      <button
        className="claim-submit"
        type="button"
        onClick={() => navigate('/professionnel-sante/factures/nouvelle')}
      >
        Créer une autre facture
        <ArrowRight aria-hidden="true" size={17} />
      </button>
    </section>
  )
}
