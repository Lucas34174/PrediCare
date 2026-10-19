"""Schémas des tables, typages stricts et constantes pour le pipeline de données (PB-04).

Ce module centralise :
- L'alignement strict avec l'ERD (§2 de docs/contrats_interface.md) et les migrations Alembic.
- La constante LEAKAGE_COLUMNS pour isoler la fuite de données (PB-05).
- Les définitions des clés primaires, colonnes monétaires (entiers en Ariary) et dates.
"""

from typing import Final

# ------------------------------------------------------------------------------
# Colonnes à fuite de données
# ------------------------------------------------------------------------------
LEAKAGE_COLUMNS: Final[list[str]] = [
    "statut",
    "motif_rejet",
    "montant_pris_en_charge",
    "date_traitement",
]

# ------------------------------------------------------------------------------
# Colonnes PII sensibles
# ------------------------------------------------------------------------------
PII_COLUMNS: Final[list[str]] = [
    "nom",
    "prenoms",
    "date_naissance",
    "telephone",
    "email",
    "adresse",
    "numero_cin",
]

# ------------------------------------------------------------------------------
# Clés primaires par table (pour détection de doublons et quarantaine)
# ------------------------------------------------------------------------------
TABLE_PRIMARY_KEYS: Final[dict[str, list[str]]] = {
    "referentiel_actes": ["code_acte"],
    "referentiel_medicaments": ["code_medicament"],
    "garanties": ["formule", "categorie"],
    "prestataires": ["prestataire_id"],
    "grille_tarifaire": ["prestataire_id", "code"],
    "contrats": ["contrat_id"],
    "assures": ["assure_id"],
    "identites_pii": ["assure_id"],
    "ordonnances": ["ordonnance_id"],
    "ordonnance_lignes": ["ordonnance_id", "num_ligne"],
    "factures": ["facture_id"],
    "lignes_facture": ["ligne_id"],
    "labels_fraude": ["facture_id"],
    "labels_prestataires": ["prestataire_id"],
}

# ------------------------------------------------------------------------------
# Définition des colonnes et types attendus (12 CSV + 2 labels)
# ------------------------------------------------------------------------------
TABLE_SCHEMAS: Final[dict[str, list[str]]] = {
    "referentiel_actes": [
        "code_acte",
        "libelle",
        "categorie",
        "specialite",
        "tarif_min",
        "tarif_reference",
        "tarif_max",
        "ordonnance_requise",
        "entente_prealable",
        "sexe_requis",
        "age_min",
        "age_max",
    ],
    "referentiel_medicaments": [
        "code_medicament",
        "libelle",
        "prix_reference",
        "remboursable",
        "classe",
        "chronique",
    ],
    "garanties": [
        "formule",
        "categorie",
        "taux_remboursement",
        "plafond_annuel_categorie",
        "franchise_par_facture",
        "delai_carence_jours",
        "plafond_annuel_global",
        "prime_annuelle_par_beneficiaire",
        "attestation_requise",
        "actes_exclus",
        "pieces_justificatives",
    ],
    "prestataires": [
        "prestataire_id",
        "nom",
        "type_prestataire",
        "specialite",
        "ville",
        "quartier",
        "adresse",
        "telephone",
        "numero_onm",
        "nif",
        "horaires",
        "jours_ouverture",
        "heure_ouverture",
        "heure_fermeture",
        "niveau_tarif",
        "note_qualite",
        "conventionne",
        "date_conventionnement",
        "date_fin_convention",
        "statut",
    ],
    "grille_tarifaire": [
        "prestataire_id",
        "code",
        "tarif_pratique",
    ],
    "contrats": [
        "contrat_id",
        "numero_police",
        "souscripteur_id",
        "souscripteur_nom",
        "secteur",
        "formule",
        "date_effet_police",
        "date_effet",
        "date_fin",
        "statut",
        "nb_beneficiaires",
        "prime_annuelle_totale",
    ],
    "assures": [
        "assure_id",
        "contrat_id",
        "rang_beneficiaire",
        "assure_principal_id",
        "sexe",
        "annee_naissance",
        "ville",
        "date_adhesion",
        "date_radiation",
    ],
    "identites_pii": [
        "assure_id",
        "nom",
        "prenoms",
        "sexe",
        "date_naissance",
        "telephone",
        "email",
        "adresse",
        "ville",
        "numero_cin",
    ],
    "ordonnances": [
        "ordonnance_id",
        "assure_id",
        "prescripteur_id",
        "date_prescription",
        "validite_jours",
        "type_ordonnance",
        "diagnostic",
        "renseignement_clinique",
    ],
    "ordonnance_lignes": [
        "ordonnance_id",
        "num_ligne",
        "code",
        "libelle",
        "quantite",
        "posologie",
    ],
    "factures": [
        "facture_id",
        "numero_facture",
        "prestataire_id",
        "assure_id",
        "contrat_id",
        "ordonnance_id",
        "type_facture",
        "date_soin",
        "heure_soin",
        "date_facture",
        "date_reception",
        "canal_reception",
        "mode_reglement",
        "attestation_pec_id",
        "entente_prealable_id",
        "devise",
        "nb_lignes",
        "montant_total",
        "montant_eligible",
        "montant_pris_en_charge",
        "reste_a_charge",
        "statut",
        "motif_rejet",
        "date_traitement",
    ],
    "lignes_facture": [
        "ligne_id",
        "facture_id",
        "num_ligne",
        "code",
        "type_ligne",
        "libelle",
        "quantite",
        "prix_unitaire",
        "montant",
    ],
    "labels_fraude": [
        "facture_id",
        "est_fraude",
        "type_fraude",
        "detail_fraude",
        "est_valide",
        "motif_invalidite",
    ],
    "labels_prestataires": [
        "prestataire_id",
        "est_suspect",
    ],
}

# Colonnes de montants en Ariary (doivent être des entiers stricts int64)
MONEY_COLUMNS: Final[set[str]] = {
    "tarif_min",
    "tarif_reference",
    "tarif_max",
    "prix_reference",
    "plafond_annuel_categorie",
    "franchise_par_facture",
    "plafond_annuel_global",
    "prime_annuelle_par_beneficiaire",
    "tarif_pratique",
    "prime_annuelle_totale",
    "montant_total",
    "montant_eligible",
    "montant_pris_en_charge",
    "reste_a_charge",
    "prix_unitaire",
    "montant",
}

# Colonnes de dates (format AAAA-MM-JJ normalisé)
DATE_COLUMNS: Final[set[str]] = {
    "date_conventionnement",
    "date_fin_convention",
    "date_effet_police",
    "date_effet",
    "date_fin",
    "date_adhesion",
    "date_radiation",
    "date_naissance",
    "date_prescription",
    "date_soin",
    "date_facture",
    "date_reception",
    "date_traitement",
}
