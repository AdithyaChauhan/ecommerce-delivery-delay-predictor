# Raw Data Audit

Last updated: 2026-09-04

## Scope and method

All nine source CSV files under the ignored `data/raw/` directory have been content-audited. The audits used Python standard-library CSV processing in memory. No joined, aggregated, processed, or report dataset was saved.

Review-to-order coverage and detailed review-text profiling were intentionally outside the review-table audit. They are not included among the verified relationship or reconciliation claims below.

## Prediction contract

- Prediction moment: immediately after an order is approved.
- Training population: orders with `order_status` equal to `delivered` and valid `order_delivered_customer_date` and `order_estimated_delivery_date` values.
- Date comparison: compare calendar dates, not complete timestamps.
- Target: `delay_flag = 1` when the actual delivered calendar date is later than the estimated calendar date; otherwise, `delay_flag = 0`.
- Eligible cohort: 96,470 orders.
- Class distribution: 6,534 late orders (6.773090%) and 89,936 on-time orders (93.226910%).
- Feature rule: use only information available at the exact prediction moment.

## Orders

File: `data/raw/olist_orders_dataset.csv`

Columns, in source order:

1. `order_id`
2. `customer_id`
3. `order_status`
4. `order_purchase_timestamp`
5. `order_approved_at`
6. `order_delivered_carrier_date`
7. `order_delivered_customer_date`
8. `order_estimated_delivery_date`

- Row meaning: one order.
- Rows: 99,441, all well formed.
- Candidate primary key: `order_id`.
- Key result: 99,441 unique values and no duplicates.
- Missing values: 160 `order_approved_at`, 1,783 `order_delivered_carrier_date`, and 2,965 `order_delivered_customer_date` values; all other columns have none.
- Timestamp result: every non-empty timestamp parsed successfully using `%Y-%m-%d %H:%M:%S`.
- Target exceptions: eight delivered orders lack an actual delivery date; six non-delivered orders contain an actual delivery date; fourteen eligible orders lack `order_approved_at`.

## Customers

File: `data/raw/olist_customers_dataset.csv`

Columns, in source order:

1. `customer_id`
2. `customer_unique_id`
3. `customer_zip_code_prefix`
4. `customer_city`
5. `customer_state`

- Row meaning: one order-specific customer record.
- Rows: 99,441, all well formed and with no missing values.
- Candidate primary key: `customer_id`.
- Key result: 99,441 unique values and no duplicates.
- Relationship: every order joins to exactly one customer record through `customer_id`, producing 99,441 rows with no lost or multiplied orders.
- Real-customer identity: 96,096 distinct `customer_unique_id` values; 93,099 link to one order and 2,997 link to multiple orders. The repeat-customer group accounts for 6,342 orders, and the maximum is 17 orders for one `customer_unique_id`.
- Location: 14,994 distinct ZIP prefixes, 4,119 cities, and 27 states. Every ZIP-prefix row contains five digits, and 23,995 row values begin with zero, so the prefix must remain a string.

## Order items

File: `data/raw/olist_order_items_dataset.csv`

Columns, in source order:

1. `order_id`
2. `order_item_id`
3. `product_id`
4. `seller_id`
5. `shipping_limit_date`
6. `price`
7. `freight_value`

- Row meaning: one item row within an order.
- Rows: 112,650, all well formed and with no missing values.
- Candidate composite key: (`order_id`, `order_item_id`).
- Key result: 112,650 unique composite values and no duplicates. Item IDs form the continuous sequence `1` through `N` within every order.
- Order grain: 98,666 distinct orders; 88,863 have one item row and 9,803 have multiple item rows. The maximum is 21 item rows for one order.
- Composition: 32,951 products and 3,095 sellers. There are 3,236 orders with multiple distinct products, 1,278 with multiple distinct sellers, and 6,968 with repeated rows for the same product.
- Relationship integrity: every item row matches exactly one order record.
- Order coverage: 775 orders have no item rows: 603 unavailable, 164 canceled, 5 created, 2 invoiced, and 1 shipped.
- Eligible coverage: all 96,470 eligible orders have item data and produce 110,189 item rows before aggregation.
- Values: all price and freight values are parseable and nonnegative; freight is zero in 383 rows.
- `shipping_limit_date` meaning: the seller's deadline for handing the order to the logistics partner.
- `shipping_limit_date` observations: 127 item rows are earlier than approval, 372 are later than estimated delivery, and 4 are dated 2019 or later.
- Decision: preserve the raw values but exclude `shipping_limit_date` from Gold-v1 because its availability at the exact prediction moment is not verified and the observed values contain anomalies.

## Products

File: `data/raw/olist_products_dataset.csv`

Columns, in source order:

1. `product_id`
2. `product_category_name`
3. `product_name_lenght`
4. `product_description_lenght`
5. `product_photos_qty`
6. `product_weight_g`
7. `product_length_cm`
8. `product_height_cm`
9. `product_width_cm`

- Row meaning: one product-catalog record.
- Rows: 32,951, all well formed.
- Candidate primary key: `product_id`.
- Key result: 32,951 unique values and no duplicates.
- Missing values: 610 each for category, name length, description length, and photo quantity; 2 each for weight, length, height, and width; none for `product_id`.
- Categories: 73 distinct non-empty source categories.
- Numeric result: every non-empty measurement parsed successfully, all were integral and nonnegative, and four product weights were zero.
- Observed ranges: name length 5-76, description length 4-3,992, photo quantity 1-20, weight 0-40,425 g, length 7-105 cm, height 2-105 cm, and width 6-118 cm.
- Relationship: every product ID used by order items exists in products, and no product record is unused by order items.

## Sellers

File: `data/raw/olist_sellers_dataset.csv`

Columns, in source order:

1. `seller_id`
2. `seller_zip_code_prefix`
3. `seller_city`
4. `seller_state`

- Row meaning: one seller record with its location.
- Rows: 3,095, all well formed and with no missing values.
- Candidate primary key: `seller_id`.
- Key result: 3,095 unique values and no duplicates.
- Location: 2,246 ZIP prefixes, 611 cities, and 23 states.
- ZIP format: all 3,095 row values contain exactly five digits; 1,027 row values and 831 distinct values begin with zero, so the prefix must remain a string.
- Relationship: every seller ID used by order items exists in sellers, and no seller record is unused by order items.

## Payments

File: `data/raw/olist_order_payments_dataset.csv`

Columns, in source order:

1. `order_id`
2. `payment_sequential`
3. `payment_type`
4. `payment_installments`
5. `payment_value`

- Row meaning: one sequenced payment record for an order.
- Rows: 103,886, all well formed and with no missing values.
- Candidate composite key: (`order_id`, `payment_sequential`).
- Key result: 103,886 unique composite values and no duplicates.
- Order grain: 99,440 distinct orders; 96,479 have one payment row and 2,961 have multiple payment rows.
- Payment types: 76,795 credit-card, 19,784 boleto, 5,775 voucher, 1,529 debit-card, and 3 `not_defined` rows.
- Integer validation: all `payment_sequential` and `payment_installments` values are parseable nonnegative integers. Sequential values range from 1 to 29; installments range from 0 to 24 and include two zeros.
- Decimal validation: all `payment_value` values parse and are nonnegative, ranging from 0.00 to 13,664.08, with nine zeros.
- Relationship integrity: every payment row matches an order record.
- Order coverage: one order has no payment row, and that order belongs to the eligible cohort. Therefore 96,469 of 96,470 eligible orders have payment data.
- Gold-v1 requirement: payment aggregates must be left-joined so the eligible order without a payment row is not silently dropped.

## Geolocation

File: `data/raw/olist_geolocation_dataset.csv`

Columns, in source order:

1. `geolocation_zip_code_prefix`
2. `geolocation_lat`
3. `geolocation_lng`
4. `geolocation_city`
5. `geolocation_state`

- Row meaning: one geocoding observation for a ZIP prefix, coordinate, city, and state.
- Rows: 1,000,163, all well formed and with no missing values.
- Key result: no unique natural row key was verified. The full-row composite contains exact duplicates.
- Exact duplicates: 738,332 unique full rows and 261,831 duplicate occurrences beyond the first. There are 128,174 distinct duplicated full-row values and 390,005 rows in duplicate groups.
- ZIP grain: 19,015 distinct prefixes; 1,043 have one row and 17,972 have multiple rows.
- Coordinate parsing: all 1,000,163 latitude and longitude values parse successfully, with none outside the global valid ranges of `[-90, 90]` and `[-180, 180]`.
- Observed coordinate ranges: latitude -36.6053744107061 to 45.06593318269697; longitude -101.46676644931476 to 121.10539381057764. These extremes create coordinate-outlier risk for this dataset; an outlier count was not calculated in the completed audit.
- Customer coverage: 14,837 of 14,994 distinct customer ZIP prefixes are present; 157 are missing.
- Seller coverage: 2,239 of 2,246 distinct seller ZIP prefixes are present; 7 are missing.
- Gold-v1 requirement: never join raw geolocation rows directly to orders. Produce one documented, outlier-resistant representative coordinate per ZIP prefix, with coordinate-wise medians as the planned default after explicit duplicate handling. Preserve missing geolocation coverage rather than dropping orders.

## Product category translation

File: `data/raw/product_category_name_translation.csv`

Columns, in source order:

1. `product_category_name`
2. `product_category_name_english`

- Row meaning: one Portuguese-to-English product-category mapping.
- Rows: 71, all well formed and with no missing values.
- Candidate primary key: `product_category_name`.
- Key result: 71 unique source category names and no duplicates.
- Coverage: 71 of the 73 non-empty product categories have translations. `pc_gamer` and `portateis_cozinha_e_preparadores_de_alimentos` do not.
- Unused mappings: none.
- The 610 products with no source category cannot receive a translation through this table.

## Order reviews

File: `data/raw/olist_order_reviews_dataset.csv`

Columns, in source order:

1. `review_id`
2. `order_id`
3. `review_score`
4. `review_comment_title`
5. `review_comment_message`
6. `review_creation_date`
7. `review_answer_timestamp`

- Rows: 99,224, all well formed.
- Candidate composite key: (`review_id`, `order_id`).
- Key result: 99,224 unique composite values and no duplicates.
- `review_id` alone is not unique: 789 values repeat, producing 814 occurrences beyond the first.
- Detailed review missingness, text analysis, and review-to-order coverage were intentionally not performed.
- Decision: exclude the entire reviews table from Gold-v1 and the first model because review information is created after the prediction moment.

## Order-level aggregation requirements

- Aggregate order items by `order_id`. Verified candidates are item-row count, distinct product count, distinct seller count, total price, total freight, and appropriately aggregated product and seller attributes.
- Aggregate payments by `order_id`, then left-join the result to retain the eligible order with no payment row.
- Aggregate geolocation to one robust representative row per ZIP prefix before deriving customer or seller geographic features.
- Customers, products, sellers, and category translation are lookup tables with verified unique join keys and do not independently require order-level aggregation.
- Exclude reviews rather than aggregating them into features.

## Fields excluded from Gold-v1 model inputs

- Direct identifiers and raw row keys: `order_id`, `customer_id`, `customer_unique_id`, `order_item_id`, `product_id`, `seller_id`, `payment_sequential`, and `review_id`.
- Post-approval or outcome information: `order_status`, `order_delivered_carrier_date`, and `order_delivered_customer_date`.
- Target leakage: `delay_flag` is the target and must never be an input feature.
- Reviews: every field in the reviews table, because review information is created after the prediction moment.
- `shipping_limit_date`: its seller-deadline meaning is documented, but its availability at the exact prediction moment is not verified and its observed values contain anomalies.

ZIP and category fields may be used as lookup keys or to derive geographic and category features; they must not be treated as entity identifiers to memorize.

## Reconciliation results

All reconciliation checks that were performed and reported passed:

- For every audited file, well-formed rows plus malformed rows equal total rows.
- Every reported missing/non-missing partition equals its table total.
- Item product and seller coverage partitions reconcile to their source-key totals.
- Payment orders reconcile as 96,479 one-row orders plus 2,961 multi-row orders, totaling 99,440 orders and 103,886 payment rows.
- Payment coverage reconciles as 99,440 orders with payment rows plus one without, totaling 99,441 orders; eligible coverage reconciles as 96,469 plus one, totaling 96,470.
- Geolocation ZIP counts reconcile as 1,043 single-row prefixes plus 17,972 multi-row prefixes, totaling 19,015.
- Geolocation full rows reconcile as 738,332 unique rows plus 261,831 duplicate occurrences, totaling 1,000,163.
- Customer geolocation coverage reconciles as 14,837 found plus 157 missing, totaling 14,994 ZIP prefixes.
- Seller geolocation coverage reconciles as 2,239 found plus 7 missing, totaling 2,246 ZIP prefixes.
- Category coverage reconciles as 71 translated plus 2 untranslated, totaling 73 non-empty product categories.
- Review composite keys reconcile as 99,224 unique keys plus no duplicate occurrences, totaling 99,224 rows.

Review-to-order coverage was not performed and is not asserted by these results.
