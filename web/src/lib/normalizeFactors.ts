import type { TopFactor } from '@/api/types'
import { factorLabel } from './factorLabels'

export interface NormalizedFactor {
  feature: string
  label: string
  shap_value?: number
  direction?: 'increases' | 'decreases' | 'neutral'
}

export function normalizeFactors(factors: readonly TopFactor[] | null | undefined): NormalizedFactor[] {
  return (factors ?? []).map((factor): NormalizedFactor => {
    if (typeof factor === 'string') {
      return { feature: factor, label: factorLabel(factor) }
    }

    const shapValue = factor.shap_value ?? factor.impact_shap
    return {
      feature: factor.feature,
      label: factorLabel(factor.feature),
      shap_value: shapValue,
      direction: shapValue === undefined ? undefined : shapValue > 0 ? 'increases' : shapValue < 0 ? 'decreases' : 'neutral',
    }
  }).sort((left, right) => Math.abs(right.shap_value ?? 0) - Math.abs(left.shap_value ?? 0))
}
