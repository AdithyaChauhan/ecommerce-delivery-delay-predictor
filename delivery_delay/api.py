"""Minimal local FastAPI inference service for the saved Model-v2 pipeline."""

from __future__ import annotations

import json
import math
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

from delivery_delay.gold_v1 import MODEL_FEATURE_COLUMNS


DEFAULT_MODEL_PATH = Path("models/delay_model_v2_pipeline.joblib")
DEFAULT_METRICS_PATH = Path("models/delay_model_v2_metrics.json")
DEFAULT_STATIC_DIR = Path("frontend/dist")
NULLABLE_FEATURES = {
    "approval_delay_hours",
    "product_weight_g_total",
    "product_volume_cm3_total",
    "seller_customer_distance_km_min",
    "seller_customer_distance_km_mean",
    "seller_customer_distance_km_max",
}
NUMERIC_FEATURES = {
    column for column in MODEL_FEATURE_COLUMNS
    if column not in {
        "customer_state",
        "primary_product_category",
        "primary_seller_state",
        "primary_payment_type",
    }
}


class PredictRequest(BaseModel):
    """One approved order containing exactly the 30 Gold-v1 model features."""

    model_config = ConfigDict(extra="forbid")

    order_id: str | None = None
    purchase_year: int = Field(ge=2016, le=2018)
    purchase_month: int = Field(ge=1, le=12)
    purchase_day_of_week: int = Field(ge=0, le=6)
    purchase_hour: int = Field(ge=0, le=23)
    approval_delay_hours: float | None = Field(ge=0)
    approval_timestamp_missing: StrictBool
    promised_delivery_window_days: float = Field(ge=0)
    customer_state: str = Field(min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")
    item_row_count: int = Field(ge=1)
    distinct_product_count: int = Field(ge=1)
    distinct_seller_count: int = Field(ge=1)
    item_price_total: float = Field(ge=0)
    freight_value_total: float = Field(ge=0)
    product_weight_g_total: float | None = Field(ge=0)
    product_volume_cm3_total: float | None = Field(ge=0)
    product_measurement_missing_item_count: int = Field(ge=0)
    product_category_fallback_item_count: int = Field(ge=0)
    primary_product_category: str = Field(min_length=1)
    primary_seller_state: str = Field(min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")
    payment_row_count: int = Field(ge=0)
    distinct_payment_type_count: int = Field(ge=0)
    payment_value_total: float = Field(ge=0)
    max_payment_installments: int = Field(ge=0)
    primary_payment_type: str = Field(min_length=1)
    payment_data_missing: StrictBool
    customer_geolocation_missing: StrictBool
    seller_customer_distance_missing_count: int = Field(ge=0)
    seller_customer_distance_km_min: float | None = Field(ge=0)
    seller_customer_distance_km_mean: float | None = Field(ge=0)
    seller_customer_distance_km_max: float | None = Field(ge=0)

    @field_validator(*NUMERIC_FEATURES, mode="after")
    @classmethod
    def reject_non_finite_numbers(cls, value: Any) -> Any:
        if value is not None and isinstance(value, (int, float)) and not math.isfinite(value):
            raise ValueError("numeric values must be finite")
        return value


class HealthResponse(BaseModel):
    status: str
    model_name: str
    expected_feature_count: int


class PredictResponse(BaseModel):
    order_id: str | None = None
    risk_score: float = Field(ge=0, le=1)
    decision_threshold: float = Field(ge=0, le=1)
    predicted_delay: bool
    model_name: str


@dataclass(frozen=True)
class RuntimeArtifacts:
    pipeline: Any
    model_name: str
    threshold: float
    feature_columns: tuple[str, ...]


def _load_artifacts(model_path: Path, metrics_path: Path) -> RuntimeArtifacts:
    if not model_path.is_file():
        raise RuntimeError(f"Model artifact not found: {model_path}")
    if not metrics_path.is_file():
        raise RuntimeError(f"Metrics artifact not found: {metrics_path}")
    try:
        pipeline = joblib.load(model_path)
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - exercised through startup error
        raise RuntimeError(f"Unable to load inference artifacts: {exc}") from exc

    feature_columns = tuple(metrics.get("model_feature_columns", ()))
    if feature_columns != tuple(MODEL_FEATURE_COLUMNS):
        raise RuntimeError("Metrics model_feature_columns do not match Gold-v1")
    model_name = metrics.get("winner")
    threshold = metrics.get("selected_validation_threshold")
    if not isinstance(model_name, str) or threshold is None:
        raise RuntimeError("Metrics must contain winner and selected_validation_threshold")
    if not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise RuntimeError("Stored selected_validation_threshold must be finite and in [0, 1]")
    if not hasattr(pipeline, "predict_proba"):
        raise RuntimeError("Model artifact must provide predict_proba")
    return RuntimeArtifacts(pipeline, model_name, float(threshold), feature_columns)


def create_app(
    model_path: Path | str | None = None,
    metrics_path: Path | str | None = None,
    static_dir: Path | str | None = None,
    *,
    pipeline: Any | None = None,
    metrics: dict[str, Any] | None = None,
) -> FastAPI:
    """Create the API; optional injected artifacts keep tests independent of local files."""

    selected_model_path = Path(model_path or os.getenv("DELIVERY_DELAY_MODEL_PATH", DEFAULT_MODEL_PATH))
    selected_metrics_path = Path(metrics_path or os.getenv("DELIVERY_DELAY_METRICS_PATH", DEFAULT_METRICS_PATH))
    selected_static_dir = Path(static_dir or os.getenv("DELIVERY_DELAY_STATIC_DIR", DEFAULT_STATIC_DIR))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if pipeline is not None or metrics is not None:
            if pipeline is None or metrics is None:
                raise RuntimeError("pipeline and metrics must be injected together")
            feature_columns = tuple(metrics.get("model_feature_columns", ()))
            model_name = metrics.get("winner")
            threshold = metrics.get("selected_validation_threshold")
            if feature_columns != tuple(MODEL_FEATURE_COLUMNS) or not isinstance(model_name, str):
                raise RuntimeError("Injected metrics do not match the Gold-v1 contract")
            if not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or not 0 <= threshold <= 1:
                raise RuntimeError("Injected threshold must be finite and in [0, 1]")
            app.state.runtime = RuntimeArtifacts(pipeline, model_name, float(threshold), feature_columns)
        else:
            app.state.runtime = _load_artifacts(selected_model_path, selected_metrics_path)
        yield
        app.state.runtime = None

    app = FastAPI(title="Delivery Delay Inference", lifespan=lifespan)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Keep a valid JSON response even when a client submits non-finite JSON numbers.
        detail = []
        for error in exc.errors():
            value = error.get("input")
            if isinstance(value, float) and not math.isfinite(value):
                value = str(value)
            detail.append({
                "loc": error.get("loc"),
                "msg": error.get("msg"),
                "type": error.get("type"),
                "input": value,
            })
        return JSONResponse(status_code=422, content={"detail": detail})

    @app.get("/health", response_model=HealthResponse)
    async def health(request: Request) -> HealthResponse:
        runtime: RuntimeArtifacts = request.app.state.runtime
        return HealthResponse(
            status="ok",
            model_name=runtime.model_name,
            expected_feature_count=len(runtime.feature_columns),
        )

    @app.post("/predict", response_model=PredictResponse)
    async def predict(payload: PredictRequest, request: Request) -> PredictResponse:
        runtime: RuntimeArtifacts = request.app.state.runtime
        values = payload.model_dump(exclude={"order_id"})
        frame = pd.DataFrame([values], columns=list(runtime.feature_columns))
        try:
            probabilities = runtime.pipeline.predict_proba(frame)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Model prediction failed: {exc}") from exc
        if getattr(probabilities, "shape", None) != (1, 2):
            raise HTTPException(status_code=500, detail="Model must return exactly one binary score")
        score = float(probabilities[0, 1])
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise HTTPException(status_code=500, detail="Model returned an invalid risk score")
        return PredictResponse(
            order_id=payload.order_id,
            risk_score=score,
            decision_threshold=runtime.threshold,
            predicted_delay=bool(score >= runtime.threshold),
            model_name=runtime.model_name,
        )

    # Mount after the API routes so /health, /predict, /docs, and /openapi.json win.
    if selected_static_dir.is_dir():
        app.mount("/", StaticFiles(directory=selected_static_dir, html=True), name="frontend")

    return app


app = create_app()
