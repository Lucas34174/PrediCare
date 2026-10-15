import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createClaim } from '@/api/claims'
import type { ClaimDraft } from '@/api/types'
import { NewClaimPage } from '@/pages/NewClaimPage'
import { mapValidationIssues, validateClaimDraft } from './claimValidation'

vi.mock('@/api/claims', () => ({ createClaim: vi.fn() }))

const validDraft: ClaimDraft = {
  prestataire_id: 'PRE-0001', assure_id: 'ASS-C60624BAFB', contrat_id: 'CTR-000048',
  ordonnance_id: 'ORD-001', date_soin: '2026-10-10', date_facture: '2026-10-11',
  date_reception: '2026-10-12', canal: 'PORTAIL', mode_reglement: 'VIREMENT',
  attestation_prise_en_charge: false, entente_prealable: false,
  lines: [{ type: 'ACTE', code: 'CONS-GEN', quantite: '1', prix_unitaire: '20000' }],
}

function renderForm() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(<QueryClientProvider client={client}><MemoryRouter><NewClaimPage /></MemoryRouter></QueryClientProvider>)
}

describe('validation de facture', () => {
  beforeEach(() => vi.mocked(createClaim).mockReset())

  it('signale les dates dans le mauvais ordre et les identifiants non pseudonymes', () => {
    const errors = validateClaimDraft({
      ...validDraft,
      assure_id: 'nom-personnel',
      date_soin: '2026-10-13',
      date_facture: '2026-10-12',
      date_reception: '2026-10-11',
    })
    expect(errors.assure_id?.[0]).toContain('identifiant pseudonyme')
    expect(errors.date_facture).toBeDefined()
    expect(errors.date_reception).toBeDefined()
  })
  it('refuse les dates qui ne suivent pas le format ISO valide', () => {
    expect(validateClaimDraft({ ...validDraft, date_soin: '14/10/2026' }).date_soin)
      .toContain('Utilisez le format AAAA-MM-JJ avec une date valide.')
    expect(validateClaimDraft({ ...validDraft, date_facture: '2026-02-30' }).date_facture)
      .toContain('Utilisez le format AAAA-MM-JJ avec une date valide.')
  })

  it('annonce les champs obligatoires avant tout appel à l’API', async () => {
    renderForm()
    fireEvent.click(screen.getByRole('button', { name: /Soumettre la facture/ }))

    expect(await screen.findByRole('alert')).toHaveTextContent('La facture contient des erreurs.')
    expect(screen.getByLabelText(/Identifiant du prestataire/)).toHaveAttribute('aria-invalid', 'true')
    expect(createClaim).not.toHaveBeenCalled()
  })

  it('convertit les emplacements FastAPI en chemins de champs des lignes', () => {
    expect(mapValidationIssues([
      { loc: ['body', 'lignes', 2, 'quantite'], msg: 'Quantité invalide.', type: 'int_parsing' },
      { loc: ['body', 'assure_id'], msg: 'Assuré inconnu.', type: 'value_error' },
    ])).toEqual({
      'lines.2.quantite': ['Quantité invalide.'],
      assure_id: ['Assuré inconnu.'],
    })
  })
})
