"""Service d'émission des alertes de fraude vers le webhook n8n"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from predicare.core.config import dashboard_base_url, n8n_webhook_url

logger = logging.getLogger("predicare.api.alertes")


def construire_payload_alerte(
    facture: dict[str, Any],
    score_fraude: float,
    seuil_applique: float,
    version_modele: str,
    top_facteurs: list[dict[str, Any]] | None = None,
    dashboard_url_base: str | None = None,
    horodatage: datetime | None = None,
) -> dict[str, Any]:
    """Construit le payload JSON conforme au §4 du contrat d'interface."""
    fid = str(facture.get("facture_id", ""))
    date_soin = facture.get("date_soin")
    date_soin_str = (
        date_soin.isoformat() if hasattr(date_soin, "isoformat") else str(date_soin or "")
    )

    montant_total = int(facture.get("montant_total", 0))
    part_assure = int(facture.get("part_assure", 0))
    montant_demande = facture.get("montant_demande")
    if montant_demande is None:
        montant_demande = montant_total - part_assure
    else:
        montant_demande = int(montant_demande)

    if hasattr(horodatage, "strftime"):
        ts = horodatage.strftime("%Y-%m-%dT%H:%M:%SZ")
    elif isinstance(horodatage, str) and horodatage:
        ts = horodatage
    else:
        ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    facteurs = top_facteurs or []
    if len(facteurs) >= 2:
        f1 = facteurs[0].get("description") or str(
            facteurs[0].get("feature", "Anomalie principale")
        )
        f2 = facteurs[1].get("description") or str(facteurs[1].get("feature", "Facteur secondaire"))
    elif len(facteurs) == 1:
        f1 = facteurs[0].get("description") or str(
            facteurs[0].get("feature", "Anomalie principale")
        )
        f2 = "Aucun facteur secondaire identifié"
    else:
        f1 = "Dépassement du seuil de risque"
        f2 = "Contrôle manuel requis"

    base_url = (dashboard_url_base or dashboard_base_url()).rstrip("/")
    dash_url = f"{base_url}/claims/{fid}" if fid else base_url

    return {
        "event": "FRAUD_ALERT",
        "timestamp": ts,
        "facture": {
            "facture_id": fid,
            "numero_facture": str(facture.get("numero_facture", "")),
            "date_soin": date_soin_str,
            "montant_total": montant_total,
            "montant_demande": montant_demande,
            "prestataire_id": str(facture.get("prestataire_id", "")),
            "assure_id": str(facture.get("assure_id", "")),
        },
        "prediction": {
            "score_fraude": float(score_fraude),
            "seuil_applique": float(seuil_applique),
            "version_modele": str(version_modele),
        },
        "explicabilite_shap": {
            "facteur_principal": f1,
            "facteur_secondaire": f2,
        },
        "liens_action": {
            "dashboard_url": dash_url,
        },
    }


def emettre_alerte_fraude(
    payload: dict[str, Any],
    url: str | None = None,
    timeout: float = 2.0,
) -> bool:
    """Envoie l'alerte vers n8n sans jamais bloquer ni lever d'exception."""
    cible = url or n8n_webhook_url()
    fid = payload.get("facture", {}).get("facture_id", "inconnue")
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(cible, json=payload)
            if resp.status_code >= 400:
                logger.warning(
                    "Échec de l'alerte n8n pour %s : code HTTP %s",
                    fid,
                    resp.status_code,
                )
                return False
            logger.info("Alerte n8n transmise avec succès pour %s (code %s)", fid, resp.status_code)
            return True
    except Exception as exc:
        logger.warning(
            "Webhook n8n injoignable ou en erreur pour %s (%s) : %s",
            fid,
            cible,
            exc,
        )
        return False
