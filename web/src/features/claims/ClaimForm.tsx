// web/src/features/claims/ClaimForm.tsx
import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Plus, ReceiptText, ShieldCheck, Trash2 } from 'lucide-react'
import { createClaim, getAssureCoverage, type AssureCoverage } from '@/api/claims'
import {
  type ClaimCreateRequest,
  type ClaimDraft,
  type ClaimLineType,
  type DraftLine,
  type ManagerClaimIntake,
} from '@/api/types'
import {
  claimChannels,
  claimChannelLabels,
  claimLineTypes,
  claimLineTypeLabels,
  demoMemberId,
  settlementMethods,
  settlementMethodLabels,
  tariffReferences,
} from '@/lib/config'
import {
  makeClaimPayload,
  mapValidationIssues,
  validateClaimDraft,
  type ClaimFieldErrors,
} from '@/lib/claimValidation'
import { UploadParser } from './UploadParser'
import {
  applyFactureToDraft,
  applyOrdonnanceToDraft,
  type ParsedDocument,
} from '@/lib/pdfParser'

export type ClaimFormProfile = 'gestionnaire' | 'professionnel_sante'

interface ClaimFormProps {
  profile: ClaimFormProfile
  providerId?: string
}

const formatMGA = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 })
const blankLine = (): DraftLine => ({
  type_ligne: 'ACTE',
  code: '',
  quantite: '1',
  prix_unitaire: '',
})

function initialDraft(profile: ClaimFormProfile, providerId?: string): ClaimDraft {
  return {
    numero_facture: '',
    prestataire_id:
      profile === 'professionnel_sante' ? providerId ?? '' : '',
    assure_id: demoMemberId,
    ordonnance_id: '',
    date_soin: '',
    date_emission: '',
    date_reception: '',
    canal_reception:
      profile === 'professionnel_sante' ? 'PORTAIL_PRESTATAIRE' : 'EMAIL',
    mode_reglement: 'TIERS_PAYANT',
    part_assure: '',
    patient_nom: '',
    attestation_pec: '',
    lines: [blankLine()],
  }
}

function tariffNote(code: string): string | undefined {
  const tariff = tariffReferences.find(
    (item) => item.code === code.trim().toUpperCase(),
  )
  if (!tariff) return undefined
  return [
    tariff.description,
    tariff.requiresPriorApproval ? 'Entente préalable requise' : '',
    tariff.reimbursable === false ? 'Non remboursable dans le barème simulé' : '',
  ]
    .filter(Boolean)
    .join(' · ')
}

export function ClaimForm({ profile, providerId }: ClaimFormProps) {
  const [draft, setDraft] = useState(() => initialDraft(profile, providerId))
  const [errors, setErrors] = useState<ClaimFieldErrors>({})
  const [summary, setSummary] = useState('')
  const [failed, setFailed] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const [factureParsed, setFactureParsed] = useState<ParsedDocument | null>(null)
  const [ordonnanceParsed, setOrdonnanceParsed] = useState<ParsedDocument | null>(null)

  const navigate = useNavigate()
  const isManager = profile === 'gestionnaire'
  const total = useMemo(
    () =>
      draft.lines.reduce(
        (sum, line) =>
          sum + Number(line.quantite || 0) * Number(line.prix_unitaire || 0),
        0,
      ),
    [draft.lines],
  )

  function setField<K extends keyof Omit<ClaimDraft, 'lines'>>(
    field: K,
    value: ClaimDraft[K],
  ) {
    setDraft((current) => ({ ...current, [field]: value }))
    setErrors((current) => ({ ...current, [field]: [] }))
    setSummary('')
  }

  function setLine(index: number, field: keyof DraftLine, value: string) {
    setDraft((current) => ({
      ...current,
      lines: current.lines.map((line, lineIndex) => {
        if (lineIndex !== index) return line
        if (field === 'code') {
          const tariff = tariffReferences.find(
            (item) => item.code === value.trim().toUpperCase(),
          )
          return {
            ...line,
            code: value,
            prix_unitaire:
              tariff?.unitPriceMGA === undefined
                ? line.prix_unitaire
                : String(tariff.unitPriceMGA),
          }
        }
        return { ...line, [field]: value }
      }),
    }))
    setErrors((current) => ({ ...current, [`lines.${index}.${field}`]: [] }))
    setSummary('')
  }

  const [coverage, setCoverage] = useState<AssureCoverage | null>(null)
  const [loadingCoverage, setLoadingCoverage] = useState(false)

  // Chargement de la formule et garanties réelles depuis l'API quand l'assure_id change
  useEffect(() => {
    const aid = draft.assure_id?.trim()
    if (!aid) {
      setCoverage(null)
      return
    }
    let active = true
    setLoadingCoverage(true)
    getAssureCoverage(aid)
      .then((cov) => {
        if (active) {
          setCoverage(cov)
          const part = Math.max(0, Math.round(total * cov.taux_part_assure + cov.franchise))
          setDraft((curr) => ({
            ...curr,
            part_assure: String(part),
            patient_nom: curr.patient_nom || cov.nom_patient || '',
          }))
        }
      })
      .catch(() => {
        if (active) setCoverage(null)
      })
      .finally(() => {
        if (active) setLoadingCoverage(false)
      })

    return () => {
      active = false
    }
  }, [draft.assure_id])

  // Recalcul automatique de la part assuré lorsque le total de la facture évolue
  useEffect(() => {
    if (coverage) {
      const part = Math.max(0, Math.round(total * coverage.taux_part_assure + coverage.franchise))
      setDraft((curr) => {
        if (curr.part_assure === String(part)) return curr
        return { ...curr, part_assure: String(part) }
      })
    }
  }, [total, coverage])

  function handleFactureParsed(doc: ParsedDocument) {
    setFactureParsed(doc)
    if (doc.kind === 'FACTURE') {
      const nextDraft = applyFactureToDraft(doc, draft, providerId)
      const nextTotal = nextDraft.lines.reduce(
        (sum, line) => sum + Number(line.quantite || 0) * Number(line.prix_unitaire || 0),
        0,
      )
      setDraft(nextDraft)
      setSummary('')
      setFailed(false)

      const targetAssureId = nextDraft.assure_id?.trim()
      if (targetAssureId) {
        setLoadingCoverage(true)
        getAssureCoverage(targetAssureId)
          .then((cov) => {
            setCoverage(cov)
            const part = Math.max(0, Math.round(nextTotal * cov.taux_part_assure + cov.franchise))
            setDraft((curr) => ({
              ...curr,
              part_assure: String(part),
              patient_nom: curr.patient_nom || cov.nom_patient || '',
            }))
          })
          .catch(() => {
            setCoverage(null)
          })
          .finally(() => {
            setLoadingCoverage(false)
          })
      }
    }
  }

function handleOrdonnanceParsed(doc: ParsedDocument) {
  setOrdonnanceParsed(doc)
  if (doc.kind === 'ORDONNANCE') {
    setDraft((current) => applyOrdonnanceToDraft(doc, current))
    setSummary('')
    setFailed(false)
  }
}

function clearFacture() {
  setFactureParsed(null)
}

function clearOrdonnance() {
  setOrdonnanceParsed(null)
}

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSummary('')
    setFailed(false)

    

    // 2. Validation champs facture
    const nextErrors = validateClaimDraft(draft, profile)
    setErrors(nextErrors)
    if (Object.values(nextErrors).some((messages) => messages.length)) {
      setSummary(
        'La facture contient des erreurs. Corrigez les champs signalés puis réessayez.',
      )
      document.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus()
      return
    }

    setSubmitting(true)
    const body = makeClaimPayload(draft)
    const payload: ClaimCreateRequest | ManagerClaimIntake = isManager
      ? {
          ...body,
          date_reception: draft.date_reception,
          canal_reception: (draft.canal_reception ||
            'EMAIL') as Exclude<
            ClaimDraft['canal_reception'],
            'PORTAIL_PRESTATAIRE' | ''
          >,
          mode_reglement: draft.mode_reglement,
        }
      : body

    void createClaim(payload)
      .then((created) => {
        // Redirection dynamique selon le profil
        if (profile === 'professionnel_sante') {
          navigate(`/professionnel-sante/factures/${encodeURIComponent(created.facture_id)}`)
        } else {
          navigate(`/gestionnaire/dossiers/${encodeURIComponent(created.facture_id)}`)
        }
      })
      .catch((error: unknown) => {
        const apiError =
          error instanceof Error ? error : new Error('Une erreur inattendue est survenue.')
        const issues =
          'validationIssues' in apiError && Array.isArray(apiError.validationIssues)
            ? apiError.validationIssues
            : []
        setFailed(true)
        if (issues.length) setErrors(mapValidationIssues(issues))
        setSummary(
          issues.length
            ? apiError.message
            : apiError.message ||
                'La facture n’a pas pu être envoyée. Vérifiez votre connexion puis réessayez.',
        )
      })
      .finally(() => setSubmitting(false))
  }

  function input(
    field: keyof Omit<
      ClaimDraft,
      'lines' | 'canal_reception' | 'mode_reglement'
    >,
    label: string,
    hint?: string,
    locked = false,
  ) {
    const fieldErrors = errors[field] ?? []
    const dateField =
      field === 'date_soin' ||
      field === 'date_emission' ||
      field === 'date_reception'
    return (
      <div className="claim-field" key={field}>
        <label htmlFor={field}>
          {label}
          {field !== 'ordonnance_id' && <span aria-hidden="true"> *</span>}
        </label>
        <input
          id={field}
          value={
            field === 'part_assure' && draft[field]
              ? formatMGA.format(Number(draft[field]))
              : draft[field]
          }
          onChange={(event) =>
            setField(
              field,
              field === 'part_assure'
                ? event.target.value.replace(/\D/g, '')
                : event.target.value,
            )
          }
          disabled={locked}
          required={field !== 'ordonnance_id'}
          inputMode={field === 'part_assure' ? 'numeric' : undefined}
          placeholder={dateField ? 'AAAA-MM-JJ' : undefined}
          pattern={dateField ? '\\d{4}-\\d{2}-\\d{2}' : undefined}
          aria-invalid={fieldErrors.length > 0}
          aria-describedby={
            fieldErrors.length
              ? `${field}-error`
              : hint
                ? `${field}-hint`
                : undefined
          }
        />
        {hint && (
          <small id={`${field}-hint`} className="claim-hint">
            {hint}
          </small>
        )}
        {fieldErrors.length > 0 && (
          <span id={`${field}-error`} className="claim-field-error">
            {fieldErrors.join(' ')}
          </span>
        )}
      </div>
    )
  }

  return (
    <div className="claim-page">
      <header className="claim-page-heading">
        <div>
          <span className="claim-heading-icon">
            <ReceiptText aria-hidden="true" size={20} />
          </span>
          <div>
            <p className="claim-kicker">GESTION DES REMBOURSEMENTS</p>
            <h1>
              {isManager
                ? 'Enregistrer une facture reçue'
                : 'Nouvelle facture'}
            </h1>
            <p>
              Complétez le bordereau ; les montants sont affichés en ariary.
            </p>
          </div>
        </div>
        <span className="synthetic-note">
          <ShieldCheck aria-hidden="true" size={15} /> Identifiants pseudonymisés
        </span>
      </header>

      {summary && (
        <div
          className={`claim-summary ${failed ? 'claim-summary-error' : ''}`}
          role="alert"
          aria-live="assertive"
        >
          <strong>{failed ? 'Envoi impossible' : 'À corriger'}</strong>
          <span>{summary}</span>
        </div>
      )}

      <form className="claim-form" onSubmit={submit} noValidate>
        <section className="claim-section" aria-labelledby="claim-upload-title">
          <div className="claim-section-heading">
            <span className="claim-section-index">01</span>
            <div>
              <h2 id="claim-upload-title">Import automatique (optionnel)</h2>
              <p>
                Glissez une facture ou une ordonnance PDF pour <strong>pré-remplir</strong>{' '}
                automatiquement les champs ci-dessus. Vous pourrez ensuite les corriger.
              </p>
            </div>
          </div>
          <div className="justif-grid">
            <UploadParser
              label="Facture (PDF)"
              accept="FACTURE"
              onParsed={handleFactureParsed}
              onClear={clearFacture}
              parsedSummary={
                factureParsed?.kind === 'FACTURE'
                  ? `Facture ${factureParsed.numero_facture || '—'} — ${factureParsed.lignes.length} ligne(s) extraite(s)`
                  : null
              }
              warnings={factureParsed?.kind === 'FACTURE' ? factureParsed.warnings : []}
            />
            <UploadParser
              label="Ordonnance (PDF)"
              accept="ORDONNANCE"
              onParsed={handleOrdonnanceParsed}
              onClear={clearOrdonnance}
              parsedSummary={
                ordonnanceParsed?.kind === 'ORDONNANCE'
                  ? `Ordonnance ${ordonnanceParsed.numero_ordonnance || '—'} — ${ordonnanceParsed.lignes.length} ligne(s) extraite(s)`
                  : null
              }
              warnings={
                ordonnanceParsed?.kind === 'ORDONNANCE' ? ordonnanceParsed.warnings : []
              }
            />
          </div>
        </section>
        <section className="claim-section" aria-labelledby="claim-header-title">
          <div className="claim-section-heading">
            <span className="claim-section-index">02</span>
            <div>
              <h2 id="claim-header-title">Informations de la facture</h2>
              <p>Références pseudonymisées et dates indiquées dans le bordereau.</p>
            </div>
          </div>
          <div className="claim-fields-grid">
            {input('numero_facture', 'Numéro de facture', 'Ex. F-2026-09871')}
            {input(
              'prestataire_id',
              'Identifiant du prestataire',
              'Identifiant pseudonyme uniquement.',
              profile === 'professionnel_sante',
            )}
            {input('assure_id', 'Identifiant de l’assuré', 'Aucune donnée nominative.', false)}
            {input('patient_nom', 'Nom du patient', 'Extrait du PDF, à vérifier.', false)}
            {input('attestation_pec', 'Attestation PEC', 'Numéro APC extrait du PDF.')}
            {input('ordonnance_id', 'Identifiant de l’ordonnance')}
            {input('date_soin', 'Date de soin')}
            {input('date_emission', 'Date d’émission')}
            {input(
              'part_assure',
              'Part de l’assuré (MGA)',
              coverage
                ? `Calculée automatiquement : ${Math.round(coverage.taux_part_assure * 100)}% du montant total${coverage.franchise > 0 ? ` + franchise ${coverage.franchise} Ar` : ''}.`
                : 'Calculée automatiquement selon la formule de l’assuré.',
            )}
            <div className="claim-field">
              <label>Formule de l'assuré (auto)</label>
              <input
                value={
                  loadingCoverage
                    ? 'Chargement de la formule…'
                    : coverage
                    ? coverage.formule
                    : 'Formule non identifiée'
                }
                readOnly
                disabled
                style={{
                  background: 'var(--surface-soft)',
                  color: coverage ? 'var(--ink)' : 'var(--ink-muted)',
                  fontWeight: 600,
                }}
              />
              <small className="claim-hint">
                {loadingCoverage
                  ? 'Interrogation de la table garanties en cours…'
                  : coverage
                  ? `Contrat ${coverage.contrat_id} (${coverage.statut_contrat}) · Prise en charge : ${Math.round(coverage.taux_prise_en_charge * 100)}% · Part assuré : ${Math.round(coverage.taux_part_assure * 100)}%`
                  : 'Saisissez ou importez un assuré pour charger sa formule.'}
              </small>
            </div>
            {isManager && input('date_reception', 'Date de réception')}
            {isManager && (
              <div className="claim-field">
                <label htmlFor="canal_reception">
                  Canal de réception <span aria-hidden="true">*</span>
                </label>
                <select
                  id="canal_reception"
                  value={draft.canal_reception}
                  onChange={(event) =>
                    setField(
                      'canal_reception',
                      event.target.value as ClaimDraft['canal_reception'],
                    )
                  }
                  aria-invalid={(errors.canal_reception ?? []).length > 0}
                >
                  {claimChannels
                    .filter((c) => c !== 'PORTAIL_PRESTATAIRE')
                    .map((c) => (
                      <option value={c} key={c}>
                        {claimChannelLabels[c]}
                      </option>
                    ))}
                </select>
              </div>
            )}
            {!isManager && (
              <div className="claim-field">
                <label htmlFor="canal_reception">Canal de réception</label>
                <input
                  id="canal_reception"
                  value={claimChannelLabels.PORTAIL_PRESTATAIRE}
                  readOnly
                  disabled
                />
              </div>
            )}
            <div className="claim-field">
              <label htmlFor="mode_reglement">
                Mode de règlement <span aria-hidden="true">*</span>
              </label>
              <select
                id="mode_reglement"
                value={draft.mode_reglement}
                onChange={(event) =>
                  setField(
                    'mode_reglement',
                    event.target.value as ClaimDraft['mode_reglement'],
                  )
                }
              >
                {settlementMethods.map((mode) => (
                  <option value={mode} key={mode}>
                    {settlementMethodLabels[mode]}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </section>

        <section className="claim-section" aria-labelledby="claim-lines-title">
          <div className="claim-section-heading claim-lines-heading">
            <span className="claim-section-index">03</span>
            <div>
              <h2 id="claim-lines-title">Lignes de la facture</h2>
              <p>
                Le montant de chaque ligne et le total sont calculés à partir de la
                quantité et du prix unitaire.
              </p>
            </div>
            <button
              type="button"
              className="add-claim-line"
              onClick={() =>
                setDraft((current) => ({
                  ...current,
                  lines: [...current.lines, blankLine()],
                }))
              }
            >
              <Plus aria-hidden="true" size={16} />
              <span>Ajouter une ligne</span>
            </button>
          </div>

          {(errors.lines ?? []).map((message) => (
            <p className="claim-field-error" role="alert" key={message}>
              {message}
            </p>
          ))}

          <datalist id="tariff-codes">
            {tariffReferences.map((item) => (
              <option key={item.code} value={item.code}>
                {item.description}
              </option>
            ))}
          </datalist>

          <div className="claim-line-list">
            {draft.lines.map((line, index) => {
              const lineError = (field: keyof DraftLine) =>
                errors[`lines.${index}.${field}`] ?? []
              const field = (
                key: keyof DraftLine,
                label: string,
                value: string,
                update: (v: string) => void,
                type = 'text',
              ) => (
                <div className="claim-field">
                  <label htmlFor={`line-${index}-${key}`}>
                    {label} <span aria-hidden="true">*</span>
                  </label>
                  <input
                    id={`line-${index}-${key}`}
                    type={type}
                    min={key === 'quantite' ? 1 : undefined}
                    step={key === 'quantite' ? 1 : undefined}
                    inputMode={
                      key === 'quantite' || key === 'prix_unitaire'
                        ? 'numeric'
                        : undefined
                    }
                    value={value}
                    onChange={(event) => update(event.target.value)}
                    aria-invalid={lineError(key).length > 0}
                  />
                  {lineError(key).length > 0 && (
                    <span className="claim-field-error">
                      {lineError(key).join(' ')}
                    </span>
                  )}
                </div>
              )
              return (
                <fieldset className="claim-line" key={index}>
                  <legend>Ligne {index + 1}</legend>
                  <div className="claim-line-fields">
                    <div className="claim-field">
                      <label htmlFor={`line-${index}-type_ligne`}>
                        Type <span aria-hidden="true">*</span>
                      </label>
                      <select
                        id={`line-${index}-type_ligne`}
                        value={line.type_ligne}
                        onChange={(event) =>
                          setLine(
                            index,
                            'type_ligne',
                            event.target.value as ClaimLineType,
                          )
                        }
                      >
                        {claimLineTypes.map((type) => (
                          <option value={type} key={type}>
                            {claimLineTypeLabels[type]}
                          </option>
                        ))}
                      </select>
                    </div>
                    {field('code', 'Code', line.code, (value) =>
                      setLine(index, 'code', value),
                    )}
                    {field(
                      'quantite',
                      'Quantité',
                      line.quantite,
                      (value) => setLine(index, 'quantite', value),
                      'number',
                    )}
                    {field(
                      'prix_unitaire',
                      'Prix unitaire (MGA)',
                      line.prix_unitaire
                        ? formatMGA.format(Number(line.prix_unitaire))
                        : '',
                      (value) =>
                        setLine(index, 'prix_unitaire', value.replace(/\D/g, '')),
                    )}
                    <div className="claim-line-amount">
                      <span>Montant ligne</span>
                      <strong>
                        {formatMGA.format(
                          Number(line.quantite || 0) *
                            Number(line.prix_unitaire || 0),
                        )}{' '}
                        MGA
                      </strong>
                    </div>
                    <button
                      type="button"
                      className="remove-claim-line"
                      aria-label={`Supprimer la ligne ${index + 1}`}
                      disabled={draft.lines.length === 1}
                      onClick={() => {
                        setDraft((current) => ({
                          ...current,
                          lines: current.lines.filter(
                            (_, itemIndex) => itemIndex !== index,
                          ),
                        }))
                        setSummary('')
                      }}
                    >
                      <Trash2 aria-hidden="true" size={17} />
                    </button>
                  </div>
                  {line.code && tariffNote(line.code) && (
                    <p className="claim-hint">{tariffNote(line.code)}</p>
                  )}
                </fieldset>
              )
            })}
          </div>

          <div className="claim-total">
            <span>Total de la facture</span>
            <strong>
              {formatMGA.format(total)} <small>MGA</small>
            </strong>
          </div>
        </section>

        <footer className="claim-form-footer">
          <p>
            {isManager
              ? 'Saisie de réception. Le contrat live ne permet actuellement la création que par le prestataire ou l’administrateur.'
              : 'La facture sera validée par l’API ; ses règles métier restent la source d’autorité.'}
          </p>
          <button className="claim-submit" type="submit" disabled={submitting}>
            {submitting ? 'Envoi en cours…' : 'Soumettre la facture'}
            <ArrowRight aria-hidden="true" size={17} />
          </button>
        </footer>
      </form>
    </div>
  )
}