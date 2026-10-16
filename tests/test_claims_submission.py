"""Tests de validation Pydantic, rejets 422 et soumission/relecture de factures (PB-21)."""

from fastapi.testclient import TestClient

from predicare.api.main import app

client = TestClient(app)


def _facture_valide() -> dict:
    return {
        "numero_facture": "F-2026-SUB-001",
        "assure_id": "ASS-00421",
        "prestataire_id": "PR-0015",
        "ordonnance_id": "ORD-0003289",
        "date_soin": "2026-10-14",
        "date_emission": "2026-10-15",
        "montant_total": 45000,
        "part_assure": 9000,
        "lignes": [
            {
                "num_ligne": 1,
                "code": "ACT-CS-01",
                "type_ligne": "ACTE",
                "quantite": 1,
                "prix_unitaire": 30000,
                "montant_total": 30000,
            },
            {
                "num_ligne": 2,
                "code": "MED-CIP-0045",
                "type_ligne": "MEDICAMENT",
                "quantite": 2,
                "prix_unitaire": 7500,
                "montant_total": 15000,
            },
        ],
    }


def test_soumission_facture_valide_et_relecture():
    """Une facture valide est enregistrée (201) et relue fidèlement via GET /claims/{id} (200)."""
    payload = _facture_valide()
    resp_create = client.post("/claims", json=payload)
    assert resp_create.status_code == 201
    data = resp_create.json()
    assert "facture_id" in data
    facture_id = data["facture_id"]

    # Relecture via GET /claims/{facture_id}
    resp_get = client.get(f"/claims/{facture_id}")
    assert resp_get.status_code == 200
    claim = resp_get.json()
    assert claim["facture_id"] == facture_id
    assert claim["numero_facture"] == payload["numero_facture"]
    assert claim["montant_total"] == 45000
    assert claim["part_assure"] == 9000
    assert claim["montant_demande"] == 36000
    assert len(claim["lignes"]) == 2
    assert claim["lignes"][0]["code"] == "ACT-CS-01"


def test_rejet_somme_lignes_incoherente():
    """Rejet 422 si le montant total ne correspond pas à la somme des lignes."""
    payload = _facture_valide()
    payload["montant_total"] = 99999  # Incohérent avec 30000 + 15000 = 45000
    resp = client.post("/claims", json=payload)
    assert resp.status_code == 422
    assert "montant_total" in resp.text


def test_rejet_part_assure_trop_elevee():
    """Rejet 422 si la part assuré dépasse le montant total de la facture."""
    payload = _facture_valide()
    payload["part_assure"] = 50000  # 50000 > montant_total (45000)
    resp = client.post("/claims", json=payload)
    assert resp.status_code == 422
    assert "part_assure" in resp.text


def test_rejet_date_soin_posterieure_a_emission():
    """Rejet 422 si la date de soin est postérieure à la date d'émission."""
    payload = _facture_valide()
    payload["date_soin"] = "2026-10-20"
    payload["date_emission"] = "2026-10-15"  # Soin après émission
    resp = client.post("/claims", json=payload)
    assert resp.status_code == 422
    assert "date_emission" in resp.text


def test_rejet_facture_sans_lignes():
    """Rejet 422 si la facture ne comporte aucune ligne."""
    payload = _facture_valide()
    payload["lignes"] = []
    resp = client.post("/claims", json=payload)
    assert resp.status_code == 422


def test_rejet_ligne_calcul_incoherent():
    """Rejet 422 si quantite * prix_unitaire != montant_total sur une ligne."""
    payload = _facture_valide()
    payload["lignes"][0]["montant_total"] = 12345  # 1 * 30000 != 12345
    resp = client.post("/claims", json=payload)
    assert resp.status_code == 422
