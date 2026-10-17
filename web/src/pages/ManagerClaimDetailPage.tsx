import { useMemo } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, ClipboardCheck, SearchX, TriangleAlert } from 'lucide-react'
import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis } from 'recharts'
import { getClaim, getClaimPrediction } from '@/api/claims'
import type { RejectionReason } from '@/api/types'
import { Money } from '@/components/Money'
import { RiskBadge } from '@/components/RiskBadge'
import { StatusBadge } from '@/components/StatusBadge'
import { claimLineTypeLabels, rejectionReasonLabels, rejectionReasons } from '@/lib/config'
import { normalizeFactors, type NormalizedFactor } from '@/lib/normalizeFactors'

/** Phrase fixe exigée sur toute carte de score : le score n'établit jamais une fraude. */
const SCORE_DISCLAIMER =
  'Signal à examiner : ce score est une aide à la décision, pas une preuve de fraude.'

type ChartFactor = NormalizedFactor & { shap_value: number }

const shapFormat = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2, signDisplay: 'always' })

function hasShapValue(factor: NormalizedFactor): factor is ChartFactor {
  return typeof factor.shap_value === 'number'
}

/** Le sens est toujours écrit ; la couleur ne porte jamais l'information seule. */
function directionLabel(direction: NormalizedFactor['direction']): string {
  if (direction === 'increases') return 'augmente le risque'
  if (direction === 'decreases') return 'diminue le risque'
  if (direction === 'neutral') return 'effet neutre sur le score'
  return 'sens non transmis'
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
              <RiskBadge anomaly={analysis?.prediction.est_anomalie ?? null} />
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
              <p>Ce que le modèle a retenu. Un facteur qui augmente le risque n’établit aucun manquement.</p>
            </div>
          </div>

          {factors.length === 0 ? (
            <p className="fiche-note">Aucun facteur explicatif n’est transmis pour ce dossier.</p>
          ) : (
            <>
              {chartFactors.length > 0 && (
                <div className="fiche-chart" aria-hidden="true">
                  <ResponsiveContainer width="100%" height={Math.max(160, chartFactors.length * 46)}>
                    <BarChart data={chartFactors} layout="vertical" margin={{ top: 4, right: 12, bottom: 4, left: 4 }}>
                      <XAxis type="number" hide />
                      <YAxis type="category" dataKey="label" width={190} tickLine={false} axisLine={false} />
                      <Bar dataKey="shap_value" radius={[0, 3, 3, 0]} isAnimationActive={false} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
              <ol className="factor-detail">
                {factors.map((factor) => (
                  <li key={factor.feature}>
                    <span className="factor-detail-label">{factor.label}</span>
                    <span className="factor-detail-direction">
                      {directionLabel(factor.direction)}
                      {typeof factor.shap_value === 'number' && <em>{shapFormat.format(factor.shap_value)}</em>}
                    </span>
                    {factor.description && <small>{factor.description}</small>}
                  </li>
                ))}
              </ol>
            </>
          )}
        </section>
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