import { useQuery } from '@tanstack/react-query'
import { request } from '@/api/request'
import { 
  BarChart, Bar, XAxis, YAxis, Tooltip as RechartsTooltip, ResponsiveContainer, 
  PieChart, Pie, Cell 
} from 'recharts'
import { Briefcase, ShieldCheck, BrainCircuit, Zap, TrendingUp, AlertTriangle } from 'lucide-react'

const COLORS = ['#0f766e', '#0ea5e9', '#8b5cf6', '#f59e0b', '#ef4444'];
const formatMGA = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 })

// Composant de Carte (Style Power BI)
const KpiCard = ({ title, value, subtitle, icon: Icon, trend }: any) => (
  <div className="bg-white p-5 rounded-xl shadow-sm border border-gray-100 flex flex-col justify-between hover:shadow-md transition-shadow">
    <div className="flex justify-between items-start">
      <div>
        <p className="text-sm font-medium text-gray-500 uppercase tracking-wider">{title}</p>
        <h3 className="text-3xl font-bold text-gray-900 mt-2">{value}</h3>
      </div>
      <div className="p-3 bg-gray-50 rounded-lg"><Icon size={24} className="text-gray-700" /></div>
    </div>
    <div className="mt-4 flex items-center text-sm">
      {trend && <span className={`font-medium ${trend > 0 ? 'text-green-600' : 'text-red-600'} mr-2`}>{trend > 0 ? '↑' : '↓'} {Math.abs(trend)}%</span>}
      <span className="text-gray-500">{subtitle}</span>
    </div>
  </div>
)

export function PublicDashboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['public-kpis'],
    queryFn: () => request<any>('/dashboard/public/kpis'),
    refetchInterval: 5000, // ⚡ Temps réel : actualise toutes les 5 sec
  })

  if (isLoading) return <div className="flex h-screen items-center justify-center text-xl text-teal-700">Chargement du Dashboard...</div>
  if (!data) return <div className="p-10 text-red-500">Erreur de connexion à l'API.</div>

  return (
    <div className="min-h-screen bg-slate-50 p-8 font-sans">
      
      {/* En-tête */}
      <header className="mb-8 flex justify-between items-end border-b pb-4">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">PrediCare TPA — Pilotage Stratégique</h1>
          <p className="text-slate-500 mt-1">Vue consolidée en temps réel (Données de démonstration)</p>
        </div>
        <div className="flex items-center gap-2 bg-green-100 text-green-800 px-3 py-1 rounded-full text-sm font-semibold animate-pulse">
          <span className="w-2 h-2 bg-green-600 rounded-full"></span> Live Data
        </div>
      </header>

      {/* GRILLE PRINCIPALE */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">

        {/* ═══════════════════════════════════════════════════════════
            LIGNE 1 : LE PÔLE BUSINESS (Stratégique)
        ═══════════════════════════════════════════════════════════ */}
        <div className="col-span-1 lg:col-span-2 bg-gradient-to-r from-teal-900 to-teal-700 rounded-xl p-6 text-white shadow-lg">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-semibold flex items-center gap-2"><Briefcase size={20}/> Pôle Business</h2>
            <span className="bg-teal-800 px-2 py-1 rounded text-xs">Portefeuille</span>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-teal-200 text-sm">Primes Totales</p>
              <p className="text-3xl font-bold">{formatMGA.format(data.business.prime_totale)} Ar</p>
            </div>
            <div>
              <p className="text-teal-200 text-sm">Contrats Actifs</p>
              <p className="text-3xl font-bold">{data.business.nb_contrats}</p>
            </div>
          </div>
        </div>
        
        <div className="col-span-1 lg:col-span-2 bg-white p-5 rounded-xl shadow-sm border border-gray-100">
           <h2 className="text-sm font-semibold text-gray-500 mb-4">Répartition par Secteur d'Activité</h2>
           <div className="h-32">
             <ResponsiveContainer width="100%" height="100%">
               <BarChart data={data.business.top_secteurs} layout="vertical" margin={{ top: 0, right: 20, left: 20, bottom: 0 }}>
                 <XAxis type="number" hide />
                 <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} tick={{fontSize: 12}} width={150} />
                 <RechartsTooltip cursor={{fill: '#f3f4f6'}} />
                 <Bar dataKey="value" fill="#0ea5e9" radius={[0, 4, 4, 0]} barSize={16} />
               </BarChart>
             </ResponsiveContainer>
           </div>
        </div>

        {/* ═══════════════════════════════════════════════════════════
            LIGNE 2 : LE PÔLE MÉTIER (Opérationnel) - Power BI Cards
        ═══════════════════════════════════════════════════════════ */}
        <KpiCard title="Montant Economisé" value={`${formatMGA.format(data.metier.montant_economise)} Ar`} subtitle="Fraudes bloquées" icon={ShieldCheck} trend={12} />
        <KpiCard title="Taux Détection" value={`${(data.metier.taux_detection * 100).toFixed(1)} %`} subtitle="Sur total factures" icon={TrendingUp} />
        <KpiCard title="À Examiner" value={data.metier.en_attente} subtitle="Dossiers en attente" icon={AlertTriangle} />
        <KpiCard title="Factures Traitées" value={formatMGA.format(data.metier.total_factures)} subtitle="Depuis le début" icon={Briefcase} />

        {/* ═══════════════════════════════════════════════════════════
            LIGNE 3 : GRAPHIQUES MÉTIER & FINOPS
        ═══════════════════════════════════════════════════════════ */}
        
        {/* Graphique Fraudes (Pie Chart) */}
        <div className="col-span-1 lg:col-span-2 bg-white p-5 rounded-xl shadow-sm border border-gray-100">
          <h2 className="text-sm font-semibold text-gray-500 mb-4">Typologie des Fraudes</h2>
          <div className="flex h-64 items-center">
            <div className="w-1/2 h-full">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={data.metier.distribution_fraudes} dataKey="count" nameKey="type" cx="50%" cy="50%" innerRadius={60} outerRadius={80} paddingAngle={5}>
                    {data.metier.distribution_fraudes.map((_e: any, index: number) => <Cell key={index} fill={COLORS[index % COLORS.length]} />)}
                  </Pie>
                  <RechartsTooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="w-1/2">
              {data.metier.distribution_fraudes.map((entry: any, index: number) => (
                <div key={index} className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full" style={{ backgroundColor: COLORS[index % COLORS.length] }}></span>
                    <span className="text-sm text-gray-700">{entry.type}</span>
                  </div>
                  <span className="text-sm font-bold">{entry.count}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Graphique FinOps (RAG) */}
        <div className="col-span-1 bg-white p-5 rounded-xl shadow-sm border border-gray-100 relative overflow-hidden">
          <div className="absolute top-0 right-0 p-4 opacity-10"><Zap size={80} /></div>
          <h2 className="text-sm font-semibold text-gray-500 mb-4 flex items-center gap-2"><Zap size={16}/> FinOps & RAG</h2>
          <div className="mb-6">
            <p className="text-3xl font-bold text-gray-900">{formatMGA.format(data.finops.tokens_economises)}</p>
            <p className="text-sm text-green-600 font-medium">Tokens LLM économisés</p>
          </div>
          <div className="space-y-3">
            <div className="flex justify-between items-center text-sm border-b pb-2">
              <span className="text-gray-500">Cache Hits</span>
              <span className="font-semibold">{data.finops.cache_hits}</span>
            </div>
            <div className="flex justify-between items-center text-sm">
              <span className="text-gray-500">Requêtes RAG</span>
              <span className="font-semibold">{data.finops.total_requetes_rag}</span>
            </div>
          </div>
        </div>

        {/* Graphique ML (Santé du modèle) */}
        <div className="col-span-1 bg-slate-900 text-white p-5 rounded-xl shadow-sm relative overflow-hidden">
          <h2 className="text-sm font-semibold text-slate-400 mb-4 flex items-center gap-2"><BrainCircuit size={16}/> Santé du Modèle ML</h2>
          <div className="flex flex-col h-full justify-center">
            <div className="text-center mb-4">
              <span className="inline-block bg-slate-800 text-teal-400 px-3 py-1 rounded-full text-xs font-mono mb-2">{data.ml.modele_actif}</span>
              <p className="text-sm text-slate-300">Dérive (PSI)</p>
              <p className="text-2xl font-bold">{data.ml.psi_score}</p>
              <p className="text-xs text-green-400 mt-1">● STABLE</p>
            </div>
            <div className="bg-slate-800 rounded p-3 text-center">
              <p className="text-xs text-slate-400">Score de risque moyen</p>
              <p className="text-lg font-semibold">{data.ml.score_moyen}</p>
            </div>
          </div>
        </div>

      </div>
    </div>
  )
}