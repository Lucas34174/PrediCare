// web/src/pages/AdminModelsPage.tsx
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Cpu, RefreshCw, CheckCircle2 } from 'lucide-react'
import { getAdminModels, activateAdminModel } from '@/api/admin'

export function AdminModelsPage() {
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: ['admin-models'], queryFn: getAdminModels })
  

  const mutation = useMutation({
      mutationFn: activateAdminModel,
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ['admin-models'] })
        alert('Modèle activé avec succès.')
      },
    })

  if (isLoading || !data) return <div className="queue-state">Chargement des modèles…</div>

  return (
    <div className="claim-page">
      <header className="claim-page-heading">
        <div>
          <span className="claim-heading-icon"><Cpu size={20} /></span>
          <div>
            <p className="claim-kicker">MLOPS</p>
            <h1>Gestion des modèles</h1>
            <p>Version active : <strong>{data.active_version}</strong></p>
          </div>
        </div>
      </header>

      {mutation.isSuccess && (
        <div className="claim-summary" style={{ borderLeftColor: 'var(--success)' }}>
          <strong>Modèle activé avec succès.</strong>
        </div>
      )}

      <section className="queue-panel">
        <div className="queue-scroll">
          <table className="queue-table">
            <thead>
              <tr>
                <th>Version</th>
                <th>Type</th>
                <th className="queue-amount">Recall</th>
                <th className="queue-amount">Precision</th>
                <th className="queue-amount">F1-Score</th>
                <th>Entraînement</th>
                <th>Statut</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {data.available_models.map((model) => (
                <tr key={model.version_id} className="queue-row">
                  <th>{model.version_id}</th>
                  <td>{model.type}</td>
                  <td className="queue-amount">{(model.recall_test * 100).toFixed(1)} %</td>
                  <td className="queue-amount">{(model.precision_test * 100).toFixed(1)} %</td>
                  <td className="queue-amount">{(model.f1_score * 100).toFixed(1)} %</td>
                  <td>{model.date_entrainement}</td>
                  <td>
                    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${
                      model.statut === 'ACTIVE' ? 'border-success bg-success-soft text-success-soft-foreground' : 'border-line bg-surface-soft text-ink-muted'
                    }`}>
                      {model.statut === 'ACTIVE' ? <CheckCircle2 size={14} /> : null}
                      {model.statut}
                    </span>
                  </td>
                  <td>
                    {model.statut !== 'ACTIVE' && (
                      <button
                        className="add-claim-line"
                        onClick={() => mutation.mutate(model.version_id)}
                        disabled={mutation.isPending}
                      >
                        <RefreshCw size={14} /> Activer
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}