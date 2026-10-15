"""donnees metier

Revision ID: 82a5a406f960
Revises: 529522b561fd
Create Date: 2026-10-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "82a5a406f960"
down_revision: str | None = "529522b561fd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MONTANT = sa.BigInteger()
FORMULES = "('ESSENTIEL', 'CONFORT', 'PREMIUM')"
FUITE = "Fuite de données : résulte de la décision historique, à exclure des variables du modèle."


def upgrade() -> None:
    op.create_table(
        "contrats",
        sa.Column("contrat_id", sa.String(20), primary_key=True),
        sa.Column("numero_police", sa.String(30), nullable=False),
        sa.Column("souscripteur_id", sa.String(20), nullable=False),
        sa.Column("souscripteur_nom", sa.Text(), nullable=False),
        sa.Column("secteur", sa.String(60), nullable=False),
        sa.Column("formule", sa.String(20), nullable=False),
        sa.Column("date_effet_police", sa.Date(), nullable=False),
        sa.Column("date_effet", sa.Date(), nullable=False),
        sa.Column("date_fin", sa.Date(), nullable=True),
        sa.Column("statut", sa.String(10), nullable=False),
        sa.Column("nb_beneficiaires", sa.SmallInteger(), nullable=False),
        sa.Column("prime_annuelle_totale", MONTANT, nullable=False),
        sa.CheckConstraint(f"formule IN {FORMULES}", name="ck_contrats_formule"),
        sa.CheckConstraint("statut IN ('ACTIF', 'RESILIE')", name="ck_contrats_statut"),
    )

    op.create_table(
        "assures",
        sa.Column("assure_id", sa.String(20), primary_key=True),
        sa.Column(
            "contrat_id",
            sa.String(20),
            sa.ForeignKey("contrats.contrat_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("rang_beneficiaire", sa.String(20), nullable=False),
        sa.Column(
            "assure_principal_id",
            sa.String(20),
            sa.ForeignKey("assures.assure_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("sexe", sa.String(1), nullable=False),
        sa.Column("annee_naissance", sa.SmallInteger(), nullable=False),
        sa.Column("ville", sa.String(40), nullable=False),
        sa.Column("date_adhesion", sa.Date(), nullable=False),
        sa.Column("date_radiation", sa.Date(), nullable=True),
        sa.CheckConstraint(
            "rang_beneficiaire IN ('ASSURE_PRINCIPAL', 'CONJOINT', 'ENFANT')",
            name="ck_assures_rang_beneficiaire",
        ),
        sa.CheckConstraint("sexe IN ('F', 'M')", name="ck_assures_sexe"),
    )
    op.create_index("ix_assures_contrat", "assures", ["contrat_id"])

    # Seules les données personnelles sont ici, chiffrées avec pgcrypto (pgp_sym_encrypt).
    # Le sexe et la ville restent dans assures (pseudonymisés).
    op.create_table(
        "identites_pii",
        sa.Column(
            "assure_id",
            sa.String(20),
            sa.ForeignKey("assures.assure_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("nom_chiffre", sa.LargeBinary(), nullable=False),
        sa.Column("prenoms_chiffre", sa.LargeBinary(), nullable=False),
        sa.Column("date_naissance_chiffre", sa.LargeBinary(), nullable=False),
        sa.Column("telephone_chiffre", sa.LargeBinary(), nullable=True),
        sa.Column("email_chiffre", sa.LargeBinary(), nullable=True),
        sa.Column("adresse_chiffre", sa.LargeBinary(), nullable=False),
        sa.Column("numero_cin_chiffre", sa.LargeBinary(), nullable=True),
    )

    op.create_table(
        "ordonnances",
        sa.Column("ordonnance_id", sa.String(20), primary_key=True),
        sa.Column(
            "assure_id",
            sa.String(20),
            sa.ForeignKey("assures.assure_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "prescripteur_id",
            sa.String(20),
            sa.ForeignKey("prestataires.prestataire_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("date_prescription", sa.Date(), nullable=False),
        sa.Column("validite_jours", sa.SmallInteger(), nullable=False),
        sa.Column("type_ordonnance", sa.String(20), nullable=False),
        sa.Column("diagnostic", sa.Text(), nullable=True),
        sa.Column("renseignement_clinique", sa.Text(), nullable=True),
    )
    op.create_index("ix_ordonnances_assure", "ordonnances", ["assure_id"])
    op.create_index("ix_ordonnances_prescripteur", "ordonnances", ["prescripteur_id"])

    # Le code désigne un acte OU un médicament (deux référentiels) : pas de clé étrangère.
    op.create_table(
        "ordonnance_lignes",
        sa.Column(
            "ordonnance_id",
            sa.String(20),
            sa.ForeignKey("ordonnances.ordonnance_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("num_ligne", sa.SmallInteger(), nullable=False),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("libelle", sa.Text(), nullable=False),
        sa.Column("quantite", sa.Integer(), nullable=False),
        sa.Column("posologie", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("ordonnance_id", "num_ligne", name="pk_ordonnance_lignes"),
    )
    op.create_index("ix_ordonnance_lignes_code", "ordonnance_lignes", ["code"])

    # numero_facture n'est pas unique : une facture renvoyée (DOUBLON) garde son numéro.
    op.create_table(
        "factures",
        sa.Column("facture_id", sa.String(20), primary_key=True),
        sa.Column("numero_facture", sa.String(40), nullable=False),
        sa.Column(
            "prestataire_id",
            sa.String(20),
            sa.ForeignKey("prestataires.prestataire_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "assure_id",
            sa.String(20),
            sa.ForeignKey("assures.assure_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "contrat_id",
            sa.String(20),
            sa.ForeignKey("contrats.contrat_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "ordonnance_id",
            sa.String(20),
            sa.ForeignKey("ordonnances.ordonnance_id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("type_facture", sa.String(20), nullable=False),
        sa.Column("date_soin", sa.Date(), nullable=False),
        sa.Column("heure_soin", sa.Time(), nullable=False),
        sa.Column("date_facture", sa.Date(), nullable=False),
        sa.Column("date_reception", sa.Date(), nullable=False),
        sa.Column("canal_reception", sa.String(30), nullable=False),
        sa.Column("mode_reglement", sa.String(30), nullable=False),
        sa.Column("attestation_pec_id", sa.String(20), nullable=True),
        sa.Column("entente_prealable_id", sa.String(20), nullable=True),
        sa.Column("devise", sa.String(3), server_default="MGA", nullable=False),
        sa.Column("nb_lignes", sa.SmallInteger(), nullable=False),
        sa.Column("montant_total", MONTANT, nullable=False),
        sa.Column("montant_eligible", MONTANT, nullable=False),
        sa.Column("montant_pris_en_charge", MONTANT, nullable=False, comment=FUITE),
        sa.Column("reste_a_charge", MONTANT, nullable=False),
        sa.Column("statut", sa.String(10), nullable=False, comment=FUITE),
        sa.Column("motif_rejet", sa.String(40), nullable=True, comment=FUITE),
        sa.Column("date_traitement", sa.Date(), nullable=True, comment=FUITE),
        sa.CheckConstraint("statut IN ('EN_COURS', 'PAYEE', 'REJETEE')", name="ck_factures_statut"),
    )
    op.create_index("ix_factures_assure_date", "factures", ["assure_id", "date_soin"])
    op.create_index("ix_factures_prestataire_date", "factures", ["prestataire_id", "date_soin"])
    op.create_index("ix_factures_ordonnance", "factures", ["ordonnance_id"])
    op.create_index("ix_factures_contrat", "factures", ["contrat_id"])
    op.create_index("ix_factures_numero", "factures", ["numero_facture"])

    op.create_table(
        "lignes_facture",
        sa.Column("ligne_id", sa.String(30), primary_key=True),
        sa.Column(
            "facture_id",
            sa.String(20),
            sa.ForeignKey("factures.facture_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("num_ligne", sa.SmallInteger(), nullable=False),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("type_ligne", sa.String(10), nullable=False),
        sa.Column("libelle", sa.Text(), nullable=False),
        sa.Column("quantite", sa.Integer(), nullable=False),
        sa.Column("prix_unitaire", MONTANT, nullable=False),
        sa.Column("montant", MONTANT, nullable=False),
        sa.UniqueConstraint("facture_id", "num_ligne", name="uq_lignes_facture_facture_num"),
        sa.CheckConstraint(
            "type_ligne IN ('ACTE', 'MEDICAMENT')", name="ck_lignes_facture_type_ligne"
        ),
    )
    op.create_index("ix_lignes_facture_code", "lignes_facture", ["code"])


def downgrade() -> None:
    op.drop_table("lignes_facture")
    op.drop_table("factures")
    op.drop_table("ordonnance_lignes")
    op.drop_table("ordonnances")
    op.drop_table("identites_pii")
    op.drop_table("assures")
    op.drop_table("contrats")
