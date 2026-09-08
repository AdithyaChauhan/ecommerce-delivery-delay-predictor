-- Run as SYSADMIN.
-- Gold is a native Snowflake snapshot of the verified Silver external table.

USE ROLE SYSADMIN;
USE WAREHOUSE DELIVERY_DELAY_WH;
USE DATABASE DELIVERY_DELAY_DB;

CREATE SCHEMA IF NOT EXISTS DELIVERY_DELAY_DB.GOLD;
USE SCHEMA GOLD;

CREATE TABLE IF NOT EXISTS ORDER_FEATURES_V1
(
  order_id TEXT NOT NULL,
  order_purchase_timestamp TIMESTAMP_NTZ,
  purchase_year NUMBER(38,0),
  purchase_month NUMBER(38,0),
  purchase_day_of_week NUMBER(38,0),
  purchase_hour NUMBER(38,0),
  approval_delay_hours REAL,
  approval_timestamp_missing BOOLEAN NOT NULL,
  promised_delivery_window_days NUMBER(38,0),
  customer_state TEXT,
  item_row_count NUMBER(38,0),
  distinct_product_count NUMBER(38,0),
  distinct_seller_count NUMBER(38,0),
  item_price_total REAL,
  freight_value_total REAL,
  product_weight_g_total REAL,
  product_volume_cm3_total REAL,
  product_measurement_missing_item_count NUMBER(38,0),
  product_category_fallback_item_count NUMBER(38,0),
  primary_product_category TEXT,
  primary_seller_state TEXT,
  payment_row_count NUMBER(38,0) NOT NULL,
  distinct_payment_type_count NUMBER(38,0) NOT NULL,
  payment_value_total REAL NOT NULL,
  max_payment_installments NUMBER(38,0) NOT NULL,
  primary_payment_type TEXT NOT NULL,
  payment_data_missing BOOLEAN NOT NULL,
  customer_geolocation_missing BOOLEAN NOT NULL,
  seller_customer_distance_missing_count NUMBER(38,0),
  seller_customer_distance_km_min REAL,
  seller_customer_distance_km_mean REAL,
  seller_customer_distance_km_max REAL,
  delay_flag NUMBER(38,0) NOT NULL
)
ENABLE_SCHEMA_EVOLUTION = FALSE
DATA_RETENTION_TIME_IN_DAYS = 1
CHANGE_TRACKING = FALSE;

-- Insert-only MERGE makes reruns safe: matched rows remain unchanged.
-- The validation script compares Silver MINUS Gold and Gold MINUS Silver
-- across all 33 columns so drift is detected rather than overwritten.
MERGE INTO DELIVERY_DELAY_DB.GOLD.ORDER_FEATURES_V1 AS target
USING (
  SELECT
    order_id,
    order_purchase_timestamp,
    purchase_year,
    purchase_month,
    purchase_day_of_week,
    purchase_hour,
    approval_delay_hours,
    approval_timestamp_missing,
    promised_delivery_window_days,
    customer_state,
    item_row_count,
    distinct_product_count,
    distinct_seller_count,
    item_price_total,
    freight_value_total,
    product_weight_g_total,
    product_volume_cm3_total,
    product_measurement_missing_item_count,
    product_category_fallback_item_count,
    primary_product_category,
    primary_seller_state,
    payment_row_count,
    distinct_payment_type_count,
    payment_value_total,
    max_payment_installments,
    primary_payment_type,
    payment_data_missing,
    customer_geolocation_missing,
    seller_customer_distance_missing_count,
    seller_customer_distance_km_min,
    seller_customer_distance_km_mean,
    seller_customer_distance_km_max,
    delay_flag
  FROM DELIVERY_DELAY_DB.SILVER.ORDER_FEATURES_V1_EXT
) AS source
ON target.order_id = source.order_id
WHEN NOT MATCHED THEN INSERT
(
  order_id,
  order_purchase_timestamp,
  purchase_year,
  purchase_month,
  purchase_day_of_week,
  purchase_hour,
  approval_delay_hours,
  approval_timestamp_missing,
  promised_delivery_window_days,
  customer_state,
  item_row_count,
  distinct_product_count,
  distinct_seller_count,
  item_price_total,
  freight_value_total,
  product_weight_g_total,
  product_volume_cm3_total,
  product_measurement_missing_item_count,
  product_category_fallback_item_count,
  primary_product_category,
  primary_seller_state,
  payment_row_count,
  distinct_payment_type_count,
  payment_value_total,
  max_payment_installments,
  primary_payment_type,
  payment_data_missing,
  customer_geolocation_missing,
  seller_customer_distance_missing_count,
  seller_customer_distance_km_min,
  seller_customer_distance_km_mean,
  seller_customer_distance_km_max,
  delay_flag
)
VALUES
(
  source.order_id,
  source.order_purchase_timestamp,
  source.purchase_year,
  source.purchase_month,
  source.purchase_day_of_week,
  source.purchase_hour,
  source.approval_delay_hours,
  source.approval_timestamp_missing,
  source.promised_delivery_window_days,
  source.customer_state,
  source.item_row_count,
  source.distinct_product_count,
  source.distinct_seller_count,
  source.item_price_total,
  source.freight_value_total,
  source.product_weight_g_total,
  source.product_volume_cm3_total,
  source.product_measurement_missing_item_count,
  source.product_category_fallback_item_count,
  source.primary_product_category,
  source.primary_seller_state,
  source.payment_row_count,
  source.distinct_payment_type_count,
  source.payment_value_total,
  source.max_payment_installments,
  source.primary_payment_type,
  source.payment_data_missing,
  source.customer_geolocation_missing,
  source.seller_customer_distance_missing_count,
  source.seller_customer_distance_km_min,
  source.seller_customer_distance_km_mean,
  source.seller_customer_distance_km_max,
  source.delay_flag
);
