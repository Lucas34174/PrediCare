"""referentiels et prestataires

Revision ID: 529522b561fd
Revises:
Create Date: 2026-10-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "529522b561fd"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Montants en ariary (MGA) : entiers, sans décimales.
MONTANT = sa.BigInteger()
FORMULES = "('ESSENTIEL', 'CONFORT', 'PREMIUM')"


def upgrade() -> None:
    # Déjà créées par infra/db/init au premier démarrage du volume ; ces lignes
    # couvrent les bases vierges (CI, autre environnement).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "referentiel_actes",
        sa.Column("code_acte", sa.String(30), primary_key=True),
        sa.Column("libelle", sa.Text(), nullable=False),
        sa.Column("categorie", sa.String(30), nullable=False),
        sa.Column("specialite", sa.String(40), nullable=True),
        sa.Column("tarif_min", MONTANT, nullable=False),
        sa.Column("tarif_reference", MONTANT, nullable=False),
        sa.Column("tarif_max", MONTANT, nullable=False),
        sa.Column("ordonnance_requise", sa.Boolean(), nullable=False),
        sa.Column("entente_prealable", sa.Boolean(), nullable=False),
        sa.Column("sexe_requis", sa.String(1), nullable=True),
        sa.Column("age_min", sa.SmallInteger(), nullable=False),
        sa.Column("age_max", sa.SmallInteger(), nullable=False),
        sa.CheckConstraint("sexe_requis IN ('F', 'M')", name="ck_referentiel_actes_sexe_requis"),
    )

    op.create_table(
        "referentiel_medicaments",
        sa.Column("code_medicament", sa.String(30), primary_key=True),
        sa.Column("libelle", sa.Text(), nullable=False),
        sa.Column("prix_reference", MONTANT, nullable=False),
        sa.Column("remboursable", sa.Boolean(), nullable=False),
        sa.Column("classe", sa.String(40), nullable=False),
        sa.Column("chronique", sa.Boolean(), nullable=False),
    )

    op.create_table(
        "garanties",
        sa.Column("formule", sa.String(20), nullable=False),
        sa.Column("categorie", sa.String(30), nullable=False),
        sa.Column("taux_remboursement", sa.SmallInteger(), nullable=False),
        sa.Column("plafond_annuel_categorie", MONTANT, nullable=False),
        sa.Column("franchise_par_facture", MONTANT, nullable=False),
        sa.Column("delai_carence_jours", sa.SmallInteger(), nullable=False),
        sa.Column("plafond_annuel_global", MONTANT, nullable=False),
        sa.Column("prime_annuelle_par_beneficiaire", MONTANT, nullable=False),
        sa.Column("attestation_requise", sa.Boolean(), nullable=False),
        sa.Column(
            "actes_exclus",
            sa.ARRAY(sa.String(30)),
            nullable=True,
            comment="Codes d'actes exclus (le CSV les sépare par |).",
        ),
        sa.Column("pieces_justificatives", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("formule", "categorie", name="pk_garanties"),
        sa.CheckConstraint(f"formule IN {FORMULES}", name="ck_garanties_formule"),
        sa.CheckConstraint(
            "taux_remboursement BETWEEN 0 AND 100", name="ck_garanties_taux_remboursement"
        ),
    )

    op.create_table(
        "prestataires",
        sa.Column("prestataire_id", sa.String(20), primary_key=True),
        sa.Column("nom", sa.Text(), nullable=False),
        sa.Column("type_prestataire", sa.String(30), nullable=False),
        sa.Column("specialite", sa.String(40), nullable=True),
        sa.Column("ville", sa.String(40), nullable=False),
        sa.Column("quartier", sa.String(60), nullable=False),
        sa.Column("adresse", sa.Text(), nullable=False),
        sa.Column("telephone", sa.String(30), nullable=False),
        sa.Column("numero_onm", sa.String(30), nullable=True),
        sa.Column("nif", sa.String(30), nullable=False),
        sa.Column("horaires", sa.Text(), nullable=False),
        sa.Column(
            "jours_ouverture",
            sa.ARRAY(sa.SmallInteger()),
            nullable=False,
            comment="Jours d'ouverture, 1 = lundi ... 7 = dimanche (le CSV les colle : 12345).",
        ),
        sa.Column("heure_ouverture", sa.SmallInteger(), nullable=False),
        sa.Column("heure_fermeture", sa.SmallInteger(), nullable=False),
        sa.Column("niveau_tarif", sa.String(20), nullable=False),
        sa.Column("note_qualite", sa.SmallInteger(), nullable=False),
        sa.Column("conventionne", sa.Boolean(), nullable=False),
        sa.Column("date_conventionnement", sa.Date(), nullable=False),
        sa.Column("date_fin_convention", sa.Date(), nullable=True),
        sa.Column("statut", sa.String(10), nullable=False),
        sa.CheckConstraint("statut IN ('ACTIF', 'RADIE')", name="ck_prestataires_statut"),
        sa.CheckConstraint("note_qualite BETWEEN 1 AND 5", name="ck_prestataires_note_qualite"),
        sa.CheckConstraint(
            "heure_ouverture BETWEEN 0 AND 24 AND heure_fermeture BETWEEN 0 AND 24",
            name="ck_prestataires_heures",
        ),
        sa.CheckConstraint(
            "cardinality(jours_ouverture) BETWEEN 1 AND 7", name="ck_prestataires_jours_ouverture"
        ),
    )

    # Le code désigne un acte OU un médicament (deux référentiels) : pas de clé étrangère.
    op.create_table(
        "grille_tarifaire",
        sa.Column(
            "prestataire_id",
            sa.String(20),
            sa.ForeignKey("prestataires.prestataire_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("tarif_pratique", MONTANT, nullable=False),
        sa.PrimaryKeyConstraint("prestataire_id", "code", name="pk_grille_tarifaire"),
    )
    op.create_index("ix_grille_tarifaire_code", "grille_tarifaire", ["code"])


def downgrade() -> None:
    # Les extensions ne sont pas supprimées : elles sont partagées avec infra/db/init.
    op.drop_table("grille_tarifaire")
    op.drop_table("prestataires")
    op.drop_table("garanties")
    op.drop_table("referentiel_medicaments")
    op.drop_table("referentiel_actes")
