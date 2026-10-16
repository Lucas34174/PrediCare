# Plan d'audit d'équité — RAG PrediCare TPA

## 1. Contexte

Obligation EU AI Act (Art. 10) : gouvernance des données et lutte contre
les biais. Obligation RGPD Art. 35 : AIPD.

Ce document décrit la **méthode d'audit d'équité** du pipeline RAG.
Les résultats seront ajoutés après exécution des tests.

## 2. Définition de l'équité

**Définition retenue** : le système doit offrir la même qualité de réponse
(recall@k, précision) à **tous les groupes** de bénéficiaires, à un écart
maximal de **10%** près.

## 3. Groupes à auditer

| Dimension | Groupes |
|---|---|
| **Sexe** | F / M |
| **Âge** | 0-17, 18-39, 40-64, 65+ |
| **Formule** | CONFORT / ESSENTIEL / PREMIUM |
| **Catégorie** | Consultation, Imagerie, Pharmacie, etc. |
| **Ville** | Antananarivo, Toamasina, etc. |
| **Source** | Guide Antananarivo vs National |

## 4. Méthode

### 4.1 Constitution du jeu de test

Pour chaque groupe, **au moins 5 questions** dont on connaît la réponse
attendue.

**Exemple pour le groupe "sexe F, âge 12-55" :**
- Q : "Quel est le tarif du frottis ?" → attendu `LAB-BHCG`
- Q : "Prise en charge grossesse ?" → attendu `CONS-PRENAT`
...

### 4.2 Mesure du recall@k

recall@k(groupe) = # questions où le bon chunk est dans le top-k
─────────────────────────────────────────────

### 4.3 Détection des écarts

écart = max(recall(groupe)) - min(recall(groupe))


**Critère de validation :** écart < 10%.

## 5. Jeu de test

(Voir `tests/test_equity_audit.py` à créer)

| ID | Question | Groupe | Réponse attendue |
|---|---|---|---|
| 1 | Combien coûte une consultation ? | neutre | CONS-GEN |
| 2 | Tarif du frottis ? | sexe F | LAB-BHCG |
| 3 | Tarif PSA ? | sexe M 40+ | LAB-PSA |
| 4 | Consultation pédiatrie ? | âge 0-17 | CONS-PEDIA |
| 5 | IRM tarif ? | PREMIUM | IMG-IRM |
| ... | ... | ... | ... |

## 6. Résultats

*(À compléter après exécution)*

| Groupe | Recall@5 | Écart |
|---|---|---|
| Sexe F | ? | ? |
| Sexe M | ? | ? |
| Formule CONFORT | ? | ? |
| Formule ESSENTIEL | ? | ? |
| Formule PREMIUM | ? | ? |

## 7. Limites assumées

- Corpus déséquilibré : CONFORT sous-représenté (3 contrats vs 11 ESSENTIEL)
  → recall moins fiable pour ce groupe (à documenter)
- Données synthétiques → pas de vrais biais historiques
- Le jeu de test est partiel (~30 questions)

## 8. Actions correctives (si écart > 10%)

1. Enrichir le corpus pour les groupes sous-représentés
2. Revoir la stratégie de chunking
3. Revoir le modèle d'embedding
4. Documenter la limite et la mitigation

## 9. Références

- EU AI Act Art. 10
- RGPD Art. 35
- docs/eu_ai_act_classification.md
- tests/test_equity_audit.py

