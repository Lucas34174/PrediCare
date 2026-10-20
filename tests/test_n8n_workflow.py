"""Tests de validation du workflow n8n (PB-24)."""

from __future__ import annotations

import json
import re
from pathlib import Path

WORKFLOW_PATH = Path("infra/n8n/fraud_alert_workflow.json")


def test_workflow_json_est_valide_et_complet():
    """Vérifie la syntaxe JSON et la structure globale du workflow."""
    assert WORKFLOW_PATH.is_file(), f"Workflow introuvable : {WORKFLOW_PATH}"
    data = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))

    assert "name" in data
    assert "nodes" in data and len(data["nodes"]) >= 6
    assert "connections" in data


def test_noeud_webhook_fraud_alert_present():
    """Garantit la présence du Webhook POST fraud-alert."""
    data = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))
    webhook_nodes = [
        n
        for n in data["nodes"]
        if n.get("type") == "n8n-nodes-base.webhook"
        and n.get("parameters", {}).get("path") == "fraud-alert"
        and n.get("parameters", {}).get("httpMethod") == "POST"
    ]
    assert len(webhook_nodes) == 1, "Le nœud Webhook POST fraud-alert doit être unique et présent"


def test_noeuds_notification_et_robustesse():
    """Garantit la présence de Slack et Email avec continueOnFail pour la tolérance aux pannes."""
    data = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))
    nodes_by_type = {n.get("type"): n for n in data["nodes"]}

    assert "n8n-nodes-base.httpRequest" in nodes_by_type, "Nœud Slack (HTTP Request) manquant"
    assert "n8n-nodes-base.emailSend" in nodes_by_type, "Nœud Email manquant"

    slack_node = nodes_by_type["n8n-nodes-base.httpRequest"]
    email_node = nodes_by_type["n8n-nodes-base.emailSend"]

    assert slack_node.get("continueOnFail") is True, "Slack doit avoir continueOnFail=true"
    assert email_node.get("continueOnFail") is True, "Email doit avoir continueOnFail=true"


def test_aucun_secret_dans_le_workflow_exporte():
    """Garantit l'absence absolue d'URL Slack réelles, tokens et mots de passe dans le JSON."""
    contenu = WORKFLOW_PATH.read_text(encoding="utf-8")

    # Aucun token Slack bot xoxb- ou webhook réel
    assert "xoxb-" not in contenu, "Token Slack bot détecté dans le JSON !"
    assert "xoxp-" not in contenu, "Token Slack user détecté dans le JSON !"
    assert not re.search(r"https://hooks\.slack\.com/services/T[A-Z0-9]+", contenu), (
        "URL de webhook Slack réelle détectée dans le JSON !"
    )

    # Aucune PII
    for mot in ["rabe", "razafy", "antananarivo@gmail", "034", "032", "033"]:
        assert mot not in contenu.lower(), f"Information suspecte/PII détectée : {mot}"
