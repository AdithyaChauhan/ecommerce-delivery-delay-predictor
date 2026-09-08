-- Run as SYSADMIN. End this script with warehouse suspension.

USE ROLE SYSADMIN;
USE WAREHOUSE DELIVERY_DELAY_WH;
USE DATABASE DELIVERY_DELAY_DB;
USE SCHEMA GOLD;

-- The expected ordinal/name pairs prove the native table has exactly the
-- existing verified 33-column order without depending on Parquet filenames.
SELECT COUNT(*) AS GOLD_COLUMN_COUNT
FROM DELIVERY_DELAY_DB.INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'GOLD'
  AND TABLE_NAME = 'ORDER_FEATURES_V1';

WITH expected (ordinal_position, column_name) AS (
  SELECT column1, column2
  FROM VALUES
    (1, 'ORDER_ID'), (2, 'ORDER_PURCHASE_TIMESTAMP'),
    (3, 'PURCHASE_YEAR'), (4, 'PURCHASE_MONTH'),
    (5, 'PURCHASE_DAY_OF_WEEK'), (6, 'PURCHASE_HOUR'),
    (7, 'APPROVAL_DELAY_HOURS'), (8, 'APPROVAL_TIMESTAMP_MISSING'),
    (9, 'PROMISED_DELIVERY_WINDOW_DAYS'), (10, 'CUSTOMER_STATE'),
    (11, 'ITEM_ROW_COUNT'), (12, 'DISTINCT_PRODUCT_COUNT'),
    (13, 'DISTINCT_SELLER_COUNT'), (14, 'ITEM_PRICE_TOTAL'),
    (15, 'FREIGHT_VALUE_TOTAL'), (16, 'PRODUCT_WEIGHT_G_TOTAL'),
    (17, 'PRODUCT_VOLUME_CM3_TOTAL'),
    (18, 'PRODUCT_MEASUREMENT_MISSING_ITEM_COUNT'),
    (19, 'PRODUCT_CATEGORY_FALLBACK_ITEM_COUNT'),
    (20, 'PRIMARY_PRODUCT_CATEGORY'), (21, 'PRIMARY_SELLER_STATE'),
    (22, 'PAYMENT_ROW_COUNT'), (23, 'DISTINCT_PAYMENT_TYPE_COUNT'),
    (24, 'PAYMENT_VALUE_TOTAL'), (25, 'MAX_PAYMENT_INSTALLMENTS'),
    (26, 'PRIMARY_PAYMENT_TYPE'), (27, 'PAYMENT_DATA_MISSING'),
    (28, 'CUSTOMER_GEOLOCATION_MISSING'),
    (29, 'SELLER_CUSTOMER_DISTANCE_MISSING_COUNT'),
    (30, 'SELLER_CUSTOMER_DISTANCE_KM_MIN'),
    (31, 'SELLER_CUSTOMER_DISTANCE_KM_MEAN'),
    (32, 'SELLER_CUSTOMER_DISTANCE_KM_MAX'), (33, 'DELAY_FLAG')
), actual AS (
  SELECT ORDINAL_POSITION, COLUMN_NAME
  FROM DELIVERY_DELAY_DB.INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = 'GOLD' AND TABLE_NAME = 'ORDER_FEATURES_V1'
)
SELECT 'EXPECTED_MINUS_ACTUAL' AS DIFFERENCE_DIRECTION,
       ordinal_position,
       column_name
FROM (
  SELECT ordinal_position, column_name FROM expected
  MINUS
  SELECT ordinal_position, column_name FROM actual
) AS expected_minus_actual
UNION ALL
SELECT 'ACTUAL_MINUS_EXPECTED' AS DIFFERENCE_DIRECTION,
       ordinal_position,
       column_name
FROM (
  SELECT ordinal_position, column_name FROM actual
  MINUS
  SELECT ordinal_position, column_name FROM expected
) AS actual_minus_expected
ORDER BY DIFFERENCE_DIRECTION, ordinal_position;

SELECT COUNT(*) AS ROW_COUNT
FROM DELIVERY_DELAY_DB.GOLD.ORDER_FEATURES_V1;

SELECT COUNT(DISTINCT order_id) AS DISTINCT_ORDER_ID_COUNT
FROM DELIVERY_DELAY_DB.GOLD.ORDER_FEATURES_V1;

SELECT
  SUM(IFF(delay_flag = 1, 1, 0)) AS LATE_COUNT,
  SUM(IFF(delay_flag = 0, 1, 0)) AS ON_TIME_COUNT,
  SUM(IFF(delay_flag IS NULL OR delay_flag NOT IN (0, 1), 1, 0)) AS INVALID_DELAY_FLAG_COUNT
FROM DELIVERY_DELAY_DB.GOLD.ORDER_FEATURES_V1;

-- Compare every explicit column in both directions; both counts must be zero.
SELECT COUNT(*) AS SILVER_ROWS_MISSING_FROM_GOLD
FROM (
  SELECT order_id, order_purchase_timestamp, purchase_year, purchase_month,
    purchase_day_of_week, purchase_hour, approval_delay_hours,
    approval_timestamp_missing, promised_delivery_window_days, customer_state,
    item_row_count, distinct_product_count, distinct_seller_count,
    item_price_total, freight_value_total, product_weight_g_total,
    product_volume_cm3_total, product_measurement_missing_item_count,
    product_category_fallback_item_count, primary_product_category,
    primary_seller_state, payment_row_count, distinct_payment_type_count,
    payment_value_total, max_payment_installments, primary_payment_type,
    payment_data_missing, customer_geolocation_missing,
    seller_customer_distance_missing_count, seller_customer_distance_km_min,
    seller_customer_distance_km_mean, seller_customer_distance_km_max,
    delay_flag
  FROM DELIVERY_DELAY_DB.SILVER.ORDER_FEATURES_V1_EXT
  MINUS
  SELECT order_id, order_purchase_timestamp, purchase_year, purchase_month,
    purchase_day_of_week, purchase_hour, approval_delay_hours,
    approval_timestamp_missing, promised_delivery_window_days, customer_state,
    item_row_count, distinct_product_count, distinct_seller_count,
    item_price_total, freight_value_total, product_weight_g_total,
    product_volume_cm3_total, product_measurement_missing_item_count,
    product_category_fallback_item_count, primary_product_category,
    primary_seller_state, payment_row_count, distinct_payment_type_count,
    payment_value_total, max_payment_installments, primary_payment_type,
    payment_data_missing, customer_geolocation_missing,
    seller_customer_distance_missing_count, seller_customer_distance_km_min,
    seller_customer_distance_km_mean, seller_customer_distance_km_max,
    delay_flag
  FROM DELIVERY_DELAY_DB.GOLD.ORDER_FEATURES_V1
) AS silver_minus_gold;

SELECT COUNT(*) AS GOLD_ROWS_MISSING_FROM_SILVER
FROM (
  SELECT order_id, order_purchase_timestamp, purchase_year, purchase_month,
    purchase_day_of_week, purchase_hour, approval_delay_hours,
    approval_timestamp_missing, promised_delivery_window_days, customer_state,
    item_row_count, distinct_product_count, distinct_seller_count,
    item_price_total, freight_value_total, product_weight_g_total,
    product_volume_cm3_total, product_measurement_missing_item_count,
    product_category_fallback_item_count, primary_product_category,
    primary_seller_state, payment_row_count, distinct_payment_type_count,
    payment_value_total, max_payment_installments, primary_payment_type,
    payment_data_missing, customer_geolocation_missing,
    seller_customer_distance_missing_count, seller_customer_distance_km_min,
    seller_customer_distance_km_mean, seller_customer_distance_km_max,
    delay_flag
  FROM DELIVERY_DELAY_DB.GOLD.ORDER_FEATURES_V1
  MINUS
  SELECT order_id, order_purchase_timestamp, purchase_year, purchase_month,
    purchase_day_of_week, purchase_hour, approval_delay_hours,
    approval_timestamp_missing, promised_delivery_window_days, customer_state,
    item_row_count, distinct_product_count, distinct_seller_count,
    item_price_total, freight_value_total, product_weight_g_total,
    product_volume_cm3_total, product_measurement_missing_item_count,
    product_category_fallback_item_count, primary_product_category,
    primary_seller_state, payment_row_count, distinct_payment_type_count,
    payment_value_total, max_payment_installments, primary_payment_type,
    payment_data_missing, customer_geolocation_missing,
    seller_customer_distance_missing_count, seller_customer_distance_km_min,
    seller_customer_distance_km_mean, seller_customer_distance_km_max,
    delay_flag
  FROM DELIVERY_DELAY_DB.SILVER.ORDER_FEATURES_V1_EXT
) AS gold_minus_silver;

SHOW TABLES LIKE 'ORDER_FEATURES_V1' IN SCHEMA DELIVERY_DELAY_DB.GOLD;
DESCRIBE TABLE DELIVERY_DELAY_DB.GOLD.ORDER_FEATURES_V1;
SHOW WAREHOUSES LIKE 'DELIVERY_DELAY_WH';

ALTER WAREHOUSE DELIVERY_DELAY_WH SUSPEND;
