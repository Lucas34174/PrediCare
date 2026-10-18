# Architecture du pipeline RAG — PrediCare TPA

## 1. Vue d'ensemble

PDFs (31) → Parsing → Chunking → Enrichissement → Embedding (BGE-M3)
→ PostgreSQL + pgvector → Retriever hybride → LLM (à venir)


## 2. Stack technique

| Composant | Choix | Version |
|---|---|---|
| Base de données | PostgreSQL + pgvector | 16 + pgvector |
| Chiffrement | pgcrypto | (inclus) |
| Langage pipeline | Python | 3.12 |
| Parsing PDF | pdfplumber | ≥ 0.11 |
| Modèle d'embedding | BGE-M3 (BAAI) | — |
| Runtime embedding | Ollama | 0.3.14 (épinglé) |
| Dimension embedding | 1024 | — |
| Index vectoriel | HNSW (cosine) | — |
| Index full-text | GIN (french) | — |
| Recherche | Hybride (vecteur + FTS + RRF) | — |

## 3. Choix du modèle d'embedding

### Décision : **BGE-M3 en local via Ollama**

### Alternatives écartées

| Alternative | Raison du rejet |
|---|---|
| OpenAI text-embedding-3-small | Transfert hors UE (RGPD), non-reproductible (EU AI Act), lock-in |
| OpenAI text-embedding-3-large | Idem + coût |
| Cohere / Voyage | Idem + DPA |
| e5-large | Correct mais moins bon en français que BGE-M3 |

### Justifications croisées

| Axe | Argument |
|---|---|
| **FinOps** | Coût marginal nul. Pas de facturation à l'usage. |
| **TCO** | Pas d'API externe, pas de lock-in, pas de coût récurrent cloud. |
| **RGPD** | Aucun transfert hors UE. Aucun sous-traitant IA. |
| **EU AI Act** | Modèle figé (version épinglée) → tests reproductibles → audit défendable. |
| **Équité** | Version contrôlée → audit d'équité reproductible. |
| **Langue** | Excellent en français (multilingue natif). |
| **Dimension** | 1024 — compatible avec l'infra existante (migration 4). |

## 4. Pipeline d'ingestion


┌──────────────────────────────────────────────────────────────┐
│ 1. Calcul SHA256 → skip si déjà indexé (idempotence) │
└──────────────────────────────────────────────────────────────┘
↓
┌──────────────────────────────────────────────────────────────┐
│ 2. Détection du type (par motif regex sur le nom de fichier) │
└──────────────────────────────────────────────────────────────┘
↓
┌──────────────────────────────────────────────────────────────┐
│ 3. Parsing spécialisé (pdfplumber) │
└──────────────────────────────────────────────────────────────┘
↓
┌──────────────────────────────────────────────────────────────┐
│ 4. Chunking spécialisé par type │
└──────────────────────────────────────────────────────────────┘
↓
┌──────────────────────────────────────────────────────────────┐
│ 5. Enrichissement contextuel │
└──────────────────────────────────────────────────────────────┘
↓
┌──────────────────────────────────────────────────────────────┐
│ 6. Embedding batch (Ollama / BGE-M3) │
└──────────────────────────────────────────────────────────────┘
↓
┌──────────────────────────────────────────────────────────────┐
│ 7. Insertion transactionnelle (documents + chunks) │
└──────────────────────────────────────────────────────────────┘


## 5. Schéma de base

### Table `documents`


id, source_path, source_filename, doc_type, formule, contract_id,
checksum_sha256, nb_pages, version_modele_embedding, metadonnees (JSONB),
actif, date_indexation, date_mise_a_jour


### Table `documents_vectorises`


id, document_id, chunk_index, chunk_type, contenu, contenu_enrichi,
token_count, embedding (VECTOR 1024), metadonnees (JSONB),
actif, date_indexation



### Index
- `ix_documents_vectorises_embedding_hnsw` (HNSW, cosine)
- `ix_documents_vectorises_content_fts` (GIN, `to_tsvector('french', ...)`)
- `ix_documents_vectorises_metadonnees` (GIN, JSONB)

## 6. Retriever hybride

| Méthode | Usage | Force |
|---|---|---|
| **Vectoriel** (`<=>`) | Questions sémantiques | Comprend le sens |
| **Full-text** (`ts_rank`) | Codes exacts, contrats | Précision |
| **RRF** (k=60) | Fusion | Récompense le consensus |
| **Filtres JSONB** | Restriction par formule, catégorie, contrat | Ciblage |

**Décision RRF** : fusion **sans pondération manuelle** (contrairement à
`alpha * vec + (1-alpha) * ft`). Le consensus est récompensé naturellement.

## 7. Idempotence

Un fichier n'est réindexé que si son **checksum SHA256** change.
Cela permet :
- Re-runs sans doublon
- Détection des modifications
- Économie de calcul d'embedding

## 8. Tests

- `test_ingest_bareme.py` — 86 chunks
- `test_ingest_cg.py` — 42 chunks
- `test_ingest_cp.py` — 120 chunks
- `test_ingest_guide.py` — 403 chunks
- `test_retriever.py` — 6/6 questions pertinentes

## 9. Limites assumées

- Guide Réseau : extraction imparfaite (PDF non structuré)
- Pas encore d'endpoint `/assistant/chat`
- Pas encore de LLM de génération branché

## 10. Références

- docs/chunking_strategy.md
- docs/eu_ai_act_classification.md
- docs/rgpd_aipd.md
- docs/decisions.md

## 7. Agent ReAct sourcé (PB-36)

### Décision : routage déterministe + LLM en fallback

**Contexte** : POC tournant sur CPU, sans GPU. Un modèle 8B met > 3 minutes 
pour générer une réponse avec un prompt ReAct complet. Inacceptable.

**Solution** :
1. **Routage déterministe** : si la question contient des mots-clés métier
   (facture, remboursement…), on appelle directement `search_my_claims`.
2. **RAG direct** : sinon, on cherche dans le corpus avec le Retriever.
3. **LLM en fallback** : le LLM local (`phi3:mini`) n'est utilisé que pour
   formuler la réponse à partir des sources trouvées.
4. **Timeout court (10s)** : si le LLM ne répond pas, on retourne le 
   contexte brut (fallback local, 0 latence).

### Conformité EU AI Act
- **Citations obligatoires** : la réponse contient toujours un champ `sources`.
- **Refus de spéculer** : si `similarity < 0.6`, abstention immédiate.
- **Supervision** : le LLM ne décide pas de l'action ; il formule uniquement.

### Limites assumées (POC)
- Le LLM n'est pas autonome (pas de vraie boucle ReAct).
- La qualité rédactionnelle est limitée par `phi3:mini`.
- En production : GPU + `llama3.1:8b` permettrait une vraie boucle ReAct.
