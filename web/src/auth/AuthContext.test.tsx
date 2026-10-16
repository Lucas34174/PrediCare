import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { AuthProvider, useAuth } from './AuthContext'
import { clearStoredSession } from '@/api/session'

function AuthProbe() {
  const { user, role, isAuthenticated, login, logout } = useAuth()
  return (
    <section>
      <output>{isAuthenticated ? `${user?.display_name}:${role}` : 'Déconnecté'}</output>
      <button onClick={() => void login({ identifier: 'ASS-C60624BAFB', password: 'Demo2026!' })}>Connexion</button>
      <button onClick={logout}>Déconnexion</button>
    </section>
  )
}

describe('AuthContext', () => {
  beforeEach(() => {
    clearStoredSession()
    sessionStorage.clear()
  })

  afterEach(() => {
    clearStoredSession()
    sessionStorage.clear()
  })

  it('connecte un utilisateur de démonstration et conserve la session en sessionStorage', async () => {
    render(<AuthProvider><AuthProbe /></AuthProvider>)

    fireEvent.click(screen.getByRole('button', { name: 'Connexion' }))

    expect(await screen.findByText('Tahina Andriam:assure')).toBeInTheDocument()
    expect(JSON.parse(sessionStorage.getItem('predicare.session') ?? '{}')).toMatchObject({
      user: { role: 'assure', nom_complet: 'Tahina Andriam' },
    })
  })

  it('efface la session à la déconnexion', async () => {
    render(<AuthProvider><AuthProbe /></AuthProvider>)
    fireEvent.click(screen.getByRole('button', { name: 'Connexion' }))
    expect(await screen.findByText('Tahina Andriam:assure')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Déconnexion' }))

    expect(screen.getByText('Déconnecté')).toBeInTheDocument()
    expect(sessionStorage.getItem('predicare.session')).toBeNull()
  })

  it('rejette des identifiants incorrects sans ouvrir de session', async () => {
    function InvalidCredentials() {
      const { login } = useAuth()
      const [message, setMessage] = useState('')
      return (
        <>
          <button onClick={() => void login({ identifier: 'identifiant-invalide', password: 'incorrect' }).catch((error: Error) => setMessage(error.message))}>Essayer</button>
          <output>{message}</output>
        </>
      )
    }

    render(<AuthProvider><InvalidCredentials /></AuthProvider>)
    fireEvent.click(screen.getByRole('button', { name: 'Essayer' }))

    expect(await screen.findByText('Identifiant ou mot de passe invalide. Vérifiez vos informations puis réessayez.')).toBeInTheDocument()
    expect(sessionStorage.getItem('predicare.session')).toBeNull()
  })
})
