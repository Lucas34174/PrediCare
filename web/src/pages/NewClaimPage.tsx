import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, ArrowRight, ShieldCheck } from 'lucide-react'
import { ClaimForm } from '@/features/claims/ClaimForm'

export function NewClaimPage() {
  const navigate = useNavigate()
  return <div className="claim-page"><button className="claim-back" type="button" onClick={() => navigate('/app')}><ArrowLeft aria-hidden="true" size={16} /> Retour à la vue d’ensemble</button><ClaimForm profile="gestionnaire" /></div>
}

export function ClaimReceiptPage() {
  const { claimId = '' } = useParams()
  const navigate = useNavigate()
  return (
    <section className="claim-receipt" aria-live="polite">
      <span className="claim-heading-icon"><ShieldCheck aria-hidden="true" size={20} /></span>
      <h1>Facture enregistrée</h1>
      <p>Le dossier <strong>{claimId}</strong> a été transmis. Son résultat explicable sera affiché ici.</p>
      <button className="claim-submit" type="button" onClick={() => navigate('/gestionnaire/factures/nouvelle')}>Créer une autre facture<ArrowRight aria-hidden="true" size={17} /></button>
    </section>
  )
}
