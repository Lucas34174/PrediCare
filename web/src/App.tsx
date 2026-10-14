import { useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from '@/auth/AuthContext'
import { ProtectedRoute } from '@/auth/ProtectedRoute'
import { AppLayout } from '@/components/AppLayout'
import { rolePaths } from '@/components/navigation'
import { DashboardPage } from '@/pages/DashboardPage'
import { LoginPage } from '@/pages/LoginPage'
import { ForbiddenPage, NotFoundPage } from '@/pages/StatusPages'
import type { Role } from '@/api/types'
import './App.css'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 60_000 } },
})
const roles = Object.keys(rolePaths) as Role[]

function AppRoutes() {
  const [dark, setDark] = useState(false)
  return (
    <div className={dark ? 'app-root dark' : 'app-root'}>
      <Routes>
        <Route path="/login" element={<LoginPage dark={dark} onToggleTheme={() => setDark((value) => !value)} />} />
        <Route path="/403" element={<ForbiddenPage />} />
        <Route element={<ProtectedRoute><AppLayout dark={dark} onToggleTheme={() => setDark((value) => !value)} /></ProtectedRoute>}>
          <Route path="/app" element={<DashboardPage />} />
          {roles.map((role) => <Route key={role} path={rolePaths[role].slice(1)} element={<ProtectedRoute allowedRoles={[role]}><DashboardPage /></ProtectedRoute>} />)}
        </Route>
        <Route path="/" element={<Navigate to="/app" replace />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </div>
  )
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter><AppRoutes /></BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}

export default App
