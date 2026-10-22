import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  ClipboardCheck,
  Info,
  SearchX,
  ShieldAlert,
  ShieldCheck,
  TrendingDown,
  TrendingUp,
  TriangleAlert,
  X,
} from 'lucide-react'
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { getClaim, getClaimPrediction } from '@/api/claims'
import type { RejectionReason } from '@/api/types'
import { Money } from '@/components/Money'
import { RiskBadge } from '@/components/RiskBadge'
import { StatusBadge } from '@/components/StatusBadge'
import { claimLineTypeLabels, rejectionReasonLabels, rejectionReasons } from '@/lib/config'
import { normalizeFactors, type NormalizedFactor } from '@/lib/normalizeFactors'
import { ManagerDecisionBlock } from '@/features/claims/ManagerDecisionBlock'

/** Phrase fixe exigée sur toute carte de score : le score n'établit jamais une fraude. */
const SCORE_DISCLAIMER =
  'Signal à examiner : ce score est une aide à la décision, pas une preuve de fraude.'

type ChartFactor = NormalizedFactor & { shap_value: number }

const shapFormat = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2, signDisplay: 'always' })

function hasShapValue(factor: NormalizedFactor): factor is ChartFactor {
  return typeof factor.shap_value === 'number'
}

/** Le sens est toujours écrit en français clair ; la couleur ne porte jamais l'information seule. */
function directionLabel(direction: NormalizedFactor['direction']): string {
  if (direction === 'increases') return 'Augmente le risque'
  if (direction === 'decreases') return 'Diminue le risque'
  if (direction === 'neutral') return 'Effet neutre sur le score'
  return 'Sens non transmis'
}

interface FactorTooltipProps {
  active?: boolean
  payload?: Array<{ payload: ChartFactor }>
}

function FactorTooltip({ active, payload }: FactorTooltipProps) {
  if (!active || !payload || !payload.length) return null
  const factor = payload[0].payload
  const isRisk = factor.shap_value > 0
  return (
    <div className="factor-chart-tooltip" role="tooltip">
      <div className="factor-chart-tooltip-badge">
        <span className={`factor-cat-pill ${factor.category.badgeClass}`}>{factor.category.label}</span>
        <span className={isRisk ? 'tooltip-risk' : 'tooltip-safe'}>
          {isRisk ? '+ Risque' : '− Modérateur'} ({shapFormat.format(factor.shap_value)})
        </span>
      </div>
      <strong className="factor-chart-tooltip-title">{factor.label}</strong>
      <p className="factor-chart-tooltip-text">{factor.explanation}</p>
    </div>
  )
}

/** `motif_rejet` est une chaîne libre côté API : une valeur inconnue reste lisible. */
function rejectionLabel(reason: RejectionReason): string {
  return rejectionReasons.includes(reason) ? rejectionReasonLabels[reason] : reason
}

export function ManagerClaimDetailPage() {
  const { factureId = '' } = useParams()
  const detailQuery = useQuery({
    queryKey: ['claim', factureId],
    queryFn: () => getClaim(factureId),
    enabled: Boolean(factureId),
  })
  // Une analyse indisponible ne doit pas masquer la facture : les deux requêtes sont indépendantes.
  const analysisQuery = useQuery({
    queryKey: ['claim-prediction', factureId],
    queryFn: () => getClaimPrediction(factureId),
    enabled: Boolean(factureId),
    retry: false,
  })

  const detail = detailQuery.data
  const analysis = analysisQuery.data
  const factors = useMemo(
    () => normalizeFactors(analysis?.explicabilite.top_facteurs),
    [analysis],
  )
  const chartFactors = useMemo(() => factors.filter(hasShapValue), [factors])

  const [selectedFeature, setSelectedFeature] = useState<string | null>(null)

  const selectedFactor = useMemo(
    () => (selectedFeature ? factors.find((f) => f.feature === selectedFeature) ?? null : null),
    [factors, selectedFeature],
  )

  const riskIncreasingCount = useMemo(
    () => chartFactors.filter((f) => f.shap_value > 0).length,
    [chartFactors],
  )
  const riskDecreasingCount = useMemo(
    () => chartFactors.filter((f) => f.shap_value < 0).length,
    [chartFactors],
  )

  const scorePercent = analysis ? Math.round(analysis.prediction.score_fraude * 100) : null

  if (detailQuery.isError) {
    return (
      <div className="claim-page">
        <BackLink />
        <div className="queue-state" role="alert">
          <SearchX aria-hidden="true" size={22} />
          <strong>Ce dossier n’a pas pu être ouvert</strong>
          <span>{detailQuery.error instanceof Error ? detailQuery.error.message : 'Réessayez dans un instant.'}</span>
          <button type="button" onClick={() => void detailQuery.refetch()}>Réessayer</button>
        </div>
      </div>
    )
  }

  if (!detail) {
    return (
      <div className="claim-page">
        <BackLink />
        <div className="queue-state" aria-live="polite">
          <TriangleAlert aria-hidden="true" size={22} />
          <strong>Chargement du dossier…</strong>
          <span>La facture et son analyse sont récupérées depuis le serveur.</span>
        </div>
      </div>
    )
  }

  return (
    <div className="claim-page">
      <BackLink />

      <header className="claim-page-heading">
        <div>
          <span className="claim-heading-icon"><ClipboardCheck aria-hidden="true" size={20} /></span>
          <div>
            <h1>{detail.facture_id}</h1>
            <p>
              {detail.numero_facture} · {detail.nom_etablissement ?? 'Établissement non renseigné'} · soin du {detail.date_soin}
            </p>
          </div>
        </div>
        <StatusBadge status={detail.statut} />
      </header>

      <div className="fiche-stack">
        <section className="claim-section" aria-labelledby="fiche-resume-title">
          <div className="claim-section-heading">
            <div>
              <h2 id="fiche-resume-title">Résumé de la facture</h2>
              <p>Montants en ariary, tels que transmis par l’API.</p>
            </div>
          </div>

          <dl className="fiche-facts">
            <div><dt>Assuré</dt><dd>{detail.assure_id}</dd></div>
            <div><dt>Prestataire</dt><dd>{detail.nom_etablissement ?? detail.prestataire_id} <small>{detail.prestataire_id}</small></dd></div>
            <div><dt>Ordonnance</dt><dd>{detail.ordonnance_id ?? 'Non transmise'}</dd></div>
            <div><dt>Date d’émission</dt><dd>{detail.date_emission}</dd></div>
          </dl>

          <div className="fiche-lines-scroll">
            <table className="fiche-lines">
              <caption className="sr-only">Lignes de la facture {detail.facture_id}</caption>
              <thead>
                <tr>
                  <th scope="col">N°</th>
                  <th scope="col">Code</th>
                  <th scope="col">Type</th>
                  <th scope="col" className="fiche-number">Quantité</th>
                  <th scope="col" className="fiche-number">Prix unitaire</th>
                  <th scope="col" className="fiche-number">Montant</th>
                </tr>
              </thead>
              <tbody>
                {detail.lignes.map((line) => (
                  <tr key={line.num_ligne}>
                    <td>{line.num_ligne}</td>
                    <td>{line.code}</td>
                    <td>{claimLineTypeLabels[line.type_ligne]}</td>
                    <td className="fiche-number">{line.quantite}</td>
                    <td className="fiche-number"><Money amount={line.prix_unitaire} /></td>
                    <td className="fiche-number"><Money amount={line.montant_total} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="fiche-totals">
            <div><span>Part de l’assuré</span><Money amount={detail.part_assure} className="fiche-amount" /></div>
            <div><span>Montant demandé</span><Money amount={detail.montant_demande} className="fiche-amount" /></div>
            {detail.montant_pris_en_charge !== null && (
              <div><span>Montant pris en charge</span><Money amount={detail.montant_pris_en_charge} className="fiche-amount" /></div>
            )}
            <div className="fiche-total-main"><span>Montant total</span><Money amount={detail.montant_total} className="fiche-amount" /></div>
          </div>

          {detail.motif_rejet !== null && (
            <p className="fiche-rejection">
              Motif de rejet transmis : <strong>{rejectionLabel(detail.motif_rejet)}</strong>
            </p>
          )}
        </section>

        <section className="claim-section" aria-labelledby="fiche-score-title">
          <div className="claim-section-heading">
            <div>
              <h2 id="fiche-score-title">Carte de score</h2>
              <p>Analyse du modèle, présentée telle quelle.</p>
            </div>
          </div>

          <div className="fiche-score">
            <div className="fiche-score-value">
              <span>Score du modèle</span>
              <strong>
                {scorePercent === null ? '—' : scorePercent}
                {scorePercent === null ? null : <small>%</small>}
              </strong>
              <div className="score-track"><span style={{ width: `${scorePercent ?? 0}%` }} /></div>
            </div>
            <div className="fiche-score-meta">
              <RiskBadge anomaly={analysis?.prediction.est_anomalie ?? false} />
              {analysis ? (
                <>
                  <p className="claim-reference">
                    Modèle <strong>{analysis.prediction.version_modele}</strong>
                    <span>{analysis.prediction.date_prediction}</span>
                  </p>
                  <p className="fiche-disclaimer">{SCORE_DISCLAIMER}</p>
                </>
              ) : (
                <p className="fiche-note" role="status">
                  {analysisQuery.isError
                    ? 'L’analyse de ce dossier n’a pas pu être récupérée.'
                    : 'Analyse en cours de récupération…'}
                </p>
              )}
            </div>
          </div>
        </section>

        <section className="claim-section" aria-labelledby="fiche-factors-title">
          <div className="claim-section-heading">
            <div>
              <h2 id="fiche-factors-title">Facteurs explicatifs</h2>
              <p>Décomposition métier des signaux ayant motivé l’évaluation de risque par l’intelligence artificielle.</p>
            </div>
          </div>

          {analysis?.explicabilite?.recommandation && (
            <div
              className={`factors-recommendation-box ${
                analysis.prediction.est_anomalie
                  ? 'factors-recommendation-box--alert'
                  : 'factors-recommendation-box--ok'
              }`}
            >
              <div className="factors-recommendation-icon">
                {analysis.prediction.est_anomalie ? (
                  <ShieldAlert aria-hidden="true" size={22} />
                ) : (
                  <ShieldCheck aria-hidden="true" size={22} />
                )}
              </div>
              <div className="factors-recommendation-content">
                <strong>Recommandation d’audit : {analysis.explicabilite.recommandation}</strong>
                <p>
                  {analysis.prediction.est_anomalie
                    ? 'Ce dossier présente des écarts significatifs par rapport aux référentiels conventionnels. Une vérification attentive des justificatifs est conseillée avant décision.'
                    : 'Les indicateurs analysés sont en cohérence avec les seuils de référence usuels.'}
                </p>
              </div>
            </div>
          )}

          {factors.length === 0 ? (
            <p className="fiche-note">Aucun facteur explicatif n’est transmis pour ce dossier.</p>
          ) : (
            <>
              

              {chartFactors.length > 0 && (
                <div className="fiche-chart-card">
                  <div className="fiche-chart-header">
                    <div>
                      <span className="fiche-chart-title">Visualisation de l’impact des facteurs (SHAP)</span>
                      <p className="fiche-chart-subtitle">
                        Cliquez sur une barre pour afficher l’explication détaillée du facteur.
                      </p>
                    </div>
                    <div className="fiche-chart-legend">
                      <span className="legend-chip legend-chip--risk">
                        <span className="legend-dot legend-dot--risk" /> Augmente le risque
                      </span>
                      <span className="legend-chip legend-chip--safe">
                        <span className="legend-dot legend-dot--safe" /> Réduit le risque
                      </span>
                    </div>
                  </div>
                  <div className="factors-summary-bar">
                    <div className="factors-summary-pill factors-summary-pill--risk">
                      <AlertCircle aria-hidden="true" size={15} />
                      <span>
                        <strong>{riskIncreasingCount}</strong> indicateur{riskIncreasingCount > 1 ? 's' : ''} aggravant{riskIncreasingCount > 1 ? 's' : ''} le risque
                      </span>
                    </div>
                    {riskDecreasingCount > 0 && (
                      <div className="factors-summary-pill factors-summary-pill--safe">
                        <CheckCircle2 aria-hidden="true" size={15} />
                        <span>
                          <strong>{riskDecreasingCount}</strong> facteur{riskDecreasingCount > 1 ? 's' : ''} atténuant{riskDecreasingCount > 1 ? 's' : ''}
                        </span>
                      </div>
                    )}
                  </div>
{/* 
                  <div className="factor-selector-chips" role="tablist" aria-label="Sélection rapide d’un facteur">
                    {chartFactors.map((f) => {
                      const isSelected = selectedFeature === f.feature
                      const isRisk = f.shap_value > 0
                      return (
                        <button
                          key={f.feature}
                          type="button"
                          role="tab"
                          aria-selected={isSelected}
                          className={`factor-chip ${isSelected ? 'factor-chip--active' : ''} ${
                            isRisk ? 'factor-chip--risk' : 'factor-chip--safe'
                          }`}
                          onClick={() => setSelectedFeature((cur) => (cur === f.feature ? null : f.feature))}
                        >
                          <span className={`factor-chip-dot ${isRisk ? 'factor-chip-dot--risk' : 'factor-chip-dot--safe'}`} />
                          <span className="factor-chip-label">{f.label}</span>
                          <span className="factor-chip-val">{shapFormat.format(f.shap_value)}</span>
                        </button>
                      )
                    })}
                  </div> */}

                  <div className="fiche-chart" aria-hidden="true">
                    <ResponsiveContainer width="100%" height={Math.max(180, chartFactors.length * 48)}>
                      <BarChart
                        data={chartFactors}
                        layout="vertical"
                        margin={{ top: 8, right: 24, bottom: 8, left: 16 }}
                      >
                        <XAxis type="number" hide />
                        <YAxis
                          type="category"
                          dataKey="label"
                          width={240}
                          tickLine={false}
                          axisLine={false}
                          tick={{ fill: 'var(--ink)', fontSize: 11, fontWeight: 500 }}
                        />
                        <Tooltip content={<FactorTooltip />} cursor={{ fill: 'var(--surface-soft)', opacity: 0.6 }} />
                        <Bar
                          dataKey="shap_value"
                          radius={[0, 4, 4, 0]}
                          isAnimationActive={false}
                          cursor="pointer"
                          onClick={(data) => {
                            const feat = (data as { feature?: string; payload?: { feature?: string } })?.feature
                              ?? (data as { payload?: { feature?: string } })?.payload?.feature
                            if (feat) {
                              setSelectedFeature((cur) => (cur === feat ? null : feat))
                            }
                          }}
                        >
                          {chartFactors.map((entry) => {
                            const isSelected = selectedFeature === entry.feature
                            return (
                              <Cell
                                key={`cell-${entry.feature}`}
                                fill={
                                  isSelected
                                    ? (entry.shap_value > 0 ? '#B91C1C' : '#047857')
                                    : (entry.shap_value > 0 ? '#EF4444' : '#10B981')
                                }
                                stroke={isSelected ? 'var(--ink)' : 'none'}
                                strokeWidth={isSelected ? 2 : 0}
                              />
                            )
                          })}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}

              {selectedFactor ? (
                <div className="factor-selected-panel" role="region" aria-labelledby="selected-factor-title">
                  <div className="factor-selected-top">
                    <div className="factor-selected-badges">
                      <span className={`factor-cat-pill ${selectedFactor.category.badgeClass}`}>
                        {selectedFactor.category.label}
                      </span>
                      <span
                        className={`factor-direction-badge ${
                          selectedFactor.direction === 'increases'
                            ? 'factor-direction-badge--risk'
                            : selectedFactor.direction === 'decreases'
                            ? 'factor-direction-badge--safe'
                            : 'factor-direction-badge--neutral'
                        }`}
                      >
                        {selectedFactor.direction === 'increases' && <TrendingUp aria-hidden="true" size={13} />}
                        {selectedFactor.direction === 'decreases' && <TrendingDown aria-hidden="true" size={13} />}
                        <span>{directionLabel(selectedFactor.direction)}</span>
                        {typeof selectedFactor.shap_value === 'number' && (
                          <span className="factor-impact-val">{shapFormat.format(selectedFactor.shap_value)}</span>
                        )}
                      </span>
                    </div>
                    <button
                      type="button"
                      className="factor-selected-close"
                      onClick={() => setSelectedFeature(null)}
                      title="Masquer le détail"
                    >
                      <X size={14} aria-hidden="true" />
                      <span>Masquer le détail</span>
                    </button>
                  </div>

                  <div className="factor-selected-main">
                    <h3 id="selected-factor-title" className="factor-selected-title">
                      {selectedFactor.label}
                    </h3>
                    <p className="factor-selected-explanation">
                      {selectedFactor.explanation}
                    </p>
                    {selectedFactor.formattedValue &&
                      selectedFactor.formattedValue !== 'Non constaté' &&
                      selectedFactor.formattedValue !== '0' &&
                      selectedFactor.formattedValue !== '0,0' && (
                        <div className="factor-selected-obs">
                          <span>Constat relevé :</span> <strong>{selectedFactor.formattedValue}</strong>
                        </div>
                      )}
                  </div>
                </div>
              ) : (
                <div className="factor-empty-hint">
                  <Info aria-hidden="true" size={15} />
                  <span>
                    Cliquez sur une barre ou une étiquette ci-dessus pour inspecter l’explication détaillée et la consigne de contrôle associée.
                  </span>
                </div>
              )}
            </>
          )}
        </section>
        <ManagerDecisionBlock 
          factureId={detail.facture_id} 
          montantDemande={detail.montant_demande} 
        />
      </div>
    </div>
  )
}

function BackLink() {
  return (
    <Link className="claim-back" to="/gestionnaire/dossiers">
      <ArrowLeft aria-hidden="true" size={16} /> Retour aux dossiers à examiner
    </Link>
  )
}