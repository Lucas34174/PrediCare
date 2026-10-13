import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { LogOut, Menu, Moon, ShieldCheck, Sun, X } from 'lucide-react'
import { useAuth } from '@/auth/AuthContext'
import { roleLabels, roleMenus } from './navigation'

interface AppLayoutProps {
  dark: boolean
  onToggleTheme: () => void
}

export function AppLayout({ dark, onToggleTheme }: AppLayoutProps) {
  const { user, logout } = useAuth()
  const [mobileOpen, setMobileOpen] = useState(false)
  if (!user) return null

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileOpen ? 'sidebar-open' : ''}`} aria-label="Navigation principale">
        <NavLink to="/app" aria-label="PrediCare, accueil" className="brand-lockup" onClick={() => setMobileOpen(false)}>
          <span className="brand-mark"><ShieldCheck aria-hidden="true" size={22} /></span>
          <span className="brand-word">Predi<span>Care</span><small>TPA · MADAGASCAR</small></span>
        </NavLink>
        <div className="workspace-chip"><span className="workspace-dot" /> Espace sécurisé <span className="workspace-code">MG</span></div>
        <p className="nav-label">ESPACE DE TRAVAIL</p>
        <nav className="primary-nav">
          {roleMenus[user.role].map(({ label, path, icon: Icon }) => (
            <NavLink key={path} to={path} aria-label={label} title={label} end={path === '/app'} onClick={() => setMobileOpen(false)} className={({ isActive }) => `nav-item ${isActive ? 'nav-item-active' : ''}`}>
              <Icon aria-hidden="true" size={18} /><span>{label}</span>{path !== '/app' && <span className="nav-arrow">↗</span>}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom"><div className="support-note"><span className="support-line" /><strong>Un accompagnement<br />qui veille sur vous.</strong><small>Tiers payant · Santé · Confiance</small></div>
          <div className="sidebar-foot"><span>© 2026 PrediCare</span><span>v0.4.2</span></div></div>
      </aside>
      {mobileOpen && <button className="mobile-scrim" aria-label="Fermer le menu" onClick={() => setMobileOpen(false)} />}
      <div className="main-column">
        <header className="topbar">
          <button className="icon-button mobile-menu-button" aria-label={mobileOpen ? 'Fermer le menu' : 'Ouvrir le menu'} onClick={() => setMobileOpen((open) => !open)}>{mobileOpen ? <X size={20} /> : <Menu size={20} />}</button>
          <div className="breadcrumb"><span>PrediCare</span><span className="crumb-divider">/</span><strong>Mon espace</strong></div>
          <div className="topbar-actions">
            <button className="icon-button theme-button" onClick={onToggleTheme} aria-label={dark ? 'Activer le mode clair' : 'Activer le mode sombre'} title={dark ? 'Mode clair' : 'Mode sombre'}>{dark ? <Sun size={18} /> : <Moon size={18} />}</button>
            <span className="topbar-divider" />
            <div className="user-chip"><span className="avatar">{user.display_name.split(' ').map((part) => part[0]).slice(0, 2).join('')}</span><span className="user-info"><strong>{user.display_name}</strong><small>{roleLabels[user.role]}</small></span></div>
            <button className="logout-button" onClick={logout}><LogOut aria-hidden="true" size={17} /><span>Se déconnecter</span></button>
          </div>
        </header>
        <main className="main-content"><Outlet /></main>
      </div>
    </div>
  )
}
