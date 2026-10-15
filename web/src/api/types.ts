export type Role =
  | 'gestionnaire'
  | 'professionnel_sante'
  | 'assure'
  | 'admin'

export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  role: Role
  display_name: string
}

export type RiskLevel = 'low' | 'medium' | 'high'
export type ClaimLineType = 'ACTE' | 'MEDICAMENT'
export type ManagerDecision = 'APPROUVER' | 'EXAMINER' | 'REJETER'

export interface DraftLine {
  type: ClaimLineType
  code: string
  quantite: string
  prix_unitaire: string
}

export interface ClaimDraft {
  prestataire_id: string
  assure_id: string
  contrat_id: string
  ordonnance_id: string
  date_soin: string
  date_facture: string
  date_reception: string
  canal: string
  mode_reglement: string
  attestation_prise_en_charge: boolean
  entente_prealable: boolean
  lines: DraftLine[]
}

// Le schéma des factures sera précisé après livraison du contrat backend.
export type ClaimSubmission = Record<string, unknown>

export interface ClaimRecord extends Record<string, unknown> {
  claim_id: string
}

export interface DecisionRequest {
  decision: ManagerDecision
  comment?: string
}

export interface DecisionResponse extends DecisionRequest {
  decided_at: string
}

export interface ShapFactor {
  feature: string
  shap_value: number
}

export type TopFactor = string | ShapFactor

export interface Prediction {
  claim_id: string
  fraud_probability: number
  risk_level: RiskLevel
  model_version: string
  explanation: {
    top_factors: TopFactor[]
  }
}

export interface ValidationIssue {
  loc: Array<string | number>
  msg: string
  type: string
}

export type ApiErrorDetail = string | ValidationIssue[]

export interface Kpis {
  claims_received: number
  claims_to_review: number
  claims_processed: number
  reimbursements_mga: number
}

export interface ChatResponse {
  answer: string
  sources: string[]
  abstained: boolean
}

export interface AuthUser {
  display_name: string
  role: Role
}

export interface ApiErrorPayload {
  detail?: ApiErrorDetail
  message?: string
}
