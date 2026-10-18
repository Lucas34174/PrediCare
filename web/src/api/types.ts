export type Role =
  | 'gestionnaire'
  | 'professionnel_sante'
  | 'assure'
  | 'administrateur'

export type UiRole = Exclude<Role, 'administrateur'> | 'admin'

export function toUiRole(role: Role): UiRole {
  return role === 'administrateur' ? 'admin' : role
}

export interface LoginRequest {
  identifier: string
  password: string
}

export interface LoginUser {
  id: string
  identifier: string
  role: Role
  nom_complet: string
  assure_id?: string | null
  prestataire_id?: string | null
}

export interface LoginResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: LoginUser
}

export type ClaimLineType = 'ACTE' | 'MEDICAMENT'
export type ClaimChannel = 'PORTAIL_PRESTATAIRE' | 'EMAIL' | 'PAPIER_SCAN'
export type SettlementMethod = 'TIERS_PAYANT' | 'REMBOURSEMENT_ASSURE'
export type ClaimStatus = 'EN_COURS' | 'PAYEE' | 'REJETEE'
export type RejectionReason =
  | 'PIECE_MANQUANTE_ATTESTATION'
  | 'ENTENTE_PREALABLE_ABSENTE'
  | 'HORS_PERIODE_COUVERTURE'
  | 'DELAI_DE_CARENCE'
  | 'ORDONNANCE_PERIMEE'
  | 'PRODUIT_NON_REMBOURSABLE'
  | 'PLAFOND_ATTEINT'
  | 'CONTROLE_MEDICAL'
  | 'FACTURE_INVALIDE'
export type ManagerDecision = 'VALIDE' | 'REJETE' | 'INVESTIGATION'

export interface DraftLine {
  type_ligne: ClaimLineType
  code: string
  quantite: string
  prix_unitaire: string
}

export interface ClaimDraft {
  numero_facture: string
  prestataire_id: string
  assure_id: string
  ordonnance_id: string
  date_soin: string
  date_emission: string
  date_reception: string
  canal_reception: ClaimChannel | ''
  mode_reglement: SettlementMethod
  part_assure: string
  lines: DraftLine[]
}

export interface ClaimLineSubmission {
  num_ligne: number
  code: string
  type_ligne: ClaimLineType
  quantite: number
  prix_unitaire: number
  montant_total: number
}

export interface ClaimCreateRequest {
  numero_facture: string
  assure_id: string
  prestataire_id: string
  ordonnance_id: string | null
  date_soin: string
  date_emission: string
  montant_total: number
  part_assure: number
  lignes: ClaimLineSubmission[]
}

export interface ManagerClaimIntake extends ClaimCreateRequest {
  date_reception: string
  canal_reception: Exclude<ClaimChannel, 'PORTAIL_PRESTATAIRE'>
  mode_reglement: SettlementMethod
}

export interface ClaimCreateResponse {
  facture_id: string
  statut: ClaimStatus
  score_fraude: number
  est_anomalie: boolean
  seuil_applique: number
  message: string
}

// Type transitoire pour le formulaire précédent, à remplacer à l'étape ClaimForm.
export type ClaimSubmission = Record<string, unknown>

export interface ClaimListItem {
  facture_id: string
  numero_facture: string
  assure_id: string
  prestataire_id: string
  date_soin: string
  date_emission: string
  montant_total: number
  part_assure: number
  montant_demande: number
  statut: ClaimStatus
}

export interface ManagerClaimListItem extends ClaimListItem {
  score_fraude: number
  est_anomalie: boolean
}

export interface ClaimsPage {
  total: number
  page: number
  page_size: number
  items: ClaimListItem[]
}

export interface ClaimsQuery {
  page?: number
  page_size?: number
  statut?: ClaimStatus
  date_debut?: string
  date_fin?: string
  fraud_alert_only?: boolean
}

export interface ClaimLine {
  num_ligne: number
  code: string
  type_ligne: ClaimLineType
  quantite: number
  prix_unitaire: number
  montant_total: number
}

export interface ClaimDetail extends ClaimListItem {
  nom_etablissement: string
  ordonnance_id: string | null
  motif_rejet: RejectionReason | null
  montant_pris_en_charge: number | null
  lignes: ClaimLine[]
}

export interface DecisionRequest {
  decision: ManagerDecision
  motif: string
  montant_accorde?: number
}

export interface DecisionResponse {
  facture_id: string
  statut: ClaimStatus
  decision: ManagerDecision
  gestionnaire_id: string
  date_decision: string
  message: string
}

export interface ShapFactor {
  feature: string
  valeur?: number | string
  impact_shap?: number
  shap_value?: number
  description?: string
}

export type TopFactor = string | ShapFactor

export interface PredictionResponse {
  facture_id: string
  prediction: {
    score_fraude: number
    seuil_applique: number
    est_anomalie: boolean
    version_modele: string
    date_prediction: string
  }
  explicabilite: {
    top_facteurs: TopFactor[]
    recommandation: string
  }
}

export interface DashboardPrediction {
  claim_id: string
  fraud_probability: number
  risk_level: 'low' | 'medium' | 'high'
  model_version: string
  explanation: { top_factors: TopFactor[] }
}

export interface ValidationIssue {
  loc: Array<string | number>
  msg: string
  type: string
}

export type ApiErrorDetail = string | ValidationIssue[]

export interface Kpis {
  periode: string
  kpis: {
    total_factures_traitees: number
    montant_total_demande: number
    montant_economise_fraude: number
    taux_detection_fraude: number
    dossiers_en_attente_arbitrage: number
  }
  distribution_fraudes: Array<{ type: string; count: number }>
}

export interface DashboardKpis {
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
  role: UiRole
}

export interface ApiErrorPayload {
  detail?: ApiErrorDetail
  message?: string
}
