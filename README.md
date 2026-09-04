# Delivery Delay Prediction

This project will build an application for e-commerce operations teams that estimates the probability that an approved order will arrive after its promised delivery date.

## Current status

- All nine source CSV files have been audited; detailed evidence is recorded in `docs/DATA_AUDIT.md`.
- The verified eligible cohort contains 96,470 orders: 6,534 late orders (6.773090%) and 89,936 on-time orders (93.226910%).
- The reproducible local Gold-v1 builder and 15 synthetic tests are implemented. Its ignored Parquet output contains exactly one row for each eligible order.
- The verified Brazil coordinate envelope rejected 31 raw geolocation rows across 20 ZIP prefixes; four ZIP prefixes lost all coordinates, 265 orders lack customer coordinates, and 477 lack a seller-to-customer distance.
- Three models were compared using validation average precision: XGBoost baseline 0.139615, shallow regularized XGBoost 0.127092, and balanced LogisticRegression 0.113171. The existing XGBoost baseline was retained.
- On the fixed, previously observed test period, the retained model scored ROC-AUC 0.584928 and average precision 0.065252. Its top 5% contains 63 late orders out of 724, with 8.701657% precision and 2.030995x lift over the 4.284431% test prevalence.
- The minimal local FastAPI inference service is implemented with `GET /health` and `POST /predict`.
- The endpoint is a historical demonstration of the 2016–2018 Model-v2 artifacts; current orders require newer training data and retraining.
- No frontend, cloud resource, or deployment exists. Further model tuning is outside the MVP.

## Prediction contract

- Prediction time: immediately after an order is approved.
- Target: `delay_flag = 1` when the actual delivered calendar date is later than the estimated calendar date; otherwise, `delay_flag = 0`.
- Training population: orders with `order_status` equal to `delivered` and valid actual and estimated delivery dates.
- Feature rule: use only information available at prediction time.
- Identifier rule: direct identifiers and raw row keys are not model features.
- Item aggregation rule: aggregate item rows to one row per order before joining the model-training table; verified candidates are item-row count, distinct product count, distinct seller count, total price, and total freight.
- Payment assumption: prediction occurs immediately after payment approval, so payment type, value, and installments are treated as available at prediction time. Payment rows are aggregated before joining, and the eligible order without payment data is retained.
- Geolocation rule: parse coordinates numerically, reject observations outside a conservative inclusive Brazil envelope based on [IBGE's published geographic extremes](https://brasilemsintese.ibge.gov.br/territorio/dados-geograficos.html), deduplicate valid ZIP/latitude/longitude triples, calculate coordinate-wise ZIP medians, preserve missing coverage, and aggregate distinct-seller distances to order level. This removes coordinates outside Brazil but cannot detect every plausible-looking coordinate assigned to the wrong in-country location.
- Shipping-limit rule: `shipping_limit_date` is the seller's deadline for handing the order to the logistics partner. Preserve its raw values, but exclude it from Gold-v1 because its availability at the exact prediction moment is not verified and its observed values contain anomalies.
- Exclusions: reviews and all post-approval events.
- Evaluation: use a time-based train/test split.

These decisions prevent information from the future from leaking into the model.

## Local setup and Gold-v1 build

From Git Bash on Windows:

```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -r requirements.txt
python -m pytest -q
python -m delivery_delay.gold_v1 --raw-dir data/raw --output data/processed/gold_v1.parquet
python -m delivery_delay.train --gold data/processed/gold_v1.parquet --artifacts-dir models
python -m uvicorn delivery_delay.api:app --reload
```

PowerShell activation alternative:

```powershell
.\.venv\Scripts\Activate.ps1
```

The raw CSVs, generated Parquet output, and model artifacts remain local and ignored by Git. Training saves the exact evaluated preprocessing-plus-XGBoost pipeline to `models/delay_xgboost_pipeline.joblib`; Model-v2 comparison artifacts are also ignored. Model outputs are delay-risk scores, not calibrated probabilities. The fixed chronological test period was already observed during baseline development and is not an untouched final holdout.

While the API is running, open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for generated documentation. `POST /predict` accepts one JSON object containing all 30 model features; `order_id` is optional metadata and is never sent to the model. A synthetic request is provided at `examples/predict_request.json`.

## Planned architecture

```text
Olist CSV files
  -> Amazon S3 Bronze
  -> AWS Glue
  -> Amazon S3 Silver (Parquet)
  -> Snowflake Gold table
  -> ML pipeline
  -> FastAPI API + React interface
  -> Docker
  -> Amazon EKS
  -> GitHub Actions
```

Local development and validation come before cloud implementation. Each layer will be introduced only when its milestone begins.

## Repository guide

- `AGENTS.md`: permanent working rules for Codex.
- `delivery_delay/gold_v1.py`: validated local Gold-v1 builder and command-line entry point.
- `delivery_delay/train.py`: reproducible chronological split, preprocessing, baseline, XGBoost training, threshold selection, evaluation, and artifact saving.
- `delivery_delay/api.py`: local FastAPI health and single-order inference endpoints using the saved Model-v2 artifacts.
- `tests/test_gold_v1.py`: synthetic tests that do not require raw Olist data.
- `tests/test_train.py`: synthetic training, leakage, preprocessing, threshold, metrics, and artifact tests.
- `tests/test_api.py`: synthetic API contract and validation tests independent of ignored artifacts.
- `docs/DATA_AUDIT.md`: verified raw-data structure, quality, relationships, aggregation requirements, and exclusions.
- `docs/PROJECT_STATUS.md`: verified progress, decisions, evidence, blockers, and the next exact action.
- `README.md`: public project overview and setup instructions as they become available.

Raw datasets, generated artifacts, credentials, and local environment files must not be committed.
