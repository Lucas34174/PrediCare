# Guide d'exploitation : Configuration externalisée et seuils dynamiques (PB-25)

Ce guide détaille le fonctionnement, les variables d'environnement, les paramètres modifiables à chaud via l'API d'administration et les commandes de démonstration en direct.

---

## 1. Tableau des paramètres et cycle de vie

| Paramètre | Source par défaut (`.env`) | Modifiable en direct via API (`PUT /admin/config`) | Effet immédiat | Redémarrage requis | Description |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **`fraud_score_threshold`** | `ALERT_THRESHOLD` ou `FRAUD_SCORE_THRESHOLD` (défaut : `0.30`) | **Oui** | **Oui (sans redémarrage)** | Non | Seuil d'anomalie de fraude ($0.0 \le \text{seuil} \le 1.0$). Si $\text{score} \ge \text{seuil}$, la facture est marquée comme anomalie et alerte n8n émise. |
| **`n8n_webhook_url`** | `N8N_WEBHOOK_URL` (défaut : `http://n8n:5678/webhook/fraud-alert`) | **Oui** | **Oui (sans redémarrage)** | Non | URL cible HTTP(S) appelée par l'API pour notifier n8n lors de la détection d'une fraude. |
| **`semantic_cache_enabled`** | `SEMANTIC_CACHE_ENABLED` (défaut : `true`) | **Oui** | **Oui** | Non | Active ou désactive le cache sémantique vectoriel de l'assistant RAG. |
| **`semantic_cache_threshold`** | `SEMANTIC_CACHE_THRESHOLD` (défaut : `0.85`) | **Oui** | **Oui** | Non | Similarité cosinus minimale ($0.0 \le \text{seuil} \le 1.0$) pour valider un hit du cache sémantique. |
| **`JWT_SECRET`** | `.env` obligatoire (32 caractères min) | Non (Secret) | Non | **Oui** | Clé secrète de signature HMAC-SHA256 des jetons d'authentification. Refus de démarrage si absente. |
| **`PII_ENCRYPTION_KEY`** | `.env` obligatoire | Non (Secret) | Non | **Oui** | Clé symétrique AES-256 (`pgcrypto`) pour le chiffrement des identités d'assurés. Refus de démarrage si absente. |
| **`POSTGRES_PASSWORD`** | `.env` obligatoire | Non (Secret) | Non | **Oui** | Mot de passe de connexion à l'instance PostgreSQL. |
| **`SMTP_FROM` / `ALERT_EMAIL_TO`** | `.env` (service n8n) | Non (géré n8n) | Non | **Oui (`docker compose up -d n8n`)** | Paramètres des alertes e-mail lus par n8n au démarrage via `$env`. Non modifiables via l'API REST backend. |

---

## 2. Hiérarchie des sources de configuration

1. **Table PostgreSQL `app_config`** : Priorité maximale. Les paramètres modifiés par un administrateur y sont enregistrés avec horodatage UTC et identité du modificateur.
2. **Cache mémoire local (TTL = 3s)** : Permet de préserver les performances de la base lors des requêtes d'inférence répétées. Tout `PUT /admin/config` **invalide immédiatement** ce cache pour garantir l'effet direct.
3. **Variables d'environnement (`.env`)** : Utilisées au premier lancement lorsque la table `app_config` est vide, ou en cas d'indisponibilité momentanée de PostgreSQL.

---

## 3. Scénario de démonstration et recette (commandes `curl`)

### Étape 0 : Obtention du jeton d'accès administrateur
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"identifier": "admin1", "password": "x"}' \
  | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)
```

### Étape 1 : Consultation de la configuration courante
```bash
curl -s -X GET http://localhost:8000/admin/config \
  -H "Authorization: Bearer $TOKEN"
```
*Réponse attendue (200 OK) :*
```json
{
  "fraud_score_threshold": 0.80,
  "n8n_webhook_url": "http://n8n:5678/webhook/fraud-alert",
  "semantic_cache_enabled": true,
  "semantic_cache_threshold": 0.85,
  "updated_at": "..."
}
```

### Étape 2 : Soumission d'une facture sous seuil 0.80 (anomalie détectée)
```bash
curl -s -X POST http://localhost:8000/claims \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "numero_facture": "F-2026-DEMO-001",
    "assure_id": "ASS-00421",
    "prestataire_id": "PR-0015",
    "date_soin": "2026-10-14",
    "date_emission": "2026-10-15",
    "montant_total": 45000,
    "part_assure": 9000,
    "lignes": [
      {"num_ligne": 1, "code": "ACT-CS-01", "type_ligne": "ACTE", "quantite": 1, "prix_unitaire": 30000, "montant_total": 30000},
      {"num_ligne": 2, "code": "MED-CIP-0045", "type_ligne": "MEDICAMENT", "quantite": 2, "prix_unitaire": 7500, "montant_total": 15000}
    ]
  }'
```
*Résultat :* `est_anomalie: true`, `seuil_applique: 0.80`.

### Étape 3 : Modification à chaud du seuil à 0.90
```bash
curl -s -X PUT http://localhost:8000/admin/config \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"fraud_score_threshold": 0.90}'
```

### Étape 4 : Soumission immédiate identique (SANS redémarrage)
```bash
curl -s -X POST http://localhost:8000/claims \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "numero_facture": "F-2026-DEMO-002",
    "assure_id": "ASS-00421",
    "prestataire_id": "PR-0015",
    "date_soin": "2026-10-14",
    "date_emission": "2026-10-15",
    "montant_total": 45000,
    "part_assure": 9000,
    "lignes": [
      {"num_ligne": 1, "code": "ACT-CS-01", "type_ligne": "ACTE", "quantite": 1, "prix_unitaire": 30000, "montant_total": 30000},
      {"num_ligne": 2, "code": "MED-CIP-0045", "type_ligne": "MEDICAMENT", "quantite": 2, "prix_unitaire": 7500, "montant_total": 15000}
    ]
  }'
```
*Résultat :* `est_anomalie: false`, `seuil_applique: 0.90`.

### Étape 5 : Contrôles de sécurité et validations (rejets)
- **Rejet d'une valeur hors limites (422)** :
```bash
curl -s -o /dev/null -w "%{http_code}\n" -X PUT http://localhost:8000/admin/config \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"fraud_score_threshold": 1.5}'
# Sortie : 422
```
- **Rejet d'un utilisateur non administrateur (403)** :
```bash
GEST_TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"identifier": "gestionnaire1", "password": "x"}' \
  | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

curl -s -o /dev/null -w "%{http_code}\n" -X PUT http://localhost:8000/admin/config \
  -H "Authorization: Bearer $GEST_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"fraud_score_threshold": 0.85}'
# Sortie : 403
```

### Étape 6 : Remise du seuil opérationnel nominal
```bash
curl -s -X PUT http://localhost:8000/admin/config \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"fraud_score_threshold": 0.80}'
```
