# FinOps, TCO et ROI — Pipeline RAG PrediCare TPA

## 1. Contexte

Solution RAG pour PrediCare TPA, en **POC/dev local**.
Ce document chiffre le coût et la valeur.

## 2. FinOps — Coût de la solution

### 2.1 Choix local : coût marginal nul

**Toutes les briques sont auto-hébergées :**
- PostgreSQL + pgvector : local
- Ollama + BGE-M3 : local
- Aucune API externe facturée

**Coût marginal d'une requête RAG :**
- Embedding de la requête : ~100 ms CPU local → **0 €**
- Recherche pgvector : ~10 ms → **0 €**
- Total : **0 €** par requête

**Coût marginal d'un nouveau document :**
- Parsing + embedding : ~30 s CPU local → **0 €**
- Stockage : ~50 KB par document → **négligeable**

### 2.2 Comparaison avec API externe

| Option | Embedding 651 chunks | Coût / 10k requêtes | Prévisibilité |
|---|---|---|---|
| **BGE-M3 local** | 0 € | 0 € | ✅ Parfaite |
| OpenAI 3-small | ~0,02 € | ~0,10 € | ⚠️ Facturation à l'usage |
| OpenAI 3-large | ~0,13 € | ~0,65 € | ⚠️ Facturation à l'usage |

**Décision** : local → **prévisibilité budgétaire totale**.

## 3. TCO sur 3 ans

| Poste | Année 1 | Année 2 | Année 3 | Total |
|---|---|---|---|---|
| Infra Postgres (local) | 0 € | 0 € | 0 € | 0 € |
| Ollama (local) | 0 € | 0 € | 0 € | 0 € |
| Embeddings | 0 € | 0 € | 0 € | 0 € |
| Dev / intégration | Temps M3 | 0 € | 0 € | Temps M3 |
| Conformité (AIPD, audit) | Temps M3 | Temps M3 | Temps M3 | Temps M3 |
| **Total récurrent** | **0 €** | **0 €** | **0 €** | **0 €** |

**Le TCO d'un POC local est dominé par le temps de dev, pas par l'infra.**

## 4. ROI

### 4.1 Bénéfices quantitatifs

| Bénéfice | Mesure | Estimation |
|---|---|---|
| Temps de traitement dossier | -X% | À mesurer |
| Taux d'erreur remboursement | -X% | À mesurer |
| Charge support | -X% | À mesurer |
| Fraudes détectées | +X% | À mesurer |

### 4.2 Bénéfices qualitatifs

- **Conformité** : éviter amendes RGPD (jusqu'à 4% CA mondial)
- **Confiance** : réponses sourcées → meilleure satisfaction
- **Auditabilité** : traçabilité complète pour EU AI Act

### 4.3 ROI indirect

Le coût du projet est **dérisoire** (temps de dev), comparé aux **sanctions
évitées** par la conformité.

## 5. Décisions FinOps

| Décision | Justification |
|---|---|
| Modèle local | Coût marginal nul, prévisibilité |
| Pas d'API externe | Pas de surprise budgétaire |
| Idempotence par checksum | Économie de calcul d'embedding |
| Cache sémantique (semantic_cache) | Économie de requêtes LLM |
| Index HNSW | Recherche rapide |

## 6. Limites et vigilance

- Coût CPU/GPU local non monétisé dans ce document
- En production, coût d'un serveur dédié à prévoir
- Si volume explose (>1M chunks), reconsidérer

## 7. Références

- docs/decisions.md
- docs/rag_architecture.md

## Semantic Caching (PB-37)

- **Table** : `semantic_cache` (déjà en base).
- **Mécanisme** : si une question identique a déjà été posée, la réponse est servie depuis la base.
- **Bénéfice** : économie d'environ 500 tokens par requête répétée.
- **Métrique exposée** : `GET /assistant/cache/stats`.
- **Conformité FinOps** : taux de hit mesurable, coût LLM réduit.