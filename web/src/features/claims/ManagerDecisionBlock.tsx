import { useState, type FormEvent } from 'react'
import { useMutation } from '@tanstack/react-query'
import { CheckCircle2, CircleAlert, RotateCcw, Search, Send, Sparkles, XCircle } from 'lucide-react'
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

const DECISION_META: Record<ManagerDecision, { label: string; desc: string; icon: typeof CheckCircle2; colorClass: string }> = {
  VALIDE: {
    label: 'Valider',
    desc: 'Autoriser la prise en charge et le remboursement',
    icon: CheckCircle2,
    colorClass: 'decision-card--valide',
  },
  REJETE: {
    label: 'Rejeter',
    desc: 'Refuser la prise en charge pour non-conformité',
    icon: XCircle,
    colorClass: 'decision-card--rejete',
  },
  INVESTIGATION: {
    label: 'Demander un examen',
    desc: 'Transmettre pour contrôle médical ou pièces requises',
    icon: Search,
    colorClass: 'decision-card--investigation',
  },
}

const PRESET_MOTIFS: Record<ManagerDecision, string[]> = {
  VALIDE: [
    'Facture conforme aux barèmes conventionnels',
    'Justificatifs complets et validés',
    'Prise en charge validée selon contrat',
  ],
  REJETE: [
    'Dépassement tarifaire non conventionné',
    'Absence de prescription médicale valide',
    'Prestation hors période de couverture',
  ],
  INVESTIGATION: [
    'Demande de pièces justificatives originales',
    'Avis médical complémentaire requis',
    'Suspicion de surfacturation à auditer',
  ],
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
          <div className="decision-record-icon">
            <CheckCircle2 aria-hidden="true" size={24} />
          </div>
          <div className="decision-record-body">
            <div className="decision-record-header">
              <span className={`decision-status-pill decision-status-pill--${recorded.decision.toLowerCase()}`}>
                {managerDecisionLabels[recorded.decision]}
              </span>
              <span className="decision-record-statut">
                Statut : <strong>{claimStatusLabels[recorded.statut]}</strong>
              </span>
            </div>
            <p className="decision-record-meta">
              Enregistrée le <strong>{recorded.date_decision}</strong> par le gestionnaire <strong>{recorded.gestionnaire_id}</strong>
            </p>
            <p className="decision-record-motif">
              <span>Motif :</span> {motif.trim()}
            </p>
          </div>
        </div>
        <p className="fiche-note">
          La décision a été transmise et archivée dans le journal d’audit du système.
        </p>
      </section>
    )
  }

  return (
    <section className="claim-section" aria-labelledby="fiche-decision-title">
      <div className="claim-section-heading">
        <div>
          <h2 id="fiche-decision-title">Décision du gestionnaire</h2>
          <p>Revue humaine obligatoire. L’API enregistre l’auteur, l’horodatage et la motivation de la décision.</p>
        </div>
      </div>

      {errors.root && (
        <div className="decision-error-banner" role="alert">
          <CircleAlert aria-hidden="true" size={18} />
          <div>
            <strong>Décision refusée par l’API</strong>
            <span>{errors.root}</span>
          </div>
        </div>
      )}

      <form className="decision-form" onSubmit={prepare} noValidate>
        <div className="decision-cards-group">
          <span className="decision-group-label">Choisir l’orientation du dossier</span>
          <div className="decision-cards-grid" role="radiogroup" aria-label="Orientation de la décision">
            {managerDecisions.map((value) => {
              const meta = DECISION_META[value]
              const Icon = meta.icon
              const isSelected = decision === value
              return (
                <button
                  key={value}
                  type="button"
                  role="radio"
                  aria-checked={isSelected}
                  className={`decision-option-card ${meta.colorClass} ${isSelected ? 'decision-option-card--active' : ''}`}
                  onClick={() => {
                    setDecision(value)
                    setErrors({})
                  }}
                >
                  <div className="decision-option-icon">
                    <Icon size={20} aria-hidden="true" />
                  </div>
                  <div className="decision-option-content">
                    <strong className="decision-option-title">{meta.label}</strong>
                    <span className="decision-option-desc">{meta.desc}</span>
                  </div>
                  <div className={`decision-option-radio ${isSelected ? 'decision-option-radio--checked' : ''}`}>
                    {isSelected && <span className="decision-option-radio-dot" />}
                  </div>
                </button>
              )
            })}
          </div>
        </div>

        <div className="decision-inputs-grid">
          <div className="decision-field">
            <div className="decision-field-header">
              <label htmlFor="decision-montant" className="decision-field-label">
                Montant accordé (MGA) <span className="required-star" aria-hidden="true">*</span>
              </label>
              <div className="decision-field-quick-actions">
                <button
                  type="button"
                  className="decision-quick-btn"
                  onClick={() => {
                    setMontantAccorde(String(montantDemande))
                    setErrors((cur) => ({ ...cur, montant_accorde: undefined, root: undefined }))
                  }}
                >
                  <Sparkles size={12} aria-hidden="true" />
                  <span>Demande totale ({formatMGA.format(montantDemande)} MGA)</span>
                </button>
                {decision === 'REJETE' && (
                  <button
                    type="button"
                    className="decision-quick-btn"
                    onClick={() => {
                      setMontantAccorde('0')
                      setErrors((cur) => ({ ...cur, montant_accorde: undefined, root: undefined }))
                    }}
                  >
                    0 MGA
                  </button>
                )}
              </div>
            </div>

            <div className="decision-amount-input-wrap">
              <input
                id="decision-montant"
                className={`decision-input ${errors.montant_accorde ? 'decision-input--error' : ''}`}
                inputMode="numeric"
                placeholder="Ex. 450 000"
                value={montantAccorde ? formatMGA.format(Number(montantAccorde)) : ''}
                onChange={(event) => {
                  setMontantAccorde(event.target.value.replace(/\D/g, ''))
                  setErrors((current) => ({ ...current, montant_accorde: undefined, root: undefined }))
                }}
                aria-invalid={Boolean(errors.montant_accorde)}
                aria-describedby={errors.montant_accorde ? 'decision-montant-error' : 'decision-montant-hint'}
              />
              <span className="decision-currency-tag" aria-hidden="true">MGA</span>
            </div>

            <small id="decision-montant-hint" className="decision-hint">
              Montant demandé transmis par la facture : <strong><Money amount={montantDemande} /></strong>
            </small>
            {errors.montant_accorde && (
              <span id="decision-montant-error" className="decision-error-message">
                {errors.montant_accorde}
              </span>
            )}
          </div>

          <div className="decision-field">
            <div className="decision-field-header">
              <label htmlFor="decision-motif" className="decision-field-label">
                Motif de la décision <span className="required-star" aria-hidden="true">*</span>
              </label>
            </div>

            <div className="decision-preset-chips" aria-label="Suggestions de motifs">
              {PRESET_MOTIFS[decision].map((chip) => (
                <button
                  key={chip}
                  type="button"
                  className="decision-preset-chip"
                  onClick={() => {
                    setMotif(chip)
                    setErrors((cur) => ({ ...cur, motif: undefined, root: undefined }))
                  }}
                >
                  + {chip}
                </button>
              ))}
            </div>

            <textarea
              id="decision-motif"
              className={`decision-textarea ${errors.motif ? 'decision-input--error' : ''}`}
              rows={3}
              placeholder="Indiquez la justification détaillée de votre décision..."
              value={motif}
              onChange={(event) => {
                setMotif(event.target.value)
                setErrors((current) => ({ ...current, motif: undefined, root: undefined }))
              }}
              aria-invalid={Boolean(errors.motif)}
              aria-describedby={errors.motif ? 'decision-motif-error' : 'decision-motif-hint'}
            />
            <small id="decision-motif-hint" className="decision-hint">
              Exigé par l’API pour toute décision afin de garantir l’auditabilité.
            </small>
            {errors.motif && (
              <span id="decision-motif-error" className="decision-error-message">
                {errors.motif}
              </span>
            )}
          </div>
        </div>

        {confirming ? (
          <div className="decision-confirm-box" role="group" aria-label="Confirmation de la décision">
            <div className="decision-confirm-icon">
              <CircleAlert aria-hidden="true" size={22} />
            </div>
            <div className="decision-confirm-content">
              <strong>Confirmer la décision « {managerDecisionLabels[decision]} » ?</strong>
              <p>
                Montant alloué : <strong><Money amount={Number(montantAccorde)} /></strong> · Motif : « {motif.trim()} »
              </p>
              <small className="decision-confirm-warning">
                Cette décision sera définitivement enregistrée au nom du gestionnaire connecté.
              </small>
            </div>
            <div className="decision-confirm-actions">
              <button
                type="submit"
                className="decision-btn decision-btn--primary"
                disabled={mutation.isPending}
                onClick={confirm}
              >
                <Send aria-hidden="true" size={16} />
                <span>{mutation.isPending ? 'Enregistrement…' : 'Confirmer et enregistrer'}</span>
              </button>
              <button
                type="button"
                className="decision-btn decision-btn--secondary"
                onClick={() => setConfirming(false)}
                disabled={mutation.isPending}
              >
                <RotateCcw aria-hidden="true" size={15} />
                <span>Modifier</span>
              </button>
            </div>
          </div>
        ) : (
          <div className="decision-actions-row">
            <button type="submit" className="decision-btn decision-btn--primary">
              <Send aria-hidden="true" size={16} />
              <span>Valider la saisie de décision</span>
            </button>
          </div>
        )}
      </form>
    </section>
  )
}