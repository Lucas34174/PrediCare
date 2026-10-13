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

export interface Prediction {
  claim_id: string
  fraud_probability: number
  risk_level: 'low' | 'medium' | 'high'
  model_version: string
  explanation: {
    top_factors: string[]
  }
}

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
  detail?: string
  message?: string
}
