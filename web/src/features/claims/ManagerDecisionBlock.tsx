import { useState, type FormEvent } from 'react'
import { useMutation } from '@tanstack/react-query'
import { CheckCircle2, CircleAlert, RotateCcw, Send } from 'lucide-react'
import { saveManagerDecision } from '@/api/claims'
import type { DecisionRequest, DecisionResponse, ManagerDecision } from '@/api/types'
import { claimStatusLabels, managerDecisionLabels, managerDecisions } from '@/lib/config'
import { mapValidationIssues, rootValidationMessages } from '@/lib/claimValidation'
import { Money } from '@/components/Money'

const formatMGA = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 })

interface ManagerDecisionBlockProps {
  factureId: string
  /** Montant demandé transmis par l'API : affiché pour information, jamais appliqué d'office. */
  montantDemande: number
  onDecided?: () => void
}

interface DecisionErrors {
  motif?: string
  montant_accorde?: string
  root?: string
}

export function ManagerDecisionBlock({ factureId, montantDemande, onDecided }: ManagerDecisionBlockProps) {
  const [decision, setDecision] = useState<ManagerDecision>('VALIDE')
  const [motif, setMotif] = useState('')
  const [montantAccorde, setMontantAccorde] = useState('')
  const [errors, setErrors] = useState<DecisionErrors>({})
  const [confirming, setConfirming] = useState(false)
  const [recorded, setRecorded] = useState<DecisionResponse | null>(null)

  const mutation = useMutation({
    mutationFn: (payload: DecisionRequest) => saveManagerDecision(factureId, payload),
    onSuccess: (response) => {
      setRecorded(response)
      setConfirming(false)
      onDecided?.()
    },
    onError: (error: unknown) => {
      const issues = error instanceof Error && 'validationIssues' in error && Array.isArray(error.validationIssues)
        ? error.validationIssues
        : []
      const mapped = mapValidationIssues(issues)
      const [root] = rootValidationMessages(issues)
      setErrors({
        motif: mapped.motif?.[0],
        montant_accorde: mapped.montant_accorde?.[0],
        root: root ?? (issues.length === 0 && error instanceof Error ? error.message : undefined),
      })
      setConfirming(false)
    },
  })

  /** L'API exige un motif pour toute décision, favorable comprise (`motif` min_length=1). */
  function review(): DecisionErrors {
    const next: DecisionErrors = {}
    if (!motif.trim()) next.motif = 'Un motif est obligatoire, y compris pour une validation.'
    const amount = Number(montantAccorde)
    if (!montantAccorde.trim() || !Number.isInteger(amount) || amount < 0) {
      next.montant_accorde = 'Indiquez un montant entier positif ou nul, en ariary.'
    }
    return next
  }

  function prepare(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const next = review()
    if (next.motif || next.montant_accorde) {
      setErrors(next)
      return
    }
    setErrors({})
    setConfirming(true)
  }

  function confirm() {
    mutation.mutate({
      decision,
      motif: motif.trim(),
      montant_accorde: Number(montantAccorde),
    })
  }

  if (recorded) {
    return (
      <section className="claim-section" aria-labelledby="fiche-decision-title">
        <div className="claim-section-heading">
          <div>
            <h2 id="fiche-decision-title">Décision enregistrée</h2>
            <p>Cette décision est en lecture seule ; elle a été horodatée par l’API.</p>
          </div>
        </div>
        <div className="decision-record" role="status">
          <CheckCircle2 aria-hidden="true" size={20} />
          <div>
            <strong>{managerDecisionLabels[recorded.decision]}</strong>
            <p className="decision-record-meta">
              Statut du dossier : {claimStatusLabels[recorded.statut]} · Enregistrée le {recorded.date_decision} · Gestionnaire {recorded.gestionnaire_id}
            </p>
            <p className="decision-record-motif">Motif : {motif.trim()}</p>
          </div>
        </div>
        <p className="fiche-note">
          Aucun endpoint ne permet de relire une décision déjà enregistrée : cet affichage est reconstruit
          à partir de la réponse de l’API, à confirmer avec M2.
        </p>
      </section>
    )
  }

  return (
    <section className="claim-section" aria-labelledby="fiche-decision-title">
      <div className="claim-section-heading">
        <div>
          <h2 id="fiche-decision-title">Décision du gestionnaire</h2>
          <p>Aucune décision défavorable n’est prise sans cette revue humaine. L’API enregistre qui a décidé, quand et pourquoi.</p>
        </div>
      </div>

      {errors.root && (
        <div className="claim-summary claim-summary-error" role="alert">
          <strong>Décision refusée par l’API</strong>
          <span>{errors.root}</span>
        </div>
      )}

      <form className="decision-form" onSubmit={prepare} noValidate>
        <fieldset className="decision-choices">
          <legend>Décision</legend>
          {managerDecisions.map((value) => (
            <label key={value} className={decision === value ? 'decision-choice decision-choice-active' : 'decision-choice'}>
              <input
                type="radio"
                name="decision"
                value={value}
                checked={decision === value}
                onChange={() => { setDecision(value); setErrors({}) }}
              />
              <span>{managerDecisionLabels[value]}</span>
            </label>
          ))}
        </fieldset>

        <div className="decision-fields">
          <div className="claim-field">
            <label htmlFor="decision-motif">Motif de la décision <span aria-hidden="true">*</span></label>
            <textarea
              id="decision-motif"
              rows={3}
              value={motif}
              onChange={(event) => { setMotif(event.target.value); setErrors((current) => ({ ...current, motif: undefined, root: undefined })) }}
              aria-invalid={Boolean(errors.motif)}
              aria-describedby={errors.motif ? 'decision-motif-error' : 'decision-motif-hint'}
            />
            <small id="decision-motif-hint" className="claim-hint">Exigé par l’API pour toute décision, y compris une validation.</small>
            {errors.motif && <span id="decision-motif-error" className="claim-field-error">{errors.motif}</span>}
          </div>

          <div className="claim-field">
            <label htmlFor="decision-montant">Montant accordé (MGA) <span aria-hidden="true">*</span></label>
            <input
              id="decision-montant"
              inputMode="numeric"
              value={montantAccorde ? formatMGA.format(Number(montantAccorde)) : ''}
              onChange={(event) => { setMontantAccorde(event.target.value.replace(/\D/g, '')); setErrors((current) => ({ ...current, montant_accorde: undefined, root: undefined })) }}
              aria-invalid={Boolean(errors.montant_accorde)}
              aria-describedby={errors.montant_accorde ? 'decision-montant-error' : 'decision-montant-hint'}
            />
            <small id="decision-montant-hint" className="claim-hint">
              Montant demandé transmis : <Money amount={montantDemande} />. Ajustez-le, rien n’est prérempli.
            </small>
            {errors.montant_accorde && <span id="decision-montant-error" className="claim-field-error">{errors.montant_accorde}</span>}
          </div>
        </div>

        {confirming ? (
          <div className="decision-confirm" role="group" aria-label="Confirmation de la décision">
            <CircleAlert aria-hidden="true" size={18} />
            <div>
              <strong>Confirmer « {managerDecisionLabels[decision].toLowerCase()} » ?</strong>
              <p>Montant accordé : <Money amount={Number(montantAccorde)} />. Motif : {motif.trim()}</p>
              <p className="claim-hint">Cette décision sera enregistrée au nom du gestionnaire connecté et ne pourra plus être modifiée ici.</p>
            </div>
            <div className="decision-confirm-actions">
              <button type="submit" className="decision-submit" disabled={mutation.isPending} onClick={confirm}>
                <Send aria-hidden="true" size={16} /> {mutation.isPending ? 'Envoi…' : 'Confirmer la décision'}
              </button>
              <button type="button" className="decision-cancel" onClick={() => setConfirming(false)} disabled={mutation.isPending}>
                <RotateCcw aria-hidden="true" size={15} /> Revenir
              </button>
            </div>
          </div>
        ) : (
          <div className="decision-actions">
            <button type="submit" className="decision-submit">
              <Send aria-hidden="true" size={16} /> Continuer
            </button>
          </div>
        )}
      </form>
    </section>
  )
}