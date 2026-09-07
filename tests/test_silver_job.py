from pathlib import Path

import pytest


pytest.importorskip("pyspark")

from glue.silver_job import OUTPUT_COLUMNS, SOURCE_SCHEMAS, parse_args, uri_join, write_silver
from pyspark.sql import functions as F
from pyspark.sql import SparkSession


@pytest.fixture(scope="module")
def spark():
    session = (SparkSession.builder.master("local[2]").appName("silver-tests")
               .config("spark.ui.enabled", "false").getOrCreate())
    yield session
    session.stop()


def test_explicit_source_schemas_preserve_identifiers_as_strings():
    for schema in SOURCE_SCHEMAS.values():
        assert all(field.dataType.simpleString() == "string" for field in schema)


def test_contract_has_exact_33_columns():
    assert len(OUTPUT_COLUMNS) == 33
    assert OUTPUT_COLUMNS[0:2] == ("order_id", "order_purchase_timestamp")
    assert OUTPUT_COLUMNS[-1] == "delay_flag"


def test_reviews_are_not_an_input():
    from glue.silver_job import SOURCE_FILES

    assert "reviews" not in SOURCE_FILES
    assert all("review" not in name for name in SOURCE_FILES.values())


def test_uri_join_preserves_s3_scheme():
    assert uri_join("data/raw", "x.csv") == "data/raw/x.csv"
    assert uri_join("s3://bucket/bronze/batch/", "x.csv") == "s3://bucket/bronze/batch/x.csv"


def test_parse_args_reads_project_arguments():
    args = parse_args(["--source-root", "s3://bucket/bronze", "--output", "s3://bucket/silver"])
    assert args.source_root == "s3://bucket/bronze"
    assert args.output == "s3://bucket/silver"


def test_parse_args_ignores_glue_injected_arguments():
    args = parse_args([
        "--source-root", "s3://bucket/bronze",
        "--output", "s3://bucket/silver",
        "--JOB_NAME", "silver-job",
        "--TempDir", "s3://bucket/temp",
    ])
    assert args.source_root == "s3://bucket/bronze"
    assert args.output == "s3://bucket/silver"


def test_parse_args_requires_project_arguments():
    with pytest.raises(SystemExit):
        parse_args(["--source-root", "s3://bucket/bronze"])
    with pytest.raises(SystemExit):
        parse_args(["--output", "s3://bucket/silver"])


def test_numeric_parse_failure_is_rejected(spark):
    from glue.silver_job import _parse

    frame = spark.createDataFrame([("bad",)], ["price"])
    with pytest.raises(ValueError, match="unparseable"):
        _parse(frame, "price", "double")


def test_spark_median_and_writer_error_if_exists(spark, tmp_path):
    geo = spark.createDataFrame(
        [("00001", "-23", "-46"), ("00001", "-21", "-44"), ("00001", "-23", "-46")],
        ["geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng"],
    )
    result = (geo.withColumn("lat", F.col("geolocation_lat").cast("double"))
              .withColumn("lng", F.col("geolocation_lng").cast("double"))
              .dropDuplicates()
              .groupBy("geolocation_zip_code_prefix")
              .agg(F.median("lat").alias("zip_latitude"), F.median("lng").alias("zip_longitude"))
              .first())
    assert result["zip_latitude"] == -22.0
    assert result["zip_longitude"] == -45.0
    output = str(tmp_path / "out")
    write_silver(spark.createDataFrame([(1,)], ["x"]), output)
    with pytest.raises(Exception):
        write_silver(spark.createDataFrame([(2,)], ["x"]), output)
