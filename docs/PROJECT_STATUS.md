# Project Status

Last updated: 2026-08-27

## Project goal

Build an application that predicts whether an approved e-commerce order will arrive after its promised delivery date.

## Current phase

Repository context scaffolding is complete. Data and application implementation have not started.

## Locked architecture

```text
Olist CSV files -> S3 Bronze -> AWS Glue -> S3 Silver Parquet
-> Snowflake Gold table -> ML pipeline -> FastAPI + React
-> Docker -> EKS -> GitHub Actions
```

Development and validation will happen locally before cloud services are introduced.

## Completed

- Selected the delivery-delay prediction problem.
- Defined the prediction moment as immediately after order approval.
- Defined the initial target and leakage restrictions.
- Chose a time-based train/test split.
- Initialized a local Git repository on the `main` branch.
- Created the repository context and progress-tracking documents.
- Created initial ignore rules for datasets, secrets, caches, build output, and generated artifacts.
- Verified that `.gitignore` is located inside the repository root.

## In progress

Nothing currently in progress.

## Next exact action

Obtain the Olist dataset, place it in the ignored local `data/raw/` directory, identify the orders CSV, and inspect only that file's columns, keys, data types, row count, and missing values without modifying it. Do not inspect the other source CSV files during this milestone.

## Verified decisions

- Target: the delivered calendar date is later than the estimated delivery calendar date.
- Train only on delivered orders.
- Exclude reviews and post-approval events from model inputs.
- Use only information available at order approval time.
- Use a time-based train/test split.
- Save preprocessing and the eventual model together as one pipeline.
- Raw datasets, credentials, and `.env` files must not be committed.
- Keep SHAP explanations optional until the core system works.
- Limit the first data-inspection milestone to the orders CSV; do not inspect all source files together.

## Verified commands and tests

- `rg --files -g '*'` returned no files before scaffolding was created.
- `git status --short --branch` reported that the starting folder was not a Git repository.
- `git init -b main` initialized the local repository successfully.
- File existence and size checks confirmed that `.gitignore`, `AGENTS.md`, `README.md`, and `docs/PROJECT_STATUS.md` exist and are non-empty.
- `git check-ignore -v --no-index data/raw/orders.csv .env models/model.joblib` confirmed that raw data, environment secrets, and model artifacts are ignored.
- `git rev-parse --show-toplevel` returned `C:/Users/Chauhan/OneDrive/Desktop/All-projects/Delivery`, and the root listing showed `.gitignore` directly inside that directory.
- `git status --short --branch` reports an uncommitted repository on `main` containing only the four scaffold files.
- No application tests exist yet.

## Known issues or blockers

- The dataset has not been obtained or inspected.
- The exact number and names of source CSV files are not yet verified in this repository.

## Results not yet available

- Source file count and names
- Row counts, keys, data types, and missing-value profile
- Delayed-order percentage
- Model metrics
- API or interface test results
- AWS, Snowflake, Docker, EKS, or CI deployment status
- Cloud cost

## Session handoff prompt

Use this in a new Codex chat:

```text
Read AGENTS.md, README.md, and docs/PROJECT_STATUS.md completely. Then inspect
the repository tree, git status, and the five most recent commits. Do not edit
anything yet. Tell me the current verified project stage, what has actually
been completed, any contradictions between the documentation and repository,
and the single next action. Treat code, data, test results, and command output
as stronger evidence than documentation or chat history.
```

## End-of-session checklist

1. Run the checks or tests relevant to the session's milestone.
2. Inspect `git diff` and `git status`.
3. Update this file using only verified facts.
4. Record completed work, successful commands or tests, blockers, and one next action.
5. Do not claim unfinished work is complete.
