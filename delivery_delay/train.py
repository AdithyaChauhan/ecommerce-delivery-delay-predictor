"""Train and evaluate the local Gold-v1 delivery-delay classifier."""

from __future__ import annotations

import argparse
import gc
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
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier

from delivery_delay.gold_v1 import MODEL_FEATURE_COLUMNS, TARGET_COLUMN


RANDOM_SEED = 42
TRAIN_FRACTION = 0.70
VALIDATION_FRACTION = 0.15
ARTIFACT_FILENAME = "delay_xgboost_pipeline.joblib"
METRICS_FILENAME = "delay_training_metrics.json"
V2_ARTIFACT_FILENAME = "delay_model_v2_pipeline.joblib"
V2_METRICS_FILENAME = "delay_model_v2_metrics.json"
TEST_PERIOD_LIMITATION = (
    "The chronological test period is fixed and has already been observed "
    "through the baseline evaluation; it is not an untouched holdout."
)

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

SHALLOW_XGBOOST_PARAMETERS = {
    "n_estimators": 400,
    "max_depth": 2,
    "learning_rate": 0.03,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 5,
    "reg_lambda": 5.0,
    "gamma": 0.1,
    "objective": "binary:logistic",
    "eval_metric": "logloss",
    "tree_method": "hist",
    "n_jobs": 1,
    "random_state": RANDOM_SEED,
}

LOGISTIC_PARAMETERS = {
    "solver": "liblinear",
    "C": 1.0,
    "max_iter": 1000,
    "class_weight": "balanced",
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


def build_logistic_preprocessor() -> ColumnTransformer:
    numeric = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
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


def build_logistic_pipeline() -> Pipeline:
    return Pipeline(
        [
            ("preprocessor", build_logistic_preprocessor()),
            ("classifier", LogisticRegression(**LOGISTIC_PARAMETERS)),
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


def calculate_ranking_metrics(
    order_ids: pd.Series | np.ndarray,
    labels: pd.Series | np.ndarray,
    scores: np.ndarray,
) -> dict[str, dict[str, float | int]]:
    order_ids_array = np.asarray(order_ids).astype(str)
    labels_array = np.asarray(labels).astype("int8")
    scores_array = np.asarray(scores, dtype=float)
    if not (
        len(order_ids_array) == len(labels_array) == len(scores_array)
    ):
        raise ValueError("Ranking inputs must have the same length")
    ranking = pd.DataFrame(
        {"order_id": order_ids_array, "label": labels_array, "score": scores_array}
    ).sort_values(
        ["score", "order_id"], ascending=[False, True], kind="stable"
    )
    total_late = int(labels_array.sum())
    results: dict[str, dict[str, float | int]] = {}
    for fraction in (0.05, 0.10, 0.20):
        selected_count = max(1, int(np.ceil(len(ranking) * fraction)))
        selected = ranking.head(selected_count)
        late_found = int(selected["label"].sum())
        precision = late_found / selected_count
        recall = late_found / total_late if total_late else 0.0
        prevalence = total_late / len(ranking) if len(ranking) else 0.0
        results[f"top_{int(fraction * 100)}_percent"] = {
            "selected_count": selected_count,
            "late_orders_found": late_found,
            "precision": float(precision),
            "recall": float(recall),
            "lift_over_prevalence": float(precision / prevalence)
            if prevalence
            else 0.0,
        }
    return results


def calculate_ranking_metrics_only(
    order_ids: pd.Series | np.ndarray,
    labels: pd.Series | np.ndarray,
    scores: np.ndarray,
) -> dict[str, dict[str, float | int]]:
    """Compatibility-named wrapper for explicit ranking evaluation."""
    return calculate_ranking_metrics(order_ids, labels, scores)


def _ranking_metrics_for_split(
    frame: pd.DataFrame, scores: np.ndarray
) -> dict[str, dict[str, float | int]]:
    return calculate_ranking_metrics(frame["order_id"], frame[TARGET_COLUMN], scores)


def _discrimination_metrics(
    labels: pd.Series | np.ndarray, scores: np.ndarray
) -> dict[str, float]:
    labels_array = np.asarray(labels)
    scores_array = np.asarray(scores, dtype=float)
    return {
        "roc_auc": float(roc_auc_score(labels_array, scores_array)),
        "average_precision": float(
            average_precision_score(labels_array, scores_array)
        ),
    }


def select_model_name(candidate_metrics: dict[str, dict[str, Any]]) -> str:
    """Select by validation AP, then ROC-AUC, then candidate name."""
    return min(
        candidate_metrics,
        key=lambda name: (
            -float(candidate_metrics[name]["validation"]["average_precision"]),
            -float(candidate_metrics[name]["validation"]["roc_auc"]),
            name,
        ),
    )


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


def train_and_evaluate_v2(gold_path: Path, artifacts_dir: Path) -> dict[str, Any]:
    """Compare candidates on validation, then evaluate only the winner on test."""
    gold = load_gold(gold_path)
    splits = split_gold(gold)
    train = splits["train"]
    validation = splits["validation"]
    test = splits["test"]
    labels = {name: frame[TARGET_COLUMN] for name, frame in splits.items()}
    features = {
        name: frame[list(MODEL_FEATURE_COLUMNS)]
        for name, frame in splits.items()
    }
    train_late = int(labels["train"].sum())
    train_on_time = int(len(train) - train_late)
    if train_late == 0 or train_on_time == 0:
        raise ValueError("Training split must contain both target classes")
    scale_pos_weight = train_on_time / train_late

    candidate_parameters = {
        "xgboost_baseline": {
            **XGBOOST_PARAMETERS,
            "scale_pos_weight": scale_pos_weight,
        },
        "xgboost_shallow_regularized": {
            **SHALLOW_XGBOOST_PARAMETERS,
            "scale_pos_weight": scale_pos_weight,
        },
        "logistic_regression_balanced": dict(LOGISTIC_PARAMETERS),
    }
    candidate_builders = {
        "xgboost_baseline": lambda: build_xgboost_pipeline(scale_pos_weight),
        "xgboost_shallow_regularized": lambda: Pipeline(
            [
                ("preprocessor", build_preprocessor()),
                (
                    "classifier",
                    XGBClassifier(
                        **{
                            **SHALLOW_XGBOOST_PARAMETERS,
                            "scale_pos_weight": scale_pos_weight,
                        }
                    ),
                ),
            ]
        ),
        "logistic_regression_balanced": build_logistic_pipeline,
    }

    candidate_metrics: dict[str, dict[str, Any]] = {}
    validation_scores: dict[str, np.ndarray] = {}
    for name in sorted(candidate_builders):
        pipeline = candidate_builders[name]()
        pipeline.fit(features["train"], labels["train"])
        train_scores = pipeline.predict_proba(features["train"])[:, 1]
        validation_scores[name] = pipeline.predict_proba(
            features["validation"]
        )[:, 1]
        candidate_metrics[name] = {
            "train": _discrimination_metrics(labels["train"], train_scores),
            "validation": _discrimination_metrics(
                labels["validation"], validation_scores[name]
            ),
        }
        del pipeline, train_scores
        gc.collect()

    winner = select_model_name(candidate_metrics)
    threshold = select_threshold(labels["validation"], validation_scores[winner])
    winning_pipeline = candidate_builders[winner]()
    winning_pipeline.fit(features["train"], labels["train"])
    winning_train_scores = winning_pipeline.predict_proba(
        features["train"]
    )[:, 1]
    winning_validation_scores = validation_scores[winner]
    winning_test_scores = winning_pipeline.predict_proba(features["test"])[:, 1]
    winner_metrics = {
        "train": calculate_metrics(labels["train"], winning_train_scores, threshold),
        "validation": calculate_metrics(
            labels["validation"], winning_validation_scores, threshold
        ),
        "test": calculate_metrics(labels["test"], winning_test_scores, threshold),
    }
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    model_path = artifacts_dir / V2_ARTIFACT_FILENAME
    metrics_path = artifacts_dir / V2_METRICS_FILENAME
    joblib.dump(winning_pipeline, model_path)
    report = {
        "model_feature_columns": list(MODEL_FEATURE_COLUMNS),
        "numeric_feature_columns": list(NUMERIC_FEATURE_COLUMNS),
        "categorical_feature_columns": list(CATEGORICAL_FEATURE_COLUMNS),
        "random_seed": RANDOM_SEED,
        "candidate_parameters": candidate_parameters,
        "candidate_comparison": candidate_metrics,
        "winner": winner,
        "selected_validation_threshold": threshold,
        "winner_metrics": winner_metrics,
        "test_ranking_metrics": _ranking_metrics_for_split(test, winning_test_scores),
        "split": {
            "sort_columns": ["order_purchase_timestamp", "order_id"],
            "fractions": {
                "train": TRAIN_FRACTION,
                "validation": VALIDATION_FRACTION,
                "test": 0.15,
            },
            "train": _split_summary(train),
            "validation": _split_summary(validation),
            "test": _split_summary(test),
        },
        "test_period_limitation": TEST_PERIOD_LIMITATION,
        "package_versions": _package_versions(),
        "python_version": platform.python_version(),
        "artifact": {
            "pipeline": str(model_path),
            "evaluated_model_saved_unchanged": True,
        },
    }
    metrics_path.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train the local Gold-v1 delay classifier.")
    parser.add_argument("--gold", type=Path,
                        default=Path("data/processed/gold_v1.parquet"))
    parser.add_argument("--artifacts-dir", type=Path, default=Path("models"))
    parser.add_argument(
        "--experiment",
        choices=("baseline", "v2"),
        default="baseline",
        help="Training experiment to run; baseline preserves the original behavior.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.experiment == "v2":
        report = train_and_evaluate_v2(args.gold, args.artifacts_dir)
    else:
        report = train_and_evaluate(args.gold, args.artifacts_dir)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
