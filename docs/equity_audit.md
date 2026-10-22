# Audit d'équité — Pipeline RAG PrediCare TPA

**Date** : 2026-10-16  
**Version** : 1.0  
**Statut** : Audit #1 effectué, 2 limites documentées  
**Responsable** : M3 (pôle Produit / Front / RAG)

---

## 1. Contexte et cadre réglementaire

### 1.1 Obligations

| Texte | Article | Exigence |
|---|---|---|
| **EU AI Act** | Art. 10 | Gouvernance des données, prévention des biais |
| **RGPD** | Art. 35 | AIPD (données de santé, catégorie spéciale) |
| **Loi malgache** | n° 2014-038 | Protection des données personnelles |

Le système PrediCare TPA est classé **haut risque** (EU AI Act, Annexe III.5.b). L'audit d'équité est donc une **obligation**, pas une option.

### 1.2 Objectif de l'audit

Vérifier que le pipeline RAG offre une **qualité de réponse équitable** à tous les groupes d'utilisateurs, sans biais détectable sur les dimensions protégées (sexe, âge) ou sensibles (formule, catégorie, ville).

---

## 2. Définition de l'équité

### 2.1 Métrique retenue

**Recall@k** : pour chaque question, le chunk attendu est-il présent dans les `k=5` premiers résultats ?

\[
\operatorname{Recall@k}(groupe) =
\frac{\text{Nombre de questions où le bon chunk est dans le top-k}}
{\text{Nombre de questions du groupe}}
\]

### 2.2 Critère de validation

**Écart maximal toléré entre groupes d'une même dimension : 10 %.**

Justification : ce seuil est un repère interne inspiré de pratiques de mesure de l'équité algorithmique. Il ne constitue pas, à lui seul, une norme universelle ou une preuve de conformité réglementaire.

---

## 3. Dimensions et groupes audités

| Dimension | Groupes | Nb questions |
|---|---|---:|
| **Sexe** | F, M, neutre | 15 |
| **Âge** | 0-17, 18-39, 40-64, 65+, neutre | 10 |
| **Formule** | CONFORT, ESSENTIEL, PREMIUM | 12 |
| **Catégorie** | Consultation, Imagerie, Pharmacie, Dentaire, Optique, Labo, Maternité, Kiné, Hospitalisation | 15 |
| **Ville** | Antananarivo, Toamasina, Antsirabe, Fianarantsoa, Mahajanga, Toliara, Antsiranana, national | 10 |
| **Contrôle** | Questions simples (doivent toujours passer) | 5 |
| ****TOTAL** | | **67** |

### Jeu de test

Le jeu de test complet est versionné dans `tests/fixtures/equity_test_cases.json`. Chaque cas contient :

- La question en langage naturel
- Le groupe testé
- Le chunk attendu (`code_acte`, formule, etc.)
- Des notes documentant la sensibilité

---

## 4. Méthode

### 4.1 Constitution du jeu de test

Chaque question a été **rédigée manuellement** pour :

- Cibler un groupe spécifique
- Avoir une réponse attendue **sans ambiguïté**
- Couvrir les restrictions du barème (sexe F/M, âge 0-17, etc.)

### 4.2 Exécution

```bash
docker compose run --rm api python -m tests.test_equity_audit
```

Le script :

1. Charge les 67 cas
2. Interroge le retriever hybride (`top_k=5`)
3. Vérifie si le chunk attendu est dans le top-5
4. Agrège les résultats par groupe
5. Calcule les écarts par dimension
6. Génère `docs/equity_audit_report.json` et `docs/equity_audit.md`

### 4.3 Reproductibilité

- Le modèle d'embedding est **figé** (BGE-M3, version épinglée dans Ollama)
- Le corpus est **versionné** (checksum SHA256)
- Le jeu de test est **versionné** (Git)
- **→ L'audit est reproductible et auditable** (EU AI Act Art. 11)

---

## 5. Résultats — Audit #1 (2026-10-16)

### 5.1 Résultat global

| Métrique | Valeur |
|---|---:|
| **Total cas** | 67 |
| **Cas réussis** | 65 |
| **Recall global** | **97.0 %** |
| **Top-k** | 5 |

### 5.2 Écarts par dimension

| Dimension | Min | Max | Écart | Statut |
|---|---:|---:|---:|---|
| **Sexe** | 100 % | 100 % | **0 %** | ✅ Conforme |
| **Catégorie** | 100 % | 100 % | **0 %** | ✅ Conforme |
| **Contrôle** | 100 % | 100 % | **0 %** | ✅ Conforme |
| **Formule** | 100 % | 100 % | **0 %** | ✅ Conforme |
| **Âge** | 66.7 % | 100 % | 33.3 % | ⚠️ Limite corpus |
| **Ville** | 0 % | 100 % | 100 % | ⚠️ Limite corpus |

### 5.3 Détail par groupe

| Dimension | Groupe | Recall | Réussis / Total |
|---|---|---:|---:|
| sexe | F | 100 % | 5/5 |
| sexe | M | 100 % | 3/3 |
| sexe | neutre | 100 % | 7/7 |
| formule | CONFORT | 100 % | 4/4 |
| formule | ESSENTIEL | 100 % | 4/4 |
| formule | PREMIUM | 100 % | 4/4 |
| catégorie | CONSULTATION | 100 % | 2/2 |
| catégorie | IMAGERIE | 100 % | 2/2 |
| catégorie | LABORATOIRE | 100 % | 2/2 |
| catégorie | PHARMACIE | 100 % | 3/3 |
| catégorie | DENTAIRE | 100 % | 2/2 |
| catégorie | OPTIQUE | 100 % | 1/1 |
| catégorie | MATERNITE | 100 % | 1/1 |
| catégorie | KINESITHERAPIE | 100 % | 1/1 |
| catégorie | HOSPITALISATION | 100 % | 1/1 |
| âge | 0-17 | **66.7 %** | 2/3 |
| âge | 18-39 | 100 % | 2/2 |
| âge | 40-64 | 100 % | 2/2 |
| âge | 65+ | 100 % | 2/2 |
| âge | neutre | 100 % | 1/1 |
| ville | Antananarivo | 100 % | 2/2 |
| ville | Toamasina | 100 % | 2/2 |
| ville | **Antsirabe** | **0 %** | 0/1 |
| ville | Fianarantsoa | 100 % | 1/1 |
| ville | Mahajanga | 100 % | 1/1 |
| ville | Toliara | 100 % | 1/1 |
| ville | Antsiranana | 100 % | 1/1 |
| ville | national | 100 % | 1/1 |
| contrôle | tous | 100 % | 5/5 |

### 5.4 Cas en échec (2)

| ID | Question | Attendu | Obtenu | Cause |
|---|---|---|---|---|
| `age_0_17_03` | « Quel pédiatre puis-je consulter à Toamasina ? » | `PEDIATRIE` à Toamasina | Autre prestataire | **Corpus** |
| `ville_Antsirabe_01` | « Quel est le tarif d'une consultation pédiatrie à Antsirabe ? » | `PEDIATRIE` à Antsirabe | Clinique à Antsirabe | **Corpus** |

---

## 6. Analyse des écarts

### 6.1 Dimensions conformes (écart 0 %)

**Sexe, catégorie, formule, contrôle** ont un écart **strictement nul**. Aucun biais détectable n'a été observé sur ces dimensions dans ce jeu de test.

> **Conclusion :** le pipeline traite de façon comparable les groupes testés pour le sexe, les catégories d'actes et les trois formules, dans les limites de l'échantillon utilisé.

### 6.2 Dimension « âge » — écart 33.3 %

**Cause identifiée :** le seul cas en échec (`age_0_17_03`) demande un **pédiatre à Toamasina**, mais le corpus **n'en contient aucun**.

**Vérification SQL :**

```sql
SELECT count(*)
FROM documents_vectorises
WHERE chunk_type = 'prestataire'
  AND metadonnees->>'categorie' = 'PEDIATRIE'
  AND metadonnees->>'ville' = 'Toamasina';
-- Résultat attendu selon l'audit : 0
```

**Décision :** limite du corpus, plutôt qu'un biais démontré du système. Cette interprétation devra être vérifiée après enrichissement du corpus et nouvel audit.

### 6.3 Dimension « ville » — écart 100 %

**Cause identifiée :** le seul cas en échec (`ville_Antsirabe_01`) demande un **pédiatre à Antsirabe**, mais le corpus **n'en contient aucun**.

**Vérification SQL :**

```sql
SELECT count(*)
FROM documents_vectorises
WHERE chunk_type = 'prestataire'
  AND metadonnees->>'categorie' = 'PEDIATRIE'
  AND metadonnees->>'ville' = 'Antsirabe';
-- Résultat attendu selon l'audit : 0
```

**Décision :** limite du corpus, plutôt qu'un biais démontré du système.

> Note : l'écart de 100 % repose sur un seul cas dans ce groupe. Un échantillon de cette taille ne permet pas de conclure à un biais généralisé.

---

## 7. Limites assumées

| Limite | Impact | Mitigation |
|---|---|---|
| **Corpus déséquilibré** (CONFORT sous-représenté : 3 contrats vs 11 ESSENTIEL) | Recall CONFORT moins fiable statistiquement | Enrichir le corpus en phase 2 |
| **Absence de pédiatres à Toamasina et Antsirabe** | 2 cas en échec | Enrichir le corpus en phase 2 |
| **Taille réduite du jeu de test** (1 à 7 questions par groupe) | Puissance statistique limitée | Étendre à 20+ questions/groupe en phase 2 |
| **Données synthétiques** | Pas de vrais biais historiques | Acceptable pour un POC pédagogique, avec cette limite explicitement documentée |
| **Un seul modèle d'embedding testé** | Pas de comparaison | Tester d'autres modèles en phase 2 |

---

## 8. Actions correctives

### 8.1 Immédiates (faites)

- ✅ Jeu de test de 67 questions construit
- ✅ Audit exécuté et documenté
- ✅ 2 limites identifiées et tracées

### 8.2 Phase 2 (recommandé)

| Action | Priorité | Effort |
|---|---|---|
| Enrichir le corpus avec un pédiatre à Toamasina | Moyenne | Faible (ajout PDF) |
| Enrichir le corpus avec un pédiatre à Antsirabe | Moyenne | Faible |
| Étendre le jeu de test à 20 questions/groupe | Haute | Moyen |
| Tester un 2e modèle d'embedding | Basse | Moyen |
| Automatiser l'audit en CI (à chaque commit) | Haute | Moyen |

### 8.3 Décision d'acceptation

**Les écarts observés de 33.3 % (âge) et 100 % (ville) sont acceptés provisoirement pour le POC**, pour les raisons suivantes :

1. Ils sont associés à deux cas individuels pour lesquels les données attendues semblent absentes du corpus.
2. Ils concernent des groupes avec 1 à 3 cas, soit un échantillon trop petit pour tirer des conclusions générales.
3. Les dimensions sexe, catégorie et formule affichent un écart de 0 % dans ce test.
4. Les 5 questions de contrôle passent toutes.
5. Le recall global observé est de 97 %.

> **Prudence réglementaire :** ces résultats documentent un premier audit technique, mais ne suffisent pas à eux seuls à démontrer la conformité à l'EU AI Act ou au RGPD. La classification réglementaire du système et les obligations applicables doivent être confirmées selon son usage réel.

---

## 9. Conclusion

### 9.1 Verdict

Dans ce premier jeu de test, le pipeline RAG PrediCare TPA présente un recall global de **97.0 %** et aucun écart observé sur les dimensions sexe, catégorie et formule. Les deux échecs semblent associés à des limites du corpus (absence de données sur les pédiatres dans deux villes). Cette hypothèse doit être confirmée par enrichissement du corpus et ré-audit.

### 9.2 État du suivi

| Point de contrôle | Statut |
|---|---|
| Audit d'équité effectué | ✅ |
| Métrique définie (Recall@k) | ✅ |
| Dimensions prévues couvertes | ✅ |
| Résultats documentés | ✅ |
| Limites identifiées | ✅ |
| Actions correctives planifiées | ✅ |
| Reproductibilité (modèle figé, corpus versionné) | À vérifier sur l'environnement d'exécution |

### 9.3 Recommandation

**Feu vert limité au POC pédagogique**, sous réserve :

- D'enrichir le corpus avec des données vérifiées pour les pédiatres à Toamasina et Antsirabe, si ces prestataires existent et peuvent être documentés.
- D'étendre le jeu de test, idéalement avec au moins 20 questions par groupe lorsque cela est pertinent.
- De ré-auditer après chaque modification significative du corpus, du retriever ou du modèle d'embedding.
- De ne pas présenter ce seul audit comme une certification de conformité réglementaire.

---

## 10. Références

- EU AI Act — Règlement (UE) 2024/1689, notamment l'article 10 et l'annexe III.
- RGPD — Règlement (UE) 2016/679, article 35.
- Loi malgache n° 2014-038 relative à la protection des données à caractère personnel.
- `tests/fixtures/equity_test_cases.json` — Jeu de test (67 cas).
- `tests/test_equity_audit.py` — Script d'audit.
- `docs/equity_audit_report.json` — Rapport brut (machine).
- `docs/rag_architecture.md` — Architecture du pipeline.
- `docs/chunking_strategy.md` — Stratégie de chunking.
- `docs/eu_ai_act_classification.md` — Classification du risque.

---

## Annexe — Historique des audits

| Version | Date | Recall global | Écarts | Changements |
|---|---|---|---|---|
| #1 | 2026-10-16 | 97.0 % (65/67) | 2 limites (âge, ville) | Audit initial |

**Prochain audit prévu :** après enrichissement du corpus (phase 2).
