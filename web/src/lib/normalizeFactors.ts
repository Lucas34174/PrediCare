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

    return {
      feature: factor.feature,
      label: factorLabel(factor.feature),
      shap_value: factor.shap_value,
      direction: factor.shap_value > 0 ? 'increases' : factor.shap_value < 0 ? 'decreases' : 'neutral',
    }
  }).sort((left, right) => Math.abs(right.shap_value ?? 0) - Math.abs(left.shap_value ?? 0))
}
