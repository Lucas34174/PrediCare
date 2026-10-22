import type { ClaimChannel, ClaimLineType, ClaimStatus, ManagerDecision, RejectionReason, SettlementMethod } from '@/api/types'

export const claimLineTypes = ['ACTE', 'MEDICAMENT'] as const satisfies readonly ClaimLineType[]
export const claimLineTypeLabels: Record<ClaimLineType, string> = { ACTE: 'Acte', MEDICAMENT: 'Médicament' }
export const settlementMethods = ['TIERS_PAYANT', 'REMBOURSEMENT_ASSURE'] as const satisfies readonly SettlementMethod[]
export const settlementMethodLabels: Record<SettlementMethod, string> = {
  TIERS_PAYANT: 'Tiers payant',
  REMBOURSEMENT_ASSURE: 'Remboursement à l’assuré',
}
export const claimChannels = ['PORTAIL_PRESTATAIRE', 'EMAIL', 'PAPIER_SCAN'] as const satisfies readonly ClaimChannel[]
export const claimChannelLabels: Record<ClaimChannel, string> = {
  PORTAIL_PRESTATAIRE: 'Portail prestataire',
  EMAIL: 'Courriel',
  PAPIER_SCAN: 'Papier numérisé',
}

export const claimStatuses = ['EN_COURS', 'PAYEE', 'REJETEE'] as const satisfies readonly ClaimStatus[]
export const claimStatusLabels: Record<ClaimStatus, string> = {
  EN_COURS: 'En cours',
  PAYEE: 'Payée',
  REJETEE: 'Rejetée',
}

export const rejectionReasons = [
  'PIECE_MANQUANTE_ATTESTATION', 'ENTENTE_PREALABLE_ABSENTE', 'HORS_PERIODE_COUVERTURE',
  'DELAI_DE_CARENCE', 'ORDONNANCE_PERIMEE', 'PRODUIT_NON_REMBOURSABLE',
  'PLAFOND_ATTEINT', 'CONTROLE_MEDICAL', 'FACTURE_INVALIDE',
] as const satisfies readonly RejectionReason[]

export const rejectionReasonLabels: Record<RejectionReason, string> = {
  PIECE_MANQUANTE_ATTESTATION: 'Attestation de prise en charge manquante',
  ENTENTE_PREALABLE_ABSENTE: 'Entente préalable absente',
  HORS_PERIODE_COUVERTURE: 'Soin hors période de couverture',
  DELAI_DE_CARENCE: 'Délai de carence non écoulé',
  ORDONNANCE_PERIMEE: 'Ordonnance périmée',
  PRODUIT_NON_REMBOURSABLE: 'Produit non remboursable',
  PLAFOND_ATTEINT: 'Plafond de garantie atteint',
  CONTROLE_MEDICAL: 'Contrôle médical requis',
  FACTURE_INVALIDE: 'Facture invalide',
}

export const managerDecisions = ['VALIDE', 'REJETE', 'INVESTIGATION'] as const satisfies readonly ManagerDecision[]
export const managerDecisionLabels: Record<ManagerDecision, string> = {
  VALIDE: 'Valider',
  REJETE: 'Rejeter',
  INVESTIGATION: 'Demander un examen',
}

export interface TariffReference {
  code: string
  description: string
  unitPriceMGA?: number
  requiresPriorApproval?: boolean
  reimbursable?: boolean
}

export const tariffReferences: readonly TariffReference[] = [
  { code: 'CONS-GEN', description: 'Consultation générale', unitPriceMGA: 20_000 },
  { code: 'IMG-ECHO', description: 'Imagerie — échographie' },
  { code: 'IMG-SCANNER', description: 'Imagerie — scanner', requiresPriorApproval: true },
  { code: 'MED-PARA500', description: 'Médicament — paracétamol 500 mg', unitPriceMGA: 2_000 },
  { code: 'MED-FORTIF', description: 'Médicament — fortifiant', unitPriceMGA: 25_000, reimbursable: false },
]

export const demoMemberId = 'ASS-C60624BAFB'
export const demoContractId = 'CTR-000048'
