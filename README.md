# Delivery Delay Prediction

This project will build an application for e-commerce operations teams that estimates the probability that an approved order will arrive after its promised delivery date.

## Current status

- All nine source CSV files have been audited; detailed evidence is recorded in `docs/DATA_AUDIT.md`.
- The verified eligible cohort contains 96,470 orders: 6,534 late orders (6.773090%) and 89,936 on-time orders (93.226910%).
- No application code, processed dataset, model, API, or deployment exists.
- The next milestone is the reproducible local Gold-v1 dataset builder.

## Prediction contract

- Prediction time: immediately after an order is approved.
- Target: `delay_flag = 1` when the actual delivered calendar date is later than the estimated calendar date; otherwise, `delay_flag = 0`.
- Training population: orders with `order_status` equal to `delivered` and valid actual and estimated delivery dates.
- Feature rule: use only information available at prediction time.
- Identifier rule: customer identifiers will not be direct model features.
- Item aggregation rule: aggregate item rows to one row per order before joining the model-training table; verified candidates are item-row count, distinct product count, distinct seller count, total price, and total freight.
- Shipping-limit rule: `shipping_limit_date` is the seller's deadline for handing the order to the logistics partner. Preserve its raw values, but exclude it from Gold-v1 because its availability at the exact prediction moment is not verified and its observed values contain anomalies.
- Exclusions: reviews and all post-approval events.
- Evaluation: use a time-based train/test split.

These decisions prevent information from the future from leaking into the model.

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
- `docs/DATA_AUDIT.md`: verified raw-data structure, quality, relationships, aggregation requirements, and exclusions.
- `docs/PROJECT_STATUS.md`: verified progress, decisions, evidence, blockers, and the next exact action.
- `README.md`: public project overview and setup instructions as they become available.

Raw datasets, generated artifacts, credentials, and local environment files must not be committed.
