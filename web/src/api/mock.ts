import { ApiError } from './errors'
import type {
  ClaimRecord,
  DecisionRequest,
  DecisionResponse,
  Kpis,
  LoginRequest,
  LoginResponse,
  Prediction,
  RiskLevel,
} from './types'

export const mockAccounts: Array<LoginRequest & LoginResponse> = [
  {
    email: 'gestionnaire@predicare.mg',
    password: 'Demo2026!',
    access_token: 'mock-token-gestionnaire',
    token_type: 'bearer',
    role: 'gestionnaire',
    display_name: 'Mialy Randria',
  },
  {
    email: 'sante@predicare.mg',
    password: 'Demo2026!',
    access_token: 'mock-token-professionnel',
    token_type: 'bearer',
    role: 'professionnel_sante',
    display_name: 'Dr. Hery Rakoto',
  },
  {
    email: 'assure@predicare.mg',
    password: 'Demo2026!',
    access_token: 'mock-token-assure',
    token_type: 'bearer',
    role: 'assure',
    display_name: 'Tahina Andriam',
  },
  {
    email: 'admin@predicare.mg',
    password: 'Demo2026!',
    access_token: 'mock-token-admin',
    token_type: 'bearer',
    role: 'admin',
    display_name: 'Soa Ravel',
  },
]

export const mockPredictions: Record<RiskLevel, Prediction> = {
  low: {
    claim_id: 'PC-2026-00481',
    fraud_probability: 0.12,
    risk_level: 'low',
    model_version: 'predicare-0.4.2',
    explanation: { top_factors: ['Actes cohérents avec le dossier', { feature: 'montant_atypique', shap_value: -0.31 }] },
  },
  medium: {
    claim_id: 'PC-2026-00482',
    fraud_probability: 0.48,
    risk_level: 'medium',
    model_version: 'predicare-0.4.2',
    explanation: { top_factors: [{ feature: 'frequence_des_actes', shap_value: 0.42 }, { feature: 'montant_atypique', shap_value: -0.16 }] },
  },
  high: {
    claim_id: 'PC-2026-00483',
    fraud_probability: 0.78,
    risk_level: 'high',
    model_version: 'predicare-0.4.2',
    explanation: { top_factors: [
      'Montant supérieur aux habitudes du dossier',
      { feature: 'absence_entente_prealable', shap_value: 0.66 },
      { feature: 'frequence_des_actes', shap_value: 0.38 },
    ] },
  },
}

export const mockPrediction = mockPredictions.high

export const mockKpis: Kpis = {
  claims_received: 128,
  claims_to_review: 14,
  claims_processed: 114,
  reimbursements_mga: 18_450_000,
}

const mockClaims = new Map<string, ClaimRecord>()
const mockDecisions = new Map<string, DecisionResponse>()
let nextScenario = 0

function getRequestBody<T>(init: RequestInit): T {
  return JSON.parse(String(init.body ?? '{}')) as T
}

export function resolveMock<T>(path: string, init: RequestInit): T {
  if (path === '/auth/login' && init.method === 'POST') {
    const credentials = JSON.parse(String(init.body ?? '{}')) as LoginRequest
    const account = mockAccounts.find(
      (candidate) =>
        candidate.email === credentials.email &&
        candidate.password === credentials.password,
    )
    if (!account) {
      throw new ApiError(
        'Identifiants invalides. Vérifiez votre adresse et votre mot de passe.',
        401,
      )
    }
    const { access_token, token_type, role, display_name } = account
    return { access_token, token_type, role, display_name } as T
  }

  if (path === '/dashboard/kpis') return mockKpis as T
  if (path === '/predictions/latest') return mockPrediction as T

  if (path === '/claims' && init.method === 'POST') {
    const riskLevels: RiskLevel[] = ['low', 'medium', 'high']
    const prediction = mockPredictions[riskLevels[nextScenario % riskLevels.length]]
    nextScenario += 1
    const claim = { claim_id: prediction.claim_id, ...getRequestBody<Record<string, unknown>>(init) }
    mockClaims.set(prediction.claim_id, claim)
    return claim as T
  }

  const predictionMatch = path.match(/^\/claims\/([^/]+)\/prediction$/)
  if (predictionMatch) {
    const claimId = decodeURIComponent(predictionMatch[1])
    const prediction = Object.values(mockPredictions).find((item) => item.claim_id === claimId)
    if (prediction) return prediction as T
    throw new ApiError(`Aucune prédiction simulée pour le dossier ${claimId}.`, 404)
  }

  const decisionMatch = path.match(/^\/claims\/([^/]+)\/decision$/)
  if (decisionMatch && init.method === 'POST') {
    const claimId = decodeURIComponent(decisionMatch[1])
    const decision = getRequestBody<DecisionRequest>(init)
    const savedDecision: DecisionResponse = { ...decision, decided_at: new Date().toISOString() }
    mockDecisions.set(claimId, savedDecision)
    return savedDecision as T
  }

  const claimMatch = path.match(/^\/claims\/([^/]+)$/)
  if (claimMatch) {
    const claimId = decodeURIComponent(claimMatch[1])
    return (mockClaims.get(claimId) ?? { claim_id: claimId }) as T
  }

  throw new ApiError(`La route simulée « ${path} » n’est pas configurée.`, 404)
}
