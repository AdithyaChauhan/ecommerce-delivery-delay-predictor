# Project Status

Last updated: 2026-09-05

## Project goal

Build an application that predicts whether an approved e-commerce order will arrive after its promised delivery date.

## Current phase

The reproducible local Gold-v1 builder and its synthetic tests are implemented. The verified geolocation correction removes coordinates outside a conservative Brazil envelope while preserving affected orders with missing geographic features. The rebuilt ignored Parquet output passed the locked cohort and target checks. The baseline and bounded Model-v2 experiment are trained and verified with a chronological split; the existing XGBoost baseline was retained by validation average precision. The minimal local FastAPI inference service and Vite/React dashboard are implemented and smoke-tested against the saved Model-v2 artifacts. Further model tuning is complete for the MVP. No cloud resource or deployment exists.

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
- Completed the read-only audit of all nine source CSV files. Detailed evidence is recorded in `docs/DATA_AUDIT.md`.
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
- Verified that the order-items file contains 112,650 well-formed rows with no missing values, representing 98,666 distinct orders.
- Verified that `(order_id, order_item_id)` is unique and that item IDs form a continuous sequence from `1` through `N` within every order.
- Verified that 88,863 orders contain one item row and 9,803 contain multiple item rows, with a maximum of 21 item rows for one order.
- Verified 32,951 distinct products and 3,095 distinct sellers.
- Verified that 3,236 orders contain multiple distinct products, 1,278 contain multiple distinct sellers, and 6,968 contain repeated rows for the same product.
- Every item row matches exactly one order record. All 112,650 item rows matched, with no unmatched or multiplied item rows.
- Verified that 775 orders have no item rows: 603 unavailable, 164 canceled, 5 created, 2 invoiced, and 1 shipped.
- Verified that every one of the 96,470 eligible training orders has item data, producing 110,189 item rows before aggregation.
- Verified that all price and freight values are parseable and nonnegative; freight is zero in 383 rows.
- Verified that `shipping_limit_date` is earlier than approval in 127 item rows, later than estimated delivery in 372 item rows, and dated 2019 or later in 4 item rows.
- Verified 32,951 well-formed product rows with unique `product_id` values. Every product used by order items exists, and no product is unused.
- Verified 3,095 well-formed seller rows with unique `seller_id` values and no missing values. Every seller used by order items exists, and no seller is unused.
- Verified 103,886 well-formed payment rows with unique (`order_id`, `payment_sequential`) values and no missing values. Every payment row matches an order record, but one eligible order has no payment row.
- Verified 1,000,163 well-formed geolocation rows with no missing values, 19,015 ZIP prefixes, and 261,831 exact duplicate occurrences beyond the first. Geolocation lacks 157 customer ZIP prefixes and 7 seller ZIP prefixes.
- Verified that every geolocation coordinate parses and falls within global valid latitude and longitude ranges. Observed extremes create coordinate-outlier risk, so Gold-v1 requires a documented, outlier-resistant ZIP-level representative coordinate.
- Verified 71 complete, unique category translations. Two used product categories lack translations, and no translation entry is unused.
- Verified 99,224 well-formed review rows and a unique (`review_id`, `order_id`) composite key. Review-to-order coverage and detailed review profiling were intentionally not performed.
- All reconciliation checks that were performed and reported passed. No unperformed relationship check is included in that conclusion.
- Added `requirements.txt` with the approved pandas 3.0.5, PyArrow 25.0.1, and pytest 9.1.1 dependency pins.
- Implemented `delivery_delay/gold_v1.py` as a functional pandas and argparse builder. It reads the eight approved source CSVs through an explicit filename map and never reads reviews or `archive.zip`.
- Defined two metadata columns, an explicit 30-column model-feature whitelist, and `delay_flag` as the target. Runtime checks prevent identifiers, post-approval fields, reviews, `shipping_limit_date`, and the target from entering the feature whitelist.
- Documented the assumption that prediction occurs immediately after payment approval, so payment type, value, and installments are available at prediction time.
- Implemented validated one-to-one and many-to-one merges, order-level item and payment aggregation, a left payment join, and deterministic primary category, seller, and payment selection.
- Implemented numeric coordinate parsing before geolocation filtering and deduplication. Coordinates outside global latitude or longitude ranges still fail validation.
- Implemented an inclusive Brazil envelope of latitude `[-34.0, 6.0]` and longitude `[-74.0, -28.0]`, based on [IBGE's published Brazilian geographic extremes](https://brasilemsintese.ibge.gov.br/territorio/dados-geograficos.html) with a small practical margin and eastern allowance for offshore territory.
- Geolocation observations outside that envelope are rejected before valid numeric (`geolocation_zip_code_prefix`, `geolocation_lat`, `geolocation_lng`) triples are deduplicated and coordinate-wise ZIP medians are calculated. ZIPs without remaining coordinates and affected orders are retained through left joins with missing geographic features.
- Verified that 31 raw geolocation rows and 27 distinct coordinate triples fall outside the Brazil envelope. They involve 20 ZIP prefixes, and 4 ZIP prefixes have no valid coordinate afterward.
- Implemented clamped Haversine distance and one distance per distinct order-seller pair, followed by order-level minimum, mean, and maximum aggregation.
- Added 15 synthetic pytest tests covering target dates, aggregation grain, payment coverage, geolocation duplicate handling and envelope rejection, missing data, deterministic selections, leakage exclusions, relationship failures, Haversine behavior, and temporary Parquet writing.
- Built `data/processed/gold_v1.parquet` with 96,470 rows and 96,470 unique `order_id` values: 6,534 late and 89,936 on time. The one eligible order without payment data remains present.
- The rebuilt generated Parquet file is ignored by Git and is 8,623,905 bytes.
- The corrected derived-feature quality summary found 14 missing `approval_delay_hours` values, 16 missing product-weight totals, 16 missing product-volume totals, and 477 missing values in each seller-distance aggregate. Every other final data column has no missing values.
- The corrected quality summary found no negative approval delays and no negative promised-delivery windows. It found 265 orders without customer coordinates and 477 orders without an available seller-to-customer distance.
- Corrected order-level mean seller-distance distribution: minimum 0.0 km, median 433.921922 km, 95th percentile 2,095.116701599999 km, 99th percentile 2,482.5390120800002 km, and maximum 3,398.552914 km.
- The national envelope removes coordinates outside Brazil, including the verified Spain-like coordinate for ZIP `83252`. It does not prove that every remaining coordinate is correctly located; plausible but incorrectly located in-country coordinates may remain.
- Added `delivery_delay/train.py` with the existing `MODEL_FEATURE_COLUMNS` whitelist, deterministic chronological 70%/15%/15% splitting, training-only preprocessing, DummyClassifier baseline, fixed-seed XGBoost, training-only class weighting, validation-only threshold selection, and one final test evaluation.
- Added `tests/test_train.py` with baseline and Model-v2 synthetic tests covering split ordering and disjointness, feature and leakage contracts, separate preprocessing, threshold and ranking selection, metrics, and artifact round-tripping.
- Added `delivery_delay/api.py` with a lifespan-based FastAPI application. It loads the saved Model-v2 pipeline and metrics once at startup, validates exactly one request containing all 30 model features, preserves feature order, rejects forbidden or non-finite inputs, and returns a risk score, stored threshold, boolean decision, model name, and optional order metadata.
- Added `tests/test_api.py` with temporary/injected-artifact tests for health, valid and tracked-example prediction, feature ordering, unknown categories, nullable values, required and forbidden fields, non-finite numbers, score validation, and threshold behavior.
- Added `examples/predict_request.json` as a documented synthetic request containing all 30 features and optional `order_id`, with no target or leakage fields.
- Added FastAPI `0.141.1`, Uvicorn `0.52.4`, and HTTPX `0.28.1` to the approved dependency set.
- Verified focused API tests: 48 passed. Verified the complete suite: 72 passed with 11 dependency warnings. Smoke-tested the real ignored Model-v2 artifacts: `/health` returned `xgboost_baseline` with 30 features, and `/predict` returned risk score `0.20008252561092377`, threshold `0.5614128112792969`, and `predicted_delay: false` for the tracked example.
- Added direct training dependencies pinned in `requirements.txt`: scikit-learn 1.8.0, xgboost 3.1.2, and joblib 1.5.2.
- Verified focused Model-v2 tests with `.venv\\Scripts\\python.exe -m pytest -q -p no:cacheprovider tests/test_train.py`: 9 passed. Verified the complete suite with `.venv\\Scripts\\python.exe -m pytest -q -p no:cacheprovider`: 24 passed with dependency deprecation warnings.
- Trained the exact saved model with `.venv\\Scripts\\python.exe -m delivery_delay.train --gold data/processed/gold_v1.parquet --artifacts-dir models` using random seed 42 and training `scale_pos_weight` 11.765406427221173.
- The training split contains 67,529 rows (62,239 on time, 5,290 late; 92.166329%/7.833671%) from `2016-09-15 12:16:38` through `2018-04-15 20:12:35`; validation contains 14,470 rows (13,846/624; 95.687630%/4.312370%) through `2018-06-21 08:29:29`; test contains 14,471 rows (13,851/620; 95.715569%/4.284431%) through `2018-08-29 15:00:37`.
- The selected validation F1 threshold is 0.5614128112792969. Test metrics are ROC-AUC 0.5849283037675166, average precision 0.0652516226594603, precision 0.06823104693140794, recall 0.30483870967741933, F1 0.11150442477876106, with TP 189, FP 2,581, TN 11,270, and FN 431.
- The DummyClassifier test baseline has ROC-AUC 0.5, average precision 0.04284430930827172, precision 0.0, recall 0.0, F1 0.0, with TP 0, FP 0, TN 13,851, and FN 620.
- Reloaded `models/delay_xgboost_pipeline.joblib` and produced five finite delay-risk scores in `[0, 1]`. Git confirmed both generated model files are ignored under `models/`.
- Compared three models using validation average precision: XGBoost baseline (train ROC-AUC 0.836851, train average precision 0.343665; validation ROC-AUC 0.769436, validation average precision 0.139615), shallow regularized XGBoost (0.779737, 0.280977; 0.746226, 0.127092), and balanced LogisticRegression (0.746825, 0.227028; 0.741976, 0.113171). Validation average precision was the sole primary selection metric, with validation ROC-AUC and candidate name as tie-breakers; the existing XGBoost baseline won.
- Selected the winner's validation threshold `0.5614128112792969`. Winner metrics were: train ROC-AUC 0.836851, average precision 0.343665, precision 0.250964, recall 0.664461, F1 0.364324; validation ROC-AUC 0.769436, average precision 0.139615, precision 0.154658, recall 0.399038, F1 0.222919; test ROC-AUC 0.584928, average precision 0.065252, precision 0.068231, recall 0.304839, F1 0.111504.
- On the fixed chronological test period, top-5% selected 724 orders and found 63 late orders (8.701657% precision, 10.161290% recall, 2.030995x lift); top-10% selected 1,448 and found 108 (7.458564%, 17.419355%, 1.740853x); top-20% selected 2,895 and found 192 (6.632124%, 30.967742%, 1.547959x).
- Reloaded the saved Model-v2 pipeline and generated 14,471 finite risk scores. Model outputs are risk scores, not calibrated probabilities.
- The initial real Model-v2 run exhausted resources because fitted candidate pipelines were retained simultaneously. This was resolved by fitting and releasing candidates sequentially before fitting the locked winner.
- Model-v2 artifacts are ignored under `models/` and will not be committed.
- The fixed chronological test period was already observed during baseline development; it is not an untouched final holdout.
- Further model tuning is complete for the MVP.

## In progress

Nothing currently in progress.

## Next exact action

Define and implement the minimal FastAPI service with `GET /health` and `POST /predict`.

## Verified decisions

- Target: `delay_flag = 1` when the actual delivered calendar date is later than the estimated calendar date; otherwise, `delay_flag = 0`.
- Train only on orders with `order_status` equal to `delivered` and valid actual and estimated delivery dates.
- Exclude reviews and post-approval events from model inputs. Review-to-order coverage is unnecessary for the first model and was not audited.
- Use only information available at order approval time.
- Do not use direct identifiers or raw row keys as model features.
- Aggregate item rows to one row per order before joining the model-training table.
- Use item-row count, distinct product count, distinct seller count, total price, and total freight as verified aggregation candidates.
- Aggregate payment rows to one row per order and left-join them so the eligible order without a payment row is retained.
- Treat payment type, value, and installments as available features because prediction occurs immediately after payment approval.
- Parse latitude and longitude numerically before geographic filtering or duplicate removal. Continue treating coordinates outside global latitude and longitude ranges as structurally invalid.
- Reject geolocation observations outside the inclusive Brazil envelope of latitude `[-34.0, 6.0]` and longitude `[-74.0, -28.0]`. The envelope is based on [IBGE's published Brazilian geographic extremes](https://brasilemsintese.ibge.gov.br/territorio/dados-geograficos.html), with a small practical margin and eastern allowance for offshore territory.
- Deduplicate valid numeric (`geolocation_zip_code_prefix`, `geolocation_lat`, `geolocation_lng`) triples, then aggregate to coordinate-wise median latitude and longitude per ZIP prefix before deriving order-level geographic features. Textual city or state differences must not give a coordinate extra weight.
- Preserve ZIPs without valid representative coordinates and their affected orders through left joins, with missing-coordinate and missing-distance indicators.
- Do not claim that the national envelope catches every coordinate error. Plausible but incorrectly located in-country coordinates may remain.
- Clamp the Haversine intermediate value to `[0, 1]` before applying square root and inverse sine.
- Preserve raw `shipping_limit_date` values unchanged.
- Treat `shipping_limit_date` as the seller's deadline for handing the order to the logistics partner.
- Exclude `shipping_limit_date` from Gold-v1 because its availability at the exact prediction moment is not verified and the observed values contain anomalies.
- Use a time-based train/test split.
- Save preprocessing and the eventual model together as one pipeline.
- Raw datasets, credentials, and `.env` files must not be committed.
- Keep SHAP explanations optional until the core system works.
- Keep metadata, the model-feature whitelist, and the target explicitly separated in the Gold-v1 column contract.
- Use only synthetic DataFrames or temporary files in tests; raw Olist data must not be required by tests or future CI.

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
- A Python standard-library scan executed through `$analysisCode | python -` inspected only `data/raw/olist_order_items_dataset.csv` and produced the verified item structure, identifier, composition, timestamp, price, and freight results recorded above.
- A Python standard-library relationship and anomaly check executed through `$analysisCode | python -` inspected only the orders and order-items files. It verified order coverage, the 110,189 eligible-cohort item rows, and the shipping-limit comparisons recorded above.
- `git status --short --branch` returned `## main` after the order-items inspection and relationship check.
- A combined Python standard-library audit executed through `$script | python -` inspected the remaining six source CSVs plus only the necessary relationship columns from orders, customers, and order items. The analysis exited successfully and produced the product, seller, payment, geolocation, translation, and review results recorded in `docs/DATA_AUDIT.md`.
- All reconciliation checks performed and reported by the combined audit passed. Review-to-order coverage was intentionally not performed and is not included in that result.
- `git status --short --branch` returned `## main...origin/main` after the combined read-only audit.
- `.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider` passed all 15 synthetic tests in 3.78 seconds.
- `.venv\Scripts\python.exe -m delivery_delay.gold_v1 --raw-dir data/raw --output data/processed/gold_v1.parquet` completed successfully and verified 96,470 rows, 96,470 unique order IDs, 6,534 late rows, 89,936 on-time rows, and one eligible order without payment data. Its quality output reported the verified envelope-rejection and corrected distance counts.
- An in-memory Parquet reconciliation verified the locked cohort again and confirmed 477 missing values in each distance aggregate, 130 orders with mean distance above 3,000 km, and no order with mean distance above 4,000 km.

## Known issues or blockers

- No implementation blocker remains for the local training milestone.
- One eligible order has no payment row; the builder retains it and sets explicit missing-payment defaults and an indicator.
- There are 265 orders without customer coordinates and 477 without an available seller-to-customer distance after filtering.
- The maximum order-level mean seller distance is 3,398.552914 km after rejecting coordinates outside the national envelope.
- The national envelope removes coordinates outside Brazil but cannot identify every plausible-looking coordinate assigned to the wrong in-country location.
- Product-weight and product-volume totals are missing for 16 orders, and approval delay is missing for 14 orders. Their indicators or source missingness remain available for preprocessing decisions.
- Two used product categories lack English translations.
- `shipping_limit_date` is the seller's logistics handoff deadline, but its availability at the exact prediction moment is not verified and its observed values contain anomalies. It is excluded from Gold-v1.

## Results not yet available

- FastAPI service implementation and endpoint tests
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

Last updated: 2026-09-05

### Current milestone

The reproducible local Gold-v1 builder, Model-v2 comparison, and minimal local FastAPI inference service are complete and verified. Further model tuning is closed for the MVP.

### Completed and verified

- Repository context scaffolding is complete.
- Change-control rules are present in `AGENTS.md`.
- The initial project documentation is committed in `4d04780` (`chore: initialize project documentation`).
- `.gitignore` no longer exempts `data/.gitkeep`; both `data/.gitkeep` and raw data paths are ignored.
- Nine source CSV files exist under the ignored `data/raw/` directory, and all nine have been audited. Detailed evidence is recorded in `docs/DATA_AUDIT.md`.
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
- The order-items file contains 112,650 well-formed rows with no missing values and represents 98,666 distinct orders.
- `(order_id, order_item_id)` is unique, and item IDs form a continuous sequence from `1` through `N` within every order.
- There are 88,863 orders with one item row and 9,803 with multiple item rows; one order contains at most 21 item rows.
- There are 32,951 products and 3,095 sellers. Of the represented orders, 3,236 contain multiple distinct products, 1,278 contain multiple distinct sellers, and 6,968 contain repeated rows for the same product.
- Every item row matches exactly one order record. All 112,650 item rows matched, while 775 orders have no item rows: 603 unavailable, 164 canceled, 5 created, 2 invoiced, and 1 shipped.
- Every eligible training order has item data. The 96,470 eligible orders produce 110,189 item rows before aggregation.
- Item rows must be aggregated to one row per order before joining the model-training table. Verified candidates are item-row count, distinct product count, distinct seller count, total price, and total freight.
- Price and freight values are parseable and nonnegative; freight is zero in 383 rows.
- `shipping_limit_date` is earlier than approval in 127 item rows, later than estimated delivery in 372 item rows, and dated 2019 or later in 4 item rows.
- `shipping_limit_date` is the seller's deadline for handing the order to the logistics partner. Raw values will remain unchanged, but the field is excluded from Gold-v1 because its availability at the exact prediction moment is not verified and its observed values contain anomalies.
- Products contain 32,951 well-formed rows, sellers contain 3,095, payments contain 103,886, geolocation contains 1,000,163, category translation contains 71, and reviews contain 99,224.
- Every item product and seller ID has a matching lookup record. Every payment row matches an order record, but one eligible order has no payment row.
- Geolocation contains 261,831 exact duplicate occurrences beyond the first, lacks 157 customer and 7 seller ZIP prefixes, and has coordinate-outlier risk. Gold-v1 requires a robust ZIP-level representative coordinate.
- Two used product categories lack translations. Reviews are excluded, and review-to-order coverage was intentionally not audited.
- All reconciliation checks that were performed and reported passed; this conclusion does not include relationships outside the audit scope.
- The functional builder explicitly reads eight source CSVs and never reads reviews or `archive.zip`. It validates schemas, keys, relationships, one-row aggregation, the feature whitelist, and the final cohort before writing.
- Payment type, value, and installments are accepted as features because prediction occurs immediately after payment approval.
- Coordinates are parsed numerically and filtered through the inclusive Brazil envelope before valid ZIP/latitude/longitude triples are deduplicated. ZIP coordinates use coordinate-wise medians, and the Haversine calculation clamps its intermediate value to `[0, 1]`.
- The envelope rejected 31 raw rows and 27 distinct coordinate triples involving 20 ZIP prefixes; 4 ZIP prefixes have no valid coordinate afterward.
- The ignored `data/processed/gold_v1.parquet` file contains 96,470 unique eligible orders: 6,534 late and 89,936 on time. The eligible order without payment data remains present.
- The rebuilt Parquet file is 8,623,905 bytes.
- The corrected quality summary found 14 missing approval delays, 16 missing product-weight and product-volume totals, 265 orders without customer coordinates, and 477 orders without an available seller distance. No approval delay or promised window is negative.
- The corrected order-level mean seller-distance distribution ranges from 0.0 km to 3,398.552914 km, with median 433.921922 km, 95th percentile 2,095.116701599999 km, and 99th percentile 2,482.5390120800002 km.
- The national envelope removes outside-Brazil coordinates but cannot detect every plausible-looking in-country location error.
- No cloud resource or deployment exists.

### Files changed

- `delivery_delay/train.py`: implemented the bounded Model-v2 comparison, validation-only selection, winner-only test evaluation, ranking metrics, and ignored artifacts.
- `tests/test_train.py`: added synthetic Model-v2 selection, preprocessing, ranking, and reload tests.
- `README.md`: recorded the verified Model-v2 checkpoint and local FastAPI usage.
- `docs/PROJECT_STATUS.md`: recorded the complete Model-v2 experiment and refreshed this handoff.
- `delivery_delay/api.py`: implemented the lifespan-based health and prediction service.
- `tests/test_api.py`: added API contract and validation tests.
- `examples/predict_request.json`: added the tracked synthetic prediction request.
- `requirements.txt`: added the approved FastAPI, Uvicorn, and HTTPX pins.
- `frontend/package.json`, `frontend/package-lock.json`, `frontend/index.html`, `frontend/vite.config.js`, `frontend/src/main.jsx`, `frontend/src/App.jsx`, `frontend/src/api.js`, `frontend/src/demoOrders.js`, `frontend/src/styles.css`, and `frontend/src/App.test.jsx`: implemented the Vite/React synthetic risk dashboard and tests.

### Commands and tests that passed

- `$csvFiles = Get-ChildItem -LiteralPath 'data/raw' -File -Filter '*.csv'; Write-Output ('CSV_COUNT=' + $csvFiles.Count)` returned `CSV_COUNT=9`.
- Python standard-library scans executed through `$analysisCode | python -` inspected only the orders CSV and returned the verified structure and target results.
- A Python standard-library scan executed through `$analysisCode | python -` inspected only the customers CSV and returned the verified customer-file results.
- A Python standard-library relationship check executed through `$analysisCode | python -` used only the required customer identifier columns from the orders and customers files and returned the verified relationship results.
- A Python standard-library scan executed through `$analysisCode | python -` inspected only the order-items CSV and returned the verified item-level results.
- A Python standard-library relationship and anomaly check executed through `$analysisCode | python -` inspected only the orders and order-items files and returned the verified coverage and shipping-limit results.
- `git status --short --branch` returned `## main` after the order-items inspection and relationship check.
- A combined Python standard-library audit executed through `$script | python -` inspected the remaining six source CSVs plus only the necessary relationship columns from the three previously inspected files. The analysis completed successfully.
- All reconciliation checks performed and reported by the combined audit passed. Review-to-order coverage was intentionally not performed.
- `git status --short --branch` returned `## main...origin/main` after the combined read-only audit.
- `.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider` passed all 15 synthetic tests in 3.78 seconds.
- `.venv\Scripts\python.exe -m delivery_delay.gold_v1 --raw-dir data/raw --output data/processed/gold_v1.parquet` rebuilt the ignored Parquet successfully with every locked cohort count satisfied and the new geolocation-quality metrics reported.
- The post-build in-memory Parquet reconciliation passed, confirming the locked cohort, target distribution, retained missing-payment order, corrected distance thresholds, and 8,623,905-byte output.
- Focused Model-v2 tests passed 9 tests; the complete suite passed 24 tests. The saved Model-v2 pipeline reloaded and generated 14,471 valid risk scores.
- The initial real Model-v2 run exhausted resources because fitted candidate pipelines were retained simultaneously; fitting and releasing candidates sequentially resolved the issue.
- Model-v2 artifacts are ignored and will not be committed. Model outputs are risk scores, not calibrated probabilities.
- The fixed chronological test period was already observed during baseline development and is not an untouched final holdout.
- Further model tuning is complete for the MVP.
- The API milestone passed focused and complete tests and real-artifact smoke tests.
- The frontend milestone passed `npm ci`, 4 Vitest tests, and `npm run build`. The Vite root returned HTTP 200, the `/health` and `/predict` proxy checks succeeded, and all 8 synthetic predictions returned scores from 0.080391 to 0.855535 with 1 predicted delay and 7 not predicted.
- Verified the frontend environment as Node.js `v24.20.0` with npm `11.19.0`. Plain `npm install` regenerated `frontend/package-lock.json`, and `npm ci` completed with no engine or peer-dependency errors; npm reported 0 vulnerabilities.

### Git verification

Git state is intentionally not stored as a lasting fact here because it changes whenever files are staged or committed. When sharing this handoff, also include fresh output from:

- `git status --short --branch`
- `git log -1 --oneline --decorate`

### Blockers or uncertainties

- No implementation blocker remains; further model tuning is complete for the MVP.
- One eligible order lacks payment data but is retained with explicit defaults and an indicator.
- There are 265 orders without customer coordinates and 477 without an available seller distance after national-envelope filtering.
- The maximum order-level mean seller distance is 3,398.552914 km. Plausible but incorrectly located in-country coordinates may remain.
- Product-weight and product-volume totals are missing for 16 orders, and approval delay is missing for 14 orders.
- `shipping_limit_date` has a documented seller-deadline meaning, but its exact prediction-time availability is not verified and its observed values contain anomalies. It is excluded from Gold-v1.

### Next exact action

Review the verified frontend milestone and authorize its commit when ready.
