import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { mockAccounts } from '@/api/mock'
import { clearStoredSession, setStoredSession } from '@/api/session'
import { ManagerClaimDetailPage } from './ManagerClaimDetailPage'

function loginAs(identifier: string) {
  const account = mockAccounts.find((candidate) => candidate.identifier === identifier)
  if (!account) throw new Error(`Compte synthétique absent : ${identifier}`)
  setStoredSession(account.response)
}

function renderDetail(factureId: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/gestionnaire/dossiers/${factureId}`]}>
        <Routes>
          <Route path="/gestionnaire/dossiers/:factureId" element={<ManagerClaimDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => clearStoredSession())

describe('fiche dossier du gestionnaire', () => {
  beforeEach(() => loginAs('gestionnaire1'))

  it('affiche le résumé, le score et l’avertissement éthique', async () => {
    renderDetail('FAC-00005639')

    expect(await screen.findByRole('heading', { name: 'FAC-00005639' })).toBeInTheDocument()
    expect(screen.getByText('Score du modèle').parentElement).toHaveTextContent('88%')
    expect(screen.getByText('Signal à examiner')).toBeInTheDocument()
    expect(screen.getByText('v1.0.0-xgb')).toBeInTheDocument()
    expect(
      screen.getByText('Signal à examiner : ce score est une aide à la décision, pas une preuve de fraude.'),
    ).toBeInTheDocument()
    expect(screen.queryByText(/fraude confirmée/i)).not.toBeInTheDocument()

    const rows = within(screen.getByRole('table')).getAllByRole('row')
    expect(rows).toHaveLength(2)
    expect(screen.getByText('IMG-SCANNER')).toBeInTheDocument()
    expect(screen.getByText('Part de l’assuré')).toBeInTheDocument()
    expect(screen.getByText('Montant demandé')).toBeInTheDocument()
    expect(screen.getByText('Montant total')).toBeInTheDocument()
    expect(screen.getAllByText(/51\s000 MGA/)).toHaveLength(1)
  })

  it('traduit le motif de rejet', async () => {
    renderDetail('FAC-00005639')
    expect(await screen.findByText('Entente préalable absente')).toBeInTheDocument()
  })

  it('écrit le sens de chaque facteur explicatif', async () => {
    renderDetail('FAC-00005639')
    await screen.findByRole('heading', { name: 'FAC-00005639' })

    const factors = within(screen.getByRole('list')).getAllByRole('listitem')
    expect(factors).toHaveLength(2)
    expect(factors[0]).toHaveTextContent('Écart au tarif conventionné')
    expect(factors[0]).toHaveTextContent('augmente le risque')
    expect(factors[0]).toHaveTextContent('+0,38')
    expect(factors[0]).toHaveTextContent('Écart au tarif de référence.')
    expect(factors[1]).toHaveTextContent('Soin réalisé un jour de fermeture')
  })

  it('annonce l’échec d’ouverture d’un dossier inconnu', async () => {
    renderDetail('FAC-99999999')
    expect(await screen.findByText('Ce dossier n’a pas pu être ouvert')).toBeInTheDocument()
  })

  it('ne divulgue ni score ni facteur lorsque l’API refuse l’analyse', async () => {
    loginAs('ASS-C60624BAFB')
    renderDetail('FAC-00005637')

    expect(await screen.findByRole('heading', { name: 'FAC-00005637' })).toBeInTheDocument()
    expect(await screen.findByText('L’analyse de ce dossier n’a pas pu être récupérée.')).toBeInTheDocument()

    const scoreBlock = screen.getByText('Score du modèle').parentElement
    expect(scoreBlock).toHaveTextContent('—')
    expect(scoreBlock).not.toHaveTextContent(/\d/)
    expect(screen.queryByText(/pas une preuve de fraude/)).not.toBeInTheDocument()
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })
})