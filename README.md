# Delivery Delay Prediction

This project will build an application for e-commerce operations teams that estimates the probability that an approved order will arrive after its promised delivery date.

## Current status

Project setup is complete. Application and data-pipeline implementation have not started.

The next milestone is to obtain the Olist dataset and inspect only its orders CSV. The other source files will remain untouched during this milestone. No dataset statistics, model results, or deployment results are available yet.

## Prediction contract

- Prediction time: immediately after an order is approved.
- Target: whether the delivered calendar date is later than the estimated delivery calendar date.
- Training population: delivered orders only.
- Feature rule: use only information available at prediction time.
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
