export interface FactorCategory {
  key: 'tarif' | 'prescription' | 'profil' | 'prestataire' | 'couverture' | 'doublon' | 'general'
  label: string
  badgeClass: string
}

export interface FactorDefinition {
  label: string
  category: FactorCategory
  explanation: string
  /** Description technique/métier extraite de features.py (FEATURE_CATALOGUE) */
  descriptionML?: string
  /** Typologie de fraude ciblée dans features.py */
  fraudeVisee?: string
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

/** Dictionnaire complet des 28 variables du modèle de détection et règles métier (issu de features.py) */
const DEFINITIONS: Record<string, FactorDefinition> = {
  // --- Groupe 1 : Tarification & Plafonds (SURFACTURATION) ---
  f_ecart_grille_prest_moy: {
    label: 'Dépassement de la grille conventionnelle',
    category: CATEGORIES.tarif,
    explanation: 'Le tarif pratiqué dépasse le barème négocié dans la convention de ce prestataire.',
    descriptionML: "Écart moyen (prix facturé − tarif_pratique de la grille prestataire) sur les lignes ayant un code dans la grille. Valeur positive = dépassement de la grille conventionnelle.",
    fraudeVisee: 'SURFACTURATION',
  },
  f_ecart_tarif_max_moy: {
    label: 'Dépassement du tarif plafond légal',
    category: CATEGORIES.tarif,
    explanation: 'Le prix unitaire moyen facturé excède le tarif maximal autorisé par le référentiel national.',
    descriptionML: "Écart moyen (prix facturé − tarif_max du référentiel) sur les lignes d'actes. Valeur positive = surfacturation par rapport au plafond.",
    fraudeVisee: 'SURFACTURATION',
  },
  f_ratio_tarif_ref_max: {
    label: 'Multiplicateur de tarif de référence excessif',
    category: CATEGORIES.tarif,
    explanation: 'Ratio élevé entre le montant facturé et le tarif de référence national opposable.',
    descriptionML: "Ratio maximal (prix facturé / tarif_reference du référentiel) sur les lignes d'actes. Ratio > 1 = facturation au-dessus du tarif de référence.",
    fraudeVisee: 'SURFACTURATION',
  },
  f_nb_lignes_hors_tarif_max: {
    label: 'Lignes excédant le tarif plafond',
    category: CATEGORIES.tarif,
    explanation: 'Plusieurs prestations de cette facture dépassent la borne supérieure de tarification.',
    descriptionML: "Nombre de lignes d'actes dont le prix unitaire dépasse le tarif_max du référentiel.",
    fraudeVisee: 'SURFACTURATION',
  },
  f_ratio_med_prix_ref_max: {
    label: 'Surcoût médicament vs référence',
    category: CATEGORIES.tarif,
    explanation: 'Le prix unitaire des médicaments facturés dépasse très significativement le référentiel pharmaceutique.',
    descriptionML: "Ratio maximal (prix médicament facturé / prix_reference du référentiel) sur les lignes de médicaments.",
    fraudeVisee: 'SURFACTURATION',
  },
  ecart_tarif_conventionne: {
    label: 'Écart au tarif conventionné',
    category: CATEGORIES.tarif,
    explanation: 'Différence significative constatée par rapport au tarif conventionnel applicable.',
    descriptionML: "Écart constaté entre le montant facturé et la grille tarifaire conventionnée applicable.",
    fraudeVisee: 'SURFACTURATION',
  },
  montant_atypique: {
    label: 'Montant atypique',
    category: CATEGORIES.tarif,
    explanation: 'Le montant total de la facture est anormalement supérieur à la moyenne des dossiers comparables.',
    descriptionML: "Montant total de la facture s'écartant significativement de la distribution habituelle.",
    fraudeVisee: 'SURFACTURATION',
  },
  montant_facture_atypique: {
    label: 'Montant facturé atypique',
    category: CATEGORIES.tarif,
    explanation: 'Montant global anormalement élevé au regard des actes mentionnés.',
    descriptionML: "Montant global anormalement élevé au regard des actes mentionnés.",
    fraudeVisee: 'SURFACTURATION',
  },
  prix_unitaire_atypique: {
    label: 'Prix unitaire atypique',
    category: CATEGORIES.tarif,
    explanation: 'Un ou plusieurs actes présentent un prix unitaire inhabituel.',
    descriptionML: "Prix unitaire d'un ou plusieurs actes s'écartant des bornes statistiques usuelles.",
    fraudeVisee: 'SURFACTURATION',
  },

  // --- Groupe 2 & 3 & 4 : Prescription & Ordonnance ---
  f_qte_fac_vs_prescrite_max: {
    label: 'Quantité supérieure à la prescription',
    category: CATEGORIES.prescription,
    explanation: 'La quantité délivrée excède la prescription médicale figurant sur l’ordonnance.',
    descriptionML: "Ratio maximal (quantité facturée / quantité prescrite) parmi les lignes dont le code figure dans l'ordonnance. Valeur > 1 = surconsommation.",
    fraudeVisee: 'QUANTITE_EXCESSIVE',
  },
  f_nb_lignes_qte_excessive: {
    label: 'Prestations en quantité anormale',
    category: CATEGORIES.prescription,
    explanation: 'Nombre de lignes pour lesquelles le volume délivré est supérieur au besoin thérapeutique prescrit.',
    descriptionML: "Nombre de lignes pour lesquelles la quantité facturée dépasse la quantité prescrite dans l'ordonnance.",
    fraudeVisee: 'QUANTITE_EXCESSIVE',
  },
  f_part_lignes_hors_ordonnance: {
    label: 'Actes non prescrits sur l’ordonnance',
    category: CATEGORIES.prescription,
    explanation: 'Des prestations ou produits facturés ne figurent pas sur l’ordonnance rattachée.',
    descriptionML: "Part (ratio 0-1) des lignes facturées dont le code est absent de l'ordonnance associée. NaN si pas d'ordonnance.",
    fraudeVisee: 'LIGNES_NON_PRESCRITES',
  },
  f_med_hors_ordo_cher: {
    label: 'Médicament coûteux non prescrit',
    category: CATEGORIES.prescription,
    explanation: 'Délivrance d’un médicament onéreux absent de l’ordonnance originale prescrite par le praticien.',
    descriptionML: "Indicateur (0/1) : au moins un médicament facturé est absent de l'ordonnance ET son prix unitaire dépasse le prix_reference médian du référentiel médicaments.",
    fraudeVisee: 'SUBSTITUTION_PRODUIT',
  },
  f_ordonnance_absente_requise: {
    label: 'Ordonnance obligatoire non transmise',
    category: CATEGORIES.prescription,
    explanation: 'Prestation soumise à prescription médicale obligatoire mais transmise sans ordonnance.',
    descriptionML: "Indicateur (0/1) : la facture n'a pas d'ordonnance (ordonnance_id null) mais contient au moins un acte pour lequel ordonnance_requise = 1 dans le référentiel.",
    fraudeVisee: 'ACTE_FICTIF',
  },
  f_ordonnance_autre_assure: {
    label: 'Ordonnance au nom d’un tiers',
    category: CATEGORIES.prescription,
    explanation: 'L’ordonnance rattachée mentionne un assuré distinct du bénéficiaire des soins.',
    descriptionML: "Indicateur (0/1) : l'ordonnance associée appartient à un assure_id différent de celui de la facture.",
    fraudeVisee: 'ACTE_FICTIF',
  },
  f_delai_soin_prescription_j: {
    label: 'Délai prescription - soin anormal',
    category: CATEGORIES.prescription,
    explanation: 'Écart temporel inhabituel entre la date d’ordonnance et la réalisation de la prestation.',
    descriptionML: "Nombre de jours entre la date de prescription et la date de soin (date_soin − date_prescription). Valeur négative = soin avant prescription.",
    fraudeVisee: 'ORDONNANCE_EXPIREE',
  },
  f_ordonnance_expiree: {
    label: 'Ordonnance médicalement expirée',
    category: CATEGORIES.prescription,
    explanation: 'La prestation a été effectuée après la fin de validité réglementaire de l’ordonnance.',
    descriptionML: "Indicateur (0/1) : le délai soin−prescription dépasse la validite_jours de l'ordonnance.",
    fraudeVisee: 'ORDONNANCE_EXPIREE',
  },
  f_nb_prest_meme_ordo_anterieurs: {
    label: 'Ordonnance multi-prestataires (nomadisme)',
    category: CATEGORIES.prescription,
    explanation: 'Cette ordonnance a déjà été présentée et facturée auprès d’autres établissements de santé.',
    descriptionML: "Nombre de prestataires distincts ayant facturé la même ordonnance_id dans des factures antérieures (hors ordonnance_id null).",
    fraudeVisee: 'SURCONSOMMATION',
  },
  prescription_non_conforme: {
    label: 'Prescription non conforme',
    category: CATEGORIES.prescription,
    explanation: 'L’ordonnance transmise ne respecte pas les critères formels requis pour la prise en charge.',
    descriptionML: "Ordonnance ou prescription ne satisfaisant pas aux critères formels et réglementaires.",
    fraudeVisee: 'ACTE_FICTIF',
  },
  absence_entente_prealable: {
    label: 'Entente préalable requise manquante',
    category: CATEGORIES.prescription,
    explanation: 'Accord médical préalable obligatoire non joint au dossier.',
    descriptionML: "Prestation soumise à entente préalable transmise sans validation préalable de l'organisme.",
    fraudeVisee: 'HORS_COUVERTURE',
  },
  piece_justificative_manquante: {
    label: 'Pièce justificative manquante',
    category: CATEGORIES.prescription,
    explanation: 'Document de justification obligatoire absent de la télétransmission.',
    descriptionML: "Justificatif obligatoire absent lors de la soumission de la facture.",
    fraudeVisee: 'ACTE_FICTIF',
  },

  // --- Groupe 6 : Doublons & Fractionnement ---
  f_numero_facture_deja_vu: {
    label: 'Numéro de facture dupliqué',
    category: CATEGORIES.doublon,
    explanation: 'Ce même numéro de facture a déjà été télétransmis par ce prestataire dans une autre soumission.',
    descriptionML: "Indicateur (0/1) : le numero_facture apparaît dans au moins une facture antérieure.",
    fraudeVisee: 'DOUBLON',
  },
  f_nb_doublons_anterieurs: {
    label: 'Prestation identique déjà enregistrée',
    category: CATEGORIES.doublon,
    explanation: 'Une facture antérieure identique (même patient, prestataire, date et montant) a déjà été traitée.',
    descriptionML: "Nombre de factures antérieures (ordre date_soin, facture_id) pour le même triplet (assure_id, prestataire_id, date_soin) avec le même montant_total.",
    fraudeVisee: 'DOUBLON',
  },
  f_nb_factures_meme_jour_prest: {
    label: 'Multiples factures le même jour (fractionnement)',
    category: CATEGORIES.doublon,
    explanation: 'Plusieurs factures émises pour le même patient le même jour, signalant un possible découpage d’actes.',
    descriptionML: "Nombre de factures antérieures pour le même (assure_id, prestataire_id, date_soin), sans contrainte de montant — signal de fractionnement.",
    fraudeVisee: 'FRACTIONNEMENT',
  },
  doublon_facture: {
    label: 'Facture potentiellement dupliquée',
    category: CATEGORIES.doublon,
    explanation: 'Forte similitude constatée avec un dossier déjà instruit pour ce même assuré.',
    descriptionML: "Similarité ou duplication identifiée avec une facture antérieure déjà instruite.",
    fraudeVisee: 'DOUBLON',
  },
  delai_entre_actes: {
    label: 'Répétition rapprochée d’actes',
    category: CATEGORIES.doublon,
    explanation: 'Délai suspect entre deux actes identiques ou similaires.',
    descriptionML: "Délai anormalement court entre la répétition d'actes identiques pour le même bénéficiaire.",
    fraudeVisee: 'FRACTIONNEMENT',
  },

  // --- Groupe 8 : Profil de l’Assuré ---
  f_sexe_incompatible_ref: {
    label: 'Incompatibilité sexe / acte médical',
    category: CATEGORIES.profil,
    explanation: 'L’acte facturé est strictement réservé au sexe opposé selon la nomenclature médicale officielle.',
    descriptionML: "Indicateur (0/1) : le sexe de l'assuré est incompatible avec sexe_requis du référentiel pour au moins un acte (quand sexe_requis est renseigné).",
    fraudeVisee: 'INCOHERENCE_PROFIL',
  },
  f_age_hors_bornes_ref: {
    label: 'Âge incompatible avec l’acte médical',
    category: CATEGORIES.profil,
    explanation: 'L’âge de l’assuré est hors des bornes d’âge autorisées pour cet acte (ex. acte pédiatrique chez un adulte).',
    descriptionML: "Indicateur (0/1) : l'âge de l'assuré est hors des bornes [age_min, age_max] du référentiel pour au moins un acte facturé.",
    fraudeVisee: 'INCOHERENCE_PROFIL',
  },
  f_age_au_soin: {
    label: 'Âge de l’assuré au moment du soin',
    category: CATEGORIES.profil,
    explanation: 'Âge calculé de l’assuré au moment de la réalisation de la prestation.',
    descriptionML: "Âge de l'assuré au moment du soin, calculé comme year(date_soin) − annee_naissance.",
    fraudeVisee: 'INCOHERENCE_PROFIL',
  },

  // --- Groupe 5 & 9 & 11 : Établissement & Prestataire ---
  f_soin_jour_ferme: {
    label: 'Soin un jour de fermeture déclaré',
    category: CATEGORIES.prestataire,
    explanation: 'Prestation datée d’un jour où l’établissement est officiellement fermé.',
    descriptionML: "Indicateur (0/1) : le jour de la semaine du soin n'est pas dans les jours_ouverture déclarés du prestataire (encodage : chiffres 1=lun … 7=dim concaténés).",
    fraudeVisee: 'SOINS_JOUR_FERME',
  },
  f_prestataire_non_conventionne: {
    label: 'Prestataire non conventionné',
    category: CATEGORIES.prestataire,
    explanation: 'Le professionnel de santé n’a pas de convention active avec l’organisme tiers payant.',
    descriptionML: "Indicateur (0/1) : le prestataire n'est pas conventionné (conventionne = 0).",
    fraudeVisee: 'PRESTATAIRE_RADIE',
  },
  f_soin_apres_fin_convention: {
    label: 'Convention échue au moment du soin',
    category: CATEGORIES.prestataire,
    explanation: 'La convention du prestataire était résiliée ou échue à la date déclarée du soin.',
    descriptionML: "Indicateur (0/1) : date_soin > date_fin_convention du prestataire (quand date_fin_convention n'est pas null).",
    fraudeVisee: 'PRESTATAIRE_RADIE',
  },
  f_type_prest_vs_cat_acte: {
    label: 'Incohérence spécialité prestataire vs acte (upcoding)',
    category: CATEGORIES.prestataire,
    explanation: 'La spécialité du praticien ne correspond pas à la nature de l’acte facturé (ex. acte de spécialiste en médecine générale).',
    descriptionML: "Indicateur (0/1) : consultation de spécialiste (spécialité de l'acte ni GENERALISTE ni URGENCE) facturée par un cabinet généraliste, ou par un cabinet spécialiste d'une autre spécialité. NaN sans consultation.",
    fraudeVisee: 'UPCODING',
  },
  jour_fermeture_etablissement: {
    label: 'Soin un jour de fermeture de l’établissement',
    category: CATEGORIES.prestataire,
    explanation: 'Acte médical déclaré un jour de fermeture hebdomadaire de l’établissement.',
    descriptionML: "Prestation datée d'un jour où l'établissement de santé est officiellement fermé.",
    fraudeVisee: 'SOINS_JOUR_FERME',
  },

  // --- Groupe 10 : Droits & Couverture (HORS_COUVERTURE) ---
  f_soin_avant_adhesion: {
    label: 'Soin antérieur à l’adhésion',
    category: CATEGORIES.couverture,
    explanation: 'La date du soin est antérieure à la date effective d’adhésion de l’assuré au contrat.',
    descriptionML: "Indicateur (0/1) : date_soin est antérieure à la date d'adhésion de l'assuré.",
    fraudeVisee: 'HORS_COUVERTURE',
  },
  f_soin_apres_radiation: {
    label: 'Soin postérieur à la radiation',
    category: CATEGORIES.couverture,
    explanation: 'La date du soin est postérieure à la date de radiation ou d’extinction des droits de l’assuré.',
    descriptionML: "Indicateur (0/1) : l'assuré est radié (date_radiation non null) et date_soin > date_radiation.",
    fraudeVisee: 'HORS_COUVERTURE',
  },
  f_soin_hors_periode_contrat: {
    label: 'Soin hors période de garantie contrat',
    category: CATEGORIES.couverture,
    explanation: 'Prestation réalisée en dehors des dates d’effet et de fin de la police d’assurance souscrite.',
    descriptionML: "Indicateur (0/1) : date_soin est hors de la période [date_effet, date_fin] du contrat (date_fin null = contrat ouvert).",
    fraudeVisee: 'HORS_COUVERTURE',
  },
  f_soin_en_carence: {
    label: 'Période de carence non purgée',
    category: CATEGORIES.couverture,
    explanation: 'Prestation réclamée pendant le délai de carence contractuel applicable à la formule.',
    descriptionML: "Indicateur (0/1) : date_soin < date_adhesion + delai_carence_jours pour la formule et la catégorie de l'acte dominant du contrat.",
    fraudeVisee: 'HORS_COUVERTURE',
  },
  acte_hors_contrat: {
    label: 'Prestation exclue du contrat',
    category: CATEGORIES.couverture,
    explanation: 'Acte médical non couvert par les garanties de la formule souscrite.',
    descriptionML: "Acte ou prestation absent des garanties souscrites dans le contrat de l'assuré.",
    fraudeVisee: 'HORS_COUVERTURE',
  },
  quantite_atypique: {
    label: 'Quantité facturée atypique',
    category: CATEGORIES.prescription,
    explanation: 'Le volume d’actes ou de produits dépasse le standard habituel pour cette pathologie.',
    descriptionML: "Volume d'actes ou de délivrances supérieur aux recommandations thérapeutiques habituelles.",
    fraudeVisee: 'QUANTITE_EXCESSIVE',
  },
  frequence_des_actes: {
    label: 'Fréquence de recours élevée',
    category: CATEGORIES.doublon,
    explanation: 'Fréquence de facturation inhabituelle sur une courte période pour cet assuré.',
    descriptionML: "Fréquence de recours anormalement élevée constatée sur une courte période temporelle.",
    fraudeVisee: 'SURCONSOMMATION',
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

/** Description technique/métier issue directement de features.py (FEATURE_CATALOGUE) */
export function factorDescriptionML(feature: string): string | undefined {
  const key = resolveKey(feature)
  return DEFINITIONS[key]?.descriptionML
}

/** Typologie de fraude visée issue de features.py (FEATURE_CATALOGUE) */
export function factorFraudeVisee(feature: string): string | undefined {
  const key = resolveKey(feature)
  return DEFINITIONS[key]?.fraudeVisee
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
