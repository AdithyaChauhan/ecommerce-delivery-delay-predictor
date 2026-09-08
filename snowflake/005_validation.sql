-- Run as SYSADMIN. This is read-only validation plus final warehouse suspend.

USE ROLE SYSADMIN;
USE WAREHOUSE DELIVERY_DELAY_WH;
USE DATABASE DELIVERY_DELAY_DB;
USE SCHEMA SILVER;

-- Do not assert a fixed number of files: the four current Parquet parts are
-- an observed output, not a contract.
LIST @ORDER_FEATURES_V1_STAGE;

-- Display inferred Parquet fields in source order.
SELECT COLUMN_NAME, TYPE, NULLABLE, ORDER_ID
FROM TABLE(INFER_SCHEMA(
  LOCATION => '@ORDER_FEATURES_V1_STAGE',
  FILE_FORMAT => 'ORDER_FEATURES_PARQUET_FORMAT'
))
ORDER BY ORDER_ID;

SELECT COUNT(*) AS ROW_COUNT
FROM ORDER_FEATURES_V1_EXT;

SELECT COUNT(DISTINCT order_id) AS DISTINCT_ORDER_ID_COUNT
FROM ORDER_FEATURES_V1_EXT;

SELECT
  SUM(IFF(delay_flag = 1, 1, 0)) AS LATE_COUNT,
  SUM(IFF(delay_flag = 0, 1, 0)) AS ON_TIME_COUNT,
  SUM(IFF(delay_flag IS NULL OR delay_flag NOT IN (0, 1), 1, 0)) AS INVALID_DELAY_FLAG_COUNT
FROM ORDER_FEATURES_V1_EXT;

SELECT
  order_id,
  order_purchase_timestamp,
  customer_state,
  item_price_total,
  payment_data_missing,
  primary_payment_type,
  seller_customer_distance_km_mean,
  delay_flag
FROM ORDER_FEATURES_V1_EXT
ORDER BY order_id
LIMIT 5;

SHOW EXTERNAL TABLES LIKE 'ORDER_FEATURES_V1_EXT' IN SCHEMA DELIVERY_DELAY_DB.SILVER;
DESCRIBE EXTERNAL TABLE DELIVERY_DELAY_DB.SILVER.ORDER_FEATURES_V1_EXT;

ALTER WAREHOUSE DELIVERY_DELAY_WH SUSPEND;
