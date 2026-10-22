import { describe, expect, it } from 'vitest'
import { normalizeFactors } from './normalizeFactors'

describe('normalizeFactors', () => {
  it('normalise une liste de chaînes sans modifier son ordre', () => {
    const res = normalizeFactors(['montant_atypique', 'acte non reconnu'])
    expect(res).toHaveLength(2)
    expect(res[0].feature).toBe('montant_atypique')
    expect(res[0].label).toBe('Montant atypique')
    expect(res[1].feature).toBe('acte non reconnu')
    expect(res[1].label).toBe('Acte non reconnu')
  })

  it('traduit les objets SHAP, indique leur sens et trie par importance absolue', () => {
    const res = normalizeFactors([
      { feature: 'montant_atypique', shap_value: -0.2 },
      { feature: 'frequence_des_actes', shap_value: 0.7 },
      { feature: 'acte_hors_contrat', shap_value: 0 },
    ])
    expect(res).toHaveLength(3)
    expect(res[0]).toMatchObject({ feature: 'frequence_des_actes', label: 'Fréquence des actes', shap_value: 0.7, direction: 'increases' })
    expect(res[1]).toMatchObject({ feature: 'montant_atypique', label: 'Montant atypique', shap_value: -0.2, direction: 'decreases' })
    expect(res[2]).toMatchObject({ feature: 'acte_hors_contrat', label: 'Acte hors contrat', shap_value: 0, direction: 'neutral' })
  })

  it('normalise la forme top_facteurs documentée avec impact_shap', () => {
    const res = normalizeFactors([
      { feature: 'ecart_tarif_conventionne', valeur: 15_000, impact_shap: 0.38 },
    ])
    expect(res).toHaveLength(1)
    expect(res[0]).toMatchObject({
      feature: 'ecart_tarif_conventionne',
      label: 'Écart au tarif conventionné',
      shap_value: 0.38,
      direction: 'increases',
    })
    expect(res[0].category.label).toBe('Tarification & Plafonds')
    expect(res[0].explanation).toBeDefined()
  })

  it('nettoie les descriptions contenant = nan', () => {
    const res = normalizeFactors([
      { feature: 'f_ecart_grille_prest_moy', description: 'Écart moyen à la grille = nan', impact_shap: 3.5 },
    ])
    expect(res[0].label).toBe('Dépassement de la grille conventionnelle')
    expect(res[0].explanation).not.toContain('nan')
    expect(res[0].description).not.toContain('nan')
  })

  it('retourne une liste vide si aucune explication n’est fournie', () => {
    expect(normalizeFactors(undefined)).toEqual([])
  })
})
