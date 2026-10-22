import { Suspense, lazy, useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { ProtectedRoute } from '@/auth/ProtectedRoute'
import { AppLayout } from '@/components/AppLayout'
// import { rolePaths } from '@/components/navigation'
import { DashboardPage } from '@/pages/DashboardPage'
import { LoginPage } from '@/pages/LoginPage'
import { ManagerQueuePage } from '@/pages/ManagerQueuePage'
import { ForbiddenPage, NotFoundPage } from '@/pages/StatusPages'
import { ClaimReceiptPage, NewProClaimPage } from '@/pages/NewClaimPage'
// import type { UiRole } from '@/api/types'
import './App.css'
import { AdminDashboardPage } from '@/pages/AdminDashboardPage'
import { AdminConfigPage } from '@/pages/AdminConfigPage'
import { AdminModelsPage } from '@/pages/AdminModelsPage'
import { AssureDashboardPage } from '@/pages/AssureDashboardPage'
import { AssureClaimDetailPage } from '@/pages/AssureClaimDetailPage'
import { AssureChatPage } from '@/pages/AssureChatPage'
import { AuthProvider, useAuth } from '@/auth/AuthContext'
import { ProDashboardPage } from '@/pages/ProDashboardPage'
import { ProDossierListPage, ProDossierDetailPage } from '@/pages/ProDossierPage'
import { AssureDashboardHome } from '@/pages/AssureDashboardHome'
import { PublicDashboardPage } from '@/pages/PublicDashboardPage'

const ManagerClaimDetailPage = lazy(() =>
  import('@/pages/ManagerClaimDetailPage').then((module) => ({ default: module.ManagerClaimDetailPage })),
)

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 60_000 } },
})
// const roles = Object.keys(rolePaths) as UiRole[]

// function useAuth(): { role: any } {
//   throw new Error('Function not implemented.')
// }

  function RoleDashboardRouter() {
    const { role } = useAuth()
    if (role === 'professionnel_sante') return <ProDashboardPage />
    if (role === 'assure') return <AssureDashboardHome />
    if (role === 'admin') return <AdminDashboardPage />
    return <DashboardPage />
  }

// function AppRoutes() {
  // const [dark, setDark] = useState(false)
  // return (
    // <div className={dark ? 'app-root dark' : 'app-root'}>
      {/* <Routes> */}
        {/* <Route path="/login" element={<LoginPage dark={dark} onToggleTheme={() => setDark((value) => !value)} />} /> */}
        {/* <Route path="/403" element={<ForbiddenPage />} /> */}
        {/* <Route element={<ProtectedRoute><AppLayout dark={dark} onToggleTheme={() => setDark((value) => !value)} /></ProtectedRoute>}> */}
          {/* <Route path="/app" element={<RoleDashboardRouter />} /> */}
          {/* <Route path="/gestionnaire/dossiers" element={<ProtectedRoute allowedRoles={['gestionnaire']}><ManagerQueuePage /></ProtectedRoute>} /> */}
          {/* <Route path="/gestionnaire/dossiers/:factureId" element={<ProtectedRoute allowedRoles={['gestionnaire']}><Suspense fallback={<PageFallback />}><ManagerClaimDetailPage /></Suspense></ProtectedRoute>} /> */}
          {/* {roles.map((role) => <Route key={role} path={rolePaths[role].slice(1)} element={<ProtectedRoute allowedRoles={[role]}><DashboardPage /></ProtectedRoute>} />)} */}
          {/* <Route */}
            // path="/professionnel-sante"
            // element={<Navigate to="/professionnel-sante/factures/nouvelle" replace />}
          // />
          {/* <Route */}
            // path="/professionnel-sante/factures/nouvelle"
            // element={
              // <ProtectedRoute allowedRoles={['professionnel_sante']}>
                {/* <NewProClaimPage /> */}
              {/* </ProtectedRoute> */}
            // }
          // />
          {/* <Route */}
            // path="/professionnel-sante/factures/:claimId"
            // element={
              // <ProtectedRoute allowedRoles={['professionnel_sante']}>
                {/* <ClaimReceiptPage /> */}
              {/* </ProtectedRoute> */}
            // }
          // />
          {/* <Route */}
            // path="/professionnel-sante/dossiers"
            // element={
              // <ProtectedRoute allowedRoles={['professionnel_sante']}>
                {/* <DashboardPage /> */}
              {/* </ProtectedRoute> */}
            // }
          // />
          {/* <Route */}
            // path="/admin/factures/nouvelle"
            // element={
              // <ProtectedRoute allowedRoles={['admin']}>
                {/* <NewClaimPage /> */}
              {/* </ProtectedRoute> */}
            // }
          // />
          {/* <Route */}
            // path="/admin/factures/:claimId"
            // element={
              // <ProtectedRoute allowedRoles={['admin']}>
                {/* <ClaimReceiptPage /> */}
              {/* </ProtectedRoute> */}
            // }
          // />
          {/* <Route path="/admin" element={<ProtectedRoute allowedRoles={['admin']}><AdminDashboardPage /></ProtectedRoute>} /> */}
          {/* <Route path="/admin/config" element={<ProtectedRoute allowedRoles={['admin']}><AdminConfigPage /></ProtectedRoute>} /> */}
          {/* <Route path="/admin/models" element={<ProtectedRoute allowedRoles={['admin']}><AdminModelsPage /></ProtectedRoute>} /> */}
          {/* <Route path="/assure" element={<ProtectedRoute allowedRoles={['assure']}><AssureDashboardPage /></ProtectedRoute>} /> */}
          {/* <Route path="/assure/dossiers/:factureId" element={<ProtectedRoute allowedRoles={['assure']}><AssureClaimDetailPage /></ProtectedRoute>} /> */}
          {/* <Route path="/assure/chat" element={<ProtectedRoute allowedRoles={['assure']}><AssureChatPage /></ProtectedRoute>} /> */}
        {/* </Route> */}
        {/* <Route path="/" element={<Navigate to="/app" replace />} /> */}
        {/* <Route path="*" element={<NotFoundPage />} /> */}
        {/*  */}
      {/* </Routes> */}
    {/* </div> */}
  // )
// }

function AppRoutes() {
  const [dark, setDark] = useState(false)
  return (
    <div className={dark ? 'app-root dark' : 'app-root'}>
      <Routes>
        {/* 1. Routes publiques */}
        <Route path="/login" element={<LoginPage dark={dark} onToggleTheme={() => setDark((v) => !v)} />} />
        <Route path="/403" element={<ForbiddenPage />} />

        {/* 2. Routes protégées AVEC le Layout (menu latéral) */}
        <Route element={<ProtectedRoute><AppLayout dark={dark} onToggleTheme={() => setDark((v) => !v)} /></ProtectedRoute>}>
          
          {/* Dashboard générique */}
          <Route path="/app" element={<RoleDashboardRouter />} />

          {/* Gestionnaire */}
          <Route path="/gestionnaire/dossiers" element={<ProtectedRoute allowedRoles={['gestionnaire']}><ManagerQueuePage /></ProtectedRoute>} />
          <Route path="/gestionnaire/dossiers/:factureId" element={<ProtectedRoute allowedRoles={['gestionnaire']}><Suspense fallback={<PageFallback />}><ManagerClaimDetailPage /></Suspense></ProtectedRoute>} />

          {/* Assuré */}
          <Route path="/assure" element={<ProtectedRoute allowedRoles={['assure']}><AssureDashboardPage /></ProtectedRoute>} />
          <Route path="/assure/dossiers/:factureId" element={<ProtectedRoute allowedRoles={['assure']}><AssureClaimDetailPage /></ProtectedRoute>} />
          <Route path="/assure/chat" element={<ProtectedRoute allowedRoles={['assure']}><AssureChatPage /></ProtectedRoute>} />

          {/* Admin */}
          <Route path="/admin" element={<ProtectedRoute allowedRoles={['admin']}><AdminDashboardPage /></ProtectedRoute>} />
          <Route path="/admin/config" element={<ProtectedRoute allowedRoles={['admin']}><AdminConfigPage /></ProtectedRoute>} />
          <Route path="/admin/models" element={<ProtectedRoute allowedRoles={['admin']}><AdminModelsPage /></ProtectedRoute>} />
          {/* {user.role === 'gestionnaire' || user.role === 'administrateur' ? ( */}
          <Route path="/dashboardi" element={<DashboardPage />} />
          {/* // ) : null} */}

          {/* Pro de santé */}
          <Route path="/professionnel-sante/factures/nouvelle" element={<ProtectedRoute allowedRoles={['professionnel_sante']}><NewProClaimPage /></ProtectedRoute>} />
          <Route path="/professionnel-sante/factures/:claimId" element={<ProtectedRoute allowedRoles={['professionnel_sante']}><ClaimReceiptPage /></ProtectedRoute>} />
          <Route path="/professionnel-sante/dossiers" element={<ProtectedRoute allowedRoles={['professionnel_sante']}><ProDossierListPage /></ProtectedRoute>} />
          <Route path="/professionnel-sante/dossiers/:factureId" element={<ProtectedRoute allowedRoles={['professionnel_sante']}><ProDossierDetailPage /></ProtectedRoute>} />
          
        </Route>

        {/* 3. Route par défaut */}
        <Route path="/" element={<Navigate to="/app" replace />} />
        <Route path="*" element={<NotFoundPage />} />
        <Route path="/dashboard-public" element={<PublicDashboardPage />} />
      </Routes>
    </div>
  )
}

function PageFallback() {
  return (
    <div style={{ padding: '40px', textAlign: 'center', color: 'var(--ink-muted)' }}>
      Chargement…
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

