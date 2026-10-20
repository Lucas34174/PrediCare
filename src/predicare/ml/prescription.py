"""PB-09 — Détection d'anomalies de prescription.

Trois familles de signaux, calculées depuis les 12 CSV sources :

1. **Nomadisme / surconsommation** : une même ordonnance facturée par plusieurs
   prestataires (``SURCONSOMMATION``) ;
2. **Lignes hors ordonnance** : codes facturés absents de l'ordonnance
   (``LIGNES_NON_PRESCRITES``) ;
3. **Inadéquation diagnostic / famille thérapeutique**
   (``INADEQUATION_DIAGNOSTIC``), ainsi que les règles prescription de l'EDA
   (doublon, prescripteur, ordonnance antidatée, surcharge, ordonnance vide).

La sortie respecte le contrat des alertes métier :
``facture_id, code_fraude, gravite, montant_en_jeu, explication``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from predicare.ml.config import SOURCE_DIR

# Gravité 1 (faible) à 3 (élevée), alignée sur ``alertes_factures_detail.csv``.
GRAVITE_PRESCRIPTION: dict[str, int] = {
    "DOUBLON_PRESCRIPTION": 2,
    "INADEQUATION_DIAGNOSTIC": 3,
    "PRESCRIPTEUR_INCOMPATIBLE": 2,
    "PRESCRIPTEUR_RADIE": 3,
    "ORDONNANCE_ANTIDATEE": 2,
    "SURCHARGE_QUANTITE": 2,
    "ORDONNANCE_SANS_LIGNE": 1,
    "SURCONSOMMATION": 3,
    "LIGNES_NON_PRESCRITES": 2,
}

# Cohérence clinique diagnostic → familles attendues (référentiel EDA, paramétrable).
ATTENDU_DIAGNOSTIC: dict[str, set[str] | None] = {
    "Infection respiratoire aiguë": {
        "ANTIBIOTIQUE", "ANTALGIQUE", "AINS", "RESPIRATOIRE", "CORTICOIDE",
        "ANTIINFECTIEUX", "LAB", "IMG",
    },
    "Hypertension artérielle": {"ANTIHYPERTENSEUR", "HYPOLIPEMIANT", "LAB", "IMG"},
    "Paludisme simple": {"ANTIPALUDEEN", "ANTALGIQUE", "AINS", "LAB", "IMG"},
    "Gastro-entérite": {
        "REHYDRATATION", "ANTIBIOTIQUE", "ANTIINFECTIEUX", "ANTALGIQUE", "AINS",
        "GASTRO", "LAB", "IMG",
    },
    "Infection urinaire": {"ANTIBIOTIQUE", "ANTIINFECTIEUX", "ANTALGIQUE", "LAB", "IMG"},
    "Diabète de type 2": {"ANTIDIABETIQUE", "LAB", "IMG"},
    "Traumatisme / entorse": {"AINS", "ANTALGIQUE", "CORTICOIDE", "KINE", "LAB", "IMG"},
    "Dyslipidémie": {"HYPOLIPEMIANT", "LAB", "IMG"},
    "Asthme": {"RESPIRATOIRE", "CORTICOIDE", "ANTIHISTAMINIQUE", "ANTIBIOTIQUE", "LAB", "IMG"},
    "Lombalgie": {"AINS", "ANTALGIQUE", "KINE", "CORTICOIDE", "LAB", "IMG"},
    "Rhinite allergique": {"ANTIHISTAMINIQUE", "CORTICOIDE", "RESPIRATOIRE", "LAB", "IMG"},
    "Céphalées": {"ANTALGIQUE", "AINS", "LAB", "IMG"},
    "Gastrite": {"GASTRO", "ANTIBIOTIQUE", "ANTALGIQUE", "LAB", "IMG"},
    "Dermatose": {"ANTIHISTAMINIQUE", "CORTICOIDE", "ANTIBIOTIQUE", "LAB", "IMG"},
    "Suivi de grossesse": {
        "SUPPLEMENTATION", "VITAMINE", "LAB", "IMG", "CONS", "ANTIBIOTIQUE", "ANTALGIQUE",
    },
    "Trouble de la réfraction": {"OPT", "LAB", "IMG"},
    "Insuffisance rénale chronique": {"DIALYSE", "ANTIHYPERTENSEUR", "LAB", "IMG"},
    "Trouble anxieux": {"ANTALGIQUE", "LAB", "IMG", "PSYCHOTROPE"},
    "Renouvellement de traitement": None,
}

SPECIALITES_PAR_ORDONNANCE: dict[str, set[str]] = {
    "OPTIQUE": {"OPHTALMOLOGIE"},
    "KINE": {"RHUMATOLOGIE", "TRAUMATO-ORTHOPEDIE", "NEUROLOGIE", "PEDIATRIE", "CABINET_KINE"},
}

COLONNES_ALERTES = ["facture_id", "ordonnance_id", "code_fraude", "gravite", "montant_en_jeu", "explication"]


def charger_tables(source_dir: Path | str | None = None) -> dict[str, pd.DataFrame]:
    """Charge les tables sources utiles à PB-09."""
    dossier = Path(source_dir) if source_dir else SOURCE_DIR
    noms = (
        "factures",
        "lignes_facture",
        "ordonnances",
        "ordonnance_lignes",
        "assures",
        "prestataires",
        "referentiel_medicaments",
    )
    tables: dict[str, pd.DataFrame] = {}
    for nom in noms:
        chemin = dossier / f"{nom}.csv"
        if not chemin.is_file():
            raise FileNotFoundError(f"Table source introuvable : {chemin}")
        tables[nom] = pd.read_csv(chemin, low_memory=False)
    return tables


def _dates(serie: pd.Series) -> pd.Series:
    return pd.to_datetime(serie, errors="coerce")


def _enrichir_lignes(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Lignes d'ordonnance enrichies (diagnostic, famille, prescripteur, adhésion)."""
    ordo = tables["ordonnances"].copy()
    ordo["date_prescription_dt"] = _dates(ordo["date_prescription"])
    lignes = tables["ordonnance_lignes"].copy()
    lignes["quantite_num"] = pd.to_numeric(lignes["quantite"], errors="coerce")

    med = tables["referentiel_medicaments"][["code_medicament", "classe", "chronique"]].copy()
    med["chronique"] = pd.to_numeric(med["chronique"], errors="coerce")

    lignes = lignes.merge(
        ordo[
            [
                "ordonnance_id",
                "assure_id",
                "prescripteur_id",
                "date_prescription_dt",
                "validite_jours",
                "diagnostic",
                "type_ordonnance",
            ]
        ],
        on="ordonnance_id",
        how="left",
    )
    lignes = lignes.merge(
        med, left_on="code", right_on="code_medicament", how="left"
    )
    lignes["famille"] = np.where(
        lignes["classe"].notna(),
        lignes["classe"],
        lignes["code"].astype(str).str.split("-").str[0],
    )

    assures = tables["assures"][["assure_id", "date_adhesion"]].copy()
    assures["adhesion_dt"] = _dates(assures["date_adhesion"])
    lignes = lignes.merge(assures[["assure_id", "adhesion_dt"]], on="assure_id", how="left")

    prest = tables["prestataires"][
        ["prestataire_id", "specialite", "date_fin_convention", "statut"]
    ].rename(columns={"statut": "statut_prestataire"})
    prest["fin_convention_dt"] = _dates(prest["date_fin_convention"])
    lignes = lignes.merge(
        prest,
        left_on="prescripteur_id",
        right_on="prestataire_id",
        how="left",
    )
    return lignes


def _alertes_ordonnance(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Règles prescription de l'EDA (niveau ordonnance)."""
    ordo = tables["ordonnances"].copy()
    ordo["date_prescription_dt"] = _dates(ordo["date_prescription"])
    ol = tables["ordonnance_lignes"].copy()
    lignes = _enrichir_lignes(tables)
    alertes: list[pd.DataFrame] = []

    def pack(src: pd.DataFrame, code: str, explication) -> pd.DataFrame:
        bloc = src[["ordonnance_id", "code"]].copy()
        bloc["code_fraude"] = code
        bloc["gravite"] = GRAVITE_PRESCRIPTION[code]
        bloc["explication"] = (
            [explication] * len(bloc) if isinstance(explication, str) else list(explication)
        )
        return bloc.rename(columns={"code": "code_concerne"})

    # P1 — doublon de prescription (même assuré, même code, ≤ 30 j ; ≤ 7 j si chronique).
    tri = lignes.sort_values(["assure_id", "code", "date_prescription_dt"]).copy()
    tri["gap"] = tri.groupby(["assure_id", "code"])["date_prescription_dt"].diff().dt.days
    doublon = tri[(tri["gap"] <= 30) & ((tri["chronique"] != 1) | (tri["gap"] <= 7))].copy()
    if len(doublon):
        alertes.append(
            pack(
                doublon,
                "DOUBLON_PRESCRIPTION",
                (
                    "Code " + doublon["code"].astype(str) + " represcrit "
                    + doublon["gap"].astype(int).astype(str)
                    + " j apres une prescription du meme assure"
                ).tolist(),
            )
        )

    # P2 — inadéquation diagnostic / famille.
    attendu = lignes["diagnostic"].map(ATTENDU_DIAGNOSTIC)
    incoherent = [isinstance(e, set) and (f not in e) for e, f in zip(attendu, lignes["famille"])]
    inad = lignes[incoherent].copy()
    if len(inad):
        alertes.append(
            pack(
                inad,
                "INADEQUATION_DIAGNOSTIC",
                (
                    "Code " + inad["code"].astype(str) + " (" + inad["famille"].astype(str)
                    + ") peu coherent avec le diagnostic '" + inad["diagnostic"].astype(str) + "'"
                ).tolist(),
            )
        )

    # P3 — prescripteur incompatible avec le type d'ordonnance.
    incompatible = [
        isinstance(SPECIALITES_PAR_ORDONNANCE.get(t), set)
        and pd.notna(sp)
        and (sp not in SPECIALITES_PAR_ORDONNANCE[t])
        for t, sp in zip(lignes["type_ordonnance"], lignes["specialite"])
    ]
    inc = lignes[incompatible].copy()
    if len(inc):
        alertes.append(
            pack(
                inc,
                "PRESCRIPTEUR_INCOMPATIBLE",
                (
                    "Ordonnance " + inc["type_ordonnance"].astype(str) + " emise par specialite "
                    + inc["specialite"].astype(str)
                ).tolist(),
            )
        )

    # P4 — prescripteur radié / hors convention.
    fin = lignes["fin_convention_dt"].notna() & (
        lignes["date_prescription_dt"] > lignes["fin_convention_dt"]
    )
    radie = lignes[
        ((lignes["statut_prestataire"] == "RADIE") & lignes["fin_convention_dt"].isna()) | fin
    ].copy()
    if len(radie):
        alertes.append(
            pack(radie, "PRESCRIPTEUR_RADIE", "Prescription emise par un prescripteur hors convention")
        )

    # P5 — ordonnance antidatée (avant l'adhésion).
    antidate = lignes[
        lignes["adhesion_dt"].notna() & (lignes["date_prescription_dt"] < lignes["adhesion_dt"])
    ].copy()
    if len(antidate):
        alertes.append(
            pack(antidate, "ORDONNANCE_ANTIDATEE", "Ordonnance datee avant l'adhesion de l'assure")
        )

    # P6 — surcharge de quantité (traitement aigu).
    surcharge = lignes[(lignes["chronique"] == 0) & (lignes["quantite_num"] >= 4)].copy()
    if len(surcharge):
        alertes.append(
            pack(surcharge, "SURCHARGE_QUANTITE", "Quantite prescrite anormalement elevee pour un traitement aigu")
        )

    # P7 — ordonnance sans ligne.
    sans = ordo[~ordo["ordonnance_id"].isin(set(ol["ordonnance_id"]))].copy()
    if len(sans):
        bloc = sans[["ordonnance_id"]].copy()
        bloc["code_concerne"] = ""
        bloc["code_fraude"] = "ORDONNANCE_SANS_LIGNE"
        bloc["gravite"] = GRAVITE_PRESCRIPTION["ORDONNANCE_SANS_LIGNE"]
        bloc["explication"] = "Ordonnance sans aucune ligne"
        alertes.append(bloc)

    if not alertes:
        return pd.DataFrame(columns=["ordonnance_id", "code_concerne", "code_fraude", "gravite", "explication"])
    return pd.concat(alertes, ignore_index=True)


def _alertes_facture(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Règles PB-09 au niveau facture : nomadisme et lignes hors ordonnance."""
    factures = tables["factures"].copy()
    lignes = tables["lignes_facture"].copy()
    ol = tables["ordonnance_lignes"].copy()
    alertes: list[pd.DataFrame] = []

    avec_ordo = factures[factures["ordonnance_id"].notna()].copy()

    # R1 — même ordonnance facturée par plusieurs prestataires.
    if len(avec_ordo):
        par_ordo = (
            avec_ordo.groupby("ordonnance_id")
            .agg(nb_prestataires=("prestataire_id", "nunique"), montant=("montant_total", "sum"))
            .reset_index()
        )
        nomade = par_ordo[par_ordo["nb_prestataires"] >= 2]
        if len(nomade):
            bloc = avec_ordo.merge(
                nomade[["ordonnance_id", "nb_prestataires", "montant"]],
                on="ordonnance_id",
                how="inner",
            )
            alertes.append(
                pd.DataFrame(
                    {
                        "facture_id": bloc["facture_id"],
                        "ordonnance_id": bloc["ordonnance_id"],
                        "code_fraude": "SURCONSOMMATION",
                        "gravite": GRAVITE_PRESCRIPTION["SURCONSOMMATION"],
                        "montant_en_jeu": bloc["montant_total"],
                        "explication": (
                            "Ordonnance " + bloc["ordonnance_id"].astype(str)
                            + " facturee par " + bloc["nb_prestataires"].astype(int).astype(str)
                            + " prestataires (montant cumule "
                            + bloc["montant"].round(0).astype(int).astype(str) + " MGA)"
                        ),
                    }
                )
            )

    # R2 — lignes facturées absentes de l'ordonnance.
    if len(avec_ordo):
        codes_prescrits = ol.groupby("ordonnance_id")["code"].apply(set).to_dict()
        lignes_ordo = lignes.merge(
            avec_ordo[["facture_id", "ordonnance_id"]], on="facture_id", how="inner"
        )
        if len(lignes_ordo):
            # Ne conserver que les factures dont l'ordonnance est connue.
            lignes_ordo = lignes_ordo[
                lignes_ordo["ordonnance_id"].isin(codes_prescrits)
            ].copy()
            lignes_ordo["non_prescrite"] = [
                code not in codes_prescrits.get(ordo_id, set())
                for ordo_id, code in zip(lignes_ordo["ordonnance_id"], lignes_ordo["code"])
            ]
            hors = lignes_ordo[lignes_ordo["non_prescrite"]].copy()
            if len(hors):
                agg = (
                    hors.groupby(["facture_id", "ordonnance_id"])
                    .agg(
                        nb_lignes=("code", "size"),
                        montant=("montant", "sum"),
                        codes=("code", lambda s: ", ".join(sorted(set(s))[:5])),
                    )
                    .reset_index()
                )
                alertes.append(
                    pd.DataFrame(
                        {
                            "facture_id": agg["facture_id"],
                            "ordonnance_id": agg["ordonnance_id"],
                            "code_fraude": "LIGNES_NON_PRESCRITES",
                            "gravite": GRAVITE_PRESCRIPTION["LIGNES_NON_PRESCRITES"],
                            "montant_en_jeu": agg["montant"],
                            "explication": (
                                agg["nb_lignes"].astype(int).astype(str)
                                + " ligne(s) facturee(s) absente(s) de l'ordonnance : "
                                + agg["codes"].astype(str)
                            ),
                        }
                    )
                )

    if not alertes:
        return pd.DataFrame(columns=COLONNES_ALERTES)
    return pd.concat(alertes, ignore_index=True)


def detecter_alertes_prescription(
    tables: dict[str, pd.DataFrame] | None = None,
    source_dir: Path | str | None = None,
) -> pd.DataFrame:
    """Calcule toutes les alertes prescription au niveau facture."""
    if tables is None:
        tables = charger_tables(source_dir)

    alertes = _alertes_facture(tables)

    # Règles ordonnance → factures rattachées.
    ordonnances = _alertes_ordonnance(tables)
    if len(ordonnances):
        factures = tables["factures"][["facture_id", "ordonnance_id", "montant_total"]].dropna(
            subset=["ordonnance_id"]
        )
        mappe = ordonnances.merge(factures, on="ordonnance_id", how="inner")
        bloc = pd.DataFrame(
            {
                "facture_id": mappe["facture_id"],
                "ordonnance_id": mappe["ordonnance_id"],
                "code_fraude": mappe["code_fraude"],
                "gravite": mappe["gravite"],
                "montant_en_jeu": mappe["montant_total"],
                "explication": mappe["explication"],
            }
        )
        alertes = pd.concat([alertes, bloc], ignore_index=True)

    if not len(alertes):
        return pd.DataFrame(columns=COLONNES_ALERTES)

    # Une seule alerte par (facture, code) : garder la première explication.
    alertes = (
        alertes.sort_values(["facture_id", "code_fraude", "gravite"], ascending=[True, True, False])
        .drop_duplicates(subset=["facture_id", "code_fraude"], keep="first")
        .reset_index(drop=True)
    )
    alertes["montant_en_jeu"] = pd.to_numeric(alertes["montant_en_jeu"], errors="coerce").fillna(0)
    return alertes[COLONNES_ALERTES]


def resumer_alertes(alertes: pd.DataFrame) -> pd.DataFrame:
    """Synthèse par code de fraude (nombre d'alertes, montant, gravité)."""
    if not len(alertes):
        return pd.DataFrame(columns=["code_fraude", "gravite", "nb_alertes", "montant_en_jeu"])
    return (
        alertes.groupby(["code_fraude", "gravite"], as_index=False)
        .agg(nb_alertes=("facture_id", "nunique"), montant_en_jeu=("montant_en_jeu", "sum"))
        .sort_values(["gravite", "nb_alertes"], ascending=[False, False])
        .reset_index(drop=True)
    )


def main() -> None:  # pragma: no cover - CLI
    from predicare.ml.config import REPORTS_DIR

    alertes = detecter_alertes_prescription()
    dossier = REPORTS_DIR / "pb09"
    dossier.mkdir(parents=True, exist_ok=True)
    alertes.to_csv(dossier / "alertes_prescription.csv", index=False)
    resume = resumer_alertes(alertes)
    resume.to_csv(dossier / "synthese_prescription.csv", index=False)
    print(f"{len(alertes)} alertes sur {alertes['facture_id'].nunique()} factures")
    print(resume.to_string(index=False))


if __name__ == "__main__":  # pragma: no cover
    main()
