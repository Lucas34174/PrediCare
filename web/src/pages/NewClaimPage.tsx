import { useMemo, useState, type ChangeEvent, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, ArrowRight, Plus, ReceiptText, ShieldCheck, Trash2 } from 'lucide-react'
import { createClaim } from '@/api/claims'
import type { ClaimDraft, ClaimLineType, DraftLine } from '@/api/types'
import { demoContractId, demoMemberId, tariffReferences } from '@/lib/config'
import { makeClaimPayload, mapValidationIssues, validateClaimDraft, type ClaimFieldErrors } from '@/lib/claimValidation'

const moneyFormat = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 })
const newLine = (): DraftLine => ({ type: 'ACTE', code: '', quantite: '1', prix_unitaire: '' })
const initialDraft: ClaimDraft = {
  prestataire_id: '', assure_id: demoMemberId, contrat_id: demoContractId, ordonnance_id: '',
  date_soin: '', date_facture: '', date_reception: '', canal: '', mode_reglement: '',
  attestation_prise_en_charge: false, entente_prealable: false, lines: [newLine()],
}

function moneyInput(value: string): string {
  return value.replace(/\D/g, '')
}

function tariffHint(code: string): string | undefined {
  const tariff = tariffReferences.find((entry) => entry.code === code.trim().toUpperCase())
  if (!tariff) return undefined
  return [
    tariff.description,
    tariff.requiresPriorApproval ? 'Entente préalable requise' : '',
    tariff.reimbursable === false ? 'Non remboursable selon le barème simulé' : '',
  ].filter(Boolean).join(' · ')
}

export function NewClaimPage() {
  const [draft, setDraft] = useState<ClaimDraft>(() => structuredClone(initialDraft))
  const [errors, setErrors] = useState<ClaimFieldErrors>({})
  const [summary, setSummary] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submissionFailed, setSubmissionFailed] = useState(false)
  const navigate = useNavigate()

  const total = useMemo(() => draft.lines.reduce(
    (sum, line) => sum + (Number(line.quantite) || 0) * (Number(line.prix_unitaire) || 0), 0,
  ), [draft.lines])

  function updateField<K extends keyof Omit<ClaimDraft, 'lines'>>(
    field: K,
    value: ClaimDraft[K],
  ) {
    setDraft((current) => ({ ...current, [field]: value }))
    setErrors((current) => ({ ...current, [field]: [] }))
    setSummary('')
  }

  function updateLine(index: number, field: keyof DraftLine, value: string) {
    setDraft((current) => ({
      ...current,
      lines: current.lines.map((line, lineIndex) => {
        if (lineIndex !== index) return line
        if (field === 'code') {
          const tariff = tariffReferences.find((entry) => entry.code === value.trim().toUpperCase())
          return { ...line, code: value, prix_unitaire: tariff?.unitPriceMGA === undefined ? line.prix_unitaire : String(tariff.unitPriceMGA) }
        }
        return { ...line, [field]: value }
      }),
    }))
    setErrors((current) => ({ ...current, [`lines.${index}.${field}`]: [] }))
    setSummary('')
  }

  function handleTypeChange(index: number, event: ChangeEvent<HTMLSelectElement>) {
    updateLine(index, 'type', event.target.value as ClaimLineType)
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSummary('')
    setSubmissionFailed(false)
    const nextErrors = validateClaimDraft(draft)
    setErrors(nextErrors)
    if (Object.values(nextErrors).some((messages) => messages.length > 0)) {
      setSummary('La facture contient des erreurs. Corrigez les champs signalés puis réessayez.')
      document.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus()
      return
    }
    setSubmitting(true)
    try {
      const claim = await createClaim(makeClaimPayload(draft))
      navigate(`/gestionnaire/factures/${encodeURIComponent(claim.claim_id)}`)
    } catch (error) {
      const apiError = error instanceof Error ? error : new Error('Une erreur inattendue est survenue.')
      const validationIssues = 'validationIssues' in apiError && Array.isArray(apiError.validationIssues)
        ? apiError.validationIssues
        : []
      setSubmissionFailed(true)
      if (validationIssues.length) setErrors(mapValidationIssues(validationIssues))
      setSummary(validationIssues.length
        ? apiError.message
        : apiError.message || 'La facture n’a pas pu être envoyée. Vérifiez votre connexion puis réessayez.')
    } finally {
      setSubmitting(false)
    }
  }

  function fieldErrors(path: string): string[] {
    return errors[path] ?? []
  }

  function renderTextField(
    field: keyof Omit<ClaimDraft, 'lines' | 'attestation_prise_en_charge' | 'entente_prealable'>,
    label: string,
    placeholder: string,
    options: { type?: string; required?: boolean; hint?: string; pattern?: string } = {},
  ) {
    const messages = fieldErrors(field)
    return (
      <div className="claim-field">
        <label htmlFor={field}>{label}{options.required !== false && <span aria-hidden="true"> *</span>}</label>
        <input
          id={field}
          name={field}
          type={options.type ?? 'text'}
          placeholder={placeholder}
          value={draft[field]}
          onChange={(event) => updateField(field, event.target.value)}
          required={options.required !== false}
          pattern={options.pattern}
          aria-invalid={messages.length > 0}
          aria-describedby={messages.length ? `${field}-error` : options.hint ? `${field}-hint` : undefined}
          autoComplete="off"
        />
        {options.hint && <small id={`${field}-hint`} className="claim-hint">{options.hint}</small>}
        {messages.length > 0 && <span id={`${field}-error`} className="claim-field-error">{messages.join(' ')}</span>}
      </div>
    )
  }

  function removeLine(index: number) {
    setDraft((current) => ({ ...current, lines: current.lines.filter((_, lineIndex) => lineIndex !== index) }))
    setErrors((current) => Object.fromEntries(Object.entries(current).filter(([key]) => !key.startsWith('lines'))))
    setSummary('')
  }

  const lineErrors = fieldErrors('lines')

  return (
    <div className="claim-page">
      <button className="claim-back" type="button" onClick={() => navigate('/app')}><ArrowLeft aria-hidden="true" size={16} /> Retour à la vue d’ensemble</button>
      <header className="claim-page-heading">
        <div><span className="claim-heading-icon"><ReceiptText aria-hidden="true" size={20} /></span><div><p className="claim-kicker">GESTION DES REMBOURSEMENTS</p><h1>Nouvelle facture</h1><p>Renseignez les informations de soin pour obtenir une analyse explicable.</p></div></div>
        <span className="synthetic-note"><ShieldCheck aria-hidden="true" size={15} /> Données pseudonymisées</span>
      </header>

      {summary && <div className={`claim-summary ${submissionFailed ? 'claim-summary-error' : ''}`} role="alert" aria-live="assertive"><strong>{submissionFailed ? 'Envoi impossible' : 'À corriger'}</strong><span>{summary}</span></div>}

      <form className="claim-form" onSubmit={handleSubmit} noValidate>
        <section className="claim-section" aria-labelledby="claim-header-title">
          <div className="claim-section-heading"><span className="claim-section-index">01</span><div><h2 id="claim-header-title">Informations de la facture</h2><p>Identifiez le dossier et les dates associées au soin.</p></div></div>
          <div className="claim-fields-grid">
            {renderTextField('prestataire_id', 'Identifiant du prestataire', 'Ex. PRE-000124', { hint: 'Utilisez uniquement l’identifiant pseudonyme du prestataire.' })}
            {renderTextField('assure_id', 'Identifiant de l’assuré', 'ASS-XXXXXXXXXX', { pattern: 'ASS-[A-Z0-9]{10}', hint: 'Identifiant pseudonyme uniquement ; aucune donnée personnelle.' })}
            {renderTextField('contrat_id', 'Contrat', 'CTR-000048')}
            {renderTextField('ordonnance_id', 'Ordonnance', 'Référence de l’ordonnance')}
            {renderTextField('date_soin', 'Date de soin', 'AAAA-MM-JJ', { pattern: '\\d{4}-\\d{2}-\\d{2}' })}
            {renderTextField('date_facture', 'Date de facture', 'AAAA-MM-JJ', { pattern: '\\d{4}-\\d{2}-\\d{2}' })}
            {renderTextField('date_reception', 'Date de réception', 'AAAA-MM-JJ', { pattern: '\\d{4}-\\d{2}-\\d{2}' })}
            {renderTextField('canal', 'Canal', 'Saisir le canal', { hint: 'Valeurs à confirmer avec le dictionnaire backend.' })}
            {renderTextField('mode_reglement', 'Mode de règlement', 'Saisir le mode', { hint: 'Valeurs à confirmer avec le dictionnaire backend.' })}
          </div>
          <div className="claim-toggle-grid">
            <label className="claim-toggle"><input type="checkbox" checked={draft.attestation_prise_en_charge} onChange={(event) => updateField('attestation_prise_en_charge', event.target.checked)} /><span><strong>Attestation de prise en charge</strong><small>Attestation reçue pour ce dossier.</small></span></label>
            <label className="claim-toggle"><input type="checkbox" checked={draft.entente_prealable} onChange={(event) => updateField('entente_prealable', event.target.checked)} /><span><strong>Entente préalable</strong><small>Autorisation préalable obtenue, si nécessaire.</small></span></label>
          </div>
        </section>

        <section className="claim-section" aria-labelledby="claim-lines-title">
          <div className="claim-section-heading claim-lines-heading"><span className="claim-section-index">02</span><div><h2 id="claim-lines-title">Lignes de la facture</h2><p>Les montants sont calculés à partir des quantités et prix indiqués.</p></div><button type="button" className="add-claim-line" onClick={() => setDraft((current) => ({ ...current, lines: [...current.lines, newLine()] }))}><Plus aria-hidden="true" size={16} /><span>Ajouter une ligne</span></button></div>
          {lineErrors.map((message) => <p className="claim-field-error" role="alert" key={message}>{message}</p>)}
          <datalist id="tariff-codes">{tariffReferences.map((tariff) => <option key={tariff.code} value={tariff.code}>{tariff.description}</option>)}</datalist>
          <div className="claim-line-list">
            {draft.lines.map((line, index) => (
              <fieldset className="claim-line" key={index}>
                <legend>Ligne {index + 1}</legend>
                <div className="claim-line-fields">
                  <div className="claim-field"><label htmlFor={`line-${index}-type`}>Type <span aria-hidden="true">*</span></label><select id={`line-${index}-type`} value={line.type} onChange={(event) => handleTypeChange(index, event)} aria-invalid={fieldErrors(`lines.${index}.type`).length > 0} aria-describedby={fieldErrors(`lines.${index}.type`).length ? `line-${index}-type-error` : undefined}><option value="ACTE">Acte</option><option value="MEDICAMENT">Médicament</option></select>{fieldErrors(`lines.${index}.type`).length > 0 && <span id={`line-${index}-type-error`} className="claim-field-error">{fieldErrors(`lines.${index}.type`).join(' ')}</span>}</div>
                  <div className="claim-field"><label htmlFor={`line-${index}-code`}>Code <span aria-hidden="true">*</span></label><input id={`line-${index}-code`} list="tariff-codes" value={line.code} onChange={(event) => updateLine(index, 'code', event.target.value)} placeholder="Ex. CONS-GEN" required aria-invalid={fieldErrors(`lines.${index}.code`).length > 0} aria-describedby={fieldErrors(`lines.${index}.code`).length ? `line-${index}-code-error` : undefined} />{fieldErrors(`lines.${index}.code`).length > 0 && <span id={`line-${index}-code-error`} className="claim-field-error">{fieldErrors(`lines.${index}.code`).join(' ')}</span>}{tariffHint(line.code) && <small className="claim-hint">{tariffHint(line.code)}</small>}</div>
                  <div className="claim-field"><label htmlFor={`line-${index}-quantity`}>Quantité <span aria-hidden="true">*</span></label><input id={`line-${index}-quantity`} type="number" min="1" step="1" inputMode="numeric" value={line.quantite} onChange={(event) => updateLine(index, 'quantite', event.target.value)} required aria-invalid={fieldErrors(`lines.${index}.quantite`).length > 0} aria-describedby={fieldErrors(`lines.${index}.quantite`).length ? `line-${index}-quantity-error` : undefined} />{fieldErrors(`lines.${index}.quantite`).length > 0 && <span id={`line-${index}-quantity-error`} className="claim-field-error">{fieldErrors(`lines.${index}.quantite`).join(' ')}</span>}</div>
                  <div className="claim-field"><label htmlFor={`line-${index}-price`}>Prix unitaire (MGA) <span aria-hidden="true">*</span></label><input id={`line-${index}-price`} type="text" inputMode="numeric" value={line.prix_unitaire ? moneyFormat.format(Number(line.prix_unitaire)) : ''} onChange={(event) => updateLine(index, 'prix_unitaire', moneyInput(event.target.value))} placeholder="0" required aria-invalid={fieldErrors(`lines.${index}.prix_unitaire`).length > 0} aria-describedby={fieldErrors(`lines.${index}.prix_unitaire`).length ? `line-${index}-price-error` : undefined} />{fieldErrors(`lines.${index}.prix_unitaire`).length > 0 && <span id={`line-${index}-price-error`} className="claim-field-error">{fieldErrors(`lines.${index}.prix_unitaire`).join(' ')}</span>}</div>
                  <div className="claim-line-amount"><span>Montant ligne</span><strong>{moneyFormat.format((Number(line.quantite) || 0) * (Number(line.prix_unitaire) || 0))} MGA</strong></div>
                  <button type="button" className="remove-claim-line" aria-label={`Supprimer la ligne ${index + 1}`} disabled={draft.lines.length === 1} onClick={() => removeLine(index)}><Trash2 aria-hidden="true" size={17} /></button>
                </div>
              </fieldset>
            ))}
          </div>
          <div className="claim-total"><span>Total de la facture</span><strong>{moneyFormat.format(total)} <small>MGA</small></strong></div>
        </section>

        <footer className="claim-form-footer"><p>Les droits réels sont vérifiés par l’API. Les montants ci-dessus sont des données de démonstration.</p><button className="claim-submit" type="submit" disabled={submitting}>{submitting ? 'Envoi en cours…' : 'Soumettre la facture'}<ArrowRight aria-hidden="true" size={17} /></button></footer>
      </form>
    </div>
  )
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
