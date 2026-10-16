import { afterEach, describe, expect, it } from 'vitest'
import { clearStoredSession, setStoredSession } from './session'
import { mockAccounts, resolveMock } from './mock'

function loginAs(identifier: string) {
  const account = mockAccounts.find((candidate) => candidate.identifier === identifier)
  if (!account) throw new Error(`Compte synthétique absent : ${identifier}`)
  setStoredSession(account.response)
}

afterEach(() => clearStoredSession())

describe('mock API contractuel', () => {
  it('accepte identifier et renvoie le profil imbriqué du contrat', () => {
    const response = resolveMock<{ user: { role: string; identifier: string } }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ identifier: 'ASS-C60624BAFB', password: 'Demo2026!' }),
    })
    expect(response.user).toMatchObject({ role: 'assure', identifier: 'ASS-C60624BAFB' })
  })

  it('applique le périmètre assuré et retire les colonnes de score de la liste et du détail', () => {
    loginAs('ASS-C60624BAFB')
    const page = resolveMock<{ total: number; items: Array<Record<string, unknown>> }>('/claims?page=1&page_size=20', {})
    expect(page.total).toBe(3)
    expect(page.items[0]).not.toHaveProperty('score_fraude')
    expect(page.items[0]).not.toHaveProperty('est_anomalie')

    const detail = resolveMock<Record<string, unknown>>(`/claims/${String(page.items[0].facture_id)}`, {})
    expect(detail).toHaveProperty('lignes')
    expect(detail).not.toHaveProperty('score_fraude')
  })

  it('pagine côté serveur simulé sans modifier le total filtré', () => {
    loginAs('gestionnaire1')
    const first = resolveMock<{ total: number; page: number; page_size: number; items: unknown[] }>('/claims?page=1&page_size=1', {})
    const second = resolveMock<{ total: number; page: number; items: unknown[] }>('/claims?page=2&page_size=1', {})
    expect(first).toMatchObject({ total: 3, page: 1, page_size: 1 })
    expect(second).toMatchObject({ total: 3, page: 2 })
    expect(first.items).toHaveLength(1)
    expect(second.items).toHaveLength(1)
  })

  it('refuse les prédictions et KPIs aux rôles assuré et professionnel', () => {
    for (const identifier of ['ASS-C60624BAFB', 'PR-0015']) {
      loginAs(identifier)
      expect(() => resolveMock('/predictions/latest', {})).toThrow(/réservées au gestionnaire/)
      expect(() => resolveMock('/dashboard/kpis', {})).toThrow(/réservées au gestionnaire/)
    }
  })
})
