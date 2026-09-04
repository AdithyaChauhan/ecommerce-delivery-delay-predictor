from __future__ import annotations

import json

import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from delivery_delay.gold_v1 import FORBIDDEN_FEATURE_COLUMNS, MODEL_FEATURE_COLUMNS, TARGET_COLUMN
from delivery_delay.train import (
    ARTIFACT_FILENAME,
    METRICS_FILENAME,
    build_preprocessor,
    calculate_metrics,
    load_gold,
    select_threshold,
    split_gold,
    train_and_evaluate,
)


def make_gold(rows: int = 20) -> pd.DataFrame:
    frame = pd.DataFrame(
        {column: [1.0] * rows for column in MODEL_FEATURE_COLUMNS}
    )
    for column in ("customer_state", "primary_product_category", "primary_seller_state", "primary_payment_type"):
        frame[column] = ["known" if index %
                         2 else None for index in range(rows)]
    frame["order_id"] = [f"order-{index:03d}" for index in range(rows)]
    frame["order_purchase_timestamp"] = pd.date_range(
        "2020-01-01", periods=rows, freq="h")
    frame[TARGET_COLUMN] = [index % 2 for index in range(rows)]
    frame["approval_delay_hours"] = [
        None if index == 0 else 1.0 for index in range(rows)]
    return frame


def test_split_is_chronological_deterministic_and_disjoint():
    gold = make_gold()
    first = split_gold(gold.sample(frac=1, random_state=7))
    second = split_gold(gold.sample(frac=1, random_state=13))

    assert [len(first[name])
            for name in ("train", "validation", "test")] == [14, 3, 3]
    assert [first[name]["order_id"].tolist() for name in first] == [
        second[name]["order_id"].tolist() for name in second]
    assert first["train"]["order_purchase_timestamp"].max(
    ) < first["validation"]["order_purchase_timestamp"].min()
    assert set(first["train"]["order_id"]).isdisjoint(
        first["validation"]["order_id"])
    assert set(first["validation"]["order_id"]).isdisjoint(
        first["test"]["order_id"])


def test_feature_whitelist_and_leakage_exclusion(tmp_path):
    path = tmp_path / "gold.parquet"
    gold = make_gold()
    gold.to_parquet(path)
    loaded = load_gold(path)

    assert loaded[list(MODEL_FEATURE_COLUMNS)].columns.tolist() == list(
        MODEL_FEATURE_COLUMNS)
    assert not set(MODEL_FEATURE_COLUMNS) & FORBIDDEN_FEATURE_COLUMNS
    assert "order_id" not in MODEL_FEATURE_COLUMNS
    assert "order_purchase_timestamp" not in MODEL_FEATURE_COLUMNS
    assert TARGET_COLUMN not in MODEL_FEATURE_COLUMNS


def test_preprocessing_handles_missing_and_unknown_categories():
    preprocessor = build_preprocessor()
    frame = make_gold()
    transformed = preprocessor.fit_transform(
        frame[list(MODEL_FEATURE_COLUMNS)])
    changed = frame[list(MODEL_FEATURE_COLUMNS)].copy()
    changed["customer_state"] = "unseen-state"
    changed_output = preprocessor.transform(changed)

    assert transformed.shape[0] == len(frame)
    assert changed_output.shape == transformed.shape
    assert np.isfinite(transformed.toarray() if hasattr(
        transformed, "toarray") else transformed).all()


def test_threshold_selection_is_deterministic_and_maximizes_f1():
    labels = np.array([0, 1, 1, 0])
    scores = np.array([0.1, 0.6, 0.8, 0.5])

    assert select_threshold(labels, scores) == 0.6


def test_metrics_and_artifacts_round_trip(tmp_path):
    gold_path = tmp_path / "gold.parquet"
    artifacts = tmp_path / "models"
    make_gold(30).to_parquet(gold_path)
    report = train_and_evaluate(gold_path, artifacts)

    metrics_path = artifacts / METRICS_FILENAME
    model_path = artifacts / ARTIFACT_FILENAME
    loaded_report = json.loads(metrics_path.read_text(encoding="utf-8"))
    pipeline = joblib.load(model_path)
    scores = pipeline.predict_proba(
        make_gold(3)[list(MODEL_FEATURE_COLUMNS)])[:, 1]

    assert isinstance(pipeline, Pipeline)
    assert report == loaded_report
    assert scores.shape == (3,)
    assert np.isfinite(scores).all()
    assert ((scores >= 0) & (scores <= 1)).all()
    assert set(report["metrics"]["test"]) >= {
        "roc_auc", "average_precision", "precision", "recall", "f1",
        "true_positives", "false_positives", "true_negatives", "false_negatives",
    }
    assert calculate_metrics(np.array([0, 1]), np.array([0.1, 0.9]), 0.5)[
        "f1"] == 1.0
