// web/src/api/assures.ts (nouveau fichier)
import { request } from './request'

export interface AssureCoverage {
  assure_id: string
  formule: 'ESSENTIEL' | 'CONFORT' | 'PREMIUM'
  taux_prise_en_charge: number // ex: 0.80 pour 80%
  plafond_annuel: number
}

export function getAssureCoverage(assureId: string): Promise<AssureCoverage> {
  return request<AssureCoverage>(`/assures/${encodeURIComponent(assureId)}/coverage`)
}