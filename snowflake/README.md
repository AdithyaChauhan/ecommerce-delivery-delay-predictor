# Snowflake Silver external table and Gold snapshot

The Silver milestone makes verified Parquet queryable from Snowflake while leaving it in private S3. The Gold milestone materializes a verified, native Snowflake snapshot for downstream queries.

## How the pieces fit

```text
Snowflake -> storage integration -> AWS IAM read-only role
-> private S3 stage -> external table -> SQL queries
```

The storage integration is Snowflake's account-level connection to AWS. It uses the dedicated role `delivery-delay-snowflake-silver-read-role`, which can list and read only the verified Silver output and Silver manifest. The external stage points at:

```text
s3://delivery-delay-silver-olist-ap-southeast-1-20260905-7f3c9a2d/silver/2026-09-05/batch-001/order_features_v1/
```

The external table does not copy Silver data into Snowflake. The Parquet files remain in S3 and Snowflake reads them through the private stage when queried. Gold is separate: `DELIVERY_DELAY_DB.GOLD.ORDER_FEATURES_V1` physically stores the verified snapshot in Snowflake.

## Execution order

Run the scripts in this order:

1. `001_foundation.sql` as `SYSADMIN`: create the X-Small warehouse, database, and `SILVER` schema with 60-second auto-suspend.
2. `002_storage_integration.sql` as `ACCOUNTADMIN`: create the storage integration and grant its usage to `SYSADMIN`. The script displays the generated external ID and IAM principal; configure those values in AWS trust, but do not store them in Git.
3. `003_silver_external_stage.sql` as `SYSADMIN`: create the Parquet format and private S3 stage.
4. `004_silver_external_table.sql` as `SYSADMIN`: create the 33-column external table. It uses `IF NOT EXISTS`, never `CREATE OR REPLACE`, and matches only Parquet files.
5. `005_validation.sql` as `SYSADMIN`: list the stage, inspect inferred schema, validate counts and flags, run a small sample query, inspect table configuration, and suspend the warehouse.
6. `006_gold_table.sql` as `SYSADMIN`: create the `GOLD` schema and native 33-column table, then insert only missing `order_id` values from Silver with an explicit-column `MERGE`. Matched rows remain unchanged.
7. `007_gold_validation.sql` as `SYSADMIN`: verify the native table contract, counts, flags, bidirectional all-column equality, table metadata, and warehouse controls; the final statement suspends the warehouse.

No `COPY INTO`, Snowpipe, task, stream, automatic refresh, replication, or continuous workload is enabled. Gold is a verified snapshot, not current/live production data, and no automatic per-batch model retraining exists.

## Rollback

Run only for this dedicated milestone and only after confirming the objects are not needed:

Gold rollback removes only native Gold metadata and data:

```sql
USE ROLE SYSADMIN;
DROP TABLE IF EXISTS DELIVERY_DELAY_DB.GOLD.ORDER_FEATURES_V1;
DROP SCHEMA IF EXISTS DELIVERY_DELAY_DB.GOLD;
```

Silver rollback removes only Silver-side Snowflake metadata:

```sql
USE ROLE SYSADMIN;
DROP EXTERNAL TABLE IF EXISTS DELIVERY_DELAY_DB.SILVER.ORDER_FEATURES_V1_EXT;
DROP STAGE IF EXISTS DELIVERY_DELAY_DB.SILVER.ORDER_FEATURES_V1_STAGE;
DROP FILE FORMAT IF EXISTS DELIVERY_DELAY_DB.SILVER.ORDER_FEATURES_PARQUET_FORMAT;

USE ROLE ACCOUNTADMIN;
REVOKE USAGE ON INTEGRATION DELIVERY_DELAY_S3_INT FROM ROLE SYSADMIN;
DROP STORAGE INTEGRATION IF EXISTS DELIVERY_DELAY_S3_INT;
```

Gold rollback must be run before the Silver rollback if both are required. Neither rollback deletes Silver or Bronze S3 objects. Do not drop the warehouse, database, or schema if they contain other project objects.

## Cost controls

- Use the dedicated X-Small warehouse.
- Keep auto-suspend at 60 seconds.
- Keep Query Acceleration Service disabled for this small workload.
- Run bounded validation queries only.
- Leave the warehouse suspended after validation.
- Do not introduce continuous refresh, tasks, streams, or automatic per-batch model retraining.
