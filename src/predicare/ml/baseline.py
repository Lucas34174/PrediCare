"""Baseline ML de détection de fraude – PrediCare TPA (PB-06).

Fonctions exposées :
  - load_dataset()     : charge features, labels et métadonnées de split
  - split_no_leakage() : split sans fuite par assuré (groupes) et temps
  - make_pipeline()    : pipeline sklearn
  - evaluate()         : métriques Recall / PR-AUC
  - train_baseline()   : orchestrateur complet
"""

from __future__ import annotations

import logging
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    recall_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

# Constantes
FEATURES_PATH = "data/processed/features.csv"
LABELS_PATH = "data/processed/labels_fraude.csv"
FACTURES_PATH = "data/processed/factures.csv"
MODELS_DIR = Path("models")

# Features exclues avant fitting si taux de NaN > seuil dans le train
NAN_THRESHOLD = 0.95


# Chargement
def load_dataset(
    features_path: str = FEATURES_PATH,
    labels_path: str = LABELS_PATH,
    factures_path: str = FACTURES_PATH,
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    """Charge et joint features, labels (est_fraude) et métadonnées de split."""
    logger.info("Chargement features : %s", features_path)
    feat = pd.read_csv(features_path, index_col="facture_id")

    logger.info("Chargement labels : %s", labels_path)
    lbl = pd.read_csv(labels_path).set_index("facture_id")["est_fraude"].astype(int)

    logger.info("Chargement métadonnées factures : %s", factures_path)
    meta = pd.read_csv(factures_path, usecols=["facture_id", "assure_id", "date_soin"])

    # Intersection des trois sources
    common = feat.index.intersection(lbl.index)
    feat = feat.loc[common]
    lbl = lbl.loc[common]
    meta = meta[meta["facture_id"].isin(common)].reset_index(drop=True)

    logger.info(
        "Dataset : %d factures | %d fraudes (%.1f %%)",
        len(feat),
        int(lbl.sum()),
        100.0 * lbl.mean(),
    )
    return feat, lbl, meta


# Split sans fuite
def split_no_leakage(
    X: pd.DataFrame,
    y: pd.Series,
    meta: pd.DataFrame,
    test_size: float = 0.2,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """Split sans fuite temporelle par assuré.

    Stratégie :
      1. Calcule la date de première visite par assure_id.
      2. Trie les assurés par cette date (ordre chronologique).
      3. Les (1-test_size)*100 % d'assurés les plus anciens → train.
      4. Les test_size*100 % les plus récents → test.

    Garanties :
      - Aucun assuré n'est dans les deux ensembles.
      - Les assurés du train ont des premières visites antérieures aux assurés du test.
    """
    meta_idx = meta.set_index("facture_id").copy()
    meta_idx["_dt"] = pd.to_datetime(meta_idx["date_soin"], errors="coerce")

    first_date = meta_idx.groupby("assure_id")["_dt"].min().sort_values()
    n_assures = len(first_date)
    n_train_grp = max(1, int(n_assures * (1 - test_size)))

    train_assures = set(first_date.index[:n_train_grp])
    train_ids = meta_idx.index[meta_idx["assure_id"].isin(train_assures)]
    test_ids = meta_idx.index[~meta_idx["assure_id"].isin(train_assures)]

    logger.info(
        "Split : train=%d factures (%d assurés) | test=%d factures (%d assurés)",
        len(train_ids),
        len(train_assures),
        len(test_ids),
        n_assures - len(train_assures),
    )
    return X.loc[train_ids], X.loc[test_ids], y.loc[train_ids], y.loc[test_ids]


# ---------------------------------------------------------------------------
# Prétraitement
# ---------------------------------------------------------------------------
def _drop_high_nan(
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    threshold: float = NAN_THRESHOLD,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Supprime les colonnes dont le taux de NaN dépasse `threshold` dans le train."""
    nan_rate = X_train.isna().mean()
    to_drop = nan_rate[nan_rate > threshold].index.tolist()
    if to_drop:
        logger.info(
            "Exclusion %d features (NaN > %.0f %%) : %s", len(to_drop), 100 * threshold, to_drop
        )
    return (
        X_train.drop(columns=to_drop),
        X_test.drop(columns=to_drop, errors="ignore"),
        to_drop,
    )


# ---------------------------------------------------------------------------
# Pipeline sklearn
# ---------------------------------------------------------------------------
def make_pipeline(model_name: str = "lr", seed: int = 42) -> Pipeline:
    """Construit un Pipeline sklearn : imputation → [scaler] → modèle.

    Parameters
    ----------
    model_name : ``"lr"`` (LogisticRegression) ou ``"rf"`` (RandomForest)
    seed       : graine pour la reproductibilité
    """
    imputer = SimpleImputer(strategy="median")
    if model_name == "lr":
        steps = [
            ("imputer", imputer),
            ("scaler", StandardScaler()),
            (
                "clf",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=1000,
                    random_state=seed,
                    solver="lbfgs",
                ),
            ),
        ]
    elif model_name == "rf":
        steps = [
            ("imputer", imputer),
            (
                "clf",
                RandomForestClassifier(
                    n_estimators=300,
                    class_weight="balanced",
                    random_state=seed,
                    n_jobs=-1,
                ),
            ),
        ]
    else:
        raise ValueError(f"model_name inconnu : {model_name!r}. Choix : 'lr', 'rf'.")
    return Pipeline(steps)


# ---------------------------------------------------------------------------
# Évaluation
# ---------------------------------------------------------------------------
def evaluate(pipeline: Pipeline, X_test: pd.DataFrame, y_test: pd.Series) -> dict:
    """Calcule Recall, PR-AUC et F1 sur le jeu de test.

    Recall est la métrique prioritaire : ne pas manquer les fraudes.
    PR-AUC est robuste au déséquilibre de classes.
    """
    y_pred = pipeline.predict(X_test)
    y_prob = pipeline.predict_proba(X_test)[:, 1]
    return {
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "pr_auc": float(average_precision_score(y_test, y_prob)),
        "f1": float(f1_score(y_test, y_pred, zero_division=0)),
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
    }


# ---------------------------------------------------------------------------
# Orchestrateur
# ---------------------------------------------------------------------------
def train_baseline(
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    y_train: pd.Series,
    y_test: pd.Series,
    model_name: str = "lr",
    seed: int = 42,
    nan_threshold: float = NAN_THRESHOLD,
) -> tuple[Pipeline, dict]:
    """Entraîne un modèle baseline et retourne (pipeline fitté, métriques).

    Étapes : suppression features haute-NaN → fit → évaluation.
    """
    X_tr, X_te, dropped = _drop_high_nan(X_train, X_test, threshold=nan_threshold)
    features_used = list(X_tr.columns)

    logger.info(
        "Entraînement %s | train=%d (fraudes=%d) | test=%d (fraudes=%d)",
        model_name.upper(),
        len(y_train),
        int(y_train.sum()),
        len(y_test),
        int(y_test.sum()),
    )
    pipe = make_pipeline(model_name, seed=seed)
    pipe.fit(X_tr, y_train)

    metrics = evaluate(pipe, X_te, y_test)
    metrics.update(
        {
            "n_train": len(y_train),
            "n_test": len(y_test),
            "n_fraude_train": int(y_train.sum()),
            "n_fraude_test": int(y_test.sum()),
            "features_used": features_used,
            "features_dropped": dropped,
        }
    )
    logger.info(
        "[%s] Recall=%.3f | PR-AUC=%.3f | F1=%.3f",
        model_name.upper(),
        metrics["recall"],
        metrics["pr_auc"],
        metrics["f1"],
    )
    return pipe, metrics


# ---------------------------------------------------------------------------
# Entrée CLI : python -m predicare.ml.baseline
# ---------------------------------------------------------------------------
if __name__ == "__main__":  # pragma: no cover
    import argparse
    import json
    import sys

    def _cli() -> None:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            stream=sys.stderr,
        )
        p = argparse.ArgumentParser(description="Baseline ML fraude – PrediCare TPA (PB-06)")
        p.add_argument("--features", default=FEATURES_PATH)
        p.add_argument("--labels", default=LABELS_PATH)
        p.add_argument("--factures", default=FACTURES_PATH)
        p.add_argument("--models-dir", default=str(MODELS_DIR))
        p.add_argument("--seed", type=int, default=42)
        p.add_argument("--test-size", type=float, default=0.2)
        args = p.parse_args()

        models_dir = Path(args.models_dir)
        models_dir.mkdir(parents=True, exist_ok=True)

        X, y, meta = load_dataset(args.features, args.labels, args.factures)
        X_tr, X_te, y_tr, y_te = split_no_leakage(X, y, meta, test_size=args.test_size)

        results: dict[str, dict] = {}
        for model_name in ("lr", "rf"):
            pipe, m = train_baseline(X_tr, X_te, y_tr, y_te, model_name=model_name, seed=args.seed)
            out = models_dir / f"baseline_{model_name}.joblib"
            joblib.dump(pipe, out)
            logger.info("Modèle sérialisé : %s", out)
            results[model_name] = m

        # Noms de features utilisées (après exclusion haute-NaN)
        feat_path = models_dir / "feature_names.json"
        feat_path.write_text(
            json.dumps(results["lr"]["features_used"], ensure_ascii=False, indent=2)
        )
        logger.info("feature_names.json : %d features", len(results["lr"]["features_used"]))

        # Rapport
        print("\n=== Rapport baseline PB-06 ===")
        for mn, m in results.items():
            print(f"\n[{mn.upper()}]")
            print(f"  Train  : {m['n_train']} factures | {m['n_fraude_train']} fraudes")
            print(f"  Test   : {m['n_test']} factures  | {m['n_fraude_test']} fraudes")
            print(f"  Recall : {m['recall']:.3f}")
            print(f"  PR-AUC : {m['pr_auc']:.3f}")
            print(f"  F1     : {m['f1']:.3f}")
            print(f"  Matrice: {m['confusion_matrix']}")

        best = max(results, key=lambda k: results[k]["pr_auc"])
        print(f"\n✓ Meilleur (PR-AUC) : {best.upper()} → models/baseline_{best}.joblib")

    _cli()
