"""Tests unitaires et d'intégration pour le pipeline d'ingestion et de nettoyage (PB-04)."""

import json
from pathlib import Path

import pandas as pd
import pytest

from predicare.db.ingest import (
    clean_all,
    clean_dataframe_base,
    run_pipeline,
)
from predicare.db.schemas import LEAKAGE_COLUMNS


@pytest.fixture
def synthetic_raw_dir(tmp_path: Path) -> Path:
    """Génère un jeu minimal de CSV synthétiques valides pour les tests unitaires isolés."""
    raw = tmp_path / "raw"
    raw.mkdir()

    # 1. Referentiel actes
    (raw / "referentiel_actes.csv").write_text(
        "code_acte,libelle,categorie,specialite,tarif_min,tarif_reference,tarif_max,ordonnance_requise,entente_prealable,sexe_requis,age_min,age_max\n"
        "ACT-01,Consultation,CONSULTATION,Generaliste,20000,25000,30000,0,0,,0,120\n",
        encoding="utf-8",
    )

    # 2. Referentiel medicaments
    (raw / "referentiel_medicaments.csv").write_text(
        "code_medicament,libelle,prix_reference,remboursable,classe,chronique\n"
        "MED-01,Paracetamol,5000,1,ANTALGIQUE,0\n",
        encoding="utf-8",
    )

    # 3. Garanties
    (raw / "garanties.csv").write_text(
        "formule,categorie,taux_remboursement,plafond_annuel_categorie,franchise_par_facture,delai_carence_jours,plafond_annuel_global,prime_annuelle_par_beneficiaire,attestation_requise,actes_exclus,pieces_justificatives\n"
        "CONFORT,CONSULTATION,80,500000,5000,0,2000000,300000,0,,\n",
        encoding="utf-8",
    )

    # 4. Prestataires
    (raw / "prestataires.csv").write_text(
        "prestataire_id,nom,type_prestataire,specialite,ville,quartier,adresse,telephone,numero_onm,nif,horaires,jours_ouverture,heure_ouverture,heure_fermeture,niveau_tarif,note_qualite,conventionne,date_conventionnement,date_fin_convention,statut\n"
        "PR-001,Clinique A,CLINIQUE,Generaliste,Tana,Centre,Rue 1,0340000000,,123456,8h-18h,12345,8,18,STANDARD,4,1,2025-01-01,,ACTIF\n",
        encoding="utf-8",
    )

    # 5. Grille tarifaire
    (raw / "grille_tarifaire.csv").write_text(
        "prestataire_id,code,tarif_pratique\nPR-001,ACT-01,25000\n",
        encoding="utf-8",
    )

    # 6. Contrats
    (raw / "contrats.csv").write_text(
        "contrat_id,numero_police,souscripteur_id,souscripteur_nom,secteur,formule,date_effet_police,date_effet,date_fin,statut,nb_beneficiaires,prime_annuelle_totale\n"
        "CTR-001,POL-001,CLI-001,Entreprise X,SERVICES,CONFORT,2025-01-01,2025-01-01,,ACTIF,1,300000\n",
        encoding="utf-8",
    )

    # 7. Assures
    (raw / "assures.csv").write_text(
        "assure_id,contrat_id,rang_beneficiaire,assure_principal_id,sexe,annee_naissance,ville,date_adhesion,date_radiation\n"
        "ASS-001,CTR-001,1,ASS-001,M,1990,Tana,2025-01-01,\n",
        encoding="utf-8",
    )

    # 8. Identites PII (données fictives)
    (raw / "identites_pii.csv").write_text(
        "assure_id,nom,prenoms,sexe,date_naissance,telephone,email,adresse,ville,numero_cin\n"
        "ASS-001,Dupont,Jean,M,1990-05-12,0340000001,j.dupont@email.fake,Lot 123,Tana,101000111222\n",
        encoding="utf-8",
    )

    # 9. Ordonnances
    (raw / "ordonnances.csv").write_text(
        "ordonnance_id,assure_id,prescripteur_id,date_prescription,validite_jours,type_ordonnance,diagnostic,renseignement_clinique\n"
        "ORD-001,ASS-001,PR-001,2026-01-10,90,CONSULTATION,Céphalées,\n",
        encoding="utf-8",
    )

    # 10. Ordonnance lignes
    (raw / "ordonnance_lignes.csv").write_text(
        "ordonnance_id,num_ligne,code,libelle,quantite,posologie\n"
        "ORD-001,1,ACT-01,Consultation,1,1 par jour\n",
        encoding="utf-8",
    )

    # 11. Factures (avec ordonnance et sans ordonnance)
    (raw / "factures.csv").write_text(
        "facture_id,numero_facture,prestataire_id,assure_id,contrat_id,ordonnance_id,type_facture,date_soin,heure_soin,date_facture,date_reception,canal_reception,mode_reglement,attestation_pec_id,entente_prealable_id,devise,nb_lignes,montant_total,montant_eligible,montant_pris_en_charge,reste_a_charge,statut,motif_rejet,date_traitement\n"
        "FAC-001,F-001,PR-001,ASS-001,CTR-001,ORD-001,CONSULTATION,2026-01-15,10:00,2026-01-15,2026-01-16,ELECTRONIQUE,VIREMENT,,,MGA,1,25000,25000,20000,5000,PAYEE,,2026-01-18\n"
        "FAC-002,F-002,PR-001,ASS-001,CTR-001,,CONSULTATION,2026-01-20,11:00,2026-01-20,2026-01-21,ELECTRONIQUE,VIREMENT,,,MGA,1,30000,30000,0,30000,REJETEE,FACTURE_INVALIDE,2026-01-22\n",
        encoding="utf-8",
    )

    # 12. Lignes facture
    (raw / "lignes_facture.csv").write_text(
        "ligne_id,facture_id,num_ligne,code,type_ligne,libelle,quantite,prix_unitaire,montant\n"
        "LIG-001,FAC-001,1,ACT-01,ACTE,Consultation,1,25000,25000\n"
        "LIG-002,FAC-002,1,ACT-01,ACTE,Consultation,1,30000,30000\n",
        encoding="utf-8",
    )

    # 13. Labels fraude
    (raw / "labels_fraude.csv").write_text(
        "facture_id,est_fraude,type_fraude,detail_fraude,est_valide,motif_invalidite\n"
        "FAC-001,0,,,1,\n"
        "FAC-002,1,SURFACTURATION,Tarif hors barème,0,\n",
        encoding="utf-8",
    )

    # 14. Labels prestataires
    (raw / "labels_prestataires.csv").write_text(
        "prestataire_id,est_suspect\nPR-001,0\n",
        encoding="utf-8",
    )

    return raw


def test_types_and_integer_amounts(synthetic_raw_dir: Path):
    """Vérifie que les montants sont en entiers stricts et les dates au format AAAA-MM-JJ."""
    tables, _ = clean_all(synthetic_raw_dir)
    df_fac = tables["factures"]

    assert df_fac["montant_total"].dtype.name == "Int64"
    assert df_fac["montant_eligible"].dtype.name == "Int64"
    assert df_fac["montant_pris_en_charge"].dtype.name == "Int64"
    assert df_fac.loc[0, "date_soin"] == "2026-01-15"


def test_exact_duplicates_removed():
    """Vérifie que deux lignes strictement identiques sont dédoublonnées."""
    import pandas as pd

    df = pd.DataFrame(
        [
            {
                "code_medicament": "M1",
                "libelle": "A",
                "prix_reference": 100,
                "remboursable": 1,
                "classe": "C",
                "chronique": 0,
            },
            {
                "code_medicament": "M1",
                "libelle": "A",
                "prix_reference": 100,
                "remboursable": 1,
                "classe": "C",
                "chronique": 0,
            },
        ]
    )
    clean, _, stats = clean_dataframe_base(df, "referentiel_medicaments")
    assert len(clean) == 1
    assert stats["doublons_parfaits_supprimes"] == 1


def test_primary_key_conflicts_quarantined():
    """Vérifie qu'un conflit de clé primaire (même PK, valeurs différentes) est mis en quarantaine."""
    import pandas as pd

    df = pd.DataFrame(
        [
            {
                "code_medicament": "M1",
                "libelle": "Nom 1",
                "prix_reference": 100,
                "remboursable": 1,
                "classe": "C",
                "chronique": 0,
            },
            {
                "code_medicament": "M1",
                "libelle": "Nom 2 (Conflit)",
                "prix_reference": 200,
                "remboursable": 1,
                "classe": "C",
                "chronique": 0,
            },
        ]
    )
    clean, quarantine, stats = clean_dataframe_base(df, "referentiel_medicaments")
    assert len(clean) == 1
    assert len(quarantine) == 2
    assert stats["conflits_pk_quarantaine"] == 2
    assert quarantine[0]["motif"] == "CONFLIT_CLE_PRIMAIRE"


def test_structural_nulls_preserved(synthetic_raw_dir: Path):
    """Vérifie que les nulls légitimes (ordonnance_id absent) restent nuls sans imputation."""
    tables, _ = clean_all(synthetic_raw_dir)
    df_fac = tables["factures"]

    assert df_fac.loc[0, "ordonnance_id"] == "ORD-001"
    assert pd.isna(df_fac.loc[1, "ordonnance_id"])


def test_leakage_columns_present_in_factures(synthetic_raw_dir: Path):
    """Vérifie que LEAKAGE_COLUMNS sont bien présentes dans factures pour l'API mais isolables."""
    tables, _ = clean_all(synthetic_raw_dir)
    df_fac = tables["factures"]

    for col in LEAKAGE_COLUMNS:
        assert col in df_fac.columns


def test_labels_not_merged_into_factures(synthetic_raw_dir: Path):
    """Vérifie que la table factures ne contient pas les colonnes de labels (pas de fuite)."""
    tables, _ = clean_all(synthetic_raw_dir)
    df_fac = tables["factures"]

    assert "est_fraude" not in df_fac.columns
    assert "type_fraude" not in df_fac.columns
    assert "labels_fraude" in tables


def test_deterministic_rerun_identical_bytes(synthetic_raw_dir: Path, tmp_path: Path):
    """Vérifie que deux exécutions consécutives produisent exactement les mêmes octets (Règle 8)."""
    out1 = tmp_path / "proc1"
    out2 = tmp_path / "proc2"

    run_pipeline(synthetic_raw_dir, out1, seed=42)
    run_pipeline(synthetic_raw_dir, out2, seed=42)

    for f1 in out1.glob("*.csv"):
        f2 = out2 / f1.name
        assert f2.exists()
        assert f1.read_bytes() == f2.read_bytes(), f"Différence d'octets sur {f1.name}"


def test_no_pii_in_processed_by_default(synthetic_raw_dir: Path, tmp_path: Path):
    """Vérifie que identites_pii n'est jamais exporté en clair par défaut (Règle 7 - RGPD)."""
    out = tmp_path / "proc"
    run_pipeline(synthetic_raw_dir, out, export_pii_unencrypted=False)

    assert not (out / "identites_pii.csv").exists()

    # Vérification dans le rapport JSON
    report = json.loads((out / "qualite_rapport.json").read_text(encoding="utf-8"))
    report_str = json.dumps(report)
    assert "Dupont" not in report_str
    assert "j.dupont@email.fake" not in report_str


def test_sampling_preserves_referential_integrity(synthetic_raw_dir: Path):
    """Vérifie que l'échantillonnage ne crée aucun orphelin."""
    tables, report = clean_all(synthetic_raw_dir, sample_n=1, seed=42)
    assert len(tables["factures"]) == 1
    assert len(report["anomalies_orphelins"]) == 0


@pytest.mark.skipif(
    not Path("data/raw/factures.csv").exists(),
    reason="data/raw non présent dans l'environnement",
)
def test_real_data_smoke_test():
    """Test fumée sur les vraies données locales (ignoré en CI si data/raw absent)."""
    tables, report = clean_all("data/raw", sample_n=50)
    assert len(tables["factures"]) == 50
    assert len(report["anomalies_orphelins"]) == 0
