import { ApiError } from './errors'
import { resolveMock } from './mock'
import { clearStoredSession, getStoredSession } from './session'
import type { ApiErrorPayload } from './types'

const useMock = import.meta.env.VITE_USE_MOCK !== 'false'

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (useMock) return resolveMock<T>(path, init)

  const baseUrl = import.meta.env.VITE_API_URL
  if (!baseUrl) {
    throw new ApiError('URL de l’API manquante. Définissez VITE_API_URL puis relancez l’application.', 0)
  }

  const headers = new Headers(init.headers)
  if (!headers.has('Content-Type') && init.body) {
    headers.set('Content-Type', 'application/json')
  }
  const session = getStoredSession()
  if (session?.access_token) {
    headers.set('Authorization', `${session.token_type} ${session.access_token}`)
  }

  let response: Response
  try {
    response = await fetch(`${baseUrl.replace(/\/$/, '')}${path}`, { ...init, headers })
  } catch {
    throw new ApiError('Le serveur est injoignable. Vérifiez votre connexion ou réessayez plus tard.', 0)
  }

  if (response.status === 401) clearStoredSession()
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as ApiErrorPayload
    const message = payload.detail ?? payload.message ?? `La requête a échoué (${response.status}). Réessayez.`
    throw new ApiError(message, response.status)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}
