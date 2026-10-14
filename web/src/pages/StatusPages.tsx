import { Link } from 'react-router-dom'
import { ArrowLeft, ShieldAlert, SearchX } from 'lucide-react'
import type { ReactNode } from 'react'

export function ForbiddenPage() {
  return <StatusPage code="403" icon={<ShieldAlert size={26} />} title="Cet espace vous est fermé." message="Votre profil ne dispose pas de l’accès à cette page. Revenez à votre espace ou contactez votre administrateur si vous pensez qu’il s’agit d’une erreur." />
}

export function NotFoundPage() {
  return <StatusPage code="404" icon={<SearchX size={26} />} title="Cette page n’existe pas." message="Le lien utilisé est peut-être incomplet ou ancien. Revenez à votre espace pour continuer." />
}

function StatusPage({ code, icon, title, message }: { code: string; icon: ReactNode; title: string; message: string }) {
  return <main className="status-screen"><div className="status-brand"><span className="brand-mark">{icon}</span><span className="brand-word">Predi<span>Care</span><small>TPA · MADAGASCAR</small></span></div><section className="status-card"><span className="status-code">{code}</span><h1>{title}</h1><p>{message}</p><Link to="/app" className="status-link"><ArrowLeft aria-hidden="true" size={17} /> Revenir à mon espace</Link><small>Les autorisations d’accès sont vérifiées par l’API.</small></section></main>
}
