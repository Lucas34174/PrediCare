import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  Eye,
  EyeOff,
  HeartPulse,
  LockKeyhole,
  Mail,
  Shield,
  ShieldCheck,
} from "lucide-react";
import { ApiError } from "@/api/errors";
import { useAuth } from "@/auth/AuthContext";

interface LocationState {
  from?: { pathname?: string };
}

const demoAccounts = [
  { identifier: 'gestionnaire1', display_name: 'Gestionnaire', role: 'Gestionnaire', initials: 'GE' },
  { identifier: 'pro1', display_name: 'Clinique / Pharmacie', role: 'Pro de santé', initials: 'PS' },
  { identifier: 'assure1', display_name: 'Assuré & Famille', role: 'Assuré', initials: 'AS' },
  { identifier: 'admin1', display_name: 'Administrateur', role: 'Admin', initials: 'AD' },
]

export function LoginPage({
  // dark,
  // onToggleTheme,
}: {
  dark: boolean;
  onToggleTheme: () => void;
}) {
  const { isAuthenticated, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (isAuthenticated) return <Navigate to="/app" replace />;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await login({ identifier: identifier.trim(), password });
      const destination = (location.state as LocationState | null)?.from?.pathname ?? "/app";
      navigate(destination, { replace: true });
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Connexion impossible. Vérifiez votre connexion puis réessayez.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  function selectAccount(accountIdentifier: string) {
    setIdentifier(accountIdentifier);
    setPassword('demo');
    setError('');
  }

  return (
    <main className="login-screen">
      {/* Colonne de gauche */}
      <section className="login-story">
        <div className="login-brand">
          <span className="brand-mark">
            <ShieldCheck size={20} />
          </span>
          <span className="brand-word">PREDICARE</span>
        </div>

        <div className="story-content">
          <div className="story-label">
            <span className="story-label-mark"><HeartPulse size={12} /></span>
            TIERS PAYANT SANTÉ · MADAGASCAR
          </div>
          <h1>
            Prendre soin.<br />
            En toute<br />
            <em>confiance.</em> <span className="story-badge">DIRECT TPA</span>
          </h1>
          
          <div className="story-images">
            <div className="story-img-1">
              <div className="img-badge"><ShieldCheck size={12} /> Praticienne certifiée</div>
            </div>
            <div className="story-img-2">
              <div className="img-badge">PRISE EN CHARGE</div>
            </div>
          </div>

          <p>
            Un tiers payant d'assurance santé prédictif, éthique et transparent. Conçu pour digitaliser, accélérer et fiabiliser chaque parcours de soins à Madagascar avec une validation instantanée.
          </p>
        </div>
        
        <div className="login-footer">
          © 2026 PrediCare Madagascar. Tous droits réservés.
        </div>
      </section>

      {/* Colonne de droite */}
      <section className="login-panel">
        <div className="login-card">
          <div className="login-lock-icon">
            <LockKeyhole size={24} />
          </div>
          
          <div className="form-intro">
            <p className="eyebrow">VOTRE ESPACE SÉCURISÉ</p>
            <h2>Content de vous revoir</h2>
          </div>

          <form className="login-form" onSubmit={handleSubmit}>
            <div>
              <label htmlFor="identifier">ADRESSE E-MAIL OU IDENTIFIANT PRO</label>
              <div className="input-wrap" style={{ marginTop: '8px' }}>
                <input
                  id="identifier"
                  type="text"
                  autoComplete="username"
                  placeholder="dr.rakoto@predicare.mg"
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  required
                />
                <Mail size={18} />
              </div>
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label htmlFor="password">MOT DE PASSE</label>
                <button type="button" className="forgot-link" style={{ background: 'none', border: 'none', color: '#3B82F6', fontSize: '11px', fontWeight: 600, cursor: 'pointer' }}>
                  Oublié ?
                </button>
              </div>
              <div className="input-wrap" style={{ marginTop: '8px' }}>
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            {error && (
              <div style={{ color: '#B91C1C', fontSize: '12px', background: '#FEF2F2', padding: '10px', borderRadius: '8px' }}>
                {error}
              </div>
            )}

            <button className="submit-button" type="submit" disabled={submitting}>
              {submitting ? "Connexion en cours…" : "Accéder à mon espace sécurisé"}
              <ArrowRight size={18} />
            </button>
          </form>

          <div className="demo-section">
            <div className="demo-header">
              <span>Profils de démonstration rapide</span>
              <small>Mot de passe : Demo2026!</small>
            </div>
            <div className="demo-grid">
              {demoAccounts.map((account) => (
                <button
                  key={account.identifier}
                  type="button"
                  className="demo-card"
                  onClick={() => selectAccount(account.identifier)}
                >
                  <span className="demo-avatar">{account.initials}</span>
                  <div className="demo-info">
                    <strong>{account.display_name}</strong>
                    <small>{account.role}</small>
                  </div>
                </button>
              ))}
            </div>
          </div>

          <div className="ethics-note">
            <Shield size={16} />
            <p>
              <strong>Engagement Éthique PrediCare :</strong> L'IA agit comme un filtre de clarification pour les gestionnaires, jamais comme une décision unilatérale.
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}
