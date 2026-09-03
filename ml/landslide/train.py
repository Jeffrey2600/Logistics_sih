#!/usr/bin/env python3
"""Train the segment-disruption classifier consumed by the routing API.

The API runs perfectly well without this: `load_risk_model()` falls back to the
transparent analytic model. Training only replaces the probability estimate; the
explanation surface stays the same.

Input
-----
A labelled CSV at `data/processed/disruption_training.csv` with one row per
(segment, month) observation:

    segment_id, month, terrain, mode, distance_km, lanes,
    monsoon_exposure, landslide_events, disrupted

`disrupted` is 1 if that segment was closed or restricted at any point in that
month. Build it with `data/ingest/build_training_set.py`, which joins the NASA
COOLR landslide catalogue and state PWD closure notices onto the OSM road
network. That join is the honest bottleneck of this project: labels are scarce
and unevenly reported, so treat a model trained on few districts as fitted to
those districts.

Usage
-----
    python ml/landslide/train.py
    python ml/landslide/train.py --bootstrap   # pipeline smoke test only
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from backend.app.config import SEASON_RAIN_INDEX  # noqa: E402
from backend.app.core.features import FEATURE_ORDER, edge_features  # noqa: E402

TRAINING_CSV = REPO_ROOT / "data" / "processed" / "disruption_training.csv"
MODEL_PATH = Path(__file__).parent / "model.joblib"
META_PATH = Path(__file__).parent / "model_meta.json"

MIN_ROWS = 200
MIN_POSITIVES = 30


def load_rows(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(
            f"No training data at {path}.\n"
            "Build it with data/ingest/build_training_set.py, or run with "
            "--bootstrap to smoke-test the pipeline on synthetic labels."
        )
    with path.open() as fh:
        return list(csv.DictReader(fh))


def bootstrap_rows() -> list[dict]:
    """Synthetic labels drawn from the analytic model, for pipeline testing.

    These are NOT evidence. A model fitted here can only rediscover the
    analytic prior it was sampled from, so its scores must never be reported
    as a validated result.
    """
    import random

    from backend.app.core.network import load_network
    from backend.app.core.risk import AnalyticRiskModel

    random.seed(20260903)
    model = AnalyticRiskModel()
    rows = []
    for edge in load_network().edges:
        for month in SEASON_RAIN_INDEX:
            # Several synthetic years so the sample is large enough to fit.
            for _ in range(4):
                probability = model.assess(edge, month).probability
                rows.append(
                    {
                        "segment_id": edge["id"],
                        "month": month,
                        "terrain": edge["terrain"],
                        "mode": edge["mode"],
                        "distance_km": edge["distance_km"],
                        "lanes": edge["lanes"],
                        "monsoon_exposure": edge["monsoon_exposure"],
                        "landslide_events": edge["landslide_events"],
                        "disrupted": int(random.random() < probability),
                    }
                )
    return rows


def to_matrix(rows: list[dict]) -> tuple[list[list[float]], list[int]]:
    features, labels = [], []
    for row in rows:
        edge = {
            "mode": row["mode"],
            "terrain": row["terrain"],
            "distance_km": float(row["distance_km"]),
            "lanes": int(float(row["lanes"])),
            "monsoon_exposure": float(row["monsoon_exposure"]),
            "landslide_events": float(row["landslide_events"]),
        }
        values = edge_features(edge, row["month"])
        features.append([values[name] for name in FEATURE_ORDER])
        labels.append(int(float(row["disrupted"])))
    return features, labels


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="fit on synthetic labels to smoke-test the pipeline (not evidence)",
    )
    parser.add_argument("--input", type=Path, default=TRAINING_CSV)
    args = parser.parse_args()

    try:
        import joblib
        from sklearn.ensemble import HistGradientBoostingClassifier
        from sklearn.metrics import average_precision_score, roc_auc_score
        from sklearn.model_selection import GroupKFold, cross_val_predict
    except ImportError:
        raise SystemExit("Training needs ml/requirements.txt: pip install -r ml/requirements.txt")

    rows = bootstrap_rows() if args.bootstrap else load_rows(args.input)
    features, labels = to_matrix(rows)
    positives = sum(labels)

    if not args.bootstrap:
        if len(rows) < MIN_ROWS:
            raise SystemExit(f"Only {len(rows)} rows; need >= {MIN_ROWS} to fit responsibly.")
        if positives < MIN_POSITIVES:
            raise SystemExit(f"Only {positives} disruption events; need >= {MIN_POSITIVES}.")

    print(f"rows={len(rows)}  disrupted={positives} ({positives / len(rows):.1%})")

    model = HistGradientBoostingClassifier(
        max_depth=4, max_iter=250, learning_rate=0.06, l2_regularization=1.0,
        random_state=20260903,
    )

    # Group by segment so the same stretch of highway never appears in both
    # folds. Random splits would let the model memorise a corridor and report
    # an accuracy it cannot reproduce on a road it has not seen.
    groups = [row["segment_id"] for row in rows]
    n_splits = min(5, len(set(groups)))
    predicted = cross_val_predict(
        model, features, labels, cv=GroupKFold(n_splits=n_splits),
        groups=groups, method="predict_proba",
    )[:, 1]

    auc = roc_auc_score(labels, predicted)
    ap = average_precision_score(labels, predicted)
    print(f"grouped {n_splits}-fold CV:  ROC-AUC={auc:.3f}  average precision={ap:.3f}")

    model.fit(features, labels)
    joblib.dump(model, MODEL_PATH)
    META_PATH.write_text(
        json.dumps(
            {
                "feature_order": FEATURE_ORDER,
                "rows": len(rows),
                "positives": positives,
                "roc_auc": round(auc, 4),
                "average_precision": round(ap, 4),
                "cv": f"GroupKFold({n_splits}) grouped by segment_id",
                "synthetic": args.bootstrap,
            },
            indent=2,
        )
    )
    print(f"wrote {MODEL_PATH.name} and {META_PATH.name}")
    if args.bootstrap:
        print("\nWARNING: fitted on synthetic labels. Do not report these scores.")


if __name__ == "__main__":
    main()
