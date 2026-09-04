# Delivery Delay Prediction

This project will build an application for e-commerce operations teams that estimates the probability that an approved order will arrive after its promised delivery date.

## Current status

- All nine source CSV files have been audited; detailed evidence is recorded in `docs/DATA_AUDIT.md`.
- The verified eligible cohort contains 96,470 orders: 6,534 late orders (6.773090%) and 89,936 on-time orders (93.226910%).
- The reproducible local Gold-v1 builder and 15 synthetic tests are implemented. Its ignored Parquet output contains exactly one row for each eligible order.
- The verified Brazil coordinate envelope rejected 31 raw geolocation rows across 20 ZIP prefixes; four ZIP prefixes lost all coordinates, 265 orders lack customer coordinates, and 477 lack a seller-to-customer distance.
- No model, API, frontend, cloud resource, or deployment exists.
- The next milestone is to approve the corrected Gold-v1 dataset contract before model training.

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
```

PowerShell activation alternative:

```powershell
.\.venv\Scripts\Activate.ps1
```

The raw CSVs and generated Parquet output remain local and ignored by Git.

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
- `tests/test_gold_v1.py`: synthetic tests that do not require raw Olist data.
- `docs/DATA_AUDIT.md`: verified raw-data structure, quality, relationships, aggregation requirements, and exclusions.
- `docs/PROJECT_STATUS.md`: verified progress, decisions, evidence, blockers, and the next exact action.
- `README.md`: public project overview and setup instructions as they become available.

Raw datasets, generated artifacts, credentials, and local environment files must not be committed.
