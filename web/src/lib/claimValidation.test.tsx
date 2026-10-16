import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createClaim } from '@/api/claims'
import type { ClaimDraft } from '@/api/types'
import { ClaimForm } from '@/features/claims/ClaimForm'
import { makeClaimPayload, mapValidationIssues, validateClaimDraft } from './claimValidation'

vi.mock('@/api/claims', () => ({ createClaim: vi.fn() }))

const validDraft: ClaimDraft = {
  numero_facture: 'F-2026-09871', prestataire_id: 'PR-0015', assure_id: 'ASS-C60624BAFB',
  ordonnance_id: 'ORD-001', date_soin: '2026-10-10', date_emission: '2026-10-11', date_reception: '2026-10-12',
  canal_reception: 'PAPIER_SCAN', mode_reglement: 'TIERS_PAYANT', part_assure: '9000',
  lines: [{ type_ligne: 'ACTE', code: 'CONS-GEN', quantite: '1', prix_unitaire: '20000' }],
}

function renderForm(profile: 'gestionnaire' | 'professionnel_sante' = 'gestionnaire') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(<QueryClientProvider client={client}><MemoryRouter><ClaimForm profile={profile} providerId="PR-0015" /></MemoryRouter></QueryClientProvider>)
}

describe('formulaire de facture', () => {
  beforeEach(() => vi.mocked(createClaim).mockReset())

  it('valide l’ordre des dates et refuse un identifiant d’assuré non pseudonyme', () => {
    const errors = validateClaimDraft({ ...validDraft, assure_id: 'nom-personnel', date_soin: '2026-10-13', date_emission: '2026-10-12', date_reception: '2026-10-11' })
    expect(errors.assure_id?.[0]).toContain('identifiant pseudonyme')
    expect(errors.date_emission).toBeDefined()
    expect(errors.date_reception).toBeDefined()
  })

  it('refuse les dates qui ne suivent pas le format ISO valide', () => {
    expect(validateClaimDraft({ ...validDraft, date_soin: '14/10/2026' }).date_soin).toContain('Utilisez le format AAAA-MM-JJ avec une date valide.')
    expect(validateClaimDraft({ ...validDraft, date_emission: '2026-02-30' }).date_emission).toContain('Utilisez le format AAAA-MM-JJ avec une date valide.')
  })

  it('n’exige date_reception et canal_reception que dans le profil gestionnaire', () => {
    expect(validateClaimDraft({ ...validDraft, date_reception: '', canal_reception: '' }, 'gestionnaire'))
      .toMatchObject({ date_reception: ['Ce champ est obligatoire.'], canal_reception: ['Ce champ est obligatoire.'] })
    expect(validateClaimDraft({ ...validDraft, date_reception: '', canal_reception: '' }, 'professionnel_sante'))
      .not.toHaveProperty('date_reception')
  })

  it('annonce les champs requis avant tout appel à l’API', async () => {
    renderForm()
    fireEvent.click(screen.getByRole('button', { name: /Soumettre la facture/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent('La facture contient des erreurs.')
    expect(screen.getByLabelText(/Numéro de facture/)).toHaveAttribute('aria-invalid', 'true')
    expect(createClaim).not.toHaveBeenCalled()
  })

  it('mappe les erreurs FastAPI 422 aux champs racine et aux lignes indexées', () => {
    expect(mapValidationIssues([
      { loc: ['body', 'lignes', 2, 'quantite'], msg: 'Quantité invalide.', type: 'int_parsing' },
      { loc: ['body', 'lignes', 0, 'code'], msg: 'Code inconnu.', type: 'value_error' },
      { loc: ['body', 'assure_id'], msg: 'Assuré inconnu.', type: 'value_error' },
    ])).toEqual({
      'lines.2.quantite': ['Quantité invalide.'],
      'lines.0.code': ['Code inconnu.'],
      assure_id: ['Assuré inconnu.'],
    })
  })

  it('sérialise POST /claims sans les colonnes de traitement', () => {
    const payload = makeClaimPayload(validDraft)
    expect(payload).toEqual({
      numero_facture: 'F-2026-09871', prestataire_id: 'PR-0015', assure_id: 'ASS-C60624BAFB',
      ordonnance_id: 'ORD-001', date_soin: '2026-10-10', date_emission: '2026-10-11', montant_total: 20_000, part_assure: 9_000,
      lignes: [{ num_ligne: 1, code: 'CONS-GEN', type_ligne: 'ACTE', quantite: 1, prix_unitaire: 20_000, montant_total: 20_000 }],
    })
    expect(payload).not.toHaveProperty('statut')
    expect(payload).not.toHaveProperty('motif_rejet')
    expect(payload).not.toHaveProperty('montant_pris_en_charge')
    expect(payload).not.toHaveProperty('date_traitement')
  })

  it('préremplit et verrouille le prestataire dans le profil santé', () => {
    renderForm('professionnel_sante')
    expect(screen.getByLabelText(/Identifiant du prestataire/)).toHaveValue('PR-0015')
    expect(screen.getByLabelText(/Identifiant du prestataire/)).toBeDisabled()
    expect(screen.getByLabelText(/Canal de réception/)).toHaveValue('Portail prestataire')
  })
})
