import type { ClaimLineType } from '@/api/types'

export const claimLineTypes = ['ACTE', 'MEDICAMENT'] as const satisfies readonly ClaimLineType[]

// Valeurs à confirmer avec le dictionnaire backend avant de les proposer dans le formulaire.
export const claimChannels: readonly string[] = []
export const settlementMethods: readonly string[] = []

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
