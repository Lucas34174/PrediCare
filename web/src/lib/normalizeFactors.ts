import type { TopFactor } from '@/api/types'
import {
  factorCategory,
  factorExplanation,
  factorLabel,
  formatFactorValue,
  type FactorCategory,
} from './factorLabels'

export interface NormalizedFactor {
  feature: string
  label: string
  category: FactorCategory
  explanation: string
  shap_value?: number
  direction?: 'increases' | 'decreases' | 'neutral'
  /** Explication lisible pour ce facteur, garantie sans variable ni nan */
  description?: string
  valeur?: unknown
  formattedValue?: string | null
}

export function normalizeFactors(factors: readonly TopFactor[] | null | undefined): NormalizedFactor[] {
  return (factors ?? []).map((factor): NormalizedFactor => {
    if (typeof factor === 'string') {
      return {
        feature: factor,
        label: factorLabel(factor),
        category: factorCategory(factor),
        explanation: factorExplanation(factor),
      }
    }

    const shapValue = factor.shap_value ?? factor.impact_shap
    const apiDesc = factor.description
    const cleanDesc = apiDesc && !apiDesc.toLowerCase().includes('nan') && !apiDesc.toLowerCase().includes('null')
      ? apiDesc
      : undefined

    return {
      feature: factor.feature,
      label: factorLabel(factor.feature),
      category: factorCategory(factor.feature),
      explanation: factorExplanation(factor.feature, cleanDesc),
      shap_value: shapValue,
      direction: shapValue === undefined ? undefined : shapValue > 0 ? 'increases' : shapValue < 0 ? 'decreases' : 'neutral',
      description: cleanDesc ?? factorExplanation(factor.feature),
      valeur: factor.valeur,
      formattedValue: formatFactorValue(factor.valeur),
    }
  }).sort((left, right) => Math.abs(right.shap_value ?? 0) - Math.abs(left.shap_value ?? 0))
}
