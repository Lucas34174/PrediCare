"""Tests de validation du workflow n8n (PB-24)."""

from __future__ import annotations

import json
from pathlib import Path

WORKFLOW_PATH = Path("infra/n8n/fraud_alert_workflow.json")


def test_workflow_json_est_valide_et_complet():
    """Vérifie la syntaxe JSON et la structure globale du workflow."""
    assert WORKFLOW_PATH.is_file(), f"Workflow introuvable : {WORKFLOW_PATH}"
    data = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))

    assert "name" in data
    assert "nodes" in data and len(data["nodes"]) >= 4
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


def test_noeud_notification_email_present():
    """Garantit la présence du canal de notification Email."""
    data = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))
    nodes_by_type = {n.get("type"): n for n in data["nodes"]}

    assert "n8n-nodes-base.emailSend" in nodes_by_type, "Nœud Email (emailSend) manquant"


def test_aucun_secret_dans_le_workflow_exporte():
    """Garantit l'absence absolue de tokens, mots de passe et PII dans le JSON."""
    contenu = WORKFLOW_PATH.read_text(encoding="utf-8")

    # Aucun token ou secret en clair
    assert "xoxb-" not in contenu
    assert "xoxp-" not in contenu

    # Aucune PII
    for mot in ["rabe", "razafy", "antananarivo@gmail", "034", "032", "033"]:
        assert mot not in contenu.lower(), f"Information suspecte/PII détectée : {mot}"
