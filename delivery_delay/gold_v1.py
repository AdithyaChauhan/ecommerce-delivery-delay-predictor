"""Build the local Gold-v1 delivery-delay training dataset."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Mapping

import pandas as pd


TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
EARTH_RADIUS_KM = 6371.0088

# Inclusive conservative envelope based on IBGE's published Brazilian
# geographic extremes, with a practical margin and an eastern allowance for
# offshore territory:
# https://brasilemsintese.ibge.gov.br/territorio/dados-geograficos.html
BRAZIL_LATITUDE_MIN = -34.0
BRAZIL_LATITUDE_MAX = 6.0
BRAZIL_LONGITUDE_MIN = -74.0
BRAZIL_LONGITUDE_MAX = -28.0

GEOLOCATION_QUALITY_KEYS = (
    "raw_geolocation_rows_outside_brazil_envelope",
    "distinct_coordinate_triples_outside_brazil_envelope",
    "zip_prefixes_with_rejected_coordinates",
    "zip_prefixes_without_valid_coordinates",
)

RAW_FILES = {
    "orders": "olist_orders_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "items": "olist_order_items_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "translations": "product_category_name_translation.csv",
}

EXPECTED_SOURCE_COLUMNS = {
    "orders": (
        "order_id",
        "customer_id",
        "order_status",
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ),
    "customers": (
        "customer_id",
        "customer_unique_id",
        "customer_zip_code_prefix",
        "customer_city",
        "customer_state",
    ),
    "items": (
        "order_id",
        "order_item_id",
        "product_id",
        "seller_id",
        "shipping_limit_date",
        "price",
        "freight_value",
    ),
    "products": (
        "product_id",
        "product_category_name",
        "product_name_lenght",
        "product_description_lenght",
        "product_photos_qty",
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
    ),
    "sellers": (
        "seller_id",
        "seller_zip_code_prefix",
        "seller_city",
        "seller_state",
    ),
    "payments": (
        "order_id",
        "payment_sequential",
        "payment_type",
        "payment_installments",
        "payment_value",
    ),
    "geolocation": (
        "geolocation_zip_code_prefix",
        "geolocation_lat",
        "geolocation_lng",
        "geolocation_city",
        "geolocation_state",
    ),
    "translations": (
        "product_category_name",
        "product_category_name_english",
    ),
}

SOURCE_USE_COLUMNS = {
    "orders": (
        "order_id",
        "customer_id",
        "order_status",
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ),
    "customers": (
        "customer_id",
        "customer_zip_code_prefix",
        "customer_state",
    ),
    "items": (
        "order_id",
        "order_item_id",
        "product_id",
        "seller_id",
        "price",
        "freight_value",
    ),
    "products": (
        "product_id",
        "product_category_name",
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
    ),
    "sellers": (
        "seller_id",
        "seller_zip_code_prefix",
        "seller_state",
    ),
    "payments": EXPECTED_SOURCE_COLUMNS["payments"],
    "geolocation": (
        "geolocation_zip_code_prefix",
        "geolocation_lat",
        "geolocation_lng",
    ),
    "translations": EXPECTED_SOURCE_COLUMNS["translations"],
}

METADATA_COLUMNS = (
    "order_id",
    "order_purchase_timestamp",
)

MODEL_FEATURE_COLUMNS = (
    "purchase_year",
    "purchase_month",
    "purchase_day_of_week",
    "purchase_hour",
    "approval_delay_hours",
    "approval_timestamp_missing",
    "promised_delivery_window_days",
    "customer_state",
    "item_row_count",
    "distinct_product_count",
    "distinct_seller_count",
    "item_price_total",
    "freight_value_total",
    "product_weight_g_total",
    "product_volume_cm3_total",
    "product_measurement_missing_item_count",
    "product_category_fallback_item_count",
    "primary_product_category",
    "primary_seller_state",
    "payment_row_count",
    "distinct_payment_type_count",
    "payment_value_total",
    "max_payment_installments",
    "primary_payment_type",
    "payment_data_missing",
    "customer_geolocation_missing",
    "seller_customer_distance_missing_count",
    "seller_customer_distance_km_min",
    "seller_customer_distance_km_mean",
    "seller_customer_distance_km_max",
)

TARGET_COLUMN = "delay_flag"
OUTPUT_COLUMNS = METADATA_COLUMNS + MODEL_FEATURE_COLUMNS + (TARGET_COLUMN,)

FORBIDDEN_FEATURE_COLUMNS = frozenset(
    {
        "order_id",
        "customer_id",
        "customer_unique_id",
        "order_item_id",
        "product_id",
        "seller_id",
        "payment_sequential",
        "review_id",
        "order_status",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "shipping_limit_date",
        "review_score",
        "review_comment_title",
        "review_comment_message",
        "review_creation_date",
        "review_answer_timestamp",
        TARGET_COLUMN,
    }
)

EXPECTED_GOLD_METRICS = {
    "rows": 96_470,
    "unique_order_id": 96_470,
    "late": 6_534,
    "on_time": 89_936,
    "eligible_orders_without_payment": 1,
}


def _require_columns(frame: pd.DataFrame, columns: tuple[str, ...], name: str) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"{name} is missing required columns: {missing}")


def _validate_unique_key(
    frame: pd.DataFrame, columns: list[str], name: str
) -> None:
    if frame[columns].isna().any(axis=None):
        raise ValueError(f"{name} contains a missing key value in {columns}")
    duplicated = frame.duplicated(subset=columns, keep=False)
    if duplicated.any():
        raise ValueError(
            f"{name} contains {int(duplicated.sum())} rows in duplicate key groups for {columns}"
        )


def _require_nonmissing(
    frame: pd.DataFrame, columns: tuple[str, ...], name: str
) -> None:
    missing = frame[list(columns)].isna().sum()
    missing = missing[missing > 0]
    if not missing.empty:
        raise ValueError(f"{name} has unexpected missing values: {missing.to_dict()}")


def _parse_datetime(series: pd.Series, column: str) -> pd.Series:
    try:
        return pd.to_datetime(series, format=TIMESTAMP_FORMAT, errors="raise")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{column} contains an invalid timestamp") from exc


def _parse_float(series: pd.Series, column: str) -> pd.Series:
    try:
        return pd.to_numeric(series, errors="raise").astype("Float64")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{column} contains a non-numeric value") from exc


def _parse_integer(series: pd.Series, column: str) -> pd.Series:
    numeric = _parse_float(series, column)
    non_integral = numeric.dropna() % 1 != 0
    if non_integral.any():
        raise ValueError(f"{column} contains a non-integer value")
    return numeric.astype("Int64")


def _require_nonnegative(series: pd.Series, column: str) -> None:
    if (series.dropna() < 0).any():
        raise ValueError(f"{column} contains a negative value")


def _assert_foreign_key(
    child: pd.DataFrame,
    parent: pd.DataFrame,
    key: str,
    relationship: str,
) -> None:
    probe = child[[key]].merge(
        parent[[key]],
        how="left",
        on=key,
        validate="many_to_one",
        indicator=True,
    )
    missing = int((probe["_merge"] != "both").sum())
    if missing:
        raise ValueError(f"{relationship} has {missing} unmatched rows")


def read_sources(raw_dir: Path) -> dict[str, pd.DataFrame]:
    """Read only the eight approved Gold-v1 inputs; reviews are never opened."""
    frames: dict[str, pd.DataFrame] = {}
    for name, filename in RAW_FILES.items():
        path = raw_dir / filename
        header = pd.read_csv(path, nrows=0)
        actual_columns = tuple(header.columns)
        if actual_columns != EXPECTED_SOURCE_COLUMNS[name]:
            raise ValueError(
                f"{filename} columns differ from the audited schema: {actual_columns}"
            )
        frames[name] = pd.read_csv(
            path,
            usecols=list(SOURCE_USE_COLUMNS[name]),
            dtype="string",
        )
    return frames


def prepare_sources(
    raw_frames: Mapping[str, pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    """Validate required columns and explicitly parse timestamps and numerics."""
    missing_frames = sorted(set(RAW_FILES) - set(raw_frames))
    if missing_frames:
        raise ValueError(f"Missing source frames: {missing_frames}")

    frames = {name: raw_frames[name].copy() for name in RAW_FILES}
    for name, columns in SOURCE_USE_COLUMNS.items():
        _require_columns(frames[name], columns, name)

    orders = frames["orders"]
    for column in (
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ):
        orders[column] = _parse_datetime(orders[column], column)

    items = frames["items"]
    items["order_item_id"] = _parse_integer(items["order_item_id"], "order_item_id")
    for column in ("price", "freight_value"):
        items[column] = _parse_float(items[column], column)
        _require_nonnegative(items[column], column)

    products = frames["products"]
    for column in (
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
    ):
        products[column] = _parse_float(products[column], column)
        _require_nonnegative(products[column], column)

    payments = frames["payments"]
    for column in ("payment_sequential", "payment_installments"):
        payments[column] = _parse_integer(payments[column], column)
        _require_nonnegative(payments[column], column)
    payments["payment_value"] = _parse_float(
        payments["payment_value"], "payment_value"
    )
    _require_nonnegative(payments["payment_value"], "payment_value")

    _validate_unique_key(orders, ["order_id"], "orders")
    _validate_unique_key(frames["customers"], ["customer_id"], "customers")
    _validate_unique_key(items, ["order_id", "order_item_id"], "items")
    _validate_unique_key(products, ["product_id"], "products")
    _validate_unique_key(frames["sellers"], ["seller_id"], "sellers")
    _validate_unique_key(
        payments, ["order_id", "payment_sequential"], "payments"
    )
    _validate_unique_key(
        frames["translations"], ["product_category_name"], "translations"
    )

    _require_nonmissing(
        orders,
        (
            "order_id",
            "customer_id",
            "order_status",
            "order_purchase_timestamp",
            "order_estimated_delivery_date",
        ),
        "orders",
    )
    _require_nonmissing(
        frames["customers"],
        ("customer_id", "customer_zip_code_prefix", "customer_state"),
        "customers",
    )
    _require_nonmissing(
        items,
        (
            "order_id",
            "order_item_id",
            "product_id",
            "seller_id",
            "price",
            "freight_value",
        ),
        "items",
    )
    _require_nonmissing(
        frames["sellers"],
        ("seller_id", "seller_zip_code_prefix", "seller_state"),
        "sellers",
    )
    _require_nonmissing(
        payments,
        (
            "order_id",
            "payment_sequential",
            "payment_type",
            "payment_installments",
            "payment_value",
        ),
        "payments",
    )
    _require_nonmissing(
        frames["translations"],
        ("product_category_name", "product_category_name_english"),
        "translations",
    )
    return frames


def build_eligible_orders(orders: pd.DataFrame) -> pd.DataFrame:
    """Create the verified cohort, target, and approval-time order features."""
    eligible = orders.loc[
        orders["order_status"].eq("delivered")
        & orders["order_delivered_customer_date"].notna()
        & orders["order_estimated_delivery_date"].notna()
    ].copy()

    purchase_date = eligible["order_purchase_timestamp"].dt.normalize()
    delivered_date = eligible["order_delivered_customer_date"].dt.normalize()
    estimated_date = eligible["order_estimated_delivery_date"].dt.normalize()

    eligible[TARGET_COLUMN] = (delivered_date > estimated_date).astype("int8")
    eligible["purchase_year"] = eligible["order_purchase_timestamp"].dt.year
    eligible["purchase_month"] = eligible["order_purchase_timestamp"].dt.month
    eligible["purchase_day_of_week"] = (
        eligible["order_purchase_timestamp"].dt.dayofweek
    )
    eligible["purchase_hour"] = eligible["order_purchase_timestamp"].dt.hour
    eligible["approval_timestamp_missing"] = eligible["order_approved_at"].isna()
    eligible["approval_delay_hours"] = (
        eligible["order_approved_at"] - eligible["order_purchase_timestamp"]
    ).dt.total_seconds() / 3600.0
    eligible["promised_delivery_window_days"] = (
        estimated_date - purchase_date
    ).dt.days

    return eligible[
        [
            "order_id",
            "customer_id",
            "order_purchase_timestamp",
            "purchase_year",
            "purchase_month",
            "purchase_day_of_week",
            "purchase_hour",
            "approval_delay_hours",
            "approval_timestamp_missing",
            "promised_delivery_window_days",
            TARGET_COLUMN,
        ]
    ]


def _prepare_geolocation(
    geolocation: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Filter coordinates and return ZIP medians with rejection counts."""
    coordinate_columns = [
        "geolocation_zip_code_prefix",
        "geolocation_lat",
        "geolocation_lng",
    ]
    _require_columns(geolocation, tuple(coordinate_columns), "geolocation")
    coordinates = geolocation[coordinate_columns].copy()
    _require_nonmissing(coordinates, tuple(coordinate_columns), "geolocation")
    coordinates["geolocation_lat"] = _parse_float(
        coordinates["geolocation_lat"], "geolocation_lat"
    )
    coordinates["geolocation_lng"] = _parse_float(
        coordinates["geolocation_lng"], "geolocation_lng"
    )

    if (~coordinates["geolocation_lat"].between(-90, 90)).any():
        raise ValueError("geolocation_lat contains a globally invalid coordinate")
    if (~coordinates["geolocation_lng"].between(-180, 180)).any():
        raise ValueError("geolocation_lng contains a globally invalid coordinate")

    outside_brazil = ~(
        coordinates["geolocation_lat"].between(
            BRAZIL_LATITUDE_MIN, BRAZIL_LATITUDE_MAX, inclusive="both"
        )
        & coordinates["geolocation_lng"].between(
            BRAZIL_LONGITUDE_MIN, BRAZIL_LONGITUDE_MAX, inclusive="both"
        )
    )
    rejected = coordinates.loc[outside_brazil]
    valid_coordinates = coordinates.loc[~outside_brazil].drop_duplicates(
        subset=coordinate_columns
    )

    all_zip_prefixes = set(coordinates["geolocation_zip_code_prefix"])
    valid_zip_prefixes = set(valid_coordinates["geolocation_zip_code_prefix"])
    geolocation_quality = {
        "raw_geolocation_rows_outside_brazil_envelope": int(outside_brazil.sum()),
        "distinct_coordinate_triples_outside_brazil_envelope": int(
            len(rejected.drop_duplicates(subset=coordinate_columns))
        ),
        "zip_prefixes_with_rejected_coordinates": int(
            rejected["geolocation_zip_code_prefix"].nunique()
        ),
        "zip_prefixes_without_valid_coordinates": int(
            len(all_zip_prefixes - valid_zip_prefixes)
        ),
    }

    aggregated = (
        valid_coordinates.groupby("geolocation_zip_code_prefix", as_index=False)
        .agg(
            zip_latitude=("geolocation_lat", "median"),
            zip_longitude=("geolocation_lng", "median"),
        )
        .sort_values("geolocation_zip_code_prefix", kind="stable")
        .reset_index(drop=True)
    )
    _validate_unique_key(
        aggregated, ["geolocation_zip_code_prefix"], "ZIP coordinates"
    )
    return aggregated, geolocation_quality


def aggregate_geolocation(geolocation: pd.DataFrame) -> pd.DataFrame:
    """Return one coordinate-wise median per ZIP from valid coordinates."""
    aggregated, _ = _prepare_geolocation(geolocation)
    return aggregated


def _rank_primary_category(enriched_items: pd.DataFrame) -> pd.DataFrame:
    category_stats = (
        enriched_items.groupby(
            ["order_id", "normalized_product_category"], as_index=False
        )
        .agg(
            category_price_total=("price", "sum"),
            category_item_row_count=("order_item_id", "size"),
        )
        .sort_values(
            [
                "order_id",
                "category_price_total",
                "category_item_row_count",
                "normalized_product_category",
            ],
            ascending=[True, False, False, True],
            kind="stable",
        )
    )
    primary = category_stats.drop_duplicates("order_id", keep="first")
    return primary[["order_id", "normalized_product_category"]].rename(
        columns={"normalized_product_category": "primary_product_category"}
    )


def _rank_primary_seller(enriched_items: pd.DataFrame) -> pd.DataFrame:
    seller_stats = (
        enriched_items.groupby(["order_id", "seller_id"], as_index=False)
        .agg(
            seller_price_total=("price", "sum"),
            seller_item_row_count=("order_item_id", "size"),
            primary_seller_state=("seller_state", "first"),
        )
        .sort_values(
            ["order_id", "seller_price_total", "seller_item_row_count", "seller_id"],
            ascending=[True, False, False, True],
            kind="stable",
        )
    )
    return seller_stats.drop_duplicates("order_id", keep="first")[[
        "order_id",
        "primary_seller_state",
    ]]


def aggregate_items(
    items: pd.DataFrame,
    products: pd.DataFrame,
    translations: pd.DataFrame,
    sellers: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Aggregate item, product, and seller facts to one row per order."""
    enriched = items.merge(
        products,
        how="left",
        on="product_id",
        validate="many_to_one",
        indicator="_product_merge",
    )
    unmatched_products = int((enriched["_product_merge"] != "both").sum())
    if unmatched_products:
        raise ValueError(f"items have {unmatched_products} unmatched product rows")
    enriched = enriched.drop(columns="_product_merge")

    enriched = enriched.merge(
        translations,
        how="left",
        on="product_category_name",
        validate="many_to_one",
    )
    enriched = enriched.merge(
        sellers,
        how="left",
        on="seller_id",
        validate="many_to_one",
        indicator="_seller_merge",
    )
    unmatched_sellers = int((enriched["_seller_merge"] != "both").sum())
    if unmatched_sellers:
        raise ValueError(f"items have {unmatched_sellers} unmatched seller rows")
    enriched = enriched.drop(columns="_seller_merge")

    source_missing = enriched["product_category_name"].isna()
    translation_missing = enriched["product_category_name_english"].isna()
    enriched["normalized_product_category"] = enriched[
        "product_category_name_english"
    ].copy()
    enriched.loc[source_missing, "normalized_product_category"] = (
        "__missing_category__"
    )
    untranslated = ~source_missing & translation_missing
    enriched.loc[untranslated, "normalized_product_category"] = (
        "__untranslated__:" + enriched.loc[untranslated, "product_category_name"]
    )
    enriched["product_category_fallback"] = source_missing | translation_missing

    measurement_columns = [
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
    ]
    enriched["product_measurement_missing"] = enriched[measurement_columns].isna().any(
        axis=1
    )
    enriched["product_volume_cm3"] = (
        enriched["product_length_cm"]
        * enriched["product_height_cm"]
        * enriched["product_width_cm"]
    )

    grouped = enriched.groupby("order_id", sort=False)
    aggregate = grouped.agg(
        item_row_count=("order_item_id", "size"),
        distinct_product_count=("product_id", "nunique"),
        distinct_seller_count=("seller_id", "nunique"),
        item_price_total=("price", "sum"),
        freight_value_total=("freight_value", "sum"),
        product_measurement_missing_item_count=(
            "product_measurement_missing",
            "sum",
        ),
        product_category_fallback_item_count=("product_category_fallback", "sum"),
    ).reset_index()

    group_sizes = grouped.size()
    weight_total = grouped["product_weight_g"].sum(min_count=1)
    weight_total = weight_total.mask(
        grouped["product_weight_g"].count() < group_sizes
    )
    volume_total = grouped["product_volume_cm3"].sum(min_count=1)
    volume_total = volume_total.mask(
        grouped["product_volume_cm3"].count() < group_sizes
    )
    aggregate = aggregate.merge(
        weight_total.rename("product_weight_g_total"),
        how="left",
        on="order_id",
        validate="one_to_one",
    ).merge(
        volume_total.rename("product_volume_cm3_total"),
        how="left",
        on="order_id",
        validate="one_to_one",
    )

    aggregate["item_price_total"] = aggregate["item_price_total"].round(2)
    aggregate["freight_value_total"] = aggregate["freight_value_total"].round(2)
    aggregate = aggregate.merge(
        _rank_primary_category(enriched),
        how="left",
        on="order_id",
        validate="one_to_one",
    ).merge(
        _rank_primary_seller(enriched),
        how="left",
        on="order_id",
        validate="one_to_one",
    )

    seller_pairs = enriched[
        ["order_id", "seller_id", "seller_zip_code_prefix"]
    ].drop_duplicates(["order_id", "seller_id"])
    return aggregate, seller_pairs


def aggregate_payments(payments: pd.DataFrame) -> pd.DataFrame:
    """Aggregate payment rows and select the primary payment type."""
    grouped = payments.groupby("order_id", sort=False)
    aggregate = grouped.agg(
        payment_row_count=("payment_sequential", "size"),
        distinct_payment_type_count=("payment_type", "nunique"),
        payment_value_total=("payment_value", "sum"),
        max_payment_installments=("payment_installments", "max"),
    ).reset_index()
    aggregate["payment_value_total"] = aggregate["payment_value_total"].round(2)

    payment_type_stats = (
        payments.groupby(["order_id", "payment_type"], as_index=False)
        .agg(
            type_payment_value_total=("payment_value", "sum"),
            type_payment_row_count=("payment_sequential", "size"),
        )
        .sort_values(
            [
                "order_id",
                "type_payment_value_total",
                "type_payment_row_count",
                "payment_type",
            ],
            ascending=[True, False, False, True],
            kind="stable",
        )
    )
    primary = payment_type_stats.drop_duplicates("order_id", keep="first")[[
        "order_id",
        "payment_type",
    ]].rename(columns={"payment_type": "primary_payment_type"})
    return aggregate.merge(
        primary,
        how="left",
        on="order_id",
        validate="one_to_one",
    )


def haversine_km(
    customer_latitude: float,
    customer_longitude: float,
    seller_latitude: float,
    seller_longitude: float,
) -> float | None:
    """Calculate great-circle distance and clamp rounding noise before asin."""
    values = (
        customer_latitude,
        customer_longitude,
        seller_latitude,
        seller_longitude,
    )
    if any(pd.isna(value) for value in values):
        return None

    customer_latitude_rad = math.radians(float(customer_latitude))
    customer_longitude_rad = math.radians(float(customer_longitude))
    seller_latitude_rad = math.radians(float(seller_latitude))
    seller_longitude_rad = math.radians(float(seller_longitude))
    latitude_delta = seller_latitude_rad - customer_latitude_rad
    longitude_delta = seller_longitude_rad - customer_longitude_rad
    a = (
        math.sin(latitude_delta / 2.0) ** 2
        + math.cos(customer_latitude_rad)
        * math.cos(seller_latitude_rad)
        * math.sin(longitude_delta / 2.0) ** 2
    )
    a = min(1.0, max(0.0, a))
    return 2.0 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def add_distance_features(
    orders: pd.DataFrame,
    seller_pairs: pd.DataFrame,
    zip_coordinates: pd.DataFrame,
) -> pd.DataFrame:
    """Left-join ZIP coordinates and aggregate distinct-seller distances."""
    customer_coordinates = zip_coordinates.rename(
        columns={
            "geolocation_zip_code_prefix": "customer_zip_code_prefix",
            "zip_latitude": "customer_latitude",
            "zip_longitude": "customer_longitude",
        }
    )
    result = orders.merge(
        customer_coordinates,
        how="left",
        on="customer_zip_code_prefix",
        validate="many_to_one",
    )
    result["customer_geolocation_missing"] = result[
        ["customer_latitude", "customer_longitude"]
    ].isna().any(axis=1)

    seller_coordinates = zip_coordinates.rename(
        columns={
            "geolocation_zip_code_prefix": "seller_zip_code_prefix",
            "zip_latitude": "seller_latitude",
            "zip_longitude": "seller_longitude",
        }
    )
    pairs = seller_pairs.merge(
        seller_coordinates,
        how="left",
        on="seller_zip_code_prefix",
        validate="many_to_one",
    ).merge(
        result[
            ["order_id", "customer_latitude", "customer_longitude"]
        ],
        how="left",
        on="order_id",
        validate="many_to_one",
    )
    pairs["seller_customer_distance_km"] = [
        haversine_km(
            row.customer_latitude,
            row.customer_longitude,
            row.seller_latitude,
            row.seller_longitude,
        )
        for row in pairs.itertuples(index=False)
    ]
    pairs["seller_customer_distance_km"] = pd.Series(
        pairs["seller_customer_distance_km"], dtype="Float64"
    )

    distance_group = pairs.groupby("order_id", sort=False)[
        "seller_customer_distance_km"
    ]
    distances = distance_group.agg(
        seller_customer_distance_km_min="min",
        seller_customer_distance_km_mean="mean",
        seller_customer_distance_km_max="max",
    )
    distances["seller_customer_distance_missing_count"] = (
        distance_group.size() - distance_group.count()
    )
    for column in (
        "seller_customer_distance_km_min",
        "seller_customer_distance_km_mean",
        "seller_customer_distance_km_max",
    ):
        distances[column] = distances[column].round(6)
    distances = distances.reset_index()

    return result.merge(
        distances,
        how="left",
        on="order_id",
        validate="one_to_one",
    )


def build_gold_v1(raw_frames: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    """Transform raw source frames into exactly one row per eligible order."""
    frames = prepare_sources(raw_frames)
    orders = frames["orders"]
    customers = frames["customers"]
    items = frames["items"]
    payments = frames["payments"]

    customer_probe = orders[["customer_id"]].merge(
        customers[["customer_id"]],
        how="left",
        on="customer_id",
        validate="one_to_one",
        indicator=True,
    )
    if (customer_probe["_merge"] != "both").any():
        raise ValueError("not every order has exactly one customer record")
    _assert_foreign_key(items, orders, "order_id", "items-to-orders")
    _assert_foreign_key(payments, orders, "order_id", "payments-to-orders")

    eligible = build_eligible_orders(orders)
    gold = eligible.merge(
        customers,
        how="left",
        on="customer_id",
        validate="one_to_one",
        indicator="_customer_merge",
    )
    if (gold["_customer_merge"] != "both").any():
        raise ValueError("an eligible order is missing its customer record")
    gold = gold.drop(columns="_customer_merge")

    item_aggregate, seller_pairs = aggregate_items(
        items,
        frames["products"],
        frames["translations"],
        frames["sellers"],
    )
    gold = gold.merge(
        item_aggregate,
        how="left",
        on="order_id",
        validate="one_to_one",
        indicator="_item_merge",
    )
    if (gold["_item_merge"] != "both").any():
        raise ValueError("an eligible order is missing item data")
    gold = gold.drop(columns="_item_merge")

    payment_aggregate = aggregate_payments(payments)
    gold = gold.merge(
        payment_aggregate,
        how="left",
        on="order_id",
        validate="one_to_one",
        indicator="_payment_merge",
    )
    gold["payment_data_missing"] = gold["_payment_merge"].eq("left_only")
    gold = gold.drop(columns="_payment_merge")
    for column in (
        "payment_row_count",
        "distinct_payment_type_count",
        "payment_value_total",
        "max_payment_installments",
    ):
        gold[column] = gold[column].fillna(0)
    gold["primary_payment_type"] = gold["primary_payment_type"].fillna(
        "__missing_payment__"
    )

    zip_coordinates, geolocation_quality = _prepare_geolocation(
        frames["geolocation"]
    )
    eligible_seller_pairs = seller_pairs.loc[
        seller_pairs["order_id"].isin(gold["order_id"])
    ]
    gold = add_distance_features(gold, eligible_seller_pairs, zip_coordinates)

    for column in (
        "item_row_count",
        "distinct_product_count",
        "distinct_seller_count",
        "product_measurement_missing_item_count",
        "product_category_fallback_item_count",
        "payment_row_count",
        "distinct_payment_type_count",
        "max_payment_installments",
        "seller_customer_distance_missing_count",
    ):
        gold[column] = gold[column].astype("int64")
    for column in (
        "item_price_total",
        "freight_value_total",
        "product_weight_g_total",
        "product_volume_cm3_total",
        "payment_value_total",
        "seller_customer_distance_km_min",
        "seller_customer_distance_km_mean",
        "seller_customer_distance_km_max",
    ):
        gold[column] = gold[column].astype("Float64")

    gold = gold.sort_values(
        ["order_purchase_timestamp", "order_id"], kind="stable"
    ).reset_index(drop=True)
    result = gold[list(OUTPUT_COLUMNS)].copy()
    result.attrs["geolocation_quality"] = geolocation_quality
    return result


def build_summary(gold: pd.DataFrame) -> dict[str, int]:
    target_counts = gold[TARGET_COLUMN].value_counts()
    return {
        "rows": len(gold),
        "unique_order_id": int(gold["order_id"].nunique()),
        "late": int(target_counts.get(1, 0)),
        "on_time": int(target_counts.get(0, 0)),
        "eligible_orders_without_payment": int(gold["payment_data_missing"].sum()),
    }


def quality_summary(gold: pd.DataFrame) -> dict[str, object]:
    geolocation_quality = gold.attrs.get("geolocation_quality")
    if not isinstance(geolocation_quality, dict) or any(
        key not in geolocation_quality for key in GEOLOCATION_QUALITY_KEYS
    ):
        raise ValueError("Gold-v1 is missing geolocation quality metadata")

    distance = gold["seller_customer_distance_km_mean"].dropna()
    distance_summary = {
        "minimum": float(distance.min()) if not distance.empty else None,
        "median": float(distance.median()) if not distance.empty else None,
        "p95": float(distance.quantile(0.95)) if not distance.empty else None,
        "p99": float(distance.quantile(0.99)) if not distance.empty else None,
        "maximum": float(distance.max()) if not distance.empty else None,
    }
    return {
        **{
            key: int(geolocation_quality[key])
            for key in GEOLOCATION_QUALITY_KEYS
        },
        "missing_values_by_column": {
            column: int(gold[column].isna().sum()) for column in OUTPUT_COLUMNS
        },
        "negative_approval_delay_count": int(
            gold["approval_delay_hours"].lt(0).fillna(False).sum()
        ),
        "negative_promised_window_count": int(
            gold["promised_delivery_window_days"].lt(0).fillna(False).sum()
        ),
        "orders_missing_customer_coordinates": int(
            gold["customer_geolocation_missing"].sum()
        ),
        "orders_with_no_available_seller_customer_distance": int(
            gold["seller_customer_distance_km_mean"].isna().sum()
        ),
        "seller_customer_distance_km_mean_distribution": distance_summary,
    }


def validate_gold_v1(
    gold: pd.DataFrame, *, verify_known_counts: bool = False
) -> dict[str, int]:
    if tuple(gold.columns) != OUTPUT_COLUMNS:
        raise ValueError("Gold-v1 columns or column order differ from the contract")
    if set(MODEL_FEATURE_COLUMNS) & FORBIDDEN_FEATURE_COLUMNS:
        raise ValueError("The model-feature whitelist contains a forbidden column")
    if set(METADATA_COLUMNS) & set(MODEL_FEATURE_COLUMNS):
        raise ValueError("Metadata leaked into the model-feature whitelist")
    if TARGET_COLUMN in MODEL_FEATURE_COLUMNS:
        raise ValueError("The target leaked into the model-feature whitelist")
    if gold["order_id"].isna().any() or not gold["order_id"].is_unique:
        raise ValueError("Gold-v1 must contain one unique, non-missing order_id per row")
    if gold["order_purchase_timestamp"].isna().any():
        raise ValueError("Gold-v1 contains a missing purchase timestamp")
    if not set(gold[TARGET_COLUMN].unique()).issubset({0, 1}):
        raise ValueError("delay_flag contains a value other than 0 or 1")

    summary = build_summary(gold)
    if verify_known_counts and summary != EXPECTED_GOLD_METRICS:
        raise ValueError(
            f"Gold-v1 metrics differ from the verified contract: {summary}"
        )
    return summary


def write_gold_v1(gold: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    gold.to_parquet(output_path, engine="pyarrow", index=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build and validate the local Gold-v1 dataset."
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/raw"),
        help="Directory containing the audited Olist CSV files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/gold_v1.parquet"),
        help="Ignored Parquet output path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw_frames = read_sources(args.raw_dir)
    gold = build_gold_v1(raw_frames)
    summary = validate_gold_v1(gold, verify_known_counts=True)
    quality = quality_summary(gold)
    write_gold_v1(gold, args.output)
    print(json.dumps({"build_summary": summary, "quality_summary": quality}, indent=2))
    print(f"output={args.output} bytes={args.output.stat().st_size}")


if __name__ == "__main__":
    main()
