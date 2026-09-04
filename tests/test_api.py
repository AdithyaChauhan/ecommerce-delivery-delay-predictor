from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from delivery_delay.api import MODEL_FEATURE_COLUMNS, create_app


class CapturingPipeline:
    def __init__(self, score: float = 0.7):
        self.score = score
        self.columns = None

    def predict_proba(self, frame):
        self.columns = tuple(frame.columns)
        return np.array([[1.0 - self.score, self.score]])


def metrics(threshold: float = 0.5):
    return {
        "winner": "xgboost_baseline",
        "selected_validation_threshold": threshold,
        "model_feature_columns": list(MODEL_FEATURE_COLUMNS),
    }


def example_payload() -> dict:
    return json.loads(
        (Path(__file__).parents[1] / "examples" / "predict_request.json").read_text()
    )


@pytest.fixture
def app_and_pipeline():
    pipeline = CapturingPipeline()
    app = create_app(pipeline=pipeline, metrics=metrics())
    return app, pipeline


def test_health_reports_stored_model_and_feature_count(app_and_pipeline):
    app, _ = app_and_pipeline
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "model_name": "xgboost_baseline",
        "expected_feature_count": 30,
    }


def test_tracked_example_is_accepted_and_columns_are_ordered(app_and_pipeline):
    app, pipeline = app_and_pipeline
    with TestClient(app) as client:
        response = client.post("/predict", json=example_payload())
    body = response.json()
    assert response.status_code == 200
    assert body["order_id"] == "demo-order-001"
    assert body["risk_score"] == pytest.approx(0.7)
    assert body["predicted_delay"] is True
    assert pipeline.columns == tuple(MODEL_FEATURE_COLUMNS)


def test_unknown_categories_and_nullable_values_are_supported(app_and_pipeline):
    app, _ = app_and_pipeline
    payload = example_payload()
    payload.update(
        {
            "customer_state": "ZZ",
            "primary_seller_state": "YY",
            "primary_product_category": "unseen-category",
            "approval_delay_hours": None,
            "product_weight_g_total": None,
            "product_volume_cm3_total": None,
            "seller_customer_distance_km_min": None,
            "seller_customer_distance_km_mean": None,
            "seller_customer_distance_km_max": None,
        }
    )
    with TestClient(app) as client:
        response = client.post(
            "/predict",
            content=json.dumps(payload, allow_nan=True),
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 200


@pytest.mark.parametrize("field", list(MODEL_FEATURE_COLUMNS))
def test_all_model_features_are_required(app_and_pipeline, field):
    app, _ = app_and_pipeline
    payload = example_payload()
    payload.pop(field)
    with TestClient(app) as client:
        response = client.post("/predict", json=payload)
    assert response.status_code == 422


@pytest.mark.parametrize("field", ["delay_flag", "order_status", "review_score", "unexpected"])
def test_forbidden_and_extra_fields_are_rejected(app_and_pipeline, field):
    app, _ = app_and_pipeline
    payload = example_payload()
    payload[field] = 1
    with TestClient(app) as client:
        response = client.post("/predict", json=payload)
    assert response.status_code == 422


@pytest.mark.parametrize("field", ["item_price_total", "payment_value_total", "promised_delivery_window_days"])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_non_finite_numeric_values_are_rejected(app_and_pipeline, field, value):
    app, _ = app_and_pipeline
    payload = example_payload()
    payload[field] = value
    with TestClient(app) as client:
        response = client.post(
            "/predict",
            content=json.dumps(payload, allow_nan=True),
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 422


def test_threshold_uses_greater_than_or_equal(app_and_pipeline):
    pipeline = CapturingPipeline(score=0.5)
    app = create_app(pipeline=pipeline, metrics=metrics(threshold=0.5))
    with TestClient(app) as client:
        response = client.post("/predict", json=example_payload())
    assert response.status_code == 200
    assert response.json()["predicted_delay"] is True


def test_invalid_pipeline_score_is_rejected():
    app = create_app(pipeline=CapturingPipeline(score=1.2), metrics=metrics())
    with TestClient(app) as client:
        response = client.post("/predict", json=example_payload())
    assert response.status_code == 500
