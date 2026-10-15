import type {
  ClaimRecord,
  ClaimSubmission,
  DecisionRequest,
  DecisionResponse,
  Prediction,
} from './types'
import { request } from './request'

const claimsApiIsEnabled = import.meta.env.VITE_CLAIMS_API_ENABLED === 'true'
const claimsUseMock = import.meta.env.VITE_USE_MOCK !== 'false' || !claimsApiIsEnabled

export function createClaim(payload: ClaimSubmission): Promise<ClaimRecord> {
  return request<ClaimRecord>('/claims', {
    method: 'POST',
    body: JSON.stringify(payload),
  }, { forceMock: claimsUseMock })
}

export function getClaim(claimId: string): Promise<ClaimRecord> {
  return request<ClaimRecord>(`/claims/${encodeURIComponent(claimId)}`, {}, { forceMock: claimsUseMock })
}

export function getClaimPrediction(claimId: string): Promise<Prediction> {
  return request<Prediction>(`/claims/${encodeURIComponent(claimId)}/prediction`, {}, { forceMock: claimsUseMock })
}

export function saveManagerDecision(
  claimId: string,
  decision: DecisionRequest,
): Promise<DecisionResponse> {
  // À brancher: endpoint de décision à confirmer avec M2
  return request<DecisionResponse>(
    `/claims/${encodeURIComponent(claimId)}/decision`,
    { method: 'POST', body: JSON.stringify(decision) },
    { forceMock: true },
  )
}
