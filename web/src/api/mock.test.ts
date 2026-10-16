import { afterEach, describe, expect, it } from 'vitest'
import { clearStoredSession, setStoredSession } from './session'
import { mockAccounts, resolveMock } from './mock'

interface ListPage {
  total: number
  page: number
  page_size: number
  items: Array<Record<string, unknown>>
}

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

  it('restreint chaque rôle à ses propres dossiers et masque le score', () => {
    const scopes = [
      { identifier: 'ASS-C60624BAFB', ownField: 'assure_id', ownValue: 'ASS-C60624BAFB' },
      { identifier: 'PR-0015', ownField: 'prestataire_id', ownValue: 'PR-0015' },
    ]
    for (const { identifier, ownField, ownValue } of scopes) {
      loginAs(identifier)
      const page = resolveMock<ListPage>('/claims?page=1&page_size=50', {})
      expect(page.items.length).toBeGreaterThan(0)
      for (const item of page.items) {
        expect(item[ownField]).toBe(ownValue)
        expect(item).not.toHaveProperty('score_fraude')
        expect(item).not.toHaveProperty('est_anomalie')
      }

      const detail = resolveMock<Record<string, unknown>>(`/claims/${String(page.items[0].facture_id)}`, {})
      expect(detail).toHaveProperty('lignes')
      expect(detail).not.toHaveProperty('score_fraude')
      expect(detail).not.toHaveProperty('est_anomalie')
    }
  })

  it('pagine côté serveur simulé sans modifier le total filtré', () => {
    loginAs('gestionnaire1')
    const first = resolveMock<ListPage>('/claims?page=1&page_size=5', {})
    const second = resolveMock<ListPage>('/claims?page=2&page_size=5', {})
    expect(first.page_size).toBe(5)
    expect(first.items).toHaveLength(5)
    expect(second.items).toHaveLength(5)
    expect(second.total).toBe(first.total)
    expect(first.items.map((item) => item.facture_id))
      .not.toEqual(second.items.map((item) => item.facture_id))
  })

  it('trie par score décroissant et isole les signaux à examiner', () => {
    loginAs('gestionnaire1')
    const all = resolveMock<ListPage>('/claims?page=1&page_size=50&sort=score_fraude:desc', {})
    const scores = all.items.map((item) => item.score_fraude as number)
    expect(scores).toEqual([...scores].sort((left, right) => right - left))

    const alerts = resolveMock<ListPage>('/claims?page=1&page_size=50&fraud_alert_only=true', {})
    expect(alerts.total).toBeLessThan(all.total)
    expect(alerts.items.length).toBeGreaterThan(0)
    for (const item of alerts.items) expect(item.est_anomalie).toBe(true)
  })

  it('filtre par identifiant de facture et par état de décision', () => {
    loginAs('gestionnaire1')
    const search = resolveMock<ListPage>('/claims?page=1&page_size=50&q=5639', {})
    expect(search.items.map((item) => item.facture_id)).toEqual(['FAC-00005639'])

    const all = resolveMock<ListPage>('/claims?page=1&page_size=50', {})
    const pending = resolveMock<ListPage>('/claims?page=1&page_size=50&decision_enregistree=false', {})
    expect(pending.total).toBe(all.total)

    resolveMock('/claims/FAC-00005639/decision', {
      method: 'POST',
      body: JSON.stringify({ decision: 'REJETE', motif: 'Contrôle demandé', montant_accorde: 0 }),
    })
    const decided = resolveMock<ListPage>('/claims?page=1&page_size=50&decision_enregistree=true', {})
    expect(decided.items.map((item) => item.facture_id)).toEqual(['FAC-00005639'])
  })

  it('refuse les prédictions et KPIs aux rôles assuré et professionnel', () => {
    for (const identifier of ['ASS-C60624BAFB', 'PR-0015']) {
      loginAs(identifier)
      expect(() => resolveMock('/predictions/latest', {})).toThrow(/réservées au gestionnaire/)
      expect(() => resolveMock('/dashboard/kpis', {})).toThrow(/réservées au gestionnaire/)
    }
  })
})