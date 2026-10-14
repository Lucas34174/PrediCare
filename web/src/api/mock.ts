import { ApiError } from './errors'
import type { Kpis, LoginRequest, LoginResponse, Prediction } from './types'

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

export const mockPrediction: Prediction = {
  claim_id: 'PC-2026-00482',
  fraud_probability: 0.78,
  risk_level: 'high',
  model_version: 'predicare-0.4.2',
  explanation: {
    top_factors: [
      'Montant supérieur aux habitudes du dossier',
      'Acte répété dans un délai rapproché',
      'Pièce justificative à vérifier',
    ],
  },
}

export const mockKpis: Kpis = {
  claims_received: 128,
  claims_to_review: 14,
  claims_processed: 114,
  reimbursements_mga: 18_450_000,
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

  throw new ApiError(`La route simulée « ${path} » n’est pas configurée.`, 404)
}
