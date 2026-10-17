import { ApiError } from './errors'
import { getStoredSession } from './session'
import type {
  ClaimCreateRequest,
  ClaimCreateResponse,
  ClaimDetail,
  ClaimLine,
  ClaimListItem,
  ClaimsPage,
  DecisionRequest,
  DecisionResponse,
  DashboardKpis,
  DashboardPrediction,
  LoginRequest,
  LoginResponse,
  ManagerClaimIntake,
  ManagerClaimListItem,
  ManagerDecision,
  PredictionResponse,
  Role,
  UiRole,
} from './types'
import { toUiRole } from './types'

export interface MockAccount {
  identifier: string
  password: string
  role: UiRole
  display_name: string
  response: LoginResponse
}

function account(identifier: string, password: string, role: Role, id: string, nom_complet: string): MockAccount {
  const user = { id, identifier, role, nom_complet }
  return { identifier, password, role: toUiRole(role), display_name: nom_complet, response: {
    access_token: `mock-token-${role}`,
    token_type: 'bearer',
    expires_in: 3600,
    user,
  } }
}

export const mockAccounts: MockAccount[] = [
  account('gestionnaire1', 'Demo2026!', 'gestionnaire', 'USR-0012', 'Mialy Randria'),
  account('PR-0015', 'Demo2026!', 'professionnel_sante', 'USR-0015', 'Clinique Analamanga'),
  account('ASS-C60624BAFB', 'Demo2026!', 'assure', 'ASS-C60624BAFB', 'Tahina Andriam'),
  account('administrateur1', 'Demo2026!', 'administrateur', 'USR-0001', 'Soa Ravel'),
]

const demoMemberId = 'ASS-C60624BAFB'
const demoProviderId = 'PR-0015'
type MockClaim = ClaimDetail & Partial<Pick<ManagerClaimListItem, 'score_fraude' | 'est_anomalie'>>

const etablissements: Record<string, string> = {
  'PR-0015': 'Clinique Analamanga',
  'PR-00021': 'Cabinet Sainte-Marie',
  'PR-00034': 'Laboratoire Ivato',
}

function makeClaim(
  facture_id: string,
  statut: ClaimDetail['statut'],
  date_soin: string,
  motif_rejet: ClaimDetail['motif_rejet'],
  score_fraude: number,
  est_anomalie: boolean,
  lignes: ClaimLine[],
  assure_id: string = demoMemberId,
  prestataire_id: string = demoProviderId,
): MockClaim {
  const montant_total = lignes.reduce((sum, line) => sum + line.montant_total, 0)
  return {
    facture_id,
    numero_facture: `F-${facture_id.slice(-5)}`,
    assure_id,
    prestataire_id,
    date_soin,
    date_emission: '2026-10-15',
    montant_total,
    part_assure: 9_000,
    montant_demande: montant_total - 9_000,
    statut,
    score_fraude,
    est_anomalie,
    nom_etablissement: etablissements[prestataire_id] ?? 'Établissement non renseigné',
    ordonnance_id: 'ORD-0003289',
    motif_rejet,
    montant_pris_en_charge: statut === 'PAYEE' ? montant_total - 9_000 : null,
    lignes,
  }
}

const mockClaims = new Map<string, MockClaim>([
  ['FAC-00005637', makeClaim('FAC-00005637', 'EN_COURS', '2026-10-12', null, 0.12, false, [
    { num_ligne: 1, code: 'CONS-GEN', type_ligne: 'ACTE', quantite: 1, prix_unitaire: 20_000, montant_total: 20_000 },
    { num_ligne: 2, code: 'MED-FORTIF', type_ligne: 'MEDICAMENT', quantite: 1, prix_unitaire: 25_000, montant_total: 25_000 },
  ])],
  ['FAC-00005638', makeClaim('FAC-00005638', 'PAYEE', '2026-10-10', null, 0.48, false, [
    { num_ligne: 1, code: 'CONS-GEN', type_ligne: 'ACTE', quantite: 1, prix_unitaire: 20_000, montant_total: 20_000 },
    { num_ligne: 2, code: 'MED-PARA500', type_ligne: 'MEDICAMENT', quantite: 1, prix_unitaire: 2_000, montant_total: 2_000 },
  ])],
  ['FAC-00005639', makeClaim('FAC-00005639', 'REJETEE', '2026-10-08', 'ENTENTE_PREALABLE_ABSENTE', 0.88, true, [
    { num_ligne: 1, code: 'IMG-SCANNER', type_ligne: 'ACTE', quantite: 1, prix_unitaire: 60_000, montant_total: 60_000 },
  ])],
])

function line(
  num_ligne: number,
  code: string,
  type_ligne: ClaimLine['type_ligne'],
  quantite: number,
  prix_unitaire: number,
): ClaimLine {
  return { num_ligne, code, type_ligne, quantite, prix_unitaire, montant_total: quantite * prix_unitaire }
}

// Compléments de démonstration : les trois factures ci-dessus sont écrites à la main,
// ces lignes donnent assez de volume pour éprouver filtres, tri et pagination serveur.
interface ClaimSeed {
  facture_id: string
  statut: ClaimDetail['statut']
  date_soin: string
  motif_rejet: ClaimDetail['motif_rejet']
  score_fraude: number
  est_anomalie: boolean
  assure_id: string
  prestataire_id: string
  lignes: ClaimLine[]
}

const extraClaims: ClaimSeed[] = [
  { facture_id: 'FAC-00005640', statut: 'EN_COURS', date_soin: '2026-10-11', motif_rejet: null, score_fraude: 0.83, est_anomalie: true, assure_id: 'ASS-7B21C4D908', prestataire_id: 'PR-00021', lignes: [line(1, 'IMG-SCANNER', 'ACTE', 1, 60_000)] },
  { facture_id: 'FAC-00005641', statut: 'EN_COURS', date_soin: '2026-10-09', motif_rejet: null, score_fraude: 0.91, est_anomalie: true, assure_id: 'ASS-3F9E12A744', prestataire_id: 'PR-00034', lignes: [line(1, 'MED-FORTIF', 'MEDICAMENT', 2, 25_000)] },
  { facture_id: 'FAC-00005642', statut: 'EN_COURS', date_soin: '2026-10-07', motif_rejet: null, score_fraude: 0.77, est_anomalie: true, assure_id: 'ASS-C60624BAFB', prestataire_id: 'PR-0015', lignes: [line(1, 'CONS-GEN', 'ACTE', 1, 20_000), line(2, 'IMG-SCANNER', 'ACTE', 1, 60_000)] },
  { facture_id: 'FAC-00005643', statut: 'PAYEE', date_soin: '2026-10-06', motif_rejet: null, score_fraude: 0.22, est_anomalie: false, assure_id: 'ASS-7B21C4D908', prestataire_id: 'PR-00021', lignes: [line(1, 'CONS-GEN', 'ACTE', 1, 20_000)] },
  { facture_id: 'FAC-00005644', statut: 'REJETEE', date_soin: '2026-10-05', motif_rejet: 'PRODUIT_NON_REMBOURSABLE', score_fraude: 0.64, est_anomalie: true, assure_id: 'ASS-3F9E12A744', prestataire_id: 'PR-00034', lignes: [line(1, 'MED-FORTIF', 'MEDICAMENT', 1, 25_000)] },
  { facture_id: 'FAC-00005645', statut: 'PAYEE', date_soin: '2026-10-04', motif_rejet: null, score_fraude: 0.35, est_anomalie: false, assure_id: 'ASS-C60624BAFB', prestataire_id: 'PR-00021', lignes: [line(1, 'MED-PARA500', 'MEDICAMENT', 3, 2_000)] },
  { facture_id: 'FAC-00005646', statut: 'EN_COURS', date_soin: '2026-10-03', motif_rejet: null, score_fraude: 0.52, est_anomalie: false, assure_id: 'ASS-7B21C4D908', prestataire_id: 'PR-0015', lignes: [line(1, 'CONS-GEN', 'ACTE', 2, 20_000)] },
  { facture_id: 'FAC-00005647', statut: 'REJETEE', date_soin: '2026-10-02', motif_rejet: 'ORDONNANCE_PERIMEE', score_fraude: 0.79, est_anomalie: true, assure_id: 'ASS-3F9E12A744', prestataire_id: 'PR-00021', lignes: [line(1, 'MED-PARA500', 'MEDICAMENT', 1, 2_000)] },
  { facture_id: 'FAC-00005648', statut: 'EN_COURS', date_soin: '2026-10-01', motif_rejet: null, score_fraude: 0.44, est_anomalie: false, assure_id: 'ASS-C60624BAFB', prestataire_id: 'PR-0015', lignes: [line(1, 'IMG-SCANNER', 'ACTE', 1, 60_000), line(2, 'MED-PARA500', 'MEDICAMENT', 1, 2_000)] },
  { facture_id: 'FAC-00005649', statut: 'EN_COURS', date_soin: '2026-09-30', motif_rejet: null, score_fraude: 0.86, est_anomalie: true, assure_id: 'ASS-7B21C4D908', prestataire_id: 'PR-00034', lignes: [line(1, 'IMG-SCANNER', 'ACTE', 1, 60_000)] },
  { facture_id: 'FAC-00005650', statut: 'EN_COURS', date_soin: '2026-09-29', motif_rejet: null, score_fraude: 0.81, est_anomalie: true, assure_id: 'ASS-C60624BAFB', prestataire_id: 'PR-0015', lignes: [line(1, 'MED-FORTIF', 'MEDICAMENT', 1, 25_000), line(2, 'CONS-GEN', 'ACTE', 1, 20_000)] },
  { facture_id: 'FAC-00005651', statut: 'REJETEE', date_soin: '2026-09-28', motif_rejet: 'FACTURE_INVALIDE', score_fraude: 0.75, est_anomalie: true, assure_id: 'ASS-3F9E12A744', prestataire_id: 'PR-00034', lignes: [line(1, 'MED-PARA500', 'MEDICAMENT', 1, 2_000)] },
  { facture_id: 'FAC-00005652', statut: 'EN_COURS', date_soin: '2026-09-27', motif_rejet: null, score_fraude: 0.88, est_anomalie: true, assure_id: 'ASS-C60624BAFB', prestataire_id: 'PR-00021', lignes: [line(1, 'IMG-SCANNER', 'ACTE', 1, 60_000), line(2, 'MED-FORTIF', 'MEDICAMENT', 1, 25_000)] },
]
extraClaims.forEach((seed) => {
  mockClaims.set(seed.facture_id, makeClaim(
    seed.facture_id, seed.statut, seed.date_soin, seed.motif_rejet,
    seed.score_fraude, seed.est_anomalie, seed.lignes, seed.assure_id, seed.prestataire_id,
  ))
})

const mockPredictions: Record<string, PredictionResponse> = {
  'FAC-00005637': {
    facture_id: 'FAC-00005637',
    prediction: { score_fraude: 0.12, seuil_applique: 0.8, est_anomalie: false, version_modele: 'v1.0.0-xgb', date_prediction: '2026-10-15T08:32:00Z' },
    explicabilite: { top_facteurs: ['Tarif conforme au barème', { feature: 'ecart_tarif_conventionne', valeur: 0, impact_shap: -0.31 }], recommandation: 'Aucun signal prioritaire relevé.' },
  },
  'FAC-00005638': {
    facture_id: 'FAC-00005638',
    prediction: { score_fraude: 0.48, seuil_applique: 0.8, est_anomalie: false, version_modele: 'v1.0.0-xgb', date_prediction: '2026-10-15T08:35:00Z' },
    explicabilite: { top_facteurs: [{ feature: 'frequence_des_actes', valeur: 2, impact_shap: 0.42 }, { feature: 'montant_atypique', valeur: 22_000, impact_shap: -0.16 }], recommandation: 'Vérification courante recommandée.' },
  },
  'FAC-00005639': {
    facture_id: 'FAC-00005639',
    prediction: { score_fraude: 0.88, seuil_applique: 0.8, est_anomalie: true, version_modele: 'v1.0.0-xgb', date_prediction: '2026-10-15T08:41:00Z' },
    explicabilite: { top_facteurs: [{ feature: 'ecart_tarif_conventionne', valeur: 15_000, impact_shap: 0.38, description: 'Écart au tarif de référence.' }, { feature: 'jour_fermeture_etablissement', valeur: 1, impact_shap: 0.25 }], recommandation: 'Revue gestionnaire recommandée.' },
  },
}

const mockDecisions = new Map<string, DecisionResponse>()
let nextClaimNumber = 5640

export const mockKpis: DashboardKpis = {
  claims_received: 128,
  claims_to_review: 14,
  claims_processed: 114,
  reimbursements_mga: 18_450_000,
}

// Compatibilité du dashboard précédent, hors périmètre de cette étape.
export const mockPrediction: DashboardPrediction = {
  claim_id: 'PC-2026-00483',
  fraud_probability: 0.78,
  risk_level: 'high',
  model_version: 'predicare-0.4.2',
  explanation: { top_factors: ['Écart au tarif de référence', { feature: 'frequence_des_actes', shap_value: 0.38 }] },
}

function parseBody<T>(init: RequestInit): T {
  return JSON.parse(String(init.body ?? '{}')) as T
}

function currentAccount(): MockAccount | undefined {
  const session = getStoredSession()
  if (!session) return undefined
  return mockAccounts.find((item) => item.response.access_token === session.access_token)
}

function canSeeAllClaims(role: UiRole): boolean {
  return role === 'gestionnaire' || role === 'admin'
}

function requireScoringRole(account: MockAccount | undefined): asserts account is MockAccount {
  if (!account) throw new ApiError('Connexion requise. Connectez-vous puis réessayez.', 401)
  if (!canSeeAllClaims(account.role)) throw new ApiError('Les analyses sont réservées au gestionnaire.', 403)
}

function visibleClaim(claim: MockClaim, role: UiRole): ClaimListItem | ManagerClaimListItem {
  const base: ClaimListItem = {
    facture_id: claim.facture_id,
    numero_facture: claim.numero_facture,
    assure_id: claim.assure_id,
    prestataire_id: claim.prestataire_id,
    date_soin: claim.date_soin,
    date_emission: claim.date_emission,
    montant_total: claim.montant_total,
    part_assure: claim.part_assure,
    montant_demande: claim.montant_demande,
    statut: claim.statut,
  }
  if (!canSeeAllClaims(role)) return base
  return { ...base, score_fraude: claim.score_fraude ?? null, est_anomalie: claim.est_anomalie ?? null }
}

function visibleClaimDetail(claim: MockClaim): ClaimDetail {
  return {
    facture_id: claim.facture_id,
    numero_facture: claim.numero_facture,
    assure_id: claim.assure_id,
    prestataire_id: claim.prestataire_id,
    date_soin: claim.date_soin,
    date_emission: claim.date_emission,
    montant_total: claim.montant_total,
    part_assure: claim.part_assure,
    montant_demande: claim.montant_demande,
    statut: claim.statut,
    nom_etablissement: claim.nom_etablissement,
    ordonnance_id: claim.ordonnance_id,
    motif_rejet: claim.motif_rejet,
    montant_pris_en_charge: claim.montant_pris_en_charge,
    lignes: claim.lignes,
  }
}

function ensureClaimAccess(claim: MockClaim, account: MockAccount | undefined): void {
  if (!account) throw new ApiError('Connexion requise. Connectez-vous puis réessayez.', 401)
  if (account.role === 'assure' && claim.assure_id !== account.identifier) {
    throw new ApiError('Ce dossier ne correspond pas à votre identifiant assuré.', 403)
  }
  if (account.role === 'professionnel_sante' && claim.prestataire_id !== account.identifier) {
    throw new ApiError('Ce dossier ne correspond pas à votre espace prestataire.', 403)
  }
}

function listClaims(url: URL, account: MockAccount | undefined): ClaimsPage {
  if (!account) throw new ApiError('Connexion requise. Connectez-vous puis réessayez.', 401)
  const role = account.role
  const params = url.searchParams
  let items: MockClaim[] = [...mockClaims.values()]
  if (role === 'assure') items = items.filter((claim) => claim.assure_id === account.identifier)
  if (role === 'professionnel_sante') items = items.filter((claim) => claim.prestataire_id === account.identifier)
  const status = params.get('statut')
  if (status) items = items.filter((claim) => claim.statut === status)
  const start = params.get('date_debut')
  const end = params.get('date_fin')
  if (start) items = items.filter((claim) => claim.date_soin >= start)
  if (end) items = items.filter((claim) => claim.date_soin <= end)
  if (params.get('fraud_alert_only') === 'true' && canSeeAllClaims(role)) {
    items = items.filter((claim) => claim.est_anomalie === true)
  }
  // À brancher: `q`, `decision_enregistree` et `sort` n'existent pas encore dans le
  // contrat M2 (docs/contrats_interface.md §3.3) ; ils ne sont interprétés qu'ici.
  const query = params.get('q')?.trim().toLowerCase()
  if (query) items = items.filter((claim) => claim.facture_id.toLowerCase().includes(query))
  const decisionEnregistree = params.get('decision_enregistree')
  if (decisionEnregistree !== null) {
    const decided = decisionEnregistree === 'true'
    items = items.filter((claim) => mockDecisions.has(claim.facture_id) === decided)
  }
  if (params.get('sort') === 'score_fraude:desc') {
    items = [...items].sort((left, right) => (right.score_fraude ?? 0) - (left.score_fraude ?? 0))
  }
  const total = items.length
  const page = Math.max(1, Number(params.get('page') ?? 1))
  const pageSize = Math.min(100, Math.max(1, Number(params.get('page_size') ?? 20)))
  return {
    total,
    page,
    page_size: pageSize,
    items: items.slice((page - 1) * pageSize, page * pageSize)
      .map((claim) => visibleClaim(claim, role)),
  }
}

/** Analyse de repli pour les factures de démonstration sans prédiction écrite à la main. */
function predictionFor(claim: MockClaim): PredictionResponse {
  const est_anomalie = claim.est_anomalie ?? false
  return {
    facture_id: claim.facture_id,
    prediction: {
      score_fraude: claim.score_fraude ?? 0,
      seuil_applique: 0.8,
      est_anomalie,
      version_modele: 'v1.0.0-xgb',
      date_prediction: '2026-10-15T08:41:00Z',
    },
    explicabilite: {
      top_facteurs: est_anomalie
        ? [
            { feature: 'ecart_tarif_conventionne', valeur: 15_000, impact_shap: 0.38, description: 'Écart au tarif de référence.' },
            { feature: 'absence_entente_prealable', valeur: 1, impact_shap: 0.22 },
          ]
        : [{ feature: 'montant_atypique', valeur: 0, impact_shap: -0.24 }],
      recommandation: est_anomalie ? 'Revue gestionnaire recommandée.' : 'Aucun signal prioritaire relevé.',
    },
  }
}

export function resolveMock<T>(path: string, init: RequestInit): T {
  const url = new URL(path, 'http://predicare.mock')
  const account = currentAccount()
  const method = (init.method ?? 'GET').toUpperCase()

  if (url.pathname === '/auth/login' && method === 'POST') {
    const credentials = parseBody<LoginRequest>(init)
    const match = mockAccounts.find((candidate) => candidate.identifier === credentials.identifier && candidate.password === credentials.password)
    if (!match) throw new ApiError('Identifiant ou mot de passe invalide. Vérifiez vos informations puis réessayez.', 401)
    return match.response as T
  }
  if (url.pathname === '/auth/me') {
    if (!account) throw new ApiError('Session expirée. Reconnectez-vous pour continuer.', 401)
    return account.response.user as T
  }
  if (url.pathname === '/dashboard/kpis') {
    requireScoringRole(account)
    return mockKpis as T
  }
  if (url.pathname === '/predictions/latest') {
    requireScoringRole(account)
    return mockPrediction as T
  }
  if (url.pathname === '/claims' && method === 'GET') return listClaims(url, account) as T

  if (url.pathname === '/claims' && method === 'POST') {
    const payload = parseBody<ClaimCreateRequest & Partial<Pick<ManagerClaimIntake, 'date_reception' | 'canal_reception' | 'mode_reglement'>>>(init)
    const isManagerReceipt = account?.role === 'gestionnaire' && Boolean(payload.canal_reception)
    if (!account || (!['professionnel_sante', 'administrateur'].includes(account.response.user.role) && !isManagerReceipt)) {
      throw new ApiError('Votre profil ne peut pas transmettre cette facture.', 403)
    }
    const factureId = `FAC-${String(nextClaimNumber++).padStart(8, '0')}`
    const lignes: ClaimLine[] = payload.lignes.map((line) => {
      const quantite = line.quantite
      const prixUnitaire = line.prix_unitaire
      return {
        num_ligne: line.num_ligne,
        code: line.code,
        type_ligne: line.type_ligne,
        quantite,
        prix_unitaire: prixUnitaire,
        montant_total: line.montant_total,
      }
    })
    const detail: MockClaim = {
      facture_id: factureId,
      numero_facture: String(payload.numero_facture ?? factureId),
      assure_id: String(payload.assure_id ?? demoMemberId),
      prestataire_id: String(payload.prestataire_id ?? demoProviderId),
      date_soin: String(payload.date_soin ?? '2026-10-14'),
      date_emission: payload.date_emission,
      montant_total: payload.montant_total,
      part_assure: payload.part_assure,
      montant_demande: payload.montant_total - payload.part_assure,
      statut: 'EN_COURS',
      score_fraude: 0.48,
      est_anomalie: false,
      nom_etablissement: 'Clinique Analamanga',
      ordonnance_id: payload.ordonnance_id,
      motif_rejet: null,
      montant_pris_en_charge: null,
      lignes,
    }
    mockClaims.set(factureId, detail)
    mockPredictions[factureId] = {
      ...mockPredictions['FAC-00005638'],
      facture_id: factureId,
    }
    const response: ClaimCreateResponse = {
      facture_id: factureId,
      statut: 'EN_COURS',
      score_fraude: 0.48,
      est_anomalie: false,
      seuil_applique: 0.8,
      message: 'Facture enregistrée. Le dossier est transmis au gestionnaire.',
    }
    return response as T
  }

  const predictionMatch = url.pathname.match(/^\/claims\/([^/]+)\/prediction$/)
  if (predictionMatch) {
    if (!account || !canSeeAllClaims(account.role)) throw new ApiError('Cette analyse est réservée au gestionnaire.', 403)
    const factureId = decodeURIComponent(predictionMatch[1])
    const source = mockClaims.get(factureId)
    const prediction = mockPredictions[factureId] ?? (source ? predictionFor(source) : undefined)
    if (prediction) return prediction as T
    throw new ApiError(`Aucune analyse simulée pour la facture ${factureId}.`, 404)
  }

  const decisionMatch = url.pathname.match(/^\/claims\/([^/]+)\/decision$/)
  if (decisionMatch && method === 'POST') {
    if (!account || !canSeeAllClaims(account.role)) throw new ApiError('Cette action est réservée au gestionnaire.', 403)
    const factureId = decodeURIComponent(decisionMatch[1])
    const body = parseBody<DecisionRequest>(init)
    const claim = mockClaims.get(factureId)
    if (!claim) throw new ApiError(`Facture ${factureId} introuvable.`, 404)
    const decision = body.decision as ManagerDecision
    const status = decision === 'VALIDE' ? 'PAYEE' : decision === 'REJETE' ? 'REJETEE' : 'EN_COURS'
    const result: DecisionResponse = {
      facture_id: factureId,
      statut: status,
      decision,
      gestionnaire_id: account.response.user.id,
      date_decision: new Date().toISOString(),
      message: 'Décision enregistrée avec succès.',
    }
    mockDecisions.set(factureId, result)
    mockClaims.set(factureId, { ...claim, statut: status })
    return result as T
  }

  const detailMatch = url.pathname.match(/^\/claims\/([^/]+)$/)
  if (detailMatch) {
    const factureId = decodeURIComponent(detailMatch[1])
    const claim = mockClaims.get(factureId)
    if (!claim) throw new ApiError(`Facture ${factureId} introuvable.`, 404)
    ensureClaimAccess(claim, account)
    return (canSeeAllClaims(account!.role) ? claim : visibleClaimDetail(claim)) as T
  }

  throw new ApiError(`La route simulée « ${url.pathname} » n’est pas configurée.`, 404)
}
