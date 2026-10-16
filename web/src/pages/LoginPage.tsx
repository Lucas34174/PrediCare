import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ArrowRight, Check, Eye, EyeOff, HeartPulse, LockKeyhole, Moon, ShieldCheck, Sparkles, Sun } from 'lucide-react'
import { ApiError } from '@/api/errors'
import { mockAccounts } from '@/api/mock'
import { useAuth } from '@/auth/AuthContext'
import { roleLabels } from '@/components/navigation'
import type { UiRole } from '@/api/types'

interface LocationState {
  from?: { pathname?: string }
}

const roleDescriptions: Record<UiRole, string> = {
  gestionnaire: 'Gestion des dossiers',
  professionnel_sante: 'Espace établissement',
  assure: 'Espace assuré',
  admin: 'Administration',
}

export function LoginPage({ dark, onToggleTheme }: { dark: boolean; onToggleTheme: () => void }) {
  const { isAuthenticated, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (isAuthenticated) return <Navigate to="/app" replace />

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await login({ identifier: identifier.trim(), password })
      const destination = (location.state as LocationState | null)?.from?.pathname ?? '/app'
      navigate(destination, { replace: true })
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Connexion impossible. Vérifiez votre connexion puis réessayez.')
    } finally {
      setSubmitting(false)
    }
  }

  function selectAccount(accountIdentifier: string) {
    setIdentifier(accountIdentifier)
    setPassword('Demo2026!')
    setError('')
  }

  return (
    <main className="login-screen">
      <section className="login-story" aria-label="PrediCare, tiers payant de santé">
        <div className="login-brand"><span className="brand-mark"><ShieldCheck aria-hidden="true" size={23} /></span><span className="brand-word">Predi<span>Care</span><small>TPA · MADAGASCAR</small></span></div>
        <div className="story-content">
          <div className="story-label"><span className="story-label-mark"><HeartPulse aria-hidden="true" size={15} /></span> LA SANTÉ, AVEC PLUS DE CLARTÉ</div>
          <h1>Prendre soin.<br /><em>En toute confiance.</em></h1>
          <p>Un tiers payant plus simple, pensé pour accompagner chaque parcours de santé à Madagascar.</p>
          <div className="story-points"><div><span><Check size={14} /></span> Un suivi transparent</div><div><span><Check size={14} /></span> Des décisions expliquées</div></div>
        </div>
        <div className="story-art" aria-hidden="true"><div className="art-sun" /><div className="art-ring ring-a" /><div className="art-ring ring-b" /><div className="art-cross"><span /><i /></div><span className="art-caption">UN MÊME ENGAGEMENT, POUR TOUS</span><span className="art-serial">PC — 014 / MG</span></div>
        <div className="story-footer"><span>© 2026 PrediCare Madagascar</span><span>Une plateforme de confiance <span className="footer-dot">·</span> 01</span></div>
      </section>
      <section className="login-panel" aria-label="Connexion à votre espace">
        <div className="login-panel-top"><span className="secure-label"><span /> Accès sécurisé</span><div className="login-top-actions"><button type="button" className="icon-button login-theme-button" onClick={onToggleTheme} aria-label={dark ? 'Activer le mode clair' : 'Activer le mode sombre'}>{dark ? <Sun size={17} /> : <Moon size={17} />}</button><button type="button" className="login-help" title="Accès de démonstration">Aide à la connexion <ArrowRight aria-hidden="true" size={14} /></button></div></div>
        <div className="login-form-wrap">
          <div className="form-intro"><span className="form-icon"><LockKeyhole aria-hidden="true" size={19} /></span><p className="eyebrow">VOTRE ESPACE, EN UN INSTANT</p><h2>Content de vous revoir.</h2><p>Connectez-vous pour accéder à votre espace PrediCare.</p></div>
          <form className="login-form" onSubmit={handleSubmit}>
            <label htmlFor="identifier">Identifiant</label>
            <div className="input-wrap"><input id="identifier" name="identifier" type="text" autoComplete="username" placeholder="Votre identifiant" value={identifier} onChange={(event) => setIdentifier(event.target.value)} required /></div>
            <div className="password-label-row"><label htmlFor="password">Mot de passe</label><button type="button" className="forgot-link" onClick={() => setError('Pour cette démonstration, utilisez un compte de test ci-dessous.')}>Mot de passe oublié ?</button></div>
            <div className="input-wrap password-wrap"><input id="password" name="password" type={showPassword ? 'text' : 'password'} autoComplete="current-password" placeholder="Votre mot de passe" value={password} onChange={(event) => setPassword(event.target.value)} required /><button type="button" aria-label={showPassword ? 'Masquer le mot de passe' : 'Afficher le mot de passe'} onClick={() => setShowPassword((visible) => !visible)}>{showPassword ? <EyeOff size={18} /> : <Eye size={18} />}</button></div>
            {error && <div className="form-error" role="alert"><span>!</span><p>{error}</p></div>}
            <button className="submit-button" type="submit" disabled={submitting}>{submitting ? 'Connexion en cours…' : 'Accéder à mon espace'}<ArrowRight aria-hidden="true" size={18} /></button>
          </form>
          {import.meta.env.VITE_USE_MOCK !== 'false' && <div className="demo-access"><div className="demo-heading"><span><Sparkles aria-hidden="true" size={15} /> Démonstration</span><small>Choisissez un profil de test</small></div><div className="demo-grid">{mockAccounts.map((account) => <button type="button" key={account.role} className="demo-account" onClick={() => selectAccount(account.identifier)}><span className="demo-avatar">{account.display_name.split(' ').map((part) => part[0]).slice(0, 2).join('')}</span><span><strong>{roleLabels[account.role]}</strong><small>{roleDescriptions[account.role]}</small></span><ArrowRight aria-hidden="true" size={15} /></button>)}</div><p>Mot de passe de démonstration : <strong>Demo2026!</strong></p></div>}
          <p className="login-legal">En continuant, vous accédez à un environnement de démonstration utilisant uniquement des données synthétiques.</p>
        </div>
        <div className="login-panel-footer"><span><ShieldCheck aria-hidden="true" size={15} /> Vos données restent protégées</span><Link to="/">PrediCare · Madagascar</Link></div>
      </section>
    </main>
  )
}
