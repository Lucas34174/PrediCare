import type { ClaimDraft, DraftLine, ValidationIssue } from '@/api/types'

export type ClaimFieldErrors = Record<string, string[]>

const requiredFields: Array<
  | 'prestataire_id' | 'assure_id' | 'contrat_id' | 'ordonnance_id'
  | 'date_soin' | 'date_facture' | 'date_reception' | 'canal' | 'mode_reglement'
> = [
  'prestataire_id', 'assure_id', 'contrat_id', 'ordonnance_id',
  'date_soin', 'date_facture', 'date_reception', 'canal', 'mode_reglement',
]

export function validateClaimDraft(draft: ClaimDraft): ClaimFieldErrors {
  const errors: ClaimFieldErrors = {}
  for (const field of requiredFields) {
    if (!draft[field].trim()) errors[field] = ['Ce champ est obligatoire.']
  }
  if (draft.assure_id && !/^ASS-[A-Z0-9]{10}$/.test(draft.assure_id)) {
    errors.assure_id = ['Utilisez un identifiant pseudonyme au format ASS-XXXXXXXXXX.']
  }
  if (draft.date_soin && draft.date_facture && draft.date_soin > draft.date_facture) {
    errors.date_facture = ['La date de facture doit être égale ou postérieure à la date de soin.']
  }
  if (draft.date_facture && draft.date_reception && draft.date_facture > draft.date_reception) {
    errors.date_reception = ['La date de réception doit être égale ou postérieure à la date de facture.']
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
  for (const field of ['date_soin', 'date_facture', 'date_reception'] as const) {
    if (draft[field] && !isValidIsoDate(draft[field])) {
      errors[field] = ['Utilisez le format AAAA-MM-JJ avec une date valide.']
    }
  }
  return errors
}

function toDraftField(loc: ValidationIssue['loc']): string {
  const parts = loc.filter((part) => part !== 'body' && part !== 'query' && part !== 'path')
  const fieldMap: Record<string, string> = {
    prestataire_id: 'prestataire_id', assure_id: 'assure_id', contrat_id: 'contrat_id',
    ordonnance_id: 'ordonnance_id', date_soin: 'date_soin', date_facture: 'date_facture',
    date_reception: 'date_reception', canal: 'canal', mode_reglement: 'mode_reglement',
    attestation_prise_en_charge: 'attestation_prise_en_charge', entente_prealable: 'entente_prealable',
    lignes: 'lines', lines: 'lines', type: 'type', code: 'code', quantite: 'quantite',
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

export function makeClaimPayload(draft: ClaimDraft): Record<string, unknown> {
  // À confirmer: ces noms reprennent le brief, le backend ne publie pas encore son schéma.
  return {
    prestataire_id: draft.prestataire_id.trim(),
    assure_id: draft.assure_id.trim(),
    contrat_id: draft.contrat_id.trim(),
    ordonnance_id: draft.ordonnance_id.trim(),
    date_soin: draft.date_soin,
    date_facture: draft.date_facture,
    date_reception: draft.date_reception,
    canal: draft.canal.trim(),
    mode_reglement: draft.mode_reglement.trim(),
    attestation_prise_en_charge: draft.attestation_prise_en_charge,
    entente_prealable: draft.entente_prealable,
    lignes: draft.lines.map((line: DraftLine) => ({
      type: line.type,
      code: line.code.trim(),
      quantite: Number(line.quantite),
      prix_unitaire: Number(line.prix_unitaire),
    })),
  }
}
