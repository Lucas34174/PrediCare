// web/src/lib/pdfParser.ts
import type { ClaimDraft, DraftLine } from '@/api/types'

// ---------- Types ----------
export interface ParsedFacture {
  kind: 'FACTURE'
  numero_facture: string
  date_soin: string
  date_emission: string
  type_prestataire: 'LABORATOIRE' | 'PHARMACIE' | 'CLINIQUE' | string
  patient_nom: string
  assure_id: string
  ordonnance_id: string
  attestation_pec: string
  entente_prealable_id: string // Gardé mais souvent vide
  mode_reglement: 'TIERS_PAYANT' | 'REMBOURSEMENT_ASSURE'
  montant_total: number
  lignes: Array<{
    code: string
    designation: string
    quantite: number
    prix_unitaire: number
    montant: number
  }>
  warnings: string[]
}

export interface ParsedOrdonnance {
  kind: 'ORDONNANCE'
  numero_ordonnance: string
  date: string
  patient_nom: string
  patient_age: string
  prescripteur: string
  specialite: string
  numero_ordre: string
  renseignement_clinique: string
  lignes: Array<{
    designation: string
    quantite: number
    posologie: string
  }>
  validite_jours: number | null
  warnings: string[]
}

export type ParsedDocument = ParsedFacture | ParsedOrdonnance

// ---------- Helpers ----------
const RE_FACTURE_NUM = /FACTURE\s*N[°o]\s*([A-Z0-9/]+)/i
const RE_DATE_SOIN = /Date\s*des\s*soins\s*(\d{4}-\d{2}-\d{2})/i
const RE_DATE_FACTURE = /Date\s*de\s*facture\s*(\d{4}-\d{2}-\d{2})/i
const RE_TYPE = /Type\s*(LABORATOIRE|PHARMACIE|CLINIQUE)/i
const RE_PATIENT = /Patient\s+(.+?)\s+N[°o]\s*assur[ée]\s*(ASS-[A-Z0-9]+)/i
const RE_ORDONNANCE = /Ordonnance\s*(ORD-[A-Z0-9]+)/i
const RE_ATTESTATION = /Attestation\s*PEC\s*(APC-[A-Z0-9]+)/i
const RE_ENTENTE = /Entente\s*pr[ée]alable\s*([A-Z0-9-]+)/i // Souvent "—"
const RE_MODE = /Mode\s*(TIERS_PAYANT|REMBOURSEMENT_ASSURE)/i
const RE_TOTAL = /TOTAL\s*([\d\s]+)\s*Ar/i

const RE_ORD_NUM = /R[ée]f\.\s*(ORD-[A-Z0-9]+)/i
const RE_ORD_DATE = /le\s*(\d{4}-\d{2}-\d{2})/i
const RE_ORD_PATIENT = /Patient\s*:\s*([^–\n]+?)\s*[–-]\s*(\d+\s*ans?)/i
const RE_ORD_PRESCRIPTEUR = /(?:Docteur|Dr\.?|Polyclinique|Clinique)\s+([A-ZÀ-Ÿ][^\n]+)/i
const RE_ORD_SPECIALITE = /(M[ée]decine\s+g[ée]n[ée]rale[^\n]*)/i
const RE_ORD_ORDRE = /ONM-(\d+)/i
const RE_ORD_CLINIQUE = /Renseignement\s+clinique\s*:\s*([^\n]+?)(?=\s+\d+\.|\s*$)/i
const RE_ORD_VALIDITE = /Validit[ée]\s*:\s*(\d+)\s*jours/i
const RE_LIGNE_ORDONNANCE = /(\d+)\.\s*([^–\n]+?)\s*–\s*Qt[ée]\s*:\s*(\d+)\s*[\n\s]+([^\d\n][^\n]*?)(?=\s*\d+\.\s*|$)/gi

// Ligne de facture : CODE DESIGNATION QTÉ P.U. MONTANT
// Format multiligne (PDF layout) : Code, Désignation, Qté, P.U., Montant
const RE_LIGNE_TABLE =
  /([A-Z]{3,4}-[A-Z0-9]+)\s*\n\s*(.+?)\s*\n\s*(\d+)\s*\n\s*([\d\s]+)\s*Ar\s*\n\s*([\d\s]+)\s*Ar/g

// Format en ligne
const RE_LIGNE_FACTURE =
  /([A-Z]{3,4}-[A-Z0-9]+)\s+(.+?)\s+(\d+)\s+([\d\s]+)\s*Ar\s+([\d\s]+)\s*Ar/g

const toInt = (s: string) => Number(s.replace(/\s/g, ''))

// ---------- Parser FACTURE ----------
export function parseFacture(rawText: string): ParsedFacture {
  // On normalise les espaces mais on garde les sauts de ligne pour les lignes
  const text = rawText.replace(/[ \t]+/g, ' ').trim()
  const warnings: string[] = []

  const numMatch = text.match(RE_FACTURE_NUM)
  const numero_facture = numMatch?.[1] ?? ''
  if (!numero_facture) warnings.push('Numéro de facture introuvable.')

  const date_soin = text.match(RE_DATE_SOIN)?.[1] ?? ''
  const date_emission = text.match(RE_DATE_FACTURE)?.[1] ?? date_soin
  if (!date_soin) warnings.push('Date de soin introuvable.')

  const type_prestataire = text.match(RE_TYPE)?.[1] ?? ''
  const patientMatch = text.match(RE_PATIENT)
  const patient_nom = patientMatch?.[1]?.trim() ?? ''
  const assure_id = patientMatch?.[2] ?? ''
  if (!assure_id) warnings.push('Identifiant assuré introuvable.')

  const ordonnance_id = text.match(RE_ORDONNANCE)?.[1] ?? ''
  const attestation_pec = text.match(RE_ATTESTATION)?.[1] ?? ''
  const entente_prealable_id = text.match(RE_ENTENTE)?.[1] ?? ''
  const mode_reglement =
    (text.match(RE_MODE)?.[1] as ParsedFacture['mode_reglement']) ?? 'TIERS_PAYANT'

  const montant_total = toInt(text.match(RE_TOTAL)?.[1] ?? '0')

  // Découpage de la zone du tableau (entre Montant/Code et TOTAL) pour éviter de capturer l'en-tête
  let tableText = rawText
  const mMatch = rawText.match(/Montant\s*\n/i)
  if (mMatch && mMatch.index !== undefined) {
    tableText = rawText.slice(mMatch.index + mMatch[0].length)
  } else {
    const cMatch = rawText.match(/Code\s*\n/i)
    if (cMatch && cMatch.index !== undefined) {
      tableText = rawText.slice(cMatch.index + cMatch[0].length)
    }
  }

  const tMatch = tableText.match(/TOTAL\s*[\d\s]+Ar/i)
  if (tMatch && tMatch.index !== undefined) {
    tableText = tableText.slice(0, tMatch.index)
  }

  const lignes: ParsedFacture['lignes'] = []

  // 1. Format multiligne standard des factures PDF PrediCare
  for (const m of tableText.matchAll(RE_LIGNE_TABLE)) {
    lignes.push({
      code: m[1].trim(),
      designation: m[2].trim(),
      quantite: Number(m[3]),
      prix_unitaire: toInt(m[4]),
      montant: toInt(m[5]),
    })
  }

  // 2. Format en ligne si non trouvé en multiligne
  if (!lignes.length) {
    for (const m of tableText.matchAll(RE_LIGNE_FACTURE)) {
      lignes.push({
        code: m[1].trim(),
        designation: m[2].trim(),
        quantite: Number(m[3]),
        prix_unitaire: toInt(m[4]),
        montant: toInt(m[5]),
      })
    }
  }

  // 3. Fallback sur le texte brut complet
  if (!lignes.length) {
    for (const m of rawText.matchAll(RE_LIGNE_FACTURE)) {
      lignes.push({
        code: m[1].trim(),
        designation: m[2].trim(),
        quantite: Number(m[3]),
        prix_unitaire: toInt(m[4]),
        montant: toInt(m[5]),
      })
    }
  }

  if (!lignes.length) warnings.push('Aucune ligne de facture détectée.')

  return {
    kind: 'FACTURE',
    numero_facture,
    date_soin,
    date_emission,
    type_prestataire,
    patient_nom,
    assure_id,
    ordonnance_id,
    attestation_pec,
    entente_prealable_id,
    mode_reglement,
    montant_total,
    lignes,
    warnings,
  }
}

// ---------- Parser ORDONNANCE ----------
export function parseOrdonnance(rawText: string): ParsedOrdonnance {
  const text = rawText.replace(/[ \t]+/g, ' ').trim()
  const warnings: string[] = []

  const numero_ordonnance = text.match(RE_ORD_NUM)?.[1] ?? ''
  if (!numero_ordonnance) warnings.push('Référence ordonnance introuvable.')

  const date = text.match(RE_ORD_DATE)?.[1] ?? ''

  const patientMatch = text.match(RE_ORD_PATIENT)
  const patient_nom = patientMatch?.[1]?.trim() ?? ''
  const patient_age = patientMatch?.[2]?.trim() ?? ''
  if (!patient_nom) warnings.push('Nom du patient introuvable.')

  const prescripteurMatch = text.match(RE_ORD_PRESCRIPTEUR)
  const prescripteur = prescripteurMatch?.[1]?.split('Médecine')[0]?.trim() ?? ''
  const specialite = text.match(RE_ORD_SPECIALITE)?.[1]?.trim() ?? ''
  const numero_ordre = text.match(RE_ORD_ORDRE)?.[0] ?? ''
  const renseignement_clinique = text.match(RE_ORD_CLINIQUE)?.[1]?.trim() ?? ''
  const validite_jours = Number(text.match(RE_ORD_VALIDITE)?.[1] ?? '') || null

  const lignes: ParsedOrdonnance['lignes'] = []
  for (const m of rawText.matchAll(RE_LIGNE_ORDONNANCE)) {
    lignes.push({
      designation: m[2].trim(),
      quantite: Number(m[3]),
      posologie: m[4].trim(),
    })
  }
  if (!lignes.length) warnings.push('Aucune ligne d’ordonnance détectée.')

  return {
    kind: 'ORDONNANCE',
    numero_ordonnance,
    date,
    patient_nom,
    patient_age,
    prescripteur,
    specialite,
    numero_ordre,
    renseignement_clinique,
    lignes,
    validite_jours,
    warnings,
  }
}

// ---------- Mapper → ClaimDraft ----------
// web/src/lib/pdfParser.ts

export function applyFactureToDraft(
  parsed: ParsedFacture,
  current: ClaimDraft,
  providerId: string | undefined,
): ClaimDraft {
  const lines: DraftLine[] = parsed.lignes.map((l) => ({
    type_ligne: l.code.startsWith('MED-') ? 'MEDICAMENT' : 'ACTE',
    code: l.code,
    quantite: String(l.quantite),
    prix_unitaire: String(l.prix_unitaire),
  }))

  return {
    ...current,
    numero_facture: parsed.numero_facture || current.numero_facture,
    prestataire_id: current.prestataire_id || providerId || '',
    assure_id: parsed.assure_id || current.assure_id,
    ordonnance_id: parsed.ordonnance_id || current.ordonnance_id,
    date_soin: parsed.date_soin || current.date_soin,
    date_emission: parsed.date_emission || current.date_emission,
    mode_reglement: parsed.mode_reglement,
    part_assure: current.part_assure,
    patient_nom: parsed.patient_nom || current.patient_nom,          // <-- AJOUT
    attestation_pec: parsed.attestation_pec || current.attestation_pec,
    lines: lines.length ? lines : current.lines,
    // On ajoute les champs spécifiques dans un objet meta si besoin
    // Mais pour l'instant, le formulaire n'a pas de champ pour patient_nom et attestation_pec
  }
}

export function applyOrdonnanceToDraft(
  parsed: ParsedOrdonnance,
  current: ClaimDraft,
): ClaimDraft {
  return {
    ...current,
    ordonnance_id: parsed.numero_ordonnance || current.ordonnance_id,
  }
}

// ---------- Détection automatique du type ----------
export function detectDocumentType(rawText: string): 'FACTURE' | 'ORDONNANCE' | 'UNKNOWN' {
  if (/FACTURE\s*N[°o]/i.test(rawText)) return 'FACTURE'
  if (/ORDONNANCE/i.test(rawText) && /R[ée]f\.\s*ORD-/i.test(rawText)) return 'ORDONNANCE'
  return 'UNKNOWN'
}