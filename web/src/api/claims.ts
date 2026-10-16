import type {
  ClaimCreateRequest,
  ClaimCreateResponse,
  ClaimDetail,
  ClaimListItem,
  ClaimsPage,
  ClaimsQuery,
  ManagerClaimIntake,
  ManagerClaimListItem,
  DecisionRequest,
  DecisionResponse,
  LoginUser,
  PredictionResponse,
} from './types'
import { request } from './request'

const claimsApiIsEnabled = import.meta.env.VITE_CLAIMS_API_ENABLED === 'true'
const claimsUseMock = import.meta.env.VITE_USE_MOCK !== 'false' || !claimsApiIsEnabled

export function listClaims<T extends ClaimListItem = ClaimListItem>(
  query: ClaimsQuery = {},
): Promise<ClaimsPage<T>> {
  // À brancher: endpoint à confirmer avec M2
  const params = new URLSearchParams()
  Object.entries(query).forEach(([key, value]) => {
    if (value !== undefined) params.set(key, String(value))
  })
  const suffix = params.size ? `?${params.toString()}` : ''
  return request<ClaimsPage<T>>(`/claims${suffix}`, {}, { forceMock: claimsUseMock })
}

/**
 * File d'examen du gestionnaire. Même endpoint que `listClaims` : le contrat
 * `GET /claims` expose déjà `score_fraude` et `est_anomalie` aux rôles habilités.
 * À brancher: filtres et tri de la file à confirmer avec M2 (voir étape 0).
 */
export function listManagerClaims(
  query: ClaimsQuery = {},
): Promise<ClaimsPage<ManagerClaimListItem>> {
  return listClaims<ManagerClaimListItem>(query)
}

export function getCurrentUser(): Promise<LoginUser> {
  return request<LoginUser>('/auth/me')
}

export function createClaim(
  payload: ClaimCreateRequest | ManagerClaimIntake,
  options: { forceMock?: boolean } = {},
): Promise<ClaimCreateResponse> {
  return request<ClaimCreateResponse>('/claims', {
    method: 'POST',
    body: JSON.stringify(payload),
  }, { forceMock: options.forceMock ?? claimsUseMock })
}

export function getClaim(claimId: string): Promise<ClaimDetail> {
  return request<ClaimDetail>(`/claims/${encodeURIComponent(claimId)}`, {}, { forceMock: claimsUseMock })
}

export function getClaimPrediction(claimId: string): Promise<PredictionResponse> {
  return request<PredictionResponse>(`/claims/${encodeURIComponent(claimId)}/prediction`, {}, { forceMock: claimsUseMock })
}

export function saveManagerDecision(
  claimId: string,
  decision: DecisionRequest,
): Promise<DecisionResponse> {
  // À brancher: endpoint à confirmer avec M2
  return request<DecisionResponse>(
    `/claims/${encodeURIComponent(claimId)}/decision`,
    { method: 'POST', body: JSON.stringify(decision) },
    { forceMock: true },
  )
}
