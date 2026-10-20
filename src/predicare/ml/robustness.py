"""PB-12 — Robustesse : validation des factures invalides et lot de 20 cas.

Le CDC exige qu'un lot de 20 factures fourni par le jury soit traité
proprement : les factures invalides doivent être **rejetées avec un code
explicite**, sans casser le scoring.

Les 10 codes d'invalidité proviennent du référentiel métier
(``referentiel_feuilles/factures_invalides.csv``).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

from predicare.ml.config import REPORTS_DIR, SOURCE_DIR

CODES_INVALIDITE = [
    "MONTANT_NEGATIF",
    "CODE_ACTE_INCONNU",
    "DATE_FUTURE",
    "DATE_IMPOSSIBLE",
    "CHAMP_OBLIGATOIRE_MANQUANT",
    "TOTAL_INCOHERENT",
    "PRESTATAIRE_INCONNU",
    "ASSURE_INCONNU",
    "DEVISE_INVALIDE",
    "FACTURE_SANS_LIGNE",
]

DEVISE_ATTENDUE = "MGA"


def charger_referentiels(source_dir: Path | str | None = None) -> dict:
    """Charge les ensembles de codes et d'identifiants connus."""
    dossier = Path(source_dir) if source_dir else SOURCE_DIR
    actes = pd.read_csv(dossier / "referentiel_actes.csv", low_memory=False)
    meds = pd.read_csv(dossier / "referentiel_medicaments.csv", low_memory=False)
    prest = pd.read_csv(dossier / "prestataires.csv", low_memory=False)
    assures = pd.read_csv(dossier / "assures.csv", low_memory=False)
    return {
        "codes": set(actes["code_acte"].astype(str)) | set(meds["code_medicament"].astype(str)),
        "prestataires": set(prest["prestataire_id"].astype(str)),
        "assures": set(assures["assure_id"].astype(str)),
    }


def _date(value) -> pd.Timestamp | None:
    if value is None or value == "":
        return None
    resultat = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(resultat) else resultat


def valider_facture(
    facture: dict,
    referentiels: dict,
    date_reference: date | pd.Timestamp | None = None,
) -> list[str]:
    """Retourne les codes d'invalidité d'une facture brute (liste vide si valide)."""
    codes: set[str] = set()
    date_reference = pd.Timestamp(date_reference) if date_reference else pd.Timestamp.today()

    lignes = facture.get("lignes") or []

    if not facture.get("assure_id") or not facture.get("prestataire_id"):
        codes.add("CHAMP_OBLIGATOIRE_MANQUANT")

    if not lignes:
        codes.add("FACTURE_SANS_LIGNE")

    if facture.get("devise") != DEVISE_ATTENDUE:
        codes.add("DEVISE_INVALIDE")

    if str(facture.get("prestataire_id")) not in referentiels.get("prestataires", set()):
        codes.add("PRESTATAIRE_INCONNU")
    if str(facture.get("assure_id")) not in referentiels.get("assures", set()):
        codes.add("ASSURE_INCONNU")

    date_soin = _date(facture.get("date_soin"))
    if facture.get("date_soin") in (None, "") or date_soin is None:
        codes.add("DATE_IMPOSSIBLE")
    elif date_soin > date_reference:
        codes.add("DATE_FUTURE")

    montant_total = facture.get("montant_total")
    try:
        montant_total = float(montant_total)
        if montant_total < 0:
            codes.add("MONTANT_NEGATIF")
    except (TypeError, ValueError):
        codes.add("CHAMP_OBLIGATOIRE_MANQUANT")

    total_lignes = 0.0
    for ligne in lignes:
        try:
            quantite = float(ligne.get("quantite", 0))
            prix = float(ligne.get("prix_unitaire", 0))
            montant = float(ligne.get("montant", quantite * prix))
        except (TypeError, ValueError):
            codes.add("CHAMP_OBLIGATOIRE_MANQUANT")
            continue
        if quantite < 0 or prix < 0 or montant < 0:
            codes.add("MONTANT_NEGATIF")
        if str(ligne.get("code")) not in referentiels.get("codes", set()):
            codes.add("CODE_ACTE_INCONNU")
        total_lignes += montant

    if lignes and montant_total is not None and abs(total_lignes - montant_total) > 0.5:
        codes.add("TOTAL_INCOHERENT")

    return sorted(codes)


def _facture_brute(ligne: pd.Series, referentiels: dict) -> dict:
    """Convertit une ligne de dataset en facture brute minimale et valide."""
    montant = float(ligne.get("montant_total", 0))
    code_valide = sorted(referentiels.get("codes", {"CONS-GEN"}))[0]
    return {
        "facture_id": ligne.get("facture_id"),
        "numero_facture": ligne.get("numero_facture", ""),
        "prestataire_id": ligne.get("meta_prestataire_id", ""),
        "assure_id": ligne.get("meta_assure_id", ""),
        "date_soin": str(ligne.get("meta_date_reception", "")),
        "date_facture": str(ligne.get("meta_date_reception", "")),
        "date_reception": str(ligne.get("meta_date_reception", "")),
        "devise": "MGA",
        "montant_total": montant,
        "lignes": [
            {"code": code_valide, "quantite": 1, "prix_unitaire": montant, "montant": montant}
        ],
    }


def construire_lot_test(
    dataset: pd.DataFrame | None = None,
    n_valides: int = 10,
    source_dir: Path | str | None = None,
) -> dict:
    """Construit un lot de 20 factures : 10 valides + 10 invalides (1 par code)."""
    from predicare.ml.scoring import charger_modele
    from predicare.ml.targets import charger_dataset_cm

    dataset = dataset if dataset is not None else charger_dataset_cm()
    test = dataset[dataset["split"] == "test"].copy()

    modele = charger_modele()
    scores = modele.scorer(test)
    test = test.merge(scores, on="facture_id")

    # 5 factures normales (probabilité faible) + 5 factures à risque.
    normales = test.sort_values("probabilite").head(n_valides // 2).copy()
    risque = test.sort_values("probabilite", ascending=False).head(n_valides - len(normales)).copy()
    normales["categorie_lot"] = "normal"
    risque["categorie_lot"] = "suspect"
    echantillon = pd.concat([normales, risque]).drop_duplicates(subset=["facture_id"])

    valides = []
    for _, ligne in echantillon.iterrows():
        valides.append(
            {
                "facture_id": ligne["facture_id"],
                "categorie": ligne["categorie_lot"],
                "attendu": {
                    "valide": True,
                    "probabilite": float(ligne["probabilite"]),
                    "score_risque": float(ligne["score_risque"]),
                    "alerte": bool(ligne["score_risque"] >= modele.seuil_produit),
                },
                "features": {k: (None if pd.isna(v) else v) for k, v in ligne.items()},
            }
        )

    # Base pour les cas invalides : une facture normale, champs bruts reconstruits.
    referentiels = charger_referentiels(source_dir)
    base = _facture_brute(normales.iloc[0], referentiels)

    def copie(**modifs) -> dict:
        facture = json.loads(json.dumps(base))
        facture.update(modifs)
        return facture

    invalides = [
        {
            "facture_id": "INV-MONTANT-NEGATIF",
            "facture": copie(
                montant_total=1000,
                lignes=[
                    {
                        "code": sorted(referentiels["codes"])[0],
                        "quantite": -1,
                        "prix_unitaire": 1000,
                        "montant": -1000,
                    }
                ],
            ),
            "attendu": ["MONTANT_NEGATIF"],
        },
        {
            "facture_id": "INV-CODE-INCONNU",
            "facture": copie(
                lignes=[
                    {
                        "code": "ACT-INCONNU-999",
                        "quantite": 1,
                        "prix_unitaire": 1000,
                        "montant": 1000,
                    }
                ],
                montant_total=1000,
            ),
            "attendu": ["CODE_ACTE_INCONNU"],
        },
        {
            "facture_id": "INV-DATE-FUTURE",
            "facture": copie(date_soin="2030-01-01"),
            "attendu": ["DATE_FUTURE"],
        },
        {
            "facture_id": "INV-DATE-IMPOSSIBLE",
            "facture": copie(date_soin="2026-02-30"),
            "attendu": ["DATE_IMPOSSIBLE"],
        },
        {
            "facture_id": "INV-CHAMP-MANQUANT",
            "facture": copie(assure_id=""),
            "attendu": ["CHAMP_OBLIGATOIRE_MANQUANT"],
        },
        {
            "facture_id": "INV-TOTAL-INCOHERENT",
            "facture": copie(
                montant_total=9999,
                lignes=[
                    {
                        "code": sorted(referentiels["codes"])[0],
                        "quantite": 1,
                        "prix_unitaire": 1000,
                        "montant": 1000,
                    }
                ],
            ),
            "attendu": ["TOTAL_INCOHERENT"],
        },
        {
            "facture_id": "INV-PRESTATAIRE-INCONNU",
            "facture": copie(prestataire_id="PR-99999"),
            "attendu": ["PRESTATAIRE_INCONNU"],
        },
        {
            "facture_id": "INV-ASSURE-INCONNU",
            "facture": copie(assure_id="ASS-INCONNU"),
            "attendu": ["ASSURE_INCONNU"],
        },
        {
            "facture_id": "INV-DEVISE",
            "facture": copie(devise="EUR"),
            "attendu": ["DEVISE_INVALIDE"],
        },
        {
            "facture_id": "INV-SANS-LIGNE",
            "facture": copie(lignes=[], montant_total=0),
            "attendu": ["FACTURE_SANS_LIGNE"],
        },
    ]

    # Catégorie de chaque cas invalide (le cas « champ manquant » est un cas incomplet).
    for cas in invalides:
        cas["categorie"] = "incomplet" if cas["facture_id"] == "INV-CHAMP-MANQUANT" else "invalide"

    return {
        "date_reference": "2026-10-19",
        "categorie_effectifs": {
            "normal": sum(1 for v in valides if v["categorie"] == "normal"),
            "suspect": sum(1 for v in valides if v["categorie"] == "suspect"),
            "invalide": sum(1 for c in invalides if c["categorie"] == "invalide"),
            "incomplet": sum(1 for c in invalides if c["categorie"] == "incomplet"),
        },
        "valides": valides,
        "invalides": invalides,
    }


def sauvegarder_lot_test(lot: dict, chemin: Path | str | None = None) -> Path:
    """Écrit le lot au format JSON (fixture pytest)."""
    chemin = (
        Path(chemin)
        if chemin
        else Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "factures_test_set.json"
    )
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(lot, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return chemin


def main() -> None:  # pragma: no cover - CLI
    lot = construire_lot_test()
    chemin = sauvegarder_lot_test(lot)
    dossier = REPORTS_DIR / "pb12"
    dossier.mkdir(parents=True, exist_ok=True)
    reference = charger_referentiels()
    resultats = []
    for cas in lot["invalides"]:
        codes = valider_facture(cas["facture"], reference, lot["date_reference"])
        resultats.append(
            {
                "facture_id": cas["facture_id"],
                "attendu": cas["attendu"],
                "obtenu": codes,
                "ok": all(c in codes for c in cas["attendu"]),
            }
        )
    pd.DataFrame(resultats).to_csv(dossier / "validation_lot_test.csv", index=False)
    print(f"Lot de {len(lot['valides'])} valides + {len(lot['invalides'])} invalides → {chemin}")
    print(pd.DataFrame(resultats).to_string(index=False))


if __name__ == "__main__":  # pragma: no cover
    main()
