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
- The minimal Vite/React dashboard is implemented under `frontend/` and displays eight synthetic order-risk predictions.
- The verified Bronze batch is stored in S3 bucket `delivery-delay-bronze-olist-ap-southeast-1-20260905-7f3c9a2d` in `ap-southeast-1` under `bronze/2026-09-05/batch-001/`; exactly nine unchanged CSVs were uploaded, with `archive.zip` excluded and checksums recorded in the tracked ingestion manifest.
- The verified Silver batch was built by AWS Glue 5.0 native PySpark from the Bronze inputs and stored as versioned Parquet in `ap-southeast-1`; it contains 96,470 rows, 33 columns, 6,534 late orders, and 89,936 on-time orders, and reconciles exactly to local Gold-v1. Reviews are excluded to prevent prediction-time leakage. See [`manifests/silver/2026-09-05/batch-001.json`](manifests/silver/2026-09-05/batch-001.json) for metadata.
- The endpoint is a historical demonstration of the 2016–2018 Model-v2 artifacts; current orders require newer training data and retraining.
- Bronze/Silver S3 and an on-demand Glue job exist, but no continuously running cloud application deployment exists. Further model tuning is outside the MVP.
- The verified Silver Parquet is queryable through a Snowflake external table in `AWS_AP_SOUTHEAST_1`, and the verified Gold snapshot is materialized as a native Snowflake table; Silver remains in private S3.
- The verified private Model-v2 release is stored in S3 bucket `delivery-delay-model-artifacts-ap-southeast-1-20260908-7f3c9a2d` in `ap-southeast-1` under `models/delay-risk/v2/release-001/`. It contains exactly the two runtime artifacts required by the API and Docker image, with versioned checksums recorded in [`manifests/model/delay-risk/v2/release-001.json`](manifests/model/delay-risk/v2/release-001.json); binary model files remain ignored and uncommitted.

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

From a second terminal, run the frontend:

```bash
cd frontend
npm ci
npm run dev
npm test -- --run
npm run build
```

The verified frontend environment is Node.js `v24.20.0` with npm `11.19.0`; `npm install` and `npm ci` completed cleanly with no engine or peer-dependency errors.

PowerShell activation alternative:

```powershell
.\.venv\Scripts\Activate.ps1
```

The raw CSVs, generated Parquet output, and model artifacts remain local and ignored by Git. Training saves the exact evaluated preprocessing-plus-XGBoost pipeline to `models/delay_xgboost_pipeline.joblib`; Model-v2 comparison artifacts are also ignored. Model outputs are delay-risk scores, not calibrated probabilities. The fixed chronological test period was already observed during baseline development and is not an untouched final holdout.

While the API is running, open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for generated documentation. `POST /predict` accepts one JSON object containing all 30 model features; `order_id` is optional metadata and is never sent to the model. A synthetic request is provided at `examples/predict_request.json`.

The dashboard uses the Vite proxy for relative `/health` and `/predict` requests. All displayed orders are synthetic historical-demo data; displayed values are risk scores, not probabilities.

## Local Docker image

Docker packages the compiled dashboard and FastAPI service in one non-root container. The local build uses the ignored Model-v2 artifacts already present in `models/`; they are copied into the image but are not committed to Git.

```bash
docker build -t delivery-delay:local .
docker run --rm -p 8000:8000 delivery-delay:local
```

The image serves the dashboard at `/`, with `/health`, `/predict`, `/docs`, and `/openapi.json` available on port 8000. GitHub Actions downloads approved model artifacts from controlled storage before running `docker build`; model files remain excluded from Git.

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

Local development and validation precede paid cloud services. The verified Bronze, Silver, Snowflake external-table, native Gold snapshot, private Model-v2 artifact release, and CI/ECR security milestones are complete; the runtime target is evaluated before assuming EKS.

## Verified Silver / AWS Glue milestone

AWS Glue 5.0 native PySpark transforms the versioned Bronze batch into versioned Parquet Silver. The output reconciles to local Gold-v1 at 96,470 rows and 33 columns, with 6,534 late and 89,936 on-time orders. The reviews input is intentionally excluded because it occurs after prediction time.

## Verified Snowflake Silver milestone

Snowflake in `AWS_AP_SOUTHEAST_1` exposes the verified Silver Parquet through a private S3 external stage and the `ORDER_FEATURES_V1_EXT` external table. The X-Small warehouse uses 60-second auto-suspend and is suspended after validation. The external table has exactly 33 explicit columns and reconciles to 96,470 rows, 96,470 distinct orders, 6,534 late orders, and 89,936 on-time orders. The native `DELIVERY_DELAY_DB.GOLD.ORDER_FEATURES_V1` table is a verified 96,470-row Snowflake-managed snapshot; no live-production claim is made.

## Verified Snowflake Gold milestone

The native Gold table has exactly 33 columns in the verified Silver order, 96,470 rows, 96,470 unique order IDs, 6,534 late orders, 89,936 on-time orders, and zero invalid or NULL delay flags. Silver MINUS Gold and Gold MINUS Silver both returned zero differences across all 33 columns. The table is SYSADMIN-owned, non-external, retains data for 1 day, has schema evolution, change tracking, automatic clustering, and search optimization disabled, and reports 5,623,808 bytes. Query Acceleration Service is disabled and the X-Small warehouse finished suspended. No tasks, streams, Snowpipe, automatic refresh, or automatic per-batch model retraining were created.

## Verified private Model-v2 artifact release

The API and Docker runtime require only `delay_model_v2_pipeline.joblib` and `delay_model_v2_metrics.json`. Release `release-001` stores those exact files privately in versioned S3 with public access blocked, `BucketOwnerEnforced` ownership, versioning enabled, default AES256 encryption, and `Project=delivery-delay`, `Environment=dev`, and `Layer=model-artifacts` tags. Local and downloaded SHA-256 hashes and bytes matched; the metadata-only release manifest records the exact keys, sizes, checksum forms, version IDs, ETags, encryption, and content types. The manifest was uploaded once to `manifests/model/delay-risk/v2/release-001.json` without overwrite; its exact S3 version is 2,694 bytes, AES256-encrypted JSON, and byte-for-byte identical to the local manifest. This enables future reproducible CI builds without committing binary model files.

## Verified CI/ECR security milestone

Commit `4d22e0a` added the fail-closed ECR vulnerability policy, and GitHub Actions completed successfully for that commit. The private immutable image tag `sha-4d22e0a9a00ebfc722e4c3c00d7a571316ef788d` has digest `sha256:b357d7ea91ea53dd6c35d8854fecad8add6e7057c2af1ebfc4be325355b29619`. Its compressed size is 158,716,554 bytes. The base image was hardened and slimmed from 669,163,824 bytes to 158,716,042 bytes (76.28% smaller) in the prior commit `f33c05a`; this commit leaves that size effectively unchanged (+512 bytes) while adding the vulnerability gate.

The `linux/amd64` scan reported 6 CRITICAL, 11 HIGH, 3 MEDIUM, and 1 LOW findings. The 17 CRITICAL/HIGH findings are reviewed temporary exceptions matched by exact CVE, severity, package, and installed version, with review/expiry on 2026-10-11; vulnerabilities were not removed and the image does not have zero vulnerabilities. CI verifies the pinned Dockerfile base and fails on unexpected, mismatched, expired, duplicate, malformed, or stale CRITICAL/HIGH entries. It publishes to private immutable ECR through GitHub OIDC. The validator, allowlist, independent fixture, and policy tests are `scripts/validate_ecr_scan.py`, `security/ecr-scan-allowlist.json`, `tests/fixtures/ecr-scan-f33c05a-high-critical.json`, and `tests/test_ecr_scan_policy.py`. No cloud application runtime is deployed yet.

## Verified live deployment

The immutable image is deployed on AWS ECS Fargate (cluster `delivery-delay-cluster`, service `delivery-delay-svc`, task family `delivery-delay-task`). On 2026-09-11, `/health` and `/predict` both returned correct responses from the running task's public IP. The IP is ephemeral and changes on redeploy; no load balancer or Elastic IP is set up yet.

## Repository guide

- `AGENTS.md`: permanent working rules for Codex.
- `delivery_delay/gold_v1.py`: validated local Gold-v1 builder and command-line entry point.
- `delivery_delay/train.py`: reproducible chronological split, preprocessing, baseline, XGBoost training, threshold selection, evaluation, and artifact saving.
- `delivery_delay/api.py`: local FastAPI health and single-order inference endpoints using the saved Model-v2 artifacts.
- `glue/silver_job.py`: native PySpark Silver transformation used by AWS Glue 5.0.
- `tests/test_gold_v1.py`: synthetic tests that do not require raw Olist data.
- `tests/test_train.py`: synthetic training, leakage, preprocessing, threshold, metrics, and artifact tests.
- `tests/test_api.py`: synthetic API contract and validation tests independent of ignored artifacts.
- `tests/test_silver_job.py`: focused Silver schema, parser, aggregation, and writer tests.
- `scripts/validate_ecr_scan.py`: fail-closed ECR CRITICAL/HIGH scan-policy validator.
- `security/ecr-scan-allowlist.json`: reviewed temporary ECR scan exceptions.
- `tests/fixtures/ecr-scan-f33c05a-high-critical.json`: independent ECR scan fixture.
- `tests/test_ecr_scan_policy.py`: synthetic ECR scan-policy tests.
- `frontend/`: Vite/React dashboard, synthetic demo orders, proxy configuration, and Vitest/React Testing Library tests.
- `docs/DATA_AUDIT.md`: verified raw-data structure, quality, relationships, aggregation requirements, and exclusions.
- `docs/PROJECT_STATUS.md`: verified progress, decisions, evidence, blockers, and the next exact action.
- `manifests/bronze/2026-09-05/batch-001.json`: verified Bronze ingestion metadata.
- `manifests/silver/2026-09-05/batch-001.json`: verified Silver Glue run, schema, reconciliation, and S3 object metadata.
- `manifests/model/delay-risk/v2/release-001.json`: verified private Model-v2 artifact release metadata and reconciliation.
- `snowflake/`: idempotent foundation, storage integration, external stage, 33-column external table, native Gold snapshot, validation SQL, and junior-friendly execution/rollback notes.
- `README.md`: public project overview and setup instructions as they become available.

Raw datasets, generated artifacts, credentials, and local environment files must not be committed.
