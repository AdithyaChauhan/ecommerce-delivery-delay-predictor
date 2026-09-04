"""Train and evaluate the local Gold-v1 delivery-delay classifier."""

from __future__ import annotations

import argparse
import json
import platform
from importlib import metadata
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBClassifier

from delivery_delay.gold_v1 import MODEL_FEATURE_COLUMNS, TARGET_COLUMN


RANDOM_SEED = 42
TRAIN_FRACTION = 0.70
VALIDATION_FRACTION = 0.15
ARTIFACT_FILENAME = "delay_xgboost_pipeline.joblib"
METRICS_FILENAME = "delay_training_metrics.json"

NUMERIC_FEATURE_COLUMNS = tuple(
    column
    for column in MODEL_FEATURE_COLUMNS
    if column
    not in {
        "customer_state",
        "primary_product_category",
        "primary_seller_state",
        "primary_payment_type",
    }
)
CATEGORICAL_FEATURE_COLUMNS = tuple(
    column for column in MODEL_FEATURE_COLUMNS if column not in NUMERIC_FEATURE_COLUMNS
)

XGBOOST_PARAMETERS = {
    "n_estimators": 300,
    "max_depth": 4,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 1,
    "objective": "binary:logistic",
    "eval_metric": "logloss",
    "tree_method": "hist",
    "n_jobs": 1,
    "random_state": RANDOM_SEED,
}


def load_gold(path: Path) -> pd.DataFrame:
    gold = pd.read_parquet(path)
    required = set(MODEL_FEATURE_COLUMNS) | {
        "order_id", "order_purchase_timestamp", TARGET_COLUMN}
    missing = sorted(required - set(gold.columns))
    if missing:
        raise ValueError(
            f"Gold-v1 is missing required training columns: {missing}")
    if gold[list(MODEL_FEATURE_COLUMNS)].columns.tolist() != list(MODEL_FEATURE_COLUMNS):
        raise ValueError(
            "Gold-v1 feature columns do not match MODEL_FEATURE_COLUMNS")
    if gold["order_id"].isna().any() or not gold["order_id"].is_unique:
        raise ValueError("Gold-v1 order_id must be unique and non-missing")
    if gold[TARGET_COLUMN].isna().any():
        raise ValueError("Gold-v1 target contains missing values")
    return gold.sort_values(
        ["order_purchase_timestamp", "order_id"], kind="stable"
    ).reset_index(drop=True)


def split_gold(gold: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if len(gold) < 3:
        raise ValueError("Gold-v1 must contain at least three rows")
    ordered = gold.sort_values(
        ["order_purchase_timestamp", "order_id"], kind="stable"
    ).reset_index(drop=True)
    train_end = int(len(ordered) * TRAIN_FRACTION)
    validation_end = int(len(ordered) * (TRAIN_FRACTION + VALIDATION_FRACTION))
    if train_end == 0 or validation_end <= train_end or validation_end >= len(ordered):
        raise ValueError(
            "Gold-v1 is too small for the configured chronological split")
    return {
        "train": ordered.iloc[:train_end].copy(),
        "validation": ordered.iloc[train_end:validation_end].copy(),
        "test": ordered.iloc[validation_end:].copy(),
    }


def build_preprocessor() -> ColumnTransformer:
    numeric = Pipeline(
        [("imputer", SimpleImputer(strategy="median"))]
    )
    categorical = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="constant", fill_value="__missing__")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    return ColumnTransformer(
        [
            ("numeric", numeric, list(NUMERIC_FEATURE_COLUMNS)),
            ("categorical", categorical, list(CATEGORICAL_FEATURE_COLUMNS)),
        ],
        remainder="drop",
    )


def build_xgboost_pipeline(scale_pos_weight: float) -> Pipeline:
    parameters = {**XGBOOST_PARAMETERS, "scale_pos_weight": scale_pos_weight}
    return Pipeline(
        [
            ("preprocessor", build_preprocessor()),
            ("classifier", XGBClassifier(**parameters)),
        ]
    )


def select_threshold(labels: pd.Series | np.ndarray, scores: np.ndarray) -> float:
    labels_array = np.asarray(labels)
    scores_array = np.asarray(scores, dtype=float)
    if labels_array.shape[0] != scores_array.shape[0]:
        raise ValueError("Labels and scores must have the same length")
    if not np.isfinite(scores_array).all() or ((scores_array < 0) | (scores_array > 1)).any():
        raise ValueError("Scores must be finite values between 0 and 1")
    candidates = np.unique(np.concatenate(([0.0, 1.0], scores_array)))
    best_threshold = 0.0
    best_key = (-1.0, -1.0, -1.0)
    for threshold in candidates:
        predictions = (scores_array >= threshold).astype("int8")
        key = (
            float(f1_score(labels_array, predictions, zero_division=0)),
            float(precision_score(labels_array, predictions, zero_division=0)),
            float(threshold),
        )
        if key > best_key:
            best_key = key
            best_threshold = float(threshold)
    return best_threshold


def calculate_metrics(labels: pd.Series | np.ndarray, scores: np.ndarray, threshold: float) -> dict[str, float | int]:
    labels_array = np.asarray(labels)
    scores_array = np.asarray(scores, dtype=float)
    predictions = (scores_array >= threshold).astype("int8")
    true_negative, false_positive, false_negative, true_positive = confusion_matrix(
        labels_array, predictions, labels=[0, 1]
    ).ravel()
    return {
        "roc_auc": float(roc_auc_score(labels_array, scores_array)),
        "average_precision": float(average_precision_score(labels_array, scores_array)),
        "precision": float(precision_score(labels_array, predictions, zero_division=0)),
        "recall": float(recall_score(labels_array, predictions, zero_division=0)),
        "f1": float(f1_score(labels_array, predictions, zero_division=0)),
        "true_positives": int(true_positive),
        "false_positives": int(false_positive),
        "true_negatives": int(true_negative),
        "false_negatives": int(false_negative),
        "selected_threshold": float(threshold),
    }


def _split_summary(frame: pd.DataFrame) -> dict[str, Any]:
    late = int(frame[TARGET_COLUMN].sum())
    rows = len(frame)
    return {
        "rows": rows,
        "class_counts": {"on_time": rows - late, "late": late},
        "class_percentages": {
            "on_time": float(100.0 * (rows - late) / rows),
            "late": float(100.0 * late / rows),
        },
        "late_percentage": float(100.0 * late / rows),
        "start": frame["order_purchase_timestamp"].min().isoformat(sep=" "),
        "end": frame["order_purchase_timestamp"].max().isoformat(sep=" "),
    }


def _package_versions() -> dict[str, str]:
    return {
        name: metadata.version(name)
        for name in ("pandas", "pyarrow", "scikit-learn", "xgboost", "joblib")
    }


def train_and_evaluate(gold_path: Path, artifacts_dir: Path) -> dict[str, Any]:
    gold = load_gold(gold_path)
    splits = split_gold(gold)
    train = splits["train"]
    validation = splits["validation"]
    test = splits["test"]
    labels = {name: frame[TARGET_COLUMN] for name, frame in splits.items()}
    features = {name: frame[list(MODEL_FEATURE_COLUMNS)]
                for name, frame in splits.items()}

    train_late = int(labels["train"].sum())
    train_on_time = int(len(train) - train_late)
    if train_late == 0 or train_on_time == 0:
        raise ValueError("Training split must contain both target classes")
    scale_pos_weight = train_on_time / train_late

    dummy = DummyClassifier(strategy="prior")
    dummy.fit(features["train"], labels["train"])
    dummy_scores = dummy.predict_proba(features["test"])[:, 1]
    dummy_metrics = calculate_metrics(labels["test"], dummy_scores, 0.5)

    pipeline = build_xgboost_pipeline(scale_pos_weight)
    pipeline.fit(features["train"], labels["train"])
    validation_scores = pipeline.predict_proba(features["validation"])[:, 1]
    threshold = select_threshold(labels["validation"], validation_scores)
    test_scores = pipeline.predict_proba(features["test"])[:, 1]
    test_metrics = calculate_metrics(labels["test"], test_scores, threshold)

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    model_path = artifacts_dir / ARTIFACT_FILENAME
    metrics_path = artifacts_dir / METRICS_FILENAME
    joblib.dump(pipeline, model_path)
    report = {
        "model_feature_columns": list(MODEL_FEATURE_COLUMNS),
        "numeric_feature_columns": list(NUMERIC_FEATURE_COLUMNS),
        "categorical_feature_columns": list(CATEGORICAL_FEATURE_COLUMNS),
        "random_seed": RANDOM_SEED,
        "xgboost_parameters": {
            **XGBOOST_PARAMETERS,
            "scale_pos_weight": scale_pos_weight,
        },
        "split": {
            "sort_columns": ["order_purchase_timestamp", "order_id"],
            "fractions": {"train": TRAIN_FRACTION, "validation": VALIDATION_FRACTION, "test": 0.15},
            "train": _split_summary(train),
            "validation": _split_summary(validation),
            "test": _split_summary(test),
        },
        "selected_threshold": threshold,
        "metrics": {"test": test_metrics, "dummy_test": dummy_metrics},
        "package_versions": _package_versions(),
        "python_version": platform.python_version(),
        "artifact": {"pipeline": str(model_path), "evaluated_model_saved_unchanged": True},
    }
    metrics_path.write_text(json.dumps(
        report, indent=2) + "\n", encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train the local Gold-v1 delay classifier.")
    parser.add_argument("--gold", type=Path,
                        default=Path("data/processed/gold_v1.parquet"))
    parser.add_argument("--artifacts-dir", type=Path, default=Path("models"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = train_and_evaluate(args.gold, args.artifacts_dir)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
