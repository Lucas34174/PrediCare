// web/src/api/admin.ts
import { request } from './request'

export interface AdminConfig {
  fraud_score_threshold: number
  n8n_webhook_url: string
  semantic_cache_enabled: boolean
  semantic_cache_threshold: number
  updated_at?: string
}

export interface AdminModel {
  version_id: string
  type: string
  recall_test: number
  precision_test: number
  f1_score: number
  date_entrainement: string
  statut: 'ACTIVE' | 'STANDBY'
}

export interface AdminModelsResponse {
  active_version: string
  available_models: AdminModel[]
}

export interface AdminMetricsResponse {
  api_metrics: {
    requests_total: number
    error_rate_5xx: number
    p95_latency_ms: number
  }
  ml_drift_monitoring: {
    metric: string
    psi_score: number
    statut_derive: 'STABLE' | 'MODÉRÉ' | 'CRITIQUE'
    alerte_derive: boolean
    derniere_evaluation: string
  }
}

export interface AdminAuditLog {
  id: number
  type_action: string
  utilisateur_id: string
  role_utilisateur: string
  ressource_type: string
  ressource_id: string
  details: Record<string, unknown>
  ip_source: string
  date_action: string
}

export interface AdminAuditResponse {
  total: number
  items: AdminAuditLog[]
}

export function getAdminConfig(): Promise<AdminConfig> {
  return request<AdminConfig>('/admin/config')
}

export function updateAdminConfig(payload: Partial<AdminConfig>): Promise<AdminConfig> {
  return request<AdminConfig>('/admin/config', {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function getAdminModels(): Promise<AdminModelsResponse> {
  return request<AdminModelsResponse>('/admin/models')
}

export function activateAdminModel(versionId: string): Promise<{ message: string; active_version: string; switched_at: string }> {
  return request(`/admin/models/${encodeURIComponent(versionId)}/activate`, {
    method: 'POST',
  })
}

export function getAdminMetrics(): Promise<AdminMetricsResponse> {
  return request<AdminMetricsResponse>('/admin/metrics')
}

export function getAdminAudit(page = 1, pageSize = 50): Promise<AdminAuditResponse> {
  return request<AdminAuditResponse>(`/admin/audit?page=${page}&page_size=${pageSize}`)
}