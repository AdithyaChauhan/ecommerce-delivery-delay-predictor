# Snowflake Silver external table

This milestone makes the verified Silver Parquet queryable from Snowflake while leaving the data in private S3.

## How the pieces fit

```text
Snowflake -> storage integration -> AWS IAM read-only role
-> private S3 stage -> external table -> SQL queries
```

The storage integration is Snowflake's account-level connection to AWS. It uses the dedicated role `delivery-delay-snowflake-silver-read-role`, which can list and read only the verified Silver output and Silver manifest. The external stage points at:

```text
s3://delivery-delay-silver-olist-ap-southeast-1-20260905-7f3c9a2d/silver/2026-09-05/batch-001/order_features_v1/
```

The external table does not copy Silver data into Snowflake. The Parquet files remain in S3 and Snowflake reads them through the private stage when queried. Snowflake Gold has not been materialized yet.

## Execution order

Run the scripts in this order:

1. `001_foundation.sql` as `SYSADMIN`: create the X-Small warehouse, database, and `SILVER` schema with 60-second auto-suspend.
2. `002_storage_integration.sql` as `ACCOUNTADMIN`: create the storage integration and grant its usage to `SYSADMIN`. The script displays the generated external ID and IAM principal; configure those values in AWS trust, but do not store them in Git.
3. `003_silver_external_stage.sql` as `SYSADMIN`: create the Parquet format and private S3 stage.
4. `004_silver_external_table.sql` as `SYSADMIN`: create the 33-column external table. It uses `IF NOT EXISTS`, never `CREATE OR REPLACE`, and matches only Parquet files.
5. `005_validation.sql` as `SYSADMIN`: list the stage, inspect inferred schema, validate counts and flags, run a small sample query, inspect table configuration, and suspend the warehouse.

No `COPY INTO`, Snowpipe, task, auto-refresh, stream, replication, or continuous workload is enabled.

## Rollback

Run only for this dedicated milestone and only after confirming the objects are not needed:

```sql
USE ROLE SYSADMIN;
DROP EXTERNAL TABLE IF EXISTS DELIVERY_DELAY_DB.SILVER.ORDER_FEATURES_V1_EXT;
DROP STAGE IF EXISTS DELIVERY_DELAY_DB.SILVER.ORDER_FEATURES_V1_STAGE;
DROP FILE FORMAT IF EXISTS DELIVERY_DELAY_DB.SILVER.ORDER_FEATURES_PARQUET_FORMAT;

USE ROLE ACCOUNTADMIN;
REVOKE USAGE ON INTEGRATION DELIVERY_DELAY_S3_INT FROM ROLE SYSADMIN;
DROP STORAGE INTEGRATION IF EXISTS DELIVERY_DELAY_S3_INT;
```

These statements remove Snowflake metadata only. They do not delete S3 objects. Do not drop the warehouse, database, or schema if they contain other project objects.

## Cost controls

- Use the dedicated X-Small warehouse.
- Keep auto-suspend at 60 seconds.
- Run bounded validation queries only.
- Leave the warehouse suspended after validation.
- Do not introduce continuous refresh, tasks, or streams in this milestone.
