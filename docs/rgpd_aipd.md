# AIPD simplifiée — Pipeline RAG PrediCare TPA

## 1. Contexte

PrediCare TPA traite des données de santé (actes, pathologies, remboursements)
de bénéficiaires d'assurance santé. Ce document constitue une **Analyse
d'Impact relative à la Protection des Données** (AIPD) simplifiée.

## 2. Qualification RGPD

| Question | Réponse | Conséquence |
|---|---|---|
| Données de santé ? | Oui | Art. 9 — catégorie spéciale |
| Identifiants ? | Pseudonymisés (ASS-xxx) | Reste **personnel** au sens RGPD |
| Personnes concernées ? | Assurés, conjoints, enfants | ~1000+ |
| Traitement automatisé ? | Oui | AIPD obligatoire (Art. 35) |
| Transfert hors UE ? | **Non** (modèle local) | Pas de Chapitre V |

## 3. Base légale

**Art. 9.2.a** : consentement explicite
OU
**Art. 9.2.g** : intérêt public important (à trancher avec le DPO)

## 4. Principes appliqués

| Principe | Mise en œuvre |
|---|---|
| **Minimisation** | Les chunks ne contiennent pas de PII en clair. Les identifiants sont pseudonymisés. |
| **Limitation des finalités** | Le RAG sert uniquement la gestion du contrat. |
| **Exactitude** | Le corpus est versionné (checksum). |
| **Limitation de conservation** | À définir avec le DPO (proposition : 5 ans après fin de contrat). |
| **Intégrité / confidentialité** | PII chiffrés (`pgcrypto`), accès RBAC, journal d'audit. |
| **Responsabilité** | Registre de traitement, ce document, docs/rag_architecture.md |

## 5. Mesures techniques et organisationnelles

### Pseudonymisation
- Les identifiants (`ASS-xxx`) sont stockés en clair dans `assures`
- Les PII (nom, prénom, etc.) sont chiffrés dans `identites_pii` avec `pgcrypto`
- Le pipeline RAG n'accède **jamais** aux PII

### Isolation des données
- Les chunks du RAG ne contiennent **que** :
  - Des identifiants pseudonymisés (contract_id, assure_id)
  - Des données non-personnelles (barème, CG, guides)
  - Jamais de nom/prénom/adresse en clair

### Contrôle d'accès
- RBAC par rôle (assure / prestataire / gestionnaire / admin)
- Un assuré ne peut interroger que son propre dossier (filtres `contract_id`)

### Journalisation
- Table `journal_audit` : toute action sensible est tracée

## 6. Risques et mitigations

| Risque | Gravité | Mitigation |
|---|---|---|
| Fuite de PII | Élevée | Chiffrement pgcrypto |
| Réidentification | Moyenne | Pseudonymisation + séparation des tables |
| Accès non autorisé | Élevée | RBAC + JWT |
| Transfert hors UE | **Éliminé** | Modèle d'embedding local (BGE-M3) |
| Sous-traitant IA | **Éliminé** | Pas d'API externe |

## 7. Droits des personnes

| Droit | Mise en œuvre |
|---|---|
| Accès | Endpoint `/auth/me` + consultation de ses dossiers |
| Rectification | Via formulaire / gestionnaire |
| Effacement | Champ `actif` (soft delete) + DELETE en cascade |
| Opposition | À gérer manuellement |

## 8. Choix d'embedding et RGPD

**Décision** : BGE-M3 servi en **local** via Ollama (pas d'API externe).

**Justifications RGPD :**
- Aucun transfert de données hors UE
- Aucun sous-traitant IA supplémentaire (pas de DPA OpenAI à signer)
- Souveraineté complète sur les vecteurs

## 9. Références

- RGPD Art. 9, 35
- CNIL — AIPD
- Loi malgache n° 2014-038
- docs/eu_ai_act_classification.md