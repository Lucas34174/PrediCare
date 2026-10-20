# Guide d'Exploitation : Alertes Fraude n8n (PB-24)

Ce guide détaille la mise en œuvre, l'importation et le test du workflow d'alerte de fraude santé (Slack & Email) orchestré par n8n (tag `2.43.4`).

---

## 1. Architecture du Flux d'Alerte

```mermaid
sequenceDiagram
    participant Pro as Professionnel de Santé
    participant API as API FastAPI (/claims)
    participant ML as Modèle Fraude & SHAP
    participant DB as PostgreSQL
    participant N8N as Workflow n8n
    participant Mail as Boîte Gestionnaire

    Pro->>API: POST /claims (télétransmission)
    API->>ML: Inférence unitaire + calcul SHAP
    ML-->>API: score_fraude, est_anomalie, top_facteurs
    API->>DB: Persistance atomique (facture + prédiction)
    alt est_anomalie == True (score >= seuil)
        API-)N8N: POST /webhook/fraud-alert (payload §4, timeout 2s)
        and Notification Email
            N8N->>Mail: Envoi de l'e-mail récapitulatif
        end
    end
    API-->>Pro: 201 Created (ClaimCreateResponse)
```

---

## 2. Configuration (`.env`)

Ajoutez ou ajustez les variables suivantes dans votre `.env` local :

```env
# URL cible du webhook n8n
N8N_WEBHOOK_URL=http://n8n:5678/webhook/fraud-alert
DASHBOARD_BASE_URL=http://localhost:3000

# Canal Email (SMTP Gmail ou local)
ALERT_EMAIL_TO=gestionnaire@predicare.mg
SMTP_FROM=alerte-fraude@predicare.mg
```
