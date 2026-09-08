-- Run the account-level statements as ACCOUNTADMIN.
-- The generated STORAGE_AWS_EXTERNAL_ID and STORAGE_AWS_IAM_USER_ARN are
-- intentionally not stored in this repository. DESCRIBE INTEGRATION returns
-- them for configuring the trust policy on the dedicated AWS role.

USE ROLE ACCOUNTADMIN;

CREATE STORAGE INTEGRATION IF NOT EXISTS DELIVERY_DELAY_S3_INT
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = S3
  ENABLED = TRUE
  STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::556071985875:role/delivery-delay-snowflake-silver-read-role'
  STORAGE_ALLOWED_LOCATIONS = (
    's3://delivery-delay-silver-olist-ap-southeast-1-20260905-7f3c9a2d/silver/2026-09-05/batch-001/order_features_v1/'
  );

DESCRIBE INTEGRATION DELIVERY_DELAY_S3_INT;

GRANT USAGE ON INTEGRATION DELIVERY_DELAY_S3_INT TO ROLE SYSADMIN;
