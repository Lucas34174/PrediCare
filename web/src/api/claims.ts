import type {
  ClaimCreateRequest,
  ClaimCreateResponse,
  ClaimDetail,
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

export function listClaims(query: ClaimsQuery = {}): Promise<ClaimsPage> {
  const params = new URLSearchParams()
  Object.entries(query).forEach(([key, value]) => {
    if (value !== undefined) params.set(key, String(value))
  })
  const suffix = params.size ? `?${params.toString()}` : ''
  return request<ClaimsPage>(`/claims${suffix}`)
}

export function getCurrentUser(): Promise<LoginUser> {
  return request<LoginUser>('/auth/me')
}

export function createClaim(
  payload: ClaimCreateRequest | ManagerClaimIntake,
): Promise<ClaimCreateResponse> {
  return request<ClaimCreateResponse>('/claims', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getClaim(claimId: string): Promise<ClaimDetail> {
  return request<ClaimDetail>(`/claims/${encodeURIComponent(claimId)}`)
}

export function getClaimPrediction(claimId: string): Promise<PredictionResponse> {
  return request<PredictionResponse>(`/claims/${encodeURIComponent(claimId)}/prediction`)
}

// web/src/api/claims.ts — REMPLACE saveManagerDecision
export function saveManagerDecision(
  claimId: string,
  decision: DecisionRequest,
): Promise<DecisionResponse> {
  return request<DecisionResponse>(
    `/claims/${encodeURIComponent(claimId)}/decision`,
    { method: 'POST', body: JSON.stringify(decision) },
  )
}

export function listManagerClaims(query: ClaimsQuery = {}): Promise<ManagerClaimsPage> {
  const params = new URLSearchParams()
  Object.entries(query).forEach(([key, value]) => {
    if (value !== undefined) params.set(key, String(value))
  })
  const suffix = params.size ? `?${params.toString()}` : ''
  return request<ManagerClaimsPage>(`/claims${suffix}`)
}

// web/src/api/types.ts — AJOUTE après `ClaimsPage`
export interface ManagerClaimsPage {
  total: number
  page: number
  page_size: number
  items: ManagerClaimListItem[]
}