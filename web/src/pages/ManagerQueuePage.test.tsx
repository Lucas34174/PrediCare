import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { mockAccounts } from '@/api/mock'
import { clearStoredSession, setStoredSession } from '@/api/session'
import { ManagerQueuePage } from './ManagerQueuePage'

function renderQueue() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/gestionnaire/dossiers']}>
        <ManagerQueuePage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function visibleScores(): number[] {
  const table = screen.getByRole('table')
  return within(table).getAllByRole('row').slice(1).map((row) => {
    const label = within(row).getByText(/^Score \d+ %$/).textContent ?? ''
    return Number(label.replace(/\D/g, ''))
  })
}

/** Cible le résumé de pagination renvoyé par le serveur simulé, ex. « 1–8 sur 16 ». */
function summaryShowing(fragment: string) {
  return (_content: string, element: Element | null) =>
    element?.tagName === 'P' && (element.textContent ?? '').includes(fragment)
}

beforeEach(() => {
  const account = mockAccounts.find((candidate) => candidate.identifier === 'gestionnaire1')
  if (!account) throw new Error('Compte gestionnaire synthétique absent')
  setStoredSession(account.response)
})

afterEach(() => clearStoredSession())

describe('file d’examen du gestionnaire', () => {
  it('présente les signaux à examiner, classés par score décroissant', async () => {
    renderQueue()
    const table = await screen.findByRole('table')

    expect(within(table).getAllByText('Signal à examiner')).toHaveLength(8)
    expect(within(table).queryByText('Aucun signal d’anomalie')).not.toBeInTheDocument()
    expect(await screen.findByText(summaryShowing('1–8 sur 10'))).toBeInTheDocument()
    expect(screen.getByText('1 / 2')).toBeInTheDocument()

    const scores = visibleScores()
    expect(scores).toHaveLength(8)
    expect(scores).toEqual([...scores].sort((left, right) => right - left))
  })

  it('énonce que le score n’est pas une preuve de fraude', async () => {
    renderQueue()
    await screen.findByRole('table')
    expect(screen.getByText(/une aide à la décision, jamais une preuve de fraude/)).toBeInTheDocument()
    expect(screen.queryByText(/fraude confirmée/i)).not.toBeInTheDocument()
  })

  it('pagine côté serveur sur tous les dossiers', async () => {
    const user = userEvent.setup()
    renderQueue()
    await screen.findByRole('table')
    expect(screen.getByRole('link', { name: 'FAC-00005641' })).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Signal'), 'all')
    expect(await screen.findByText(summaryShowing('1–8 sur 16'))).toBeInTheDocument()
    expect(screen.getByText('1 / 2')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'FAC-00005641' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Page suivante' }))
    expect(await screen.findByText(summaryShowing('9–16 sur 16'))).toBeInTheDocument()
    expect(screen.getByText('2 / 2')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'FAC-00005641' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'FAC-00005637' })).toBeInTheDocument()
  })

  it('recherche un dossier par identifiant de facture', async () => {
    const user = userEvent.setup()
    renderQueue()
    await screen.findByRole('table')
    await user.selectOptions(screen.getByLabelText('Signal'), 'all')
    await screen.findByText(summaryShowing('1–8 sur 16'))
    await user.type(screen.getByLabelText('Identifiant de facture'), '5639')

    await waitFor(() => {
      expect(screen.queryByRole('link', { name: 'FAC-00005641' })).not.toBeInTheDocument()
    })
    expect(screen.getByRole('link', { name: 'FAC-00005639' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'FAC-00005637' })).not.toBeInTheDocument()
  })

  it('annonce l’absence de résultat et permet de réinitialiser', async () => {
    const user = userEvent.setup()
    renderQueue()
    await screen.findByRole('table')
    await user.type(screen.getByLabelText('Identifiant de facture'), 'ZZZ-00000000')

    expect(await screen.findByText('Aucun dossier ne correspond')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Réinitialiser les filtres' }))
    expect(await screen.findByRole('table')).toBeInTheDocument()
  })
})