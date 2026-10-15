"""cree le schema initial complet

Revision ID: 20261014_4f06d78eaacf
Revises:
Create Date: 2026-10-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "20261014_4f06d78eaacf"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 0. Extensions PostgreSQL
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    # 1. Référentiels et Prestataires
    op.create_table(
        "referentiel_actes",
        sa.Column("code_acte", sa.String(50), primary_key=True),
        sa.Column("libelle", sa.String(255), nullable=False),
        sa.Column("categorie", sa.String(100), nullable=True),
        sa.Column("tarif_conventionnel_base", sa.Numeric(12, 2), nullable=False),
        sa.Column("plafond_remboursement", sa.Numeric(12, 2), nullable=True),
        sa.Column("incompatible_avec", sa.ARRAY(sa.String(50)), nullable=True),
    )

    op.create_table(
        "referentiel_medicaments",
        sa.Column("code_cip", sa.String(50), primary_key=True),
        sa.Column("nom_commercial", sa.String(255), nullable=False),
        sa.Column("dci", sa.String(255), nullable=True),
        sa.Column("forme", sa.String(100), nullable=True),
        sa.Column("dosage", sa.String(100), nullable=True),
        sa.Column("prix_unitaire_base", sa.Numeric(12, 2), nullable=False),
        sa.Column("taux_remboursement_base", sa.Numeric(5, 2), nullable=True),
    )

    op.create_table(
        "prestataires",
        sa.Column("prestataire_id", sa.String(50), primary_key=True),
        sa.Column("nom_etablissement", sa.String(255), nullable=False),
        sa.Column("specialite", sa.String(100), nullable=True),
        sa.Column("type_etablissement", sa.String(100), nullable=True),
        sa.Column("ville", sa.String(100), nullable=True),
        sa.Column("code_postal", sa.String(20), nullable=True),
        sa.Column("adresse", sa.String(255), nullable=True),
        sa.Column("telephone", sa.String(50), nullable=True),
        sa.Column("conventionne", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("date_agrement", sa.Date(), nullable=True),
    )

    op.create_table(
        "grille_tarifaire",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "code_acte",
            sa.String(50),
            sa.ForeignKey("referentiel_actes.code_acte", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "prestataire_id",
            sa.String(50),
            sa.ForeignKey("prestataires.prestataire_id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("type_etablissement", sa.String(100), nullable=True),
        sa.Column("tarif_autorise", sa.Numeric(12, 2), nullable=False),
        sa.Column("date_debut_validite", sa.Date(), nullable=False),
        sa.Column("date_fin_validite", sa.Date(), nullable=True),
    )

    # 2. Contrats & Garanties
    op.create_table(
        "garanties",
        sa.Column("code_garantie", sa.String(50), primary_key=True),
        sa.Column("formule", sa.String(50), nullable=False),
        sa.Column("type_soin", sa.String(100), nullable=False),
        sa.Column("taux_couverture", sa.Numeric(5, 2), nullable=False),
        sa.Column("plafond_annuel", sa.Numeric(12, 2), nullable=True),
        sa.Column("delai_carence_jours", sa.Integer(), server_default="0", nullable=False),
    )

    op.create_table(
        "contrats",
        sa.Column("contrat_id", sa.String(50), primary_key=True),
        sa.Column("formule", sa.String(50), nullable=False),
        sa.Column("date_debut", sa.Date(), nullable=False),
        sa.Column("date_fin", sa.Date(), nullable=True),
        sa.Column("statut", sa.String(50), nullable=False),
        sa.Column("cotisations_a_jour", sa.Boolean(), server_default="true", nullable=False),
    )

    # 3. Assurés & PII Chiffrée
    op.create_table(
        "assures",
        sa.Column("assure_id", sa.String(50), primary_key=True),
        sa.Column(
            "contrat_id",
            sa.String(50),
            sa.ForeignKey("contrats.contrat_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("annee_naissance", sa.Integer(), nullable=True),
        sa.Column("genre", sa.String(20), nullable=True),
        sa.Column("statut_activite", sa.String(100), nullable=True),
        sa.Column("ville_residence", sa.String(100), nullable=True),
        sa.Column("date_adhesion", sa.Date(), nullable=False),
    )

    op.create_table(
        "identites_pii",
        sa.Column(
            "assure_id",
            sa.String(50),
            sa.ForeignKey("assures.assure_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("nom_chiffre", sa.LargeBinary(), nullable=False),
        sa.Column("prenom_chiffre", sa.LargeBinary(), nullable=False),
        sa.Column("date_naissance_chiffre", sa.LargeBinary(), nullable=True),
        sa.Column("telephone_chiffre", sa.LargeBinary(), nullable=True),
        sa.Column("email_chiffre", sa.LargeBinary(), nullable=True),
        sa.Column("adresse_chiffree", sa.LargeBinary(), nullable=True),
        sa.Column("numero_secu_chiffre", sa.LargeBinary(), nullable=True),
        sa.Column(
            "date_derniere_maj",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # 4. Ordonnances et Prescriptions
    op.create_table(
        "ordonnances",
        sa.Column("ordonnance_id", sa.String(50), primary_key=True),
        sa.Column(
            "assure_id",
            sa.String(50),
            sa.ForeignKey("assures.assure_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "prescripteur_id",
            sa.String(50),
            sa.ForeignKey("prestataires.prestataire_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("date_prescription", sa.Date(), nullable=False),
        sa.Column("diagnostic_code", sa.String(100), nullable=True),
        sa.Column("duree_validite_jours", sa.Integer(), server_default="90", nullable=False),
    )

    op.create_table(
        "ordonnance_lignes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "ordonnance_id",
            sa.String(50),
            sa.ForeignKey("ordonnances.ordonnance_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "code_cip",
            sa.String(50),
            sa.ForeignKey("referentiel_medicaments.code_cip", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "code_acte",
            sa.String(50),
            sa.ForeignKey("referentiel_actes.code_acte", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("quantite_prescrite", sa.Integer(), nullable=False),
        sa.Column("posologie", sa.String(255), nullable=True),
    )

    # 5. Factures et Lignes de facture
    op.create_table(
        "factures",
        sa.Column("facture_id", sa.String(50), primary_key=True),
        sa.Column(
            "assure_id",
            sa.String(50),
            sa.ForeignKey("assures.assure_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "prestataire_id",
            sa.String(50),
            sa.ForeignKey("prestataires.prestataire_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "ordonnance_id",
            sa.String(50),
            sa.ForeignKey("ordonnances.ordonnance_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("date_soin", sa.Date(), nullable=False),
        sa.Column("date_emission", sa.Date(), nullable=False),
        sa.Column("montant_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("part_assure", sa.Numeric(12, 2), nullable=False),
        sa.Column("montant_demande", sa.Numeric(12, 2), nullable=False),
        sa.Column("statut", sa.String(50), server_default="EN_ATTENTE", nullable=False),
        sa.Column("motif_rejet", sa.String(255), nullable=True),
        sa.Column("montant_pris_en_charge", sa.Numeric(12, 2), nullable=True),
        sa.Column("date_traitement", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "lignes_facture",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "facture_id",
            sa.String(50),
            sa.ForeignKey("factures.facture_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "code_acte",
            sa.String(50),
            sa.ForeignKey("referentiel_actes.code_acte", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "code_cip",
            sa.String(50),
            sa.ForeignKey("referentiel_medicaments.code_cip", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("quantite", sa.Integer(), server_default="1", nullable=False),
        sa.Column("prix_unitaire", sa.Numeric(12, 2), nullable=False),
        sa.Column("montant_ligne", sa.Numeric(12, 2), nullable=False),
        sa.Column("depassement", sa.Numeric(12, 2), server_default="0.00", nullable=False),
    )

    # 6. ML, Explicabilité & Décisions
    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "facture_id",
            sa.String(50),
            sa.ForeignKey("factures.facture_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("score_fraude", sa.Float(), nullable=False),
        sa.Column("est_fraude_predite", sa.Boolean(), nullable=False),
        sa.Column("seuil_applique", sa.Float(), nullable=False),
        sa.Column("version_modele", sa.String(50), nullable=False),
        sa.Column(
            "date_prediction",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "explications_shap",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "prediction_id",
            sa.Integer(),
            sa.ForeignKey("predictions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("top_features", sa.JSON(), nullable=False),
        sa.Column("raw_shap_values", sa.JSON(), nullable=True),
        sa.Column(
            "date_generation",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "decisions_gestionnaire",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "facture_id",
            sa.String(50),
            sa.ForeignKey("factures.facture_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("decision", sa.String(50), nullable=False),
        sa.Column("motif", sa.String(255), nullable=True),
        sa.Column("montant_final_accorde", sa.Numeric(12, 2), nullable=True),
        sa.Column("gestionnaire_id", sa.String(50), nullable=False),
        sa.Column(
            "date_decision",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # 7. RAG Vector Store & Semantic Caching
    op.create_table(
        "documents_vectorises",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("titre_document", sa.String(255), nullable=False),
        sa.Column("formule_concernee", sa.String(50), nullable=True),
        sa.Column("section", sa.String(255), nullable=True),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("contenu", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "date_indexation",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "semantic_cache",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("query_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("query_embedding", Vector(1024), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=False),
        sa.Column("similarity_threshold", sa.Float(), server_default="0.85", nullable=False),
        sa.Column("hit_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    # 8. Journal d'audit & Traçabilité
    op.create_table(
        "journal_audit",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("type_action", sa.String(100), nullable=False),
        sa.Column("utilisateur_id", sa.String(50), nullable=True),
        sa.Column("role_utilisateur", sa.String(50), nullable=True),
        sa.Column("ressource_type", sa.String(100), nullable=True),
        sa.Column("ressource_id", sa.String(100), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("ip_source", sa.String(50), nullable=True),
        sa.Column(
            "date_action", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    # 9. Index de performance et détection de fraude
    op.create_index("idx_factures_assure", "factures", ["assure_id"])
    op.create_index("idx_factures_prestataire", "factures", ["prestataire_id"])
    op.create_index("idx_factures_ordonnance", "factures", ["ordonnance_id"])
    op.create_index("idx_factures_date_soin", "factures", ["date_soin"])
    op.create_index("idx_ordonnances_assure", "ordonnances", ["assure_id"])
    op.create_index("idx_lignes_facture_facture", "lignes_facture", ["facture_id"])
    op.create_index("idx_predictions_facture", "predictions", ["facture_id"])


def downgrade() -> None:
    # Suppression des index
    op.drop_index("idx_predictions_facture", table_name="predictions")
    op.drop_index("idx_lignes_facture_facture", table_name="lignes_facture")
    op.drop_index("idx_ordonnances_assure", table_name="ordonnances")
    op.drop_index("idx_factures_date_soin", table_name="factures")
    op.drop_index("idx_factures_ordonnance", table_name="factures")
    op.drop_index("idx_factures_prestataire", table_name="factures")
    op.drop_index("idx_factures_assure", table_name="factures")

    # Suppression des tables dans l'ordre inverse des dépendances
    op.drop_table("journal_audit")
    op.drop_table("semantic_cache")
    op.drop_table("documents_vectorises")
    op.drop_table("decisions_gestionnaire")
    op.drop_table("explications_shap")
    op.drop_table("predictions")
    op.drop_table("lignes_facture")
    op.drop_table("factures")
    op.drop_table("ordonnance_lignes")
    op.drop_table("ordonnances")
    op.drop_table("identites_pii")
    op.drop_table("assures")
    op.drop_table("contrats")
    op.drop_table("garanties")
    op.drop_table("grille_tarifaire")
    op.drop_table("prestataires")
    op.drop_table("referentiel_medicaments")
    op.drop_table("referentiel_actes")
