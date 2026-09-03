# Delivery Delay Prediction

This project will build an application for e-commerce operations teams that estimates the probability that an approved order will arrive after its promised delivery date.

## Current status

- The orders- and customers-file inspections and their `customer_id` relationship check are complete.
- Two of the nine source CSV files have been content-inspected: `olist_orders_dataset.csv` and `olist_customers_dataset.csv`. The other seven source CSV contents remain uninspected.
- The orders file contains 99,441 rows. The verified eligible training cohort contains 96,470 rows: 6,534 late orders (6.773090%) and 89,936 on-time orders (93.226910%).
- The customers file contains 99,441 well-formed rows and no missing values. Every order joins to exactly one customer record through `customer_id`, producing 99,441 joined rows with no lost or multiplied orders.
- No application code, processed dataset, joined dataset, or model has been created.
- The next exact action is to inspect only the header and first three rows of `data/raw/olist_order_items_dataset.csv`.

## Prediction contract

- Prediction time: immediately after an order is approved.
- Target: `delay_flag = 1` when the actual delivered calendar date is later than the estimated calendar date; otherwise, `delay_flag = 0`.
- Training population: orders with `order_status` equal to `delivered` and valid actual and estimated delivery dates.
- Feature rule: use only information available at prediction time.
- Identifier rule: customer identifiers will not be direct model features.
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
- `docs/PROJECT_STATUS.md`: verified progress, decisions, evidence, blockers, and the next exact action.
- `README.md`: public project overview and setup instructions as they become available.

Raw datasets, generated artifacts, credentials, and local environment files must not be committed.
