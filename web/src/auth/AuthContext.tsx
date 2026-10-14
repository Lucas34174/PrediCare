import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type PropsWithChildren,
} from 'react'
import { request } from '@/api/request'
import {
  clearStoredSession,
  getStoredSession,
  setStoredSession,
  subscribeToSession,
} from '@/api/session'
import type { AuthUser, LoginRequest, LoginResponse, Role } from '@/api/types'

interface AuthContextValue {
  user: AuthUser | null
  role: Role | null
  isAuthenticated: boolean
  login: (credentials: LoginRequest) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: PropsWithChildren) {
  const [session, setSession] = useState<LoginResponse | null>(() => getStoredSession())

  useEffect(() => subscribeToSession(setSession), [])

  const login = useCallback(async (credentials: LoginRequest) => {
    const response = await request<LoginResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(credentials),
    })
    setStoredSession(response)
  }, [])

  const logout = useCallback(() => clearStoredSession(), [])
  const user = session
    ? { display_name: session.display_name, role: session.role }
    : null

  return (
    <AuthContext.Provider
      value={{ user, role: session?.role ?? null, isAuthenticated: Boolean(session), login, logout }}
    >
      {children}
    </AuthContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth doit être utilisé dans AuthProvider.')
  return context
}
