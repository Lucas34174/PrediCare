# Stratégie de chunking — Corpus PrediCare TPA

## 1. Principe directeur

> **Un chunk doit être une unité sémantique autoportante.**

Un chunk est **autoportant** si, lu isolément, il contient assez de contexte
pour répondre à une question. Un chunk uniforme (512 tokens / 50 overlap)
ne respecte pas ce principe sur les corpus hétérogènes.

## 2. Corpus et types identifiés

| Type | Fichiers | Structure | Stratégie |
|---|---|---|---|
| Barème | 1 | Tableaux denses | 1 ligne = 1 chunk |
| Conditions Générales | 3 | Articles | 1 article = 1 chunk |
| Conditions Particulières | 25 | Sections + bénéficiaires | 1 section/bénéf = 1 chunk |
| Guide Réseau | 2 | Tableaux de prestataires | 1 prestataire = 1 chunk |

## 3. Détail par type

### 3.1 Barème — 86 chunks

**Structure** : Tableaux `Code | Libellé | Catégorie | Min | Référence | Max | ...`

**Stratégie** : 1 ligne = 1 chunk.

**Exemple de chunk :**
[Barème | Catégorie: CONSULTATION | Code: CONS-CARDIO]
Libellé : Consultation cardiologie
Tarif minimum : 30 000 Ar
Tarif de référence : 40 000 Ar
Tarif maximum : 200 000 Ar
Ordonnance requise : non
Entente préalable : non
Restriction : aucune

**Justifications :**
- FinOps : 86 chunks × ~60 tokens = petit volume
- RGPD : aucune PII
- EU AI Act : traçabilité par code d'acte
- Équité : granularité par acte → audit par catégorie

### 3.2 Conditions Générales — 42 chunks (3 × 14 articles)

**Structure** : `Article N – Titre` + contenu

**Stratégie** : 1 article = 1 chunk. Si > 800 tokens → découpage par paragraphe.

**Exemple :**
[Conditions Générales | Formule CONFORT | Article 5 – Tableau des garanties]
Les taux s'appliquent à la base de remboursement...
[tableau des garanties]


**Justifications :**
- Cohérence juridique : 1 article = 1 unité de sens
- Citation possible : "Article 5 des CG CONFORT"
- Filtrage par formule

### 3.3 Conditions Particulières — 120 chunks

**Structure** : Métadonnées contrat + tableau bénéficiaires + section garanties

**Stratégie** : 3 types de chunks
- `contrat_metadata` : 1 par contrat (25)
- `beneficiaire` : 1 par bénéficiaire (~70)
- `section_garanties` : 1 par contrat (25)

**Justifications :**
- Filtrage par `contract_id` → indispensable pour RGPD (un assuré = son contrat)
- Détection d'anomalies par bénéficiaire (audit équité : sexe, âge)

### 3.4 Guide Réseau — 403 chunks

**Structure** : Sections thématiques + tableaux de prestataires

**Stratégie** : 1 prestataire = 1 chunk.

**Exemple :**
[Guide Réseau | Catégorie: PHARMACIES | Ville: Antananarivo]
Prestataire : Pharmacie Aingavao Andoharanofotsy
Horaires : HEURE DE BUREAU (LUNDI AU VENDREDI 8H-17H)
Contact : 038 00 116 25
Adresse : Lot III B 12 Andoharanofotsy, Antananarivo
Tarifs : TARIF UNIQUE


**Justifications :**
- Granularité fine : "Quelle pharmacie ouvre 24h/24 ?"
- Filtrage par catégorie + ville
- Qualité (top 1/2/3) exploitable

## 4. Enrichissement contextuel

**Règle :** Ne jamais stocker de chunk brut. Toujours préfixer avec un
contexte structuré.

**Raison :** Une ligne brute `10 000 Ar 20 000 Ar 50 000 Ar` n'a **aucun
sens sémantique**. L'embedding serait inutile. Le préfixe contextuel
`[Barème | Catégorie: CONSULTATION | Code: CONS-GEN]` rend le chunk
interrogeable.

## 5. Alternative écartée : chunking uniforme (512/50)

**Pourquoi écarté ?**
- Casse les tableaux (perte des codes)
- Mélange les sections (perte de contexte)
- Non filtrable par métadonnées métier

**Preuve :** test sur le barème → les codes `CONS-CARDIO` disparaissent.

## 6. Limites assumées

- Guide Réseau : ~15% des prestataires ont des champs partiellement mal extraits
  (PDF entremêle les colonnes). La `ligne_brute` est conservée en fallback.
- Article CG > 800 tokens : découpage par paragraphe (perte de cohésion
  légère, mais nécessaire).

## 7. Métriques

| Type | Chunks | Tokens moyens |
|---|---|---|
| Barème | 86 | ~60 |
| CG | 42 | ~350 |
| CP | 120 | ~80 |
| Guide | 403 | ~50 |
| **Total** | **651** | ~85 |

