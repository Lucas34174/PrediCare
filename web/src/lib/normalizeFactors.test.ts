import { describe, expect, it } from 'vitest'
import { normalizeFactors } from './normalizeFactors'

describe('normalizeFactors', () => {
  it('normalise une liste de chaînes sans modifier son ordre', () => {
    expect(normalizeFactors(['montant_atypique', 'acte non reconnu'])).toEqual([
      { feature: 'montant_atypique', label: 'Montant atypique' },
      { feature: 'acte non reconnu', label: 'Acte non reconnu' },
    ])
  })

  it('traduit les objets SHAP, indique leur sens et trie par importance absolue', () => {
    expect(normalizeFactors([
      { feature: 'montant_atypique', shap_value: -0.2 },
      { feature: 'frequence_des_actes', shap_value: 0.7 },
      { feature: 'acte_hors_contrat', shap_value: 0 },
    ])).toEqual([
      { feature: 'frequence_des_actes', label: 'Fréquence des actes', shap_value: 0.7, direction: 'increases' },
      { feature: 'montant_atypique', label: 'Montant atypique', shap_value: -0.2, direction: 'decreases' },
      { feature: 'acte_hors_contrat', label: 'Acte hors contrat', shap_value: 0, direction: 'neutral' },
    ])
  })

  it('normalise la forme top_facteurs documentée avec impact_shap', () => {
    expect(normalizeFactors([
      { feature: 'ecart_tarif_conventionne', valeur: 15_000, impact_shap: 0.38 },
    ])).toEqual([
      { feature: 'ecart_tarif_conventionne', label: 'Écart au tarif conventionné', shap_value: 0.38, direction: 'increases' },
    ])
  })

  it('retourne une liste vide si aucune explication n’est fournie', () => {
    expect(normalizeFactors(undefined)).toEqual([])
  })
})
