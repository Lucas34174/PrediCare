import { render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { clearStoredSession, setStoredSession } from '@/api/session'
import type { LoginResponse } from '@/api/types'
import { AuthProvider } from './AuthContext'
import { ProtectedRoute } from './ProtectedRoute'

const assureSession: LoginResponse = {
  access_token: 'test-token',
  token_type: 'bearer',
  role: 'assure',
  display_name: 'Tahina Andriam',
}

function renderProtectedRoute(initialEntry = '/admin') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<p>Connexion</p>} />
          <Route path="/403" element={<p>Accès refusé</p>} />
          <Route element={<ProtectedRoute allowedRoles={['admin']} />}>
            <Route path="/admin" element={<p>Administration</p>} />
          </Route>
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('ProtectedRoute', () => {
  beforeEach(() => {
    clearStoredSession()
    sessionStorage.clear()
  })

  afterEach(() => {
    clearStoredSession()
    sessionStorage.clear()
  })

  it('redirige vers la connexion si aucune session n’existe', () => {
    renderProtectedRoute()
    expect(screen.getByText('Connexion')).toBeInTheDocument()
  })

  it('affiche 403 lorsqu’un rôle connecté ne possède pas l’accès', () => {
    setStoredSession(assureSession)
    renderProtectedRoute()
    expect(screen.getByText('Accès refusé')).toBeInTheDocument()
  })

  it('affiche la page autorisée pour le rôle correspondant', () => {
    setStoredSession({ ...assureSession, role: 'admin' })
    renderProtectedRoute()
    expect(screen.getByText('Administration')).toBeInTheDocument()
  })
})
