// web/src/pages/AdminConfigPage.tsx
import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Save, ShieldCheck } from 'lucide-react'
import { getAdminConfig, updateAdminConfig, type AdminConfig } from '@/api/admin'

export function AdminConfigPage() {
  const queryClient = useQueryClient()
  const { data: config, isLoading } = useQuery({ queryKey: ['admin-config'], queryFn: getAdminConfig })
  
  const [formData, setFormData] = useState<Partial<AdminConfig>>({})
  const [successMsg, setSuccessMsg] = useState('')

  useEffect(() => {
    if (config) setFormData(config)
  }, [config])

  const mutation = useMutation({
    mutationFn: updateAdminConfig,
    onSuccess: (data) => {
      queryClient.setQueryData(['admin-config'], data)
      setSuccessMsg('Configuration mise à jour avec succès.')
      setTimeout(() => setSuccessMsg(''), 3000)
    },
  })

  if (isLoading || !config) return <div className="queue-state">Chargement de la configuration…</div>

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    mutation.mutate({
      fraud_score_threshold: Number(formData.fraud_score_threshold),
      semantic_cache_threshold: Number(formData.semantic_cache_threshold),
      semantic_cache_enabled: formData.semantic_cache_enabled,
    })
  }

  return (
    <div className="claim-page">
      <header className="claim-page-heading">
        <div>
          <span className="claim-heading-icon"><ShieldCheck size={20} /></span>
          <div>
            <p className="claim-kicker">ADMINISTRATION</p>
            <h1>Configuration à chaud</h1>
            <p>Modifiez les paramètres opérationnels sans redémarrer le serveur.</p>
          </div>
        </div>
      </header>

      {successMsg && (
        <div className="claim-summary" style={{ borderLeftColor: 'var(--success)', background: 'var(--success-soft)' }}>
          <strong style={{ color: 'var(--success-soft-foreground)' }}>{successMsg}</strong>
        </div>
      )}

      {mutation.isError && (
        <div className="claim-summary claim-summary-error">
          <strong>Erreur lors de la sauvegarde</strong>
          <span>{mutation.error instanceof Error ? mutation.error.message : 'Réessayez.'}</span>
        </div>
      )}

      <form className="claim-form" onSubmit={handleSubmit}>
        <section className="claim-section">
          <div className="claim-section-heading">
            <span className="claim-section-index">01</span>
            <div><h2>Seuils de détection</h2><p>Impact direct sur le déclenchement des alertes n8n.</p></div>
          </div>
          <div className="claim-fields-grid">
            <div className="claim-field">
              <label>Seuil de score de fraude</label>
              <input
                type="number" step="0.01" min="0" max="1"
                value={formData.fraud_score_threshold ?? ''}
                onChange={(e) => setFormData({ ...formData, fraud_score_threshold: Number(e.target.value) })}
              />
              <small className="claim-hint">Valeur actuelle : {config.fraud_score_threshold}</small>
            </div>
            <div className="claim-field">
              <label>Seuil du cache sémantique</label>
              <input
                type="number" step="0.01" min="0" max="1"
                value={formData.semantic_cache_threshold ?? ''}
                onChange={(e) => setFormData({ ...formData, semantic_cache_threshold: Number(e.target.value) })}
              />
              <small className="claim-hint">Similarité minimale pour utiliser le cache RAG.</small>
            </div>
          </div>

          <div className="claim-toggle-grid" style={{ marginTop: '1.5rem' }}>
            <label className="claim-toggle">
              <input
                type="checkbox"
                checked={formData.semantic_cache_enabled ?? false}
                onChange={(e) => setFormData({ ...formData, semantic_cache_enabled: e.target.checked })}
              />
              <span>
                <strong>Activer le cache sémantique</strong>
                <small>Réduit la latence de l'assistant RAG.</small>
              </span>
            </label>
          </div>
        </section>

        <section className="claim-section">
          <div className="claim-section-heading">
            <span className="claim-section-index">02</span>
            <div><h2>Intégrations</h2><p>URL du webhook pour les alertes de fraude.</p></div>
          </div>
          <div className="claim-fields-grid">
            <div className="claim-field" style={{ gridColumn: '1 / -1' }}>
              <label>URL du webhook n8n</label>
              <input
                type="url"
                value={formData.n8n_webhook_url ?? ''}
                onChange={(e) => setFormData({ ...formData, n8n_webhook_url: e.target.value })}
                disabled
              />
              <small className="claim-hint">La modification de l'URL nécessite une intervention manuelle sur le serveur.</small>
            </div>
          </div>
        </section>

        <footer className="claim-form-footer">
          <p>Les modifications sont appliquées instantanément à la prochaine requête.</p>
          <button className="claim-submit" type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? 'Sauvegarde…' : 'Sauvegarder la configuration'} <Save size={16} />
          </button>
        </footer>
      </form>
    </div>
  )
}