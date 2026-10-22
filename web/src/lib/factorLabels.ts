export interface FactorCategory {
  key: 'tarif' | 'prescription' | 'profil' | 'prestataire' | 'couverture' | 'doublon' | 'general'
  label: string
  badgeClass: string
}

export interface FactorDefinition {
  label: string
  category: FactorCategory
  explanation: string
}

const CATEGORIES: Record<string, FactorCategory> = {
  tarif: { key: 'tarif', label: 'Tarification & Plafonds', badgeClass: 'factor-cat--tarif' },
  prescription: { key: 'prescription', label: 'Prescription & Ordonnance', badgeClass: 'factor-cat--prescription' },
  profil: { key: 'profil', label: 'Profil de l’Assuré', badgeClass: 'factor-cat--profil' },
  prestataire: { key: 'prestataire', label: 'Convention Prestataire', badgeClass: 'factor-cat--prestataire' },
  couverture: { key: 'couverture', label: 'Droits & Couverture', badgeClass: 'factor-cat--couverture' },
  doublon: { key: 'doublon', label: 'Doublons & Fractionnement', badgeClass: 'factor-cat--doublon' },
  general: { key: 'general', label: 'Contrôle Général', badgeClass: 'factor-cat--general' },
}

/** Dictionnaire complet des 28 variables du modèle de détection et règles métier */
const DEFINITIONS: Record<string, FactorDefinition> = {
  // --- Tarification & Plafonds ---
  f_ecart_grille_prest_moy: {
    label: 'Dépassement de la grille conventionnelle',
    category: CATEGORIES.tarif,
    explanation: 'Le tarif pratiqué dépasse le barème négocié dans la convention de ce prestataire.',
  },
  f_ecart_tarif_max_moy: {
    label: 'Dépassement du tarif plafond légal',
    category: CATEGORIES.tarif,
    explanation: 'Le prix unitaire moyen facturé excède le tarif maximal autorisé par le référentiel national.',
  },
  f_ratio_tarif_ref_max: {
    label: 'Multiplicateur de tarif de référence excessif',
    category: CATEGORIES.tarif,
    explanation: 'Ratio élevé entre le montant facturé et le tarif de référence national opposable.',
  },
  f_nb_lignes_hors_tarif_max: {
    label: 'Lignes excédant le tarif plafond',
    category: CATEGORIES.tarif,
    explanation: 'Plusieurs prestations de cette facture dépassent la borne supérieure de tarification.',
  },
  f_ratio_med_prix_ref_max: {
    label: 'Surcoût médicament vs référence',
    category: CATEGORIES.tarif,
    explanation: 'Le prix unitaire des médicaments facturés dépasse très significativement le référentiel pharmaceutique.',
  },
  ecart_tarif_conventionne: {
    label: 'Écart au tarif conventionné',
    category: CATEGORIES.tarif,
    explanation: 'Différence significative constatée par rapport au tarif conventionnel applicable.',
  },
  montant_atypique: {
    label: 'Montant atypique',
    category: CATEGORIES.tarif,
    explanation: 'Le montant total de la facture est anormalement supérieur à la moyenne des dossiers comparables.',
  },
  montant_facture_atypique: {
    label: 'Montant facturé atypique',
    category: CATEGORIES.tarif,
    explanation: 'Montant global anormalement élevé au regard des actes mentionnés.',
  },
  prix_unitaire_atypique: {
    label: 'Prix unitaire atypique',
    category: CATEGORIES.tarif,
    explanation: 'Un ou plusieurs actes présentent un prix unitaire inhabituel.',
  },

  // --- Prescription & Ordonnance ---
  f_qte_fac_vs_prescrite_max: {
    label: 'Quantité supérieure à la prescription',
    category: CATEGORIES.prescription,
    explanation: 'La quantité délivrée excède la prescription médicale figurant sur l’ordonnance.',
  },
  f_nb_lignes_qte_excessive: {
    label: 'Prestations en quantité anormale',
    category: CATEGORIES.prescription,
    explanation: 'Nombre de lignes pour lesquelles le volume délivré est supérieur au besoin thérapeutique prescrit.',
  },
  f_part_lignes_hors_ordonnance: {
    label: 'Actes non prescrits sur l’ordonnance',
    category: CATEGORIES.prescription,
    explanation: 'Des prestations ou produits facturés ne figurent pas sur l’ordonnance rattachée.',
  },
  f_med_hors_ordo_cher: {
    label: 'Médicament coûteux non prescrit',
    category: CATEGORIES.prescription,
    explanation: 'Délivrance d’un médicament onéreux absent de l’ordonnance originale prescrite par le praticien.',
  },
  f_ordonnance_absente_requise: {
    label: 'Ordonnance obligatoire non transmise',
    category: CATEGORIES.prescription,
    explanation: 'Prestation soumise à prescription médicale obligatoire mais transmise sans ordonnance.',
  },
  f_ordonnance_autre_assure: {
    label: 'Ordonnance au nom d’un tiers',
    category: CATEGORIES.prescription,
    explanation: 'L’ordonnance rattachée mentionne un assuré distinct du bénéficiaire des soins.',
  },
  f_delai_soin_prescription_j: {
    label: 'Délai prescription - soin anormal',
    category: CATEGORIES.prescription,
    explanation: 'Écart temporel inhabituel entre la date d’ordonnance et la réalisation de la prestation.',
  },
  f_ordonnance_expiree: {
    label: 'Ordonnance médicalement expirée',
    category: CATEGORIES.prescription,
    explanation: 'La prestation a été effectuée après la fin de validité réglementaire de l’ordonnance.',
  },
  f_nb_prest_meme_ordo_anterieurs: {
    label: 'Ordonnance multi-prestataires (nomadisme)',
    category: CATEGORIES.prescription,
    explanation: 'Cette ordonnance a déjà été présentée et facturée auprès d’autres établissements de santé.',
  },
  prescription_non_conforme: {
    label: 'Prescription non conforme',
    category: CATEGORIES.prescription,
    explanation: 'L’ordonnance transmise ne respecte pas les critères formels requis pour la prise en charge.',
  },
  absence_entente_prealable: {
    label: 'Entente préalable requise manquante',
    category: CATEGORIES.prescription,
    explanation: 'Accord médical préalable obligatoire non joint au dossier.',
  },
  piece_justificative_manquante: {
    label: 'Pièce justificative manquante',
    category: CATEGORIES.prescription,
    explanation: 'Document de justification obligatoire absent de la télétransmission.',
  },

  // --- Doublons & Fractionnement ---
  f_numero_facture_deja_vu: {
    label: 'Numéro de facture dupliqué',
    category: CATEGORIES.doublon,
    explanation: 'Ce même numéro de facture a déjà été télétransmis par ce prestataire dans une autre soumission.',
  },
  f_nb_doublons_anterieurs: {
    label: 'Prestation identique déjà enregistrée',
    category: CATEGORIES.doublon,
    explanation: 'Une facture antérieure identique (même patient, prestataire, date et montant) a déjà été traitée.',
  },
  f_nb_factures_meme_jour_prest: {
    label: 'Multiples factures le même jour (fractionnement)',
    category: CATEGORIES.doublon,
    explanation: 'Plusieurs factures émises pour le même patient le même jour, signalant un possible découpage d’actes.',
  },
  doublon_facture: {
    label: 'Facture potentiellement dupliquée',
    category: CATEGORIES.doublon,
    explanation: 'Forte similitude constatée avec un dossier déjà instruit pour ce même assuré.',
  },
  delai_entre_actes: {
    label: 'Répétition rapprochée d’actes',
    category: CATEGORIES.doublon,
    explanation: 'Délai suspect entre deux actes identiques ou similaires.',
  },

  // --- Profil de l’Assuré ---
  f_sexe_incompatible_ref: {
    label: 'Incompatibilité sexe / acte médical',
    category: CATEGORIES.profil,
    explanation: 'L’acte facturé est strictement réservé au sexe opposé selon la nomenclature médicale officielle.',
  },
  f_age_hors_bornes_ref: {
    label: 'Âge incompatible avec l’acte médical',
    category: CATEGORIES.profil,
    explanation: 'L’âge de l’assuré est hors des bornes d’âge autorisées pour cet acte (ex. acte pédiatrique chez un adulte).',
  },
  f_age_au_soin: {
    label: 'Âge de l’assuré au moment du soin',
    category: CATEGORIES.profil,
    explanation: 'Âge calculé de l’assuré au moment de la réalisation de la prestation.',
  },

  // --- Établissement & Prestataire ---
  f_soin_jour_ferme: {
    label: 'Soin un jour de fermeture déclaré',
    category: CATEGORIES.prestataire,
    explanation: 'Prestation datée d’un jour où l’établissement est officiellement fermé.',
  },
  f_prestataire_non_conventionne: {
    label: 'Prestataire non conventionné',
    category: CATEGORIES.prestataire,
    explanation: 'Le professionnel de santé n’a pas de convention active avec l’organisme tiers payant.',
  },
  f_soin_apres_fin_convention: {
    label: 'Convention échue au moment du soin',
    category: CATEGORIES.prestataire,
    explanation: 'La convention du prestataire était résiliée ou échue à la date déclarée du soin.',
  },
  f_type_prest_vs_cat_acte: {
    label: 'Incohérence spécialité prestataire vs acte (upcoding)',
    category: CATEGORIES.prestataire,
    explanation: 'La spécialité du praticien ne correspond pas à la nature de l’acte facturé (ex. acte de spécialiste en médecine générale).',
  },
  jour_fermeture_etablissement: {
    label: 'Soin un jour de fermeture de l’établissement',
    category: CATEGORIES.prestataire,
    explanation: 'Acte médical déclaré un jour de fermeture hebdomadaire de l’établissement.',
  },

  // --- Droits & Couverture ---
  f_soin_avant_adhesion: {
    label: 'Soin antérieur à l’adhésion',
    category: CATEGORIES.couverture,
    explanation: 'La date du soin est antérieure à la date effective d’adhésion de l’assuré au contrat.',
  },
  f_soin_apres_radiation: {
    label: 'Soin postérieur à la radiation',
    category: CATEGORIES.couverture,
    explanation: 'La date du soin est postérieure à la date de radiation ou d’extinction des droits de l’assuré.',
  },
  f_soin_hors_periode_contrat: {
    label: 'Soin hors période de garantie contrat',
    category: CATEGORIES.couverture,
    explanation: 'Prestation réalisée en dehors des dates d’effet et de fin de la police d’assurance souscrite.',
  },
  f_soin_en_carence: {
    label: 'Période de carence non purgée',
    category: CATEGORIES.couverture,
    explanation: 'Prestation réclamée pendant le délai de carence contractuel applicable à la formule.',
  },
  acte_hors_contrat: {
    label: 'Prestation exclue du contrat',
    category: CATEGORIES.couverture,
    explanation: 'Acte médical non couvert par les garanties de la formule souscrite.',
  },
  quantite_atypique: {
    label: 'Quantité facturée atypique',
    category: CATEGORIES.prescription,
    explanation: 'Le volume d’actes ou de produits dépasse le standard habituel pour cette pathologie.',
  },
  frequence_des_actes: {
    label: 'Fréquence de recours élevée',
    category: CATEGORIES.doublon,
    explanation: 'Fréquence de facturation inhabituelle sur une courte période pour cet assuré.',
  },
}

/** Retrouve la clé sans préfixe f_ pour normalisation */
function resolveKey(feature: string): string {
  const trimmed = feature.trim()
  if (DEFINITIONS[trimmed]) return trimmed
  const stripped = trimmed.replace(/^f_/, '')
  if (DEFINITIONS[stripped]) return stripped
  const prefixed = `f_${trimmed}`
  if (DEFINITIONS[prefixed]) return prefixed
  return trimmed
}

/** Libellé métier clair et convivial pour l'interface gestionnaire */
export function factorLabel(feature: string): string {
  const key = resolveKey(feature)
  if (DEFINITIONS[key]) return DEFINITIONS[key].label

  // Repli propre : supprime préfixes techniques et met en forme lisible
  const cleaned = feature
    .trim()
    .replace(/^f_/, '')
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
  if (!cleaned) return 'Facteur non renseigné'
  return cleaned.charAt(0).toLocaleUpperCase('fr-FR') + cleaned.slice(1)
}

/** Description et explication métier détaillée du facteur */
export function factorExplanation(feature: string, apiDescription?: string): string {
  // Si l'API a fourni une description textuelle propre sans '= nan'
  if (apiDescription && !apiDescription.toLowerCase().includes('nan') && !apiDescription.toLowerCase().includes('null')) {
    const trimmed = apiDescription.trim()
    // Si l'API fournit déjà une phrase descriptive complète
    if (trimmed.length > 20 && !trimmed.includes('=')) {
      return trimmed
    }
  }

  const key = resolveKey(feature)
  if (DEFINITIONS[key]?.explanation) {
    return DEFINITIONS[key].explanation
  }

  return 'Ce critère statistique a contribué à l’évaluation du niveau de risque par le modèle.'
}

/** Catégorie métier avec libellé et badge associé */
export function factorCategory(feature: string): FactorCategory {
  const key = resolveKey(feature)
  return DEFINITIONS[key]?.category ?? CATEGORIES.general
}

/** Formate une valeur constatée sans jamais afficher de termes techniques (ex: nan) */
export function formatFactorValue(valeur: unknown): string | null {
  if (valeur === undefined || valeur === null) return null
  const str = String(valeur).trim().toLowerCase()
  if (str === 'nan' || str === 'none' || str === 'null' || str === '') return null

  if (typeof valeur === 'boolean' || str === 'true' || str === 'false') {
    return valeur === true || str === 'true' ? 'Constaté (Oui)' : 'Non constaté'
  }

  if (typeof valeur === 'number' || (!Number.isNaN(Number(str)) && !str.includes(':'))) {
    const num = typeof valeur === 'number' ? valeur : Number(str)
    if (Number.isNaN(num)) return null
    if (num === 1) return 'Signal avéré'
    if (num === 0) return 'Non constaté'
    if (Number.isInteger(num)) return String(num)
    return num.toLocaleString('fr-FR', { maximumFractionDigits: 2 })
  }

  return String(valeur)
}
