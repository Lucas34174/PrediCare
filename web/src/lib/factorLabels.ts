const labels: Record<string, string> = {
  montant_atypique: 'Montant atypique',
  frequence_des_actes: 'Fréquence des actes',
  acte_hors_contrat: 'Acte hors contrat',
  quantite_atypique: 'Quantité atypique',
  prix_unitaire_atypique: 'Prix unitaire atypique',
  absence_entente_prealable: 'Entente préalable absente',
  piece_justificative_manquante: 'Pièce justificative manquante',
  delai_entre_actes: 'Délai entre les actes',
  ecart_tarif_conventionne: 'Écart au tarif conventionné',
  jour_fermeture_etablissement: 'Soin réalisé un jour de fermeture',
  montant_facture_atypique: 'Montant facturé atypique',
  doublon_facture: 'Facture potentiellement dupliquée',
  prescription_non_conforme: 'Prescription non conforme',
}

export function factorLabel(feature: string): string {
  const normalized = feature.trim()
  if (!normalized) return 'Facteur non renseigné'
  return labels[normalized] ?? normalized
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .replace(/^\p{L}/u, (letter) => letter.toLocaleUpperCase('fr-FR'))
}
