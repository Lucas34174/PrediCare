"""Reconstruction de labels faibles de fraude à partir des 12 CSV métiers.

Contexte
--------
Les fichiers ``labels_fraude.csv`` et ``labels_prestataires.csv`` d'origine ne
sont plus disponibles. Ce module reconstruit une **cible faible** (weak
supervision) à partir :

* des 12 CSV du jeu de données PrediCare ;
* du référentiel métier « Fraudes factures » (14 types de fraude) ;
* des précisions mesurées dans l'EDA d'origine (``01_eda_exploration_donnees``)
  lorsque les vrais labels existaient encore.

Il ne s'agit **pas** de la vérité terrain. Les labels produits doivent être
documentés comme reconstruits et utilisés avec des précautions méthodologiques
(circularité règles/features, calibration à la prévalence connue).

Sorties
-------
* ``labels_fraude.csv`` : schéma compatible avec ``predicare.ml.dataset``
  (``facture_id``, ``est_fraude``, ``type_fraude``, ``detail_fraude``,
  ``est_valide``, ``motif_invalidite``) enrichi de colonnes d'audit.
* ``weak_labels_manifest.json`` : règles, volumes, précisions, calibration,
  limites.
* ``signaux_faibles.csv`` : matrice des 19 signaux par facture (audit).

Usage
-----
::

    PYTHONPATH=src python -m predicare.ml.weak_labels \
        --raw-dir ../CohorteAI_datagen/dataset \
        --out-dir data/raw/labels \
        --target-positifs 7347
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Prévalence réelle connue depuis l'EDA d'origine : 7 347 fraudes / 84 593.
TARGET_POSITIFS_DEFAUT = 7347
PREVALENCE_REELLE = 7347 / 84593

TABLES = (
    "factures",
    "lignes_facture",
    "ordonnances",
    "ordonnance_lignes",
    "assures",
    "contrats",
    "prestataires",
    "garanties",
    "grille_tarifaire",
    "referentiel_actes",
    "referentiel_medicaments",
)

DATES = {
    "factures": ["date_soin", "date_facture", "date_reception", "date_traitement"],
    "ordonnances": ["date_prescription"],
    "assures": ["date_adhesion", "date_radiation"],
    "contrats": ["date_effet_police", "date_effet", "date_fin"],
    "prestataires": ["date_conventionnement", "date_fin_convention"],
}

#: Métadonnées des signaux.
#: (type de fraude visé, précision mesurée dans l'EDA, niveau de confiance)
SIGNAL_META: dict[str, tuple[str, float, str]] = {
    # --- haute précision (>= 0,80) ---
    "surf_grille": ("SURFACTURATION", 0.842, "haute"),
    "qte": ("QUANTITE_EXCESSIVE", 1.000, "haute"),
    "non_prescrites": ("LIGNES_NON_PRESCRITES", 1.000, "haute"),
    "substitution": ("SUBSTITUTION_PRODUIT", 1.000, "haute"),
    "expiree": ("ORDONNANCE_EXPIREE", 1.000, "haute"),
    "ferme": ("SOINS_JOUR_FERME", 0.985, "haute"),
    "doublon_copie": ("DOUBLON", 0.847, "haute"),
    "fictif_autre": ("ACTE_FICTIF", 1.000, "haute"),
    "profil": ("INCOHERENCE_PROFIL", 1.000, "haute"),
    "radie_fin": ("PRESTATAIRE_RADIE", 1.000, "haute"),
    "hors_couv": ("HORS_COUVERTURE", 1.000, "haute"),
    # --- précision moyenne (0,40 - 0,80) ---
    "surf_acte": ("SURFACTURATION", 0.423, "moyenne"),
    "doublon_tous": ("DOUBLON", 0.456, "moyenne"),
    "surconso": ("SURCONSOMMATION", 0.512, "moyenne"),
    # --- précision faible (< 0,40) : candidats, pas positifs seuls ---
    "surf_med": ("SURFACTURATION", 0.110, "faible"),
    "fraction": ("FRACTIONNEMENT", 0.237, "faible"),
    "fictif_sans_ord": ("ACTE_FICTIF", 0.317, "faible"),
    "radie_statut": ("PRESTATAIRE_RADIE", 0.134, "faible"),
    "upcoding": ("UPCODING", 0.200, "faible"),
}

#: Ordre de spécificité pour départager deux signaux de même précision.
PRIORITY = [
    "SUBSTITUTION_PRODUIT",
    "ACTE_FICTIF",
    "SURCONSOMMATION",
    "FRACTIONNEMENT",
    "DOUBLON",
    "PRESTATAIRE_RADIE",
    "HORS_COUVERTURE",
    "INCOHERENCE_PROFIL",
    "SOINS_JOUR_FERME",
    "ORDONNANCE_EXPIREE",
    "QUANTITE_EXCESSIVE",
    "LIGNES_NON_PRESCRITES",
    "UPCODING",
    "SURFACTURATION",
]
PRIO_PAR_TYPE = {t: i for i, t in enumerate(PRIORITY)}

#: Motifs de rejet considérés comme 100 % fraudes dans l'EDA d'origine.
ANCHORS: dict[str, str] = {
    "CONTROLE_MEDICAL": "CONTROLE_MEDICAL",
    "ORDONNANCE_PERIMEE": "ORDONNANCE_EXPIREE",
    "HORS_PERIODE_COUVERTURE": "HORS_COUVERTURE",
    "PRODUIT_NON_REMBOURSABLE": "HORS_COUVERTURE",
}

#: Distribution réelle connue (EDA) pour comparaison / documentation.
DISTRIBUTION_REELLE = {
    "SURFACTURATION": 1272,
    "DOUBLON": 909,
    "UPCODING": 742,
    "LIGNES_NON_PRESCRITES": 733,
    "QUANTITE_EXCESSIVE": 568,
    "ORDONNANCE_EXPIREE": 502,
    "ACTE_FICTIF": 496,
    "SURCONSOMMATION": 469,
    "INCOHERENCE_PROFIL": 379,
    "SUBSTITUTION_PRODUIT": 368,
    "FRACTIONNEMENT": 340,
    "SOINS_JOUR_FERME": 227,
    "HORS_COUVERTURE": 195,
    "PRESTATAIRE_RADIE": 147,
}


# ---------------------------------------------------------------------------
# Chargement
# ---------------------------------------------------------------------------
def charger_tables(raw_dir: str | Path) -> dict[str, pd.DataFrame]:
    """Charge les 11 tables utiles et convertit les dates."""
    raw = Path(raw_dir)
    tables: dict[str, pd.DataFrame] = {}
    for name in TABLES:
        path = raw / f"{name}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Table manquante : {path}")
        tables[name] = pd.read_csv(path, low_memory=False)
        logger.info("Chargé %s : %s lignes", name, len(tables[name]))

    for table, cols in DATES.items():
        for col in cols:
            if col in tables[table].columns:
                tables[table][col] = pd.to_datetime(
                    tables[table][col], errors="coerce"
                )
    return tables


# ---------------------------------------------------------------------------
# Outils signaux
# ---------------------------------------------------------------------------
def _by_fact(mask: Any, ids: pd.Series) -> pd.Series:
    """Agrège un masque ligne -> facture (OR logique)."""
    return (
        pd.Series(np.asarray(mask, dtype=bool), index=ids.to_numpy())
        .groupby(level=0)
        .any()
    )


def _normaliser_signal(serie: pd.Series, factures: pd.DataFrame, nom: str) -> pd.Series:
    serie = serie[~serie.index.duplicated()]
    serie = serie.reindex(factures["facture_id"]).fillna(False).astype(bool)
    serie.name = nom
    return serie


def _num(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(np.nan, index=df.index)
    return pd.to_numeric(df[col], errors="coerce")


# ---------------------------------------------------------------------------
# Signaux (règles du référentiel métier)
# ---------------------------------------------------------------------------
def _signal_surf_acte(t: dict[str, pd.DataFrame], lf: pd.DataFrame) -> pd.Series:
    act = t["referentiel_actes"][["code_acte", "tarif_max"]].drop_duplicates("code_acte")
    lig = lf[lf["type_ligne"] == "ACTE"].merge(
        act, left_on="code", right_on="code_acte", how="left"
    )
    return _by_fact(_num(lig, "prix_unitaire") > _num(lig, "tarif_max"), lig["facture_id"])


def _signal_surf_med(t: dict[str, pd.DataFrame], lf: pd.DataFrame) -> pd.Series:
    med = t["referentiel_medicaments"][["code_medicament", "prix_reference"]].drop_duplicates(
        "code_medicament"
    )
    lig = lf[lf["type_ligne"] == "MEDICAMENT"].merge(
        med, left_on="code", right_on="code_medicament", how="left"
    )
    return _by_fact(
        _num(lig, "prix_unitaire") > _num(lig, "prix_reference"), lig["facture_id"]
    )


def _signal_surf_grille(t: dict[str, pd.DataFrame], lf: pd.DataFrame, facteur: float = 1.0) -> pd.Series:
    gr = t["grille_tarifaire"][
        ["prestataire_id", "code", "tarif_pratique"]
    ].drop_duplicates(["prestataire_id", "code"])
    lig = lf.merge(gr, on=["prestataire_id", "code"], how="left")
    return _by_fact(
        _num(lig, "prix_unitaire") > _num(lig, "tarif_pratique") * facteur,
        lig["facture_id"],
    )


def _signal_qte(t: dict[str, pd.DataFrame], lf: pd.DataFrame) -> pd.Series:
    ol = t["ordonnance_lignes"]
    pres = (
        ol.groupby(["ordonnance_id", "code"], as_index=False)["quantite"]
        .sum()
        .rename(columns={"code": "_code_ordo", "quantite": "_qte_prescrite"})
    )
    lig = lf[lf["ordonnance_id"].notna()].merge(
        pres,
        left_on=["ordonnance_id", "code"],
        right_on=["ordonnance_id", "_code_ordo"],
        how="inner",
    )
    return _by_fact(
        _num(lig, "quantite") > _num(lig, "_qte_prescrite"), lig["facture_id"]
    )


def _lignes_hors_ordonnance(
    t: dict[str, pd.DataFrame], lf: pd.DataFrame, seulement_medicaments: bool = False
) -> tuple[pd.DataFrame, pd.Series]:
    ol = t["ordonnance_lignes"]
    cles = (
        ol[["ordonnance_id", "code"]]
        .drop_duplicates()
        .rename(columns={"code": "_code_ordo"})
        .assign(_present=1)
    )
    lig = lf[lf["ordonnance_id"].notna()]
    if seulement_medicaments:
        lig = lig[lig["type_ligne"] == "MEDICAMENT"]
    lig = lig.merge(
        cles,
        left_on=["ordonnance_id", "code"],
        right_on=["ordonnance_id", "_code_ordo"],
        how="left",
    )
    return lig, lig["_present"].isna()


def _signal_non_prescrites(t: dict[str, pd.DataFrame], lf: pd.DataFrame) -> pd.Series:
    lig, absent = _lignes_hors_ordonnance(t, lf)
    return _by_fact(absent, lig["facture_id"])


def _signal_substitution(t: dict[str, pd.DataFrame], lf: pd.DataFrame) -> pd.Series:
    med = t["referentiel_medicaments"]
    seuil = _num(med, "prix_reference").quantile(0.75)
    lig, absent = _lignes_hors_ordonnance(t, lf, seulement_medicaments=True)
    return _by_fact(absent & (_num(lig, "prix_unitaire") > seuil), lig["facture_id"])


def _signal_expiree(t: dict[str, pd.DataFrame]) -> pd.Series:
    fac, ordo = t["factures"], t["ordonnances"]
    d = (
        fac[["facture_id", "ordonnance_id", "date_soin"]]
        .dropna(subset=["ordonnance_id"])
        .merge(
            ordo[
                [
                    "ordonnance_id",
                    "date_prescription",
                    "validite_jours",
                    "type_ordonnance",
                ]
            ],
            on="ordonnance_id",
            how="left",
        )
    )
    delai = (d["date_soin"] - d["date_prescription"]).dt.days
    limite = _num(d, "validite_jours")
    optique = d["type_ordonnance"].astype(str).str.lower().str.contains("optiq")
    defaut = pd.Series(np.where(optique.to_numpy(), 30, 10), index=limite.index)
    limite = limite.fillna(defaut)
    return _by_fact(delai > limite, d["facture_id"])


def _parser_jours(valeur: Any) -> set[int]:
    texte = str(valeur)
    plage = re.fullmatch(r"\s*([1-7])\s*-\s*([1-7])\s*", texte)
    if plage:
        return set(range(int(plage.group(1)), int(plage.group(2)) + 1))
    return {int(x) for x in re.findall(r"[1-7]", texte)}


def _signal_ferme(t: dict[str, pd.DataFrame]) -> pd.Series:
    pre, fac = t["prestataires"], t["factures"]
    ouverture = (
        pre.drop_duplicates("prestataire_id")
        .set_index("prestataire_id")["jours_ouverture"]
        .map(_parser_jours)
    )
    d = fac[["facture_id", "prestataire_id", "date_soin"]].copy()
    jours = d["prestataire_id"].map(ouverture)
    weekday = d["date_soin"].dt.dayofweek + 1
    drapeau = [
        isinstance(js, set) and len(js) > 0 and pd.notna(j) and int(j) not in js
        for js, j in zip(jours, weekday)
    ]
    return pd.Series(drapeau, index=d["facture_id"].to_numpy())


def _signal_doublon(t: dict[str, pd.DataFrame], keep: str | bool) -> pd.Series:
    fac = t["factures"]
    dup = fac.duplicated(
        subset=["assure_id", "prestataire_id", "montant_total", "date_soin"],
        keep=keep,
    )
    return pd.Series(dup.to_numpy(), index=fac["facture_id"].to_numpy())


def _signal_fraction(t: dict[str, pd.DataFrame]) -> pd.Series:
    fac = t["factures"]
    taille = fac.groupby(["assure_id", "prestataire_id", "date_soin"])[
        "facture_id"
    ].transform("size")
    return pd.Series((taille >= 2).to_numpy(), index=fac["facture_id"].to_numpy())


def _signal_surconso(t: dict[str, pd.DataFrame]) -> pd.Series:
    fac = t["factures"]
    d = fac.dropna(subset=["ordonnance_id"])
    nb = d.groupby("ordonnance_id")["prestataire_id"].transform("nunique")
    return pd.Series((nb > 1).to_numpy(), index=d["facture_id"].to_numpy())


def _signal_fictif_sans_ord(t: dict[str, pd.DataFrame], lf: pd.DataFrame) -> pd.Series:
    fac, act = t["factures"], t["referentiel_actes"]
    sans_ordo = fac["ordonnance_id"].isna()
    requises = act.loc[
        act["ordonnance_requise"]
        .astype(str)
        .str.lower()
        .isin(["1", "1.0", "true", "oui", "o", "vrai", "yes"]),
        "code_acte",
    ]
    ids = lf.loc[
        (lf["type_ligne"] == "ACTE") & lf["code"].isin(requises), "facture_id"
    ].unique()
    return pd.Series(
        (sans_ordo & fac["facture_id"].isin(ids)).to_numpy(),
        index=fac["facture_id"].to_numpy(),
    )


def _signal_fictif_autre(t: dict[str, pd.DataFrame]) -> pd.Series:
    fac, ordo = t["factures"], t["ordonnances"]
    d = (
        fac[["facture_id", "assure_id", "ordonnance_id"]]
        .dropna(subset=["ordonnance_id"])
        .merge(
            ordo[["ordonnance_id", "assure_id"]].rename(
                columns={"assure_id": "_assure_ordo"}
            ),
            on="ordonnance_id",
            how="left",
        )
    )
    drapeau = d["_assure_ordo"].notna() & (d["_assure_ordo"] != d["assure_id"])
    return pd.Series(drapeau.to_numpy(), index=d["facture_id"].to_numpy())


def _signal_profil(t: dict[str, pd.DataFrame], lf: pd.DataFrame) -> pd.Series:
    act, ass = t["referentiel_actes"], t["assures"]
    ref = act[["code_acte", "sexe_requis", "age_min", "age_max"]].drop_duplicates(
        "code_acte"
    )
    assur = ass[["assure_id", "sexe", "annee_naissance"]].rename(
        columns={"sexe": "_sexe", "annee_naissance": "_annee_naissance"}
    )
    lig = (
        lf[lf["type_ligne"] == "ACTE"]
        .merge(ref, left_on="code", right_on="code_acte", how="left")
        .merge(assur, on="assure_id", how="left")
    )
    age = lig["date_soin"].dt.year - _num(lig, "_annee_naissance")
    requis = lig["sexe_requis"].astype(str).str.strip().str.upper().str[:1]
    sexe = lig["_sexe"].astype(str).str.strip().str.upper().str[:1]
    drapeau = requis.isin(["M", "F"]) & sexe.isin(["M", "F"]) & (requis != sexe)
    drapeau |= (age + 1) < _num(lig, "age_min")
    drapeau |= (age - 1) > _num(lig, "age_max")
    return _by_fact(drapeau, lig["facture_id"])


def _signal_radie(t: dict[str, pd.DataFrame], mode: str) -> pd.Series:
    pre, fac = t["prestataires"], t["factures"]
    d = fac[["facture_id", "prestataire_id", "date_soin"]].merge(
        pre[["prestataire_id", "date_fin_convention", "statut"]],
        on="prestataire_id",
        how="left",
    )
    if mode == "fin":
        drapeau = d["date_fin_convention"].notna() & (
            d["date_soin"] > d["date_fin_convention"]
        )
    else:
        drapeau = d["statut"].astype(str).str.upper().eq("RADIE")
    return pd.Series(drapeau.to_numpy(), index=d["facture_id"].to_numpy())


def _signal_hors_couv(t: dict[str, pd.DataFrame]) -> pd.Series:
    fac, ass, con = t["factures"], t["assures"], t["contrats"]
    d = (
        fac[["facture_id", "assure_id", "contrat_id", "date_soin"]]
        .merge(
            ass[["assure_id", "date_adhesion", "date_radiation"]],
            on="assure_id",
            how="left",
        )
        .merge(con[["contrat_id", "date_effet", "date_fin"]], on="contrat_id", how="left")
    )
    soin = d["date_soin"]
    drapeau = (
        (soin < d["date_adhesion"])
        | (d["date_radiation"].notna() & (soin > d["date_radiation"]))
        | (soin < d["date_effet"])
        | (d["date_fin"].notna() & (soin > d["date_fin"]))
    )
    return pd.Series(drapeau.to_numpy(), index=d["facture_id"].to_numpy())


def _signal_upcoding(t: dict[str, pd.DataFrame], lf: pd.DataFrame) -> pd.Series:
    act, pre = t["referentiel_actes"], t["prestataires"]
    ref = act.loc[act["categorie"] == "CONSULTATION", ["code_acte", "specialite"]].rename(
        columns={"code_acte": "code", "specialite": "_spec_acte"}
    )
    lig = lf[lf["type_ligne"] == "ACTE"].merge(ref, on="code", how="inner")
    lig = lig.merge(
        pre[["prestataire_id", "type_prestataire", "specialite"]].rename(
            columns={"specialite": "_spec_prest"}
        ),
        on="prestataire_id",
        how="left",
    )
    est_specialiste = lig["_spec_acte"].notna() & ~lig["_spec_acte"].isin(
        ["GENERALISTE", "URGENCE"]
    )
    incoherent = est_specialiste & (
        (lig["type_prestataire"] == "CABINET_GENERALISTE")
        | (
            (lig["type_prestataire"] == "CABINET_SPECIALISTE")
            & (lig["_spec_prest"] != lig["_spec_acte"])
        )
    )
    return _by_fact(incoherent, lig["facture_id"])


def calculer_signaux(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Calcule les 19 signaux par facture."""
    fac = tables["factures"].copy()
    fac["facture_id"] = fac["facture_id"].astype(str)
    lig = tables["lignes_facture"].copy()
    lig["facture_id"] = lig["facture_id"].astype(str)

    lf = lig.merge(
        fac[["facture_id", "assure_id", "prestataire_id", "ordonnance_id", "date_soin"]],
        on="facture_id",
        how="left",
    )

    fonctions = {
        "surf_acte": lambda: _signal_surf_acte(tables, lf),
        "surf_med": lambda: _signal_surf_med(tables, lf),
        "surf_grille": lambda: _signal_surf_grille(tables, lf, 1.0),
        "qte": lambda: _signal_qte(tables, lf),
        "non_prescrites": lambda: _signal_non_prescrites(tables, lf),
        "substitution": lambda: _signal_substitution(tables, lf),
        "expiree": lambda: _signal_expiree(tables),
        "ferme": lambda: _signal_ferme(tables),
        "doublon_copie": lambda: _signal_doublon(tables, "first"),
        "doublon_tous": lambda: _signal_doublon(tables, False),
        "fraction": lambda: _signal_fraction(tables),
        "surconso": lambda: _signal_surconso(tables),
        "fictif_sans_ord": lambda: _signal_fictif_sans_ord(tables, lf),
        "fictif_autre": lambda: _signal_fictif_autre(tables),
        "profil": lambda: _signal_profil(tables, lf),
        "radie_fin": lambda: _signal_radie(tables, "fin"),
        "radie_statut": lambda: _signal_radie(tables, "statut"),
        "hors_couv": lambda: _signal_hors_couv(tables),
        "upcoding": lambda: _signal_upcoding(tables, lf),
    }

    signaux = {}
    for nom, fn in fonctions.items():
        serie = fn()
        signaux[nom] = _normaliser_signal(serie, fac, nom)
        logger.info("Signal %-20s : %6d factures", nom, int(signaux[nom].sum()))
    return pd.DataFrame(signaux, index=fac["facture_id"])


# ---------------------------------------------------------------------------
# Construction du label
# ---------------------------------------------------------------------------
def _type_principal(ligne: pd.Series) -> str | None:
    candidats = []
    for nom, (type_fraude, precision, _) in SIGNAL_META.items():
        if bool(ligne.get(nom, False)):
            candidats.append((precision, -PRIO_PAR_TYPE.get(type_fraude, 99), type_fraude))
    if not candidats:
        return None
    candidats.sort(key=lambda x: (-x[0], -x[1]))
    return candidats[0][2]


def _types_multi(ligne: pd.Series) -> str:
    types = []
    for nom, (type_fraude, _, _) in SIGNAL_META.items():
        if bool(ligne.get(nom, False)) and type_fraude not in types:
            types.append(type_fraude)
    return ";".join(sorted(types, key=lambda t: PRIO_PAR_TYPE.get(t, 99)))


def construire_labels(
    signaux: pd.DataFrame,
    factures: pd.DataFrame,
    target_positifs: int = TARGET_POSITIFS_DEFAUT,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Agrège les signaux en labels faibles hiérarchisés.

    * ``haute`` : au moins un signal de précision >= 0,80 ou une ancre 100 %.
    * ``moyenne`` : signal moyen seul, retenu par calibration de prévalence.
    * ``faible`` : signaux faibles seuls -> candidats, non positifs.
    """
    sig = signaux.copy()
    hauts = [n for n, (_, _, t) in SIGNAL_META.items() if t == "haute"]
    moyens = [n for n, (_, _, t) in SIGNAL_META.items() if t == "moyenne"]
    faibles = [n for n, (_, _, t) in SIGNAL_META.items() if t == "faible"]

    sig["n_haute"] = sig[hauts].sum(axis=1)
    sig["n_moyenne"] = sig[moyens].sum(axis=1)
    sig["n_faible"] = sig[faibles].sum(axis=1)

    fac = factures.set_index("facture_id")
    motif = fac["motif_rejet"].reindex(sig.index)
    ancres = motif.isin(ANCHORS)
    type_ancre = motif.map(ANCHORS).reindex(sig.index)

    haute = sig[hauts].any(axis=1) | ancres
    moyenne = (~haute) & sig[moyens].any(axis=1)
    faible = (~haute) & (~moyenne) & sig[faibles].any(axis=1)

    # Précision attendue = max des précisions des signaux déclenchés.
    ordre = list(SIGNAL_META)
    precisions = np.array([SIGNAL_META[n][1] for n in ordre])
    matrice = sig[ordre].to_numpy(dtype=float) * precisions
    sig["precision_attendue"] = matrice.max(axis=1)

    # Calibration de prévalence : on complète la base haute confiance avec les
    # meilleurs candidats moyens pour atteindre la prévalence réelle connue.
    base = haute.copy()
    pool = moyenne.copy()
    manquants = max(0, int(target_positifs) - int(base.sum()))
    retenus = pd.Series(False, index=sig.index)
    if manquants > 0 and pool.any():
        classement = (
            sig.loc[pool]
            .assign(_n_moy=sig.loc[pool, "n_moyenne"], _n_faible=sig.loc[pool, "n_faible"])
            .sort_values(
                ["precision_attendue", "_n_moy", "_n_faible"],
                ascending=[False, False, False],
            )
        )
        retenus.loc[classement.head(manquants).index] = True

    positif = base | retenus
    sig["est_fraude"] = positif.astype(int)
    sig["candidat"] = (haute | moyenne | faible).astype(int)
    sig["tier"] = np.select(
        [
            base,
            retenus,
            moyenne & ~retenus,
            faible,
        ],
        ["haute", "moyenne_retenue", "candidate_moyenne", "candidate_faible"],
        default="aucune",
    )
    sig["confiance"] = np.select(
        [base, retenus, faible | (moyenne & ~retenus)],
        ["haute", "moyenne", "faible"],
        default="aucune",
    )

    sig["type_fraude"] = sig.apply(_type_principal, axis=1)
    sans_type = ancres & sig["type_fraude"].isna()
    sig.loc[sans_type, "type_fraude"] = type_ancre[sans_type]
    sig["type_fraude"] = sig["type_fraude"].fillna("AUCUN")
    sig["types_fraude"] = sig.apply(_types_multi, axis=1)
    sig["detail_fraude"] = sig.apply(
        lambda r: ";".join([n for n in SIGNAL_META if bool(r.get(n, False))]), axis=1
    )
    sig["est_valide"] = 1
    sig["motif_invalidite"] = pd.NA
    sig["source"] = "weak_labels_v1"

    manifest: dict[str, Any] = {
        "version": "weak_labels_v1",
        "avertissement": (
            "Cible reconstruite par règles, pas une vérité terrain. "
            "Ne pas présenter comme des fraudes confirmées."
        ),
        "source": "12 CSV métiers + référentiel métier (14 types de fraude facture)",
        "prevalence_reelle_connue": PREVALENCE_REELLE,
        "target_positifs": int(target_positifs),
        "nb_factures": int(len(sig)),
        "nb_positifs": int(sig["est_fraude"].sum()),
        "prevalence_faible": float(sig["est_fraude"].mean()),
        "nb_candidats": int(sig["candidat"].sum()),
        "nb_ancres": int(ancres.sum()),
        "nb_haute": int(base.sum()),
        "nb_moyenne_retenue": int(retenus.sum()),
        "nb_moyenne_non_retenue": int((moyenne & ~retenus).sum()),
        "nb_faible": int(faible.sum()),
        "signaux": {
            nom: {
                "type_fraude": meta[0],
                "precision_eda": meta[1],
                "niveau": meta[2],
                "nb_factures": int(sig[nom].sum()),
            }
            for nom, meta in SIGNAL_META.items()
        },
        "ancres": ANCHORS,
        "distribution_reelle_eda": DISTRIBUTION_REELLE,
        "distribution_faible_type_principal": {
            k: int(v)
            for k, v in sig.loc[sig["est_fraude"] == 1, "type_fraude"]
            .value_counts()
            .items()
        },
        "limites": [
            "Les règles sont déterministes mais imparfaites (précision 0,11 à 1,00).",
            "La calibration à 7 347 positifs utilise la prévalence réelle de l'EDA.",
            "Le type principal est indicatif : plusieurs types peuvent co-occurrer.",
            "Les features du modèle ne doivent pas réutiliser les mêmes règles, "
            "sous peine de circularité.",
            "UPCODING, FRACTIONNEMENT et ACTE_FICTIF sont sous-représentés "
            "faute de signaux fiables.",
        ],
    }
    return sig, manifest


# ---------------------------------------------------------------------------
# Écriture
# ---------------------------------------------------------------------------
def ecrire_labels(
    labels: pd.DataFrame,
    factures: pd.DataFrame,
    out_dir: str | Path,
    manifest: dict[str, Any],
    signaux: pd.DataFrame | None = None,
) -> dict[str, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    resultat = labels.reset_index().rename(columns={"index": "facture_id"})
    colonnes = [
        "facture_id",
        "est_fraude",
        "type_fraude",
        "detail_fraude",
        "est_valide",
        "motif_invalidite",
        "confiance",
        "candidat",
        "types_fraude",
        "precision_attendue",
        "tier",
        "n_haute",
        "n_moyenne",
        "n_faible",
        "source",
    ]
    resultat = resultat[colonnes]
    chemin_labels = out / "labels_fraude.csv"
    resultat.to_csv(chemin_labels, index=False, encoding="utf-8")

    chemin_manifest = out / "weak_labels_manifest.json"
    chemin_manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    chemins = {"labels": chemin_labels, "manifest": chemin_manifest}
    if signaux is not None:
        chemin_signaux = out / "signaux_faibles.csv"
        signaux.reset_index().rename(columns={"index": "facture_id"}).to_csv(
            chemin_signaux, index=False, encoding="utf-8"
        )
        chemins["signaux"] = chemin_signaux
    return chemins


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Reconstruit des labels faibles de fraude à partir des 12 CSV."
    )
    parser.add_argument(
        "--raw-dir", default="../CohorteAI_datagen/dataset", help="Dossier des 12 CSV"
    )
    parser.add_argument(
        "--out-dir", default="data/raw/labels", help="Dossier de sortie des labels"
    )
    parser.add_argument(
        "--target-positifs",
        type=int,
        default=TARGET_POSITIFS_DEFAUT,
        help="Nombre de positifs visé (prévalence réelle connue : 7347)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s"
    )

    tables = charger_tables(args.raw_dir)
    signaux = calculer_signaux(tables)
    labels, manifest = construire_labels(
        signaux, tables["factures"], target_positifs=args.target_positifs
    )
    chemins = ecrire_labels(
        labels, tables["factures"], args.out_dir, manifest, signaux=signaux
    )

    logger.info("Labels faibles : %s", chemins["labels"])
    logger.info("Manifest : %s", chemins["manifest"])
    logger.info("Signaux : %s", chemins.get("signaux"))
    logger.info(
        "Positifs : %d (%.2f%%) | candidats : %d | haute : %d | moyenne retenue : %d",
        manifest["nb_positifs"],
        100 * manifest["prevalence_faible"],
        manifest["nb_candidats"],
        manifest["nb_haute"],
        manifest["nb_moyenne_retenue"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
