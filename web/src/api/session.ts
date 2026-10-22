// web/src/api/session.ts
import type { LoginResponse } from './types'

const SESSION_KEY = 'predicare.session'
let currentSession: LoginResponse | null = null
const listeners = new Set<(session: LoginResponse | null) => void>()

// Fonction utilitaire pour tester si sessionStorage est dispo
function isStorageAvailable(): boolean {
  try {
    const test = '__test__'
    window.sessionStorage.setItem(test, test)
    window.sessionStorage.removeItem(test)
    return true
  } catch {
    return false
  }
}

const storageAvailable = isStorageAvailable()

function readSession(): LoginResponse | null {
  if (!storageAvailable) return null
  try {
    const serialized = window.sessionStorage.getItem(SESSION_KEY)
    if (!serialized) return null
    const session = JSON.parse(serialized) as LoginResponse
    if (!session.access_token || !session.user?.nom_complet || !session.user?.role) return null
    return session
  } catch {
    return null
  }
}

currentSession = readSession()

function publishSession(): void {
  listeners.forEach((listener) => listener(currentSession))
}

export function getStoredSession(): LoginResponse | null {
  return currentSession
}

export function setStoredSession(session: LoginResponse): void {
  currentSession = session
  if (storageAvailable) {
    try {
      window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(session))
    } catch {
      // Ignore
    }
  }
  publishSession()
}

export function clearStoredSession(): void {
  currentSession = null
  if (storageAvailable) {
    try {
      window.sessionStorage.removeItem(SESSION_KEY)
    } catch {
      // Ignore
    }
  }
  publishSession()
}

export function subscribeToSession(
  listener: (session: LoginResponse | null) => void,
): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}