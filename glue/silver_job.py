"""Standalone native-PySpark Silver builder."""
from __future__ import annotations

import argparse

from pyspark.sql import SparkSession, Window, functions as F, types as T

OUTPUT_COLUMNS = (
    "order_id", "order_purchase_timestamp", "purchase_year", "purchase_month",
    "purchase_day_of_week", "purchase_hour", "approval_delay_hours",
    "approval_timestamp_missing", "promised_delivery_window_days", "customer_state",
    "item_row_count", "distinct_product_count", "distinct_seller_count",
    "item_price_total", "freight_value_total", "product_weight_g_total",
    "product_volume_cm3_total", "product_measurement_missing_item_count",
    "product_category_fallback_item_count", "primary_product_category",
    "primary_seller_state", "payment_row_count", "distinct_payment_type_count",
    "payment_value_total", "max_payment_installments", "primary_payment_type",
    "payment_data_missing", "customer_geolocation_missing",
    "seller_customer_distance_missing_count", "seller_customer_distance_km_min",
    "seller_customer_distance_km_mean", "seller_customer_distance_km_max", "delay_flag",
)

SOURCE_SCHEMAS = {
    "orders": T.StructType([T.StructField(c, T.StringType(), True) for c in (
        "order_id", "customer_id", "order_status", "order_purchase_timestamp",
        "order_approved_at", "order_delivered_carrier_date",
        "order_delivered_customer_date", "order_estimated_delivery_date")]),
    "customers": T.StructType([T.StructField(c, T.StringType(), True) for c in (
        "customer_id", "customer_unique_id", "customer_zip_code_prefix",
        "customer_city", "customer_state")]),
    "items": T.StructType([T.StructField(c, T.StringType(), True) for c in (
        "order_id", "order_item_id", "product_id", "seller_id",
        "shipping_limit_date", "price", "freight_value")]),
    "products": T.StructType([T.StructField(c, T.StringType(), True) for c in (
        "product_id", "product_category_name", "product_name_lenght",
        "product_description_lenght", "product_photos_qty", "product_weight_g",
        "product_length_cm", "product_height_cm", "product_width_cm")]),
    "sellers": T.StructType([T.StructField(c, T.StringType(), True) for c in (
        "seller_id", "seller_zip_code_prefix", "seller_city", "seller_state")]),
    "payments": T.StructType([T.StructField(c, T.StringType(), True) for c in (
        "order_id", "payment_sequential", "payment_type",
        "payment_installments", "payment_value")]),
    "geolocation": T.StructType([T.StructField(c, T.StringType(), True) for c in (
        "geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng",
        "geolocation_city", "geolocation_state")]),
    "translations": T.StructType([T.StructField(c, T.StringType(), True) for c in (
        "product_category_name", "product_category_name_english")]),
}

SOURCE_FILES = {
    "orders": "olist_orders_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "items": "olist_order_items_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "translations": "product_category_name_translation.csv",
}


def uri_join(root: str, filename: str) -> str:
    return root.rstrip("/") + "/" + filename


def read_bronze(spark: SparkSession, source_root: str):
    return {name: spark.read.option("header", True).option("mode", "FAILFAST")
            .schema(SOURCE_SCHEMAS[name]).csv(uri_join(source_root, filename))
            for name, filename in SOURCE_FILES.items()}


def _parse(frame, column, data_type):
    parsed = frame.withColumn("__parsed", F.col(column).cast(data_type))
    if parsed.where(F.col(column).isNotNull() & (F.trim(F.col(column)) != "") & F.col("__parsed").isNull()).limit(1).count():
        raise ValueError(f"{column} contains an unparseable value")
    return parsed.drop(column).withColumnRenamed("__parsed", column)


def _unique(frame, keys, name):
    if frame.groupBy(*keys).count().where(F.col("count") > 1).limit(1).count():
        raise ValueError(f"{name} has duplicate keys")


def build_silver(spark: SparkSession, source_root: str):
    f = read_bronze(spark, source_root)
    orders = f["orders"]
    for c in ("order_purchase_timestamp", "order_approved_at", "order_delivered_customer_date", "order_estimated_delivery_date"):
        orders = _parse(orders, c, "timestamp")
    for c in ("order_item_id",): f["items"] = _parse(f["items"], c, "long")
    for c in ("price", "freight_value"): f["items"] = _parse(f["items"], c, "double")
    for c in ("product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"): f["products"] = _parse(f["products"], c, "double")
    for c in ("payment_sequential", "payment_installments"): f["payments"] = _parse(f["payments"], c, "long")
    f["payments"] = _parse(f["payments"], "payment_value", "double")
    for name, keys in (("orders", ["order_id"]), ("customers", ["customer_id"]), ("products", ["product_id"]), ("sellers", ["seller_id"]), ("payments", ["order_id", "payment_sequential"]), ("translations", ["product_category_name"])): _unique(f[name], keys, name)
    orders = (orders.where((F.col("order_status") == "delivered") & F.col("order_delivered_customer_date").isNotNull() & F.col("order_estimated_delivery_date").isNotNull())
        .withColumn("delay_flag", (F.to_date("order_delivered_customer_date") > F.to_date("order_estimated_delivery_date")).cast("long"))
        .withColumn("purchase_year", F.year("order_purchase_timestamp")).withColumn("purchase_month", F.month("order_purchase_timestamp"))
        .withColumn("purchase_day_of_week", (F.dayofweek("order_purchase_timestamp") + 5) % 7).withColumn("purchase_hour", F.hour("order_purchase_timestamp"))
        .withColumn("approval_timestamp_missing", F.col("order_approved_at").isNull())
        .withColumn("approval_delay_hours", (F.col("order_approved_at").cast("long") - F.col("order_purchase_timestamp").cast("long")) / 3600.0)
        .withColumn("promised_delivery_window_days", F.datediff(F.to_date("order_estimated_delivery_date"), F.to_date("order_purchase_timestamp"))))
    customers = f["customers"].select("customer_id", "customer_zip_code_prefix", "customer_state")
    gold = orders.join(customers, "customer_id", "left")
    items = f["items"].join(f["products"], "product_id", "left").join(f["translations"], "product_category_name", "left").join(f["sellers"], "seller_id", "left")
    items = items.withColumn("category", F.when(F.col("product_category_name").isNull(), "__missing_category__").when(F.col("product_category_name_english").isNull(), F.concat(F.lit("__untranslated__:"), F.col("product_category_name"))).otherwise(F.col("product_category_name_english")))
    items = items.withColumn("measurement_missing", F.col("product_weight_g").isNull() | F.col("product_length_cm").isNull() | F.col("product_height_cm").isNull() | F.col("product_width_cm").isNull()).withColumn("category_fallback", F.col("product_category_name").isNull() | F.col("product_category_name_english").isNull()).withColumn("volume", F.col("product_length_cm") * F.col("product_height_cm") * F.col("product_width_cm"))
    ia = items.groupBy("order_id").agg(F.count("order_item_id").alias("item_row_count"), F.countDistinct("product_id").alias("distinct_product_count"), F.countDistinct("seller_id").alias("distinct_seller_count"), F.round(F.sum("price"), 2).alias("item_price_total"), F.round(F.sum("freight_value"), 2).alias("freight_value_total"), F.sum(F.col("measurement_missing").cast("long")).alias("product_measurement_missing_item_count"), F.sum(F.col("category_fallback").cast("long")).alias("product_category_fallback_item_count"), F.when(F.count("product_weight_g") == F.count("order_item_id"), F.sum("product_weight_g")).alias("product_weight_g_total"), F.when(F.count("volume") == F.count("order_item_id"), F.sum("volume")).alias("product_volume_cm3_total"))
    cat_stats = items.groupBy("order_id", "category").agg(F.sum("price").alias("v"), F.count("order_item_id").alias("n")); cw = Window.partitionBy("order_id").orderBy(F.col("v").desc(), F.col("n").desc(), F.col("category").asc()); pc = cat_stats.withColumn("rn", F.row_number().over(cw)).where("rn=1").select("order_id", F.col("category").alias("primary_product_category"))
    sell_stats = items.groupBy("order_id", "seller_id").agg(F.sum("price").alias("v"), F.count("order_item_id").alias("n"), F.first("seller_state").alias("primary_seller_state")); sw = Window.partitionBy("order_id").orderBy(F.col("v").desc(), F.col("n").desc(), F.col("seller_id").asc()); ps = sell_stats.withColumn("rn", F.row_number().over(sw)).where("rn=1").select("order_id", "primary_seller_state")
    gold = gold.join(ia.join(pc, "order_id").join(ps, "order_id"), "order_id", "left")
    payments = f["payments"]; pa = payments.groupBy("order_id").agg(F.count("payment_sequential").alias("payment_row_count"), F.countDistinct("payment_type").alias("distinct_payment_type_count"), F.round(F.sum("payment_value"), 2).alias("payment_value_total"), F.max("payment_installments").alias("max_payment_installments")); pt = payments.groupBy("order_id", "payment_type").agg(F.sum("payment_value").alias("v"), F.count("payment_sequential").alias("n")); pw = Window.partitionBy("order_id").orderBy(F.col("v").desc(), F.col("n").desc(), F.col("payment_type").asc()); pp = pt.withColumn("rn", F.row_number().over(pw)).where("rn=1").select("order_id", F.col("payment_type").alias("primary_payment_type")); gold = gold.join(pa.join(pp, "order_id"), "order_id", "left").withColumn("payment_data_missing", F.col("payment_row_count").isNull())
    for c in ("payment_row_count", "distinct_payment_type_count", "max_payment_installments"): gold = gold.withColumn(c, F.coalesce(F.col(c), F.lit(0)))
    gold = gold.withColumn("payment_value_total", F.coalesce(F.col("payment_value_total"), F.lit(0.0))).withColumn("primary_payment_type", F.coalesce(F.col("primary_payment_type"), F.lit("__missing_payment__")))
    g = f["geolocation"].withColumn("lat", F.col("geolocation_lat").cast("double")).withColumn("lng", F.col("geolocation_lng").cast("double")).where(F.col("lat").between(-34.0, 6.0) & F.col("lng").between(-74.0, -28.0)).select("geolocation_zip_code_prefix", "lat", "lng").dropDuplicates(); coords = g.groupBy("geolocation_zip_code_prefix").agg(F.median("lat").alias("zip_latitude"), F.median("lng").alias("zip_longitude"))
    gold = gold.join(coords.select(F.col("geolocation_zip_code_prefix").alias("customer_zip_code_prefix"), F.col("zip_latitude").alias("clat"), F.col("zip_longitude").alias("clng")), "customer_zip_code_prefix", "left").withColumn("customer_geolocation_missing", F.col("clat").isNull() | F.col("clng").isNull())
    pairs = items.select("order_id", "seller_id", "seller_zip_code_prefix").dropDuplicates(["order_id", "seller_id"]).join(coords.select(F.col("geolocation_zip_code_prefix").alias("seller_zip_code_prefix"), F.col("zip_latitude").alias("slat"), F.col("zip_longitude").alias("slng")), "seller_zip_code_prefix", "left").join(gold.select("order_id", "clat", "clng"), "order_id")
    lat1, lat2 = F.radians("clat"), F.radians("slat"); a = F.pow(F.sin((lat2-lat1)/2), 2) + F.cos(lat1)*F.cos(lat2)*F.pow(F.sin((F.radians("slng")-F.radians("clng"))/2), 2); a = F.least(F.lit(1.0), F.greatest(F.lit(0.0), a)); pairs = pairs.withColumn("distance", F.when(F.col("clat").isNull() | F.col("slat").isNull(), F.lit(None).cast("double")).otherwise(2*6371.0088*F.asin(F.sqrt(a)))); d = pairs.groupBy("order_id").agg(F.round(F.min("distance"), 6).alias("seller_customer_distance_km_min"), F.round(F.avg("distance"), 6).alias("seller_customer_distance_km_mean"), F.round(F.max("distance"), 6).alias("seller_customer_distance_km_max"), (F.count("seller_id")-F.count("distance")).alias("seller_customer_distance_missing_count")); gold = gold.join(d, "order_id", "left")
    return gold.select(*OUTPUT_COLUMNS)


def write_silver(frame: DataFrame, output_path: str) -> None:
    frame.write.mode("errorifexists").option("compression", "snappy").parquet(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Silver order features")
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    spark = (SparkSession.builder.appName("delivery-delay-silver-v1").getOrCreate())
    try:
        silver = build_silver(spark, args.source_root)
        write_silver(silver, args.output)
        print(f"rows={silver.count()} columns={len(silver.columns)}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
