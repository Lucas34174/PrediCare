# Classification EU AI Act — Système RAG PrediCare TPA

## 1. Contexte

PrediCare TPA est un système d'IA utilisé dans la gestion de tiers payant
santé (remboursements, prises en charge, contrôle médical, assistant RAG
pour les assurés).

Ce document classe le système selon le Règlement (UE) 2024/1689 (EU AI Act).

## 2. Classification

### Système considéré

Le périmètre analysé couvre :
- Le pipeline RAG (parsing, chunking, embedding, retrieval)
- Le modèle de détection de fraude (XGBoost, PB-19)
- L'agent ReAct (PB-36)
- Le tableau de bord et les décisions gestionnaires

### Catégorie : **HAUT RISQUE**

Référence : **Annexe III, point 5.b) — Accès aux services essentiels**

> "Les systèmes d'IA destinés à être utilisés pour l'évaluation des risques
> et la tarification en ce qui concerne les personnes physiques dans le cas
> de l'assurance vie et santé."

**Justifications :**
1. Le système intervient dans l'**accès aux soins remboursés** d'assurés réels.
2. Le modèle de fraude attribue un **score de risque** aux factures.
3. Les décisions (arbitrage gestionnaire) impactent directement le bénéficiaire.

## 3. Obligations applicables

| Obligation EU AI Act | Article | Statut PrediCare | Preuve |
|---|---|---|---|
| Système de management des risques | Art. 9 | À formaliser | Ce document + plan |
| Gouvernance des données | Art. 10 | Partiel | docs/chunking_strategy.md |
| Documentation technique | Art. 11 + Annexe IV | En cours | docs/rag_architecture.md |
| Journalisation | Art. 12 | ✅ | Table `journal_audit` |
| Transparence | Art. 13 | À implémenter | Endpoint `/assistant/chat` |
| Supervision humaine | Art. 14 | ✅ | `decisions_gestionnaire` |
| Exactitude / robustesse / cybersécurité | Art. 15 | Partiel | Tests à venir |
| Évaluation de conformité | Art. 43 | À faire | docs/equity_audit.md |
| Marquage CE | Art. 48 | À faire | (hors périmètre pédagogique) |
| Enregistrement UE | Art. 49 | À faire | (hors périmètre pédagogique) |

## 4. Risques identifiés et mitigations

| Risque | Impact | Mitigation |
|---|---|---|
| Réponse erronée du RAG | Décision de remboursement erronée | Citations obligatoires + seuil de similarité |
| Biais de genre / âge | Discrimination | Audit d'équité (docs/equity_audit.md) |
| Fuite de données de santé | Sanction RGPD | PII chiffrés + pseudonymisation |
| Hallucination du LLM | Désinformation | Refus de spéculer (PB-36) |

## 5. Limites assumées

- Le système est un POC pédagogique. La conformité **complète** nécessiterait
  un organisme notifié, un marquage CE, un enregistrement UE.
- Les données sont **synthétiques** (pas de personnes réelles).

## 6. Références

- Règlement (UE) 2024/1689, Annexe III.5.b
- CNIL — Recommandations IA
- docs/rgpd_aipd.md
- docs/equity_audit.md