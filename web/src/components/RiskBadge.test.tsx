import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { RiskBadge } from './RiskBadge'

describe('RiskBadge', () => {
  it('écrit le signal en toutes lettres plutôt que de le confier à la couleur', () => {
    const { rerender } = render(<RiskBadge anomaly={true} />)
    expect(screen.getByText('Signal à examiner')).toBeInTheDocument()

    rerender(<RiskBadge anomaly={false} />)
    expect(screen.getByText('Aucun signal d’anomalie')).toBeInTheDocument()
  })

  it('ne présente jamais une analyse absente comme une absence d’anomalie', () => {
    render(<RiskBadge anomaly={null} />)
    expect(screen.getByText('Analyse non disponible')).toBeInTheDocument()
    expect(screen.queryByText('Aucun signal d’anomalie')).not.toBeInTheDocument()
  })
})