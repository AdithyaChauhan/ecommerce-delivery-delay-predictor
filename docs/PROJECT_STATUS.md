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
- Created the initial Git commit, `4d04780` (`chore: initialize project documentation`).

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
- `git log -1 --oneline --decorate` returned `4d04780 (HEAD -> main) chore: initialize project documentation`.
- `git status --short --branch` reported a clean working tree on `main` before the current approved status and ignore-rule edits.
- `git check-ignore -v --no-index data/.gitkeep data/raw/orders.csv .env models/model.joblib` confirmed that `data/.gitkeep`, raw data, environment secrets, and model artifacts are ignored.
- `git diff --check` passed after the current approved edits.
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

## Shareable handoff

Last updated: 2026-08-27

### Current milestone

Obtain the Olist dataset and inspect only its orders CSV without modifying it or inspecting the other source CSV files.

### Completed and verified

- Repository context scaffolding is complete.
- Change-control rules are present in `AGENTS.md`.
- The initial project documentation is committed in `4d04780` (`chore: initialize project documentation`).
- `.gitignore` no longer exempts `data/.gitkeep`; both `data/.gitkeep` and raw data paths are ignored.
- Data and application implementation have not started, and no application tests exist yet.

### Files changed

- `.gitignore`: removed the obsolete `data/.gitkeep` exception.
- `docs/PROJECT_STATUS.md`: corrected the Git evidence and added this shareable handoff.

### Commands and tests that passed

- `git log -1 --oneline --decorate`
- `git check-ignore -v --no-index data/.gitkeep data/raw/orders.csv .env models/model.joblib`
- `git diff --check`

### Git verification

Git state is intentionally not stored as a lasting fact here because it changes whenever files are staged or committed. When sharing this handoff, also include fresh output from:

- `git status --short --branch`
- `git log -1 --oneline --decorate`

### Blockers or uncertainties

- The dataset has not been obtained or inspected.
- The exact number and names of source CSV files are not yet verified in this repository.

### Next exact action

Obtain the Olist dataset, place it in the ignored local `data/raw/` directory, identify the orders CSV, and inspect only that file's columns, keys, data types, row count, and missing values without modifying it. Do not inspect the other source CSV files during this milestone.
