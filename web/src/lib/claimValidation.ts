import type { ClaimDraft, DraftLine, ValidationIssue } from '@/api/types'

export type ClaimFieldErrors = Record<string, string[]>

type RequiredDraftField =
  | 'numero_facture' | 'prestataire_id' | 'assure_id' | 'date_soin' | 'date_emission'
  | 'date_reception' | 'canal_reception' | 'mode_reglement' | 'part_assure'

const requiredFields: RequiredDraftField[] = [
  'numero_facture', 'prestataire_id', 'assure_id', 'date_soin', 'date_emission', 'mode_reglement', 'part_assure',
]

export function validateClaimDraft(draft: ClaimDraft, profile: 'gestionnaire' | 'professionnel_sante' = 'gestionnaire'): ClaimFieldErrors {
  const errors: ClaimFieldErrors = {}
  const fields: RequiredDraftField[] = profile === 'gestionnaire'
    ? [...requiredFields, 'date_reception', 'canal_reception']
    : requiredFields
  for (const field of fields) {
    if (!draft[field].trim()) errors[field] = ['Ce champ est obligatoire.']
  }
  if (draft.assure_id && !/^ASS-[A-Z0-9]{10}$/.test(draft.assure_id)) {
    errors.assure_id = ['Utilisez un identifiant pseudonyme au format ASS-XXXXXXXXXX.']
  }
  if (draft.date_soin && draft.date_emission && draft.date_soin > draft.date_emission) {
    errors.date_emission = ['La date d’émission doit être égale ou postérieure à la date de soin.']
  }
  if (draft.date_emission && draft.date_reception && draft.date_emission > draft.date_reception) {
    errors.date_reception = ['La date de réception doit être égale ou postérieure à la date d’émission.']
  }
  if (!Number.isInteger(Number(draft.part_assure)) || Number(draft.part_assure) < 0) {
    errors.part_assure = ['La part de l’assuré doit être un montant entier positif ou nul.']
  }
  if (!draft.lines.length) errors.lines = ['Ajoutez au moins une ligne à la facture.']
  draft.lines.forEach((line, index) => {
    const prefix = `lines.${index}`
    if (!line.code.trim()) errors[`${prefix}.code`] = ['Le code est obligatoire.']
    if (!Number.isInteger(Number(line.quantite)) || Number(line.quantite) < 1) {
      errors[`${prefix}.quantite`] = ['La quantité doit être un entier supérieur ou égal à 1.']
    }
    if (!line.prix_unitaire.trim() || !Number.isInteger(Number(line.prix_unitaire)) || Number(line.prix_unitaire) < 0) {
      errors[`${prefix}.prix_unitaire`] = ['Le prix unitaire doit être un montant entier positif ou nul.']
    }
  })
  function isValidIsoDate(value: string): boolean {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
    const date = new Date(`${value}T00:00:00Z`)
    return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value
  }
  for (const field of ['date_soin', 'date_emission', 'date_reception'] as const) {
    if (draft[field] && !isValidIsoDate(draft[field])) {
      errors[field] = ['Utilisez le format AAAA-MM-JJ avec une date valide.']
    }
  }
  return errors
}

function toDraftField(loc: ValidationIssue['loc']): string {
  const parts = loc.filter((part) => part !== 'body' && part !== 'query' && part !== 'path')
  const fieldMap: Record<string, string> = {
    numero_facture: 'numero_facture', prestataire_id: 'prestataire_id', assure_id: 'assure_id',
    ordonnance_id: 'ordonnance_id', date_soin: 'date_soin', date_emission: 'date_emission',
    part_assure: 'part_assure', date_reception: 'date_reception', canal_reception: 'canal_reception',
    mode_reglement: 'mode_reglement', lignes: 'lines', type_ligne: 'type_ligne', code: 'code', quantite: 'quantite',
    prix_unitaire: 'prix_unitaire',
  }
  return parts.map((part) => fieldMap[String(part)] ?? String(part)).join('.')
}

export function mapValidationIssues(issues: readonly ValidationIssue[]): ClaimFieldErrors {
  return issues.reduce<ClaimFieldErrors>((result, issue) => {
    const field = toDraftField(issue.loc)
    result[field] = [...(result[field] ?? []), issue.msg]
    return result
  }, {})
}

export function makeClaimPayload(draft: ClaimDraft) {
  return {
    numero_facture: draft.numero_facture.trim(),
    prestataire_id: draft.prestataire_id.trim(),
    assure_id: draft.assure_id.trim(),
    ordonnance_id: draft.ordonnance_id.trim() || null,
    date_soin: draft.date_soin,
    date_emission: draft.date_emission,
    montant_total: draft.lines.reduce((sum, line) => sum + Number(line.quantite) * Number(line.prix_unitaire), 0),
    part_assure: Number(draft.part_assure),
    lignes: draft.lines.map((line: DraftLine, index) => ({
      num_ligne: index + 1,
      type_ligne: line.type_ligne,
      code: line.code.trim(),
      quantite: Number(line.quantite),
      prix_unitaire: Number(line.prix_unitaire),
      montant_total: Number(line.quantite) * Number(line.prix_unitaire),
    })),
  }
}
