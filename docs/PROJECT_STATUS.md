# Project Status

Last updated: 2026-09-03

## Project goal

Build an application that predicts whether an approved e-commerce order will arrive after its promised delivery date.

## Current phase

The orders- and customers-file inspections and their `customer_id` relationship check are complete. Two of the nine source CSV files have been content-inspected. No application code, processed dataset, joined dataset, or model has been created.

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
- Defined `delay_flag = 1` when the actual delivered calendar date is later than the estimated calendar date; otherwise, `delay_flag = 0`.
- Defined the initial leakage restrictions.
- Chose a time-based train/test split.
- Initialized a local Git repository on the `main` branch.
- Created the repository context and progress-tracking documents.
- Created initial ignore rules for datasets, secrets, caches, build output, and generated artifacts.
- Verified that `.gitignore` is located inside the repository root.
- Created the initial Git commit, `4d04780` (`chore: initialize project documentation`).
- Verified that nine source CSV files exist under the ignored `data/raw/` directory.
- Content-inspected `olist_orders_dataset.csv` and `olist_customers_dataset.csv`; the other seven source CSV contents remain uninspected.
- Verified 99,441 rows and 99,441 unique `order_id` values, with no duplicate `order_id` values, malformed rows, or unparseable timestamps.
- Verified an eligible training cohort of 96,470 delivered orders with valid actual and estimated delivery dates.
- Verified 6,534 late orders (6.773090%) and 89,936 on-time orders (93.226910%) in the eligible cohort.
- Verified that eight delivered orders lack an actual delivery date, six non-delivered orders contain an actual delivery date, and fourteen eligible orders lack `order_approved_at`.
- Verified that the customers file contains 99,441 well-formed rows and no missing values.
- Verified that `customer_id` is unique in both the orders and customers files.
- Every order joins to exactly one customer record through `customer_id`. The verified join contains 99,441 rows, with no lost or multiplied orders.
- Verified 96,096 distinct `customer_unique_id` values: 93,099 are linked to one order and 2,997 are linked to multiple orders.
- Verified that the 2,997 multi-order customers account for 6,342 orders, with a maximum of 17 orders linked to one `customer_unique_id`.
- Verified 14,994 distinct `customer_zip_code_prefix` values, and every ZIP-prefix row value contains exactly five digits.
- Verified that 23,995 ZIP-prefix row values begin with zero, so `customer_zip_code_prefix` must be stored as a string.
- Verified 4,119 distinct `customer_city` values and 27 distinct `customer_state` values.

## In progress

Nothing currently in progress.

## Next exact action

Inspect only `data/raw/olist_order_items_dataset.csv`, beginning with its header and first three rows. Do not inspect the contents of any other source CSV during this milestone.

## Verified decisions

- Target: `delay_flag = 1` when the actual delivered calendar date is later than the estimated calendar date; otherwise, `delay_flag = 0`.
- Train only on orders with `order_status` equal to `delivered` and valid actual and estimated delivery dates.
- Exclude reviews and post-approval events from model inputs.
- Use only information available at order approval time.
- Do not use customer identifiers as direct model features.
- Use a time-based train/test split.
- Save preprocessing and the eventual model together as one pipeline.
- Raw datasets, credentials, and `.env` files must not be committed.
- Keep SHAP explanations optional until the core system works.
- Inspect source CSV files one at a time; the next inspection is limited to the header and first three rows of `data/raw/olist_order_items_dataset.csv`.

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
- `$csvFiles = Get-ChildItem -LiteralPath 'data/raw' -File -Filter '*.csv'; Write-Output ('CSV_COUNT=' + $csvFiles.Count)` returned `CSV_COUNT=9` without reading CSV contents.
- Python standard-library scans executed through `$analysisCode | python -` inspected only `data/raw/olist_orders_dataset.csv` and produced the verified structural and target results recorded above.
- `git status --short --branch` returned `## main` after the orders-file inspection.
- A Python standard-library scan executed through `$analysisCode | python -` inspected only `data/raw/olist_customers_dataset.csv` and produced the verified customer-file results recorded above.
- A Python standard-library relationship check executed through `$analysisCode | python -` read only `customer_id` from the orders file and `customer_id` plus `customer_unique_id` from the customers file. It verified that every order joins to exactly one customer record and that the join contains 99,441 rows.
- `git status --short --branch` returned `## main` after the customers-file inspection and relationship check.
- No application tests exist yet.

## Known issues or blockers

- The contents of the other seven source CSV files have not been inspected.

## Results not yet available

- Content profiles for the other seven source CSV files
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

Last updated: 2026-09-03

### Current milestone

The orders- and customers-file inspections and their `customer_id` relationship check are complete. The next milestone is to inspect only the header and first three rows of `data/raw/olist_order_items_dataset.csv`.

### Completed and verified

- Repository context scaffolding is complete.
- Change-control rules are present in `AGENTS.md`.
- The initial project documentation is committed in `4d04780` (`chore: initialize project documentation`).
- `.gitignore` no longer exempts `data/.gitkeep`; both `data/.gitkeep` and raw data paths are ignored.
- Nine source CSV files exist under the ignored `data/raw/` directory. `olist_orders_dataset.csv` and `olist_customers_dataset.csv` have been content-inspected; the other seven source CSV contents remain uninspected.
- The orders file contains 99,441 rows and 99,441 unique `order_id` values, with no duplicate `order_id` values, malformed rows, or unparseable timestamps.
- The eligible training cohort contains 96,470 delivered orders with valid actual and estimated delivery dates.
- `delay_flag = 1` when the actual delivered calendar date is later than the estimated calendar date; otherwise, `delay_flag = 0`.
- The eligible cohort contains 6,534 late orders (6.773090%) and 89,936 on-time orders (93.226910%).
- Eight delivered orders lack an actual delivery date, six non-delivered orders contain an actual delivery date, and fourteen eligible orders lack `order_approved_at`.
- The customers file contains 99,441 well-formed rows and no missing values.
- `customer_id` is unique in both files. Every order joins to exactly one customer record through `customer_id`, producing 99,441 joined rows with no lost or multiplied orders.
- The verified join contains 96,096 distinct `customer_unique_id` values: 93,099 are linked to one order and 2,997 are linked to multiple orders.
- The 2,997 multi-order customers account for 6,342 orders, and the maximum number of orders linked to one `customer_unique_id` is 17.
- There are 14,994 distinct ZIP prefixes, and every ZIP-prefix row value contains exactly five digits.
- There are 23,995 ZIP-prefix row values beginning with zero, so the ZIP prefix must be stored as a string.
- There are 4,119 distinct cities and 27 distinct states.
- Customer identifiers will not be direct model features.
- No application code, processed dataset, joined dataset, or model has been created, and no application tests exist yet.
- `git status --short --branch` returned `## main` after the customers-file inspection and relationship check.

### Files changed

- `README.md`: updated the current status and refined the prediction contract.
- `docs/PROJECT_STATUS.md`: recorded the completed customers-file inspection and relationship check and refreshed this shareable handoff.

### Commands and tests that passed

- `$csvFiles = Get-ChildItem -LiteralPath 'data/raw' -File -Filter '*.csv'; Write-Output ('CSV_COUNT=' + $csvFiles.Count)` returned `CSV_COUNT=9`.
- Python standard-library scans executed through `$analysisCode | python -` inspected only the orders CSV and returned the verified structure and target results.
- A Python standard-library scan executed through `$analysisCode | python -` inspected only the customers CSV and returned the verified customer-file results.
- A Python standard-library relationship check executed through `$analysisCode | python -` used only the required customer identifier columns from the orders and customers files and returned the verified relationship results.
- `git status --short --branch` returned `## main` after the customers-file inspection and relationship check.

### Git verification

Git state is intentionally not stored as a lasting fact here because it changes whenever files are staged or committed. When sharing this handoff, also include fresh output from:

- `git status --short --branch`
- `git log -1 --oneline --decorate`

### Blockers or uncertainties

- The contents of the other seven source CSV files remain uninspected.

### Next exact action

Inspect only `data/raw/olist_order_items_dataset.csv`, beginning with its header and first three rows. Do not inspect the contents of any other source CSV during this milestone.
