-- Run as SYSADMIN.
-- Do not use replacement DDL: the table is intentionally protected from
-- accidental replacement. Execute this only once for a new table name.

USE ROLE SYSADMIN;
USE DATABASE DELIVERY_DELAY_DB;
USE SCHEMA SILVER;

CREATE EXTERNAL TABLE IF NOT EXISTS ORDER_FEATURES_V1_EXT
(
  order_id TEXT AS (VALUE:"order_id"::TEXT),
  order_purchase_timestamp TIMESTAMP_NTZ AS (VALUE:"order_purchase_timestamp"::TIMESTAMP_NTZ),
  purchase_year NUMBER(38,0) AS (VALUE:"purchase_year"::NUMBER(38,0)),
  purchase_month NUMBER(38,0) AS (VALUE:"purchase_month"::NUMBER(38,0)),
  purchase_day_of_week NUMBER(38,0) AS (VALUE:"purchase_day_of_week"::NUMBER(38,0)),
  purchase_hour NUMBER(38,0) AS (VALUE:"purchase_hour"::NUMBER(38,0)),
  approval_delay_hours REAL AS (VALUE:"approval_delay_hours"::REAL),
  approval_timestamp_missing BOOLEAN AS (VALUE:"approval_timestamp_missing"::BOOLEAN),
  promised_delivery_window_days NUMBER(38,0) AS (VALUE:"promised_delivery_window_days"::NUMBER(38,0)),
  customer_state TEXT AS (VALUE:"customer_state"::TEXT),
  item_row_count NUMBER(38,0) AS (VALUE:"item_row_count"::NUMBER(38,0)),
  distinct_product_count NUMBER(38,0) AS (VALUE:"distinct_product_count"::NUMBER(38,0)),
  distinct_seller_count NUMBER(38,0) AS (VALUE:"distinct_seller_count"::NUMBER(38,0)),
  item_price_total REAL AS (VALUE:"item_price_total"::REAL),
  freight_value_total REAL AS (VALUE:"freight_value_total"::REAL),
  product_weight_g_total REAL AS (VALUE:"product_weight_g_total"::REAL),
  product_volume_cm3_total REAL AS (VALUE:"product_volume_cm3_total"::REAL),
  product_measurement_missing_item_count NUMBER(38,0) AS (VALUE:"product_measurement_missing_item_count"::NUMBER(38,0)),
  product_category_fallback_item_count NUMBER(38,0) AS (VALUE:"product_category_fallback_item_count"::NUMBER(38,0)),
  primary_product_category TEXT AS (VALUE:"primary_product_category"::TEXT),
  primary_seller_state TEXT AS (VALUE:"primary_seller_state"::TEXT),
  payment_row_count NUMBER(38,0) AS (VALUE:"payment_row_count"::NUMBER(38,0)),
  distinct_payment_type_count NUMBER(38,0) AS (VALUE:"distinct_payment_type_count"::NUMBER(38,0)),
  payment_value_total REAL AS (VALUE:"payment_value_total"::REAL),
  max_payment_installments NUMBER(38,0) AS (VALUE:"max_payment_installments"::NUMBER(38,0)),
  primary_payment_type TEXT AS (VALUE:"primary_payment_type"::TEXT),
  payment_data_missing BOOLEAN AS (VALUE:"payment_data_missing"::BOOLEAN),
  customer_geolocation_missing BOOLEAN AS (VALUE:"customer_geolocation_missing"::BOOLEAN),
  seller_customer_distance_missing_count NUMBER(38,0) AS (VALUE:"seller_customer_distance_missing_count"::NUMBER(38,0)),
  seller_customer_distance_km_min REAL AS (VALUE:"seller_customer_distance_km_min"::REAL),
  seller_customer_distance_km_mean REAL AS (VALUE:"seller_customer_distance_km_mean"::REAL),
  seller_customer_distance_km_max REAL AS (VALUE:"seller_customer_distance_km_max"::REAL),
  delay_flag NUMBER(38,0) AS (VALUE:"delay_flag"::NUMBER(38,0))
)
WITH LOCATION = @ORDER_FEATURES_V1_STAGE
FILE_FORMAT = (FORMAT_NAME = ORDER_FEATURES_PARQUET_FORMAT)
PATTERN = '.*[.]parquet'
REFRESH_ON_CREATE = TRUE
AUTO_REFRESH = FALSE;

-- Created under SYSADMIN, so the resulting external table is SYSADMIN-owned.
