import type { LoginResponse } from './types'

const SESSION_KEY = 'predicare.session'
let currentSession: LoginResponse | null = readSession()
const listeners = new Set<(session: LoginResponse | null) => void>()

function readSession(): LoginResponse | null {
  try {
    const serialized = sessionStorage.getItem(SESSION_KEY)
    if (!serialized) return null
    const session = JSON.parse(serialized) as LoginResponse
    if (!session.access_token || !session.user?.nom_complet || !session.user?.role) return null
    return session
  } catch {
    return null
  }
}

function publishSession(): void {
  listeners.forEach((listener) => listener(currentSession))
}

export function getStoredSession(): LoginResponse | null {
  return currentSession
}

export function setStoredSession(session: LoginResponse): void {
  currentSession = session
  try {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(session))
  } catch {
    // La session reste disponible en mémoire si le stockage du navigateur est bloqué.
  }
  publishSession()
}

export function clearStoredSession(): void {
  currentSession = null
  try {
    sessionStorage.removeItem(SESSION_KEY)
  } catch {
    // La session en mémoire est tout de même effacée.
  }
  publishSession()
}

export function subscribeToSession(
  listener: (session: LoginResponse | null) => void,
): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}
