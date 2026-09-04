from __future__ import annotations

import math

import pandas as pd
import pytest

from delivery_delay.gold_v1 import (
    FORBIDDEN_FEATURE_COLUMNS,
    MODEL_FEATURE_COLUMNS,
    OUTPUT_COLUMNS,
    RAW_FILES,
    aggregate_geolocation,
    build_gold_v1,
    haversine_km,
    quality_summary,
    validate_gold_v1,
    write_gold_v1,
)


@pytest.fixture
def raw_frames() -> dict[str, pd.DataFrame]:
    orders = pd.DataFrame(
        [
            {
                "order_id": "same_date",
                "customer_id": "c1",
                "order_status": "delivered",
                "order_purchase_timestamp": "2020-01-01 10:00:00",
                "order_approved_at": "2020-01-01 12:00:00",
                "order_delivered_customer_date": "2020-01-05 23:59:59",
                "order_estimated_delivery_date": "2020-01-05 00:00:00",
            },
            {
                "order_id": "later_date",
                "customer_id": "c2",
                "order_status": "delivered",
                "order_purchase_timestamp": "2020-01-02 08:00:00",
                "order_approved_at": "2020-01-02 09:00:00",
                "order_delivered_customer_date": "2020-01-07 00:00:01",
                "order_estimated_delivery_date": "2020-01-06 23:59:59",
            },
            {
                "order_id": "no_payment",
                "customer_id": "c3",
                "order_status": "delivered",
                "order_purchase_timestamp": "2020-01-03 08:00:00",
                "order_approved_at": None,
                "order_delivered_customer_date": "2020-01-04 12:00:00",
                "order_estimated_delivery_date": "2020-01-05 12:00:00",
            },
            {
                "order_id": "canceled",
                "customer_id": "c4",
                "order_status": "canceled",
                "order_purchase_timestamp": "2020-01-04 08:00:00",
                "order_approved_at": "2020-01-04 09:00:00",
                "order_delivered_customer_date": None,
                "order_estimated_delivery_date": "2020-01-10 00:00:00",
            },
        ]
    )
    customers = pd.DataFrame(
        [
            {
                "customer_id": "c1",
                "customer_zip_code_prefix": "00001",
                "customer_state": "SP",
            },
            {
                "customer_id": "c2",
                "customer_zip_code_prefix": "00002",
                "customer_state": "RJ",
            },
            {
                "customer_id": "c3",
                "customer_zip_code_prefix": "99999",
                "customer_state": "MG",
            },
            {
                "customer_id": "c4",
                "customer_zip_code_prefix": "00004",
                "customer_state": "BA",
            },
        ]
    )
    items = pd.DataFrame(
        [
            {
                "order_id": "same_date",
                "order_item_id": "1",
                "product_id": "p1",
                "seller_id": "s2",
                "price": "10.00",
                "freight_value": "2.00",
            },
            {
                "order_id": "same_date",
                "order_item_id": "2",
                "product_id": "p2",
                "seller_id": "s1",
                "price": "10.00",
                "freight_value": "3.00",
            },
            {
                "order_id": "later_date",
                "order_item_id": "1",
                "product_id": "p1",
                "seller_id": "s1",
                "price": "5.00",
                "freight_value": "1.00",
            },
            {
                "order_id": "no_payment",
                "order_item_id": "1",
                "product_id": "p3",
                "seller_id": "s1",
                "price": "7.00",
                "freight_value": "1.50",
            },
            {
                "order_id": "canceled",
                "order_item_id": "1",
                "product_id": "p1",
                "seller_id": "s1",
                "price": "4.00",
                "freight_value": "1.00",
            },
        ]
    )
    products = pd.DataFrame(
        [
            {
                "product_id": "p1",
                "product_category_name": "cat_a",
                "product_weight_g": "100",
                "product_length_cm": "1",
                "product_height_cm": "2",
                "product_width_cm": "3",
            },
            {
                "product_id": "p2",
                "product_category_name": "cat_b",
                "product_weight_g": "200",
                "product_length_cm": "2",
                "product_height_cm": "3",
                "product_width_cm": "4",
            },
            {
                "product_id": "p3",
                "product_category_name": None,
                "product_weight_g": None,
                "product_length_cm": None,
                "product_height_cm": None,
                "product_width_cm": None,
            },
        ]
    )
    sellers = pd.DataFrame(
        [
            {
                "seller_id": "s1",
                "seller_zip_code_prefix": "11111",
                "seller_state": "SP",
            },
            {
                "seller_id": "s2",
                "seller_zip_code_prefix": "88888",
                "seller_state": "RJ",
            },
        ]
    )
    payments = pd.DataFrame(
        [
            {
                "order_id": "same_date",
                "payment_sequential": "1",
                "payment_type": "voucher",
                "payment_installments": "1",
                "payment_value": "5.00",
            },
            {
                "order_id": "same_date",
                "payment_sequential": "2",
                "payment_type": "credit_card",
                "payment_installments": "1",
                "payment_value": "5.00",
            },
            {
                "order_id": "later_date",
                "payment_sequential": "1",
                "payment_type": "boleto",
                "payment_installments": "1",
                "payment_value": "6.00",
            },
            {
                "order_id": "canceled",
                "payment_sequential": "1",
                "payment_type": "credit_card",
                "payment_installments": "2",
                "payment_value": "5.00",
            },
        ]
    )
    geolocation = pd.DataFrame(
        [
            {
                "geolocation_zip_code_prefix": "00001",
                "geolocation_lat": "-23",
                "geolocation_lng": "-46",
            },
            {
                "geolocation_zip_code_prefix": "00001",
                "geolocation_lat": "-23",
                "geolocation_lng": "-46",
            },
            {
                "geolocation_zip_code_prefix": "00001",
                "geolocation_lat": "-21",
                "geolocation_lng": "-44",
            },
            {
                "geolocation_zip_code_prefix": "00002",
                "geolocation_lat": "-22",
                "geolocation_lng": "-43",
            },
            {
                "geolocation_zip_code_prefix": "11111",
                "geolocation_lat": "-23",
                "geolocation_lng": "-47",
            },
        ]
    )
    translations = pd.DataFrame(
        [
            {
                "product_category_name": "cat_a",
                "product_category_name_english": "Alpha",
            },
            {
                "product_category_name": "cat_b",
                "product_category_name_english": "Beta",
            },
        ]
    )
    return {
        "orders": orders,
        "customers": customers,
        "items": items,
        "products": products,
        "sellers": sellers,
        "payments": payments,
        "geolocation": geolocation,
        "translations": translations,
    }


def test_calendar_date_target_and_unique_order_grain(raw_frames):
    gold = build_gold_v1(raw_frames)

    assert len(gold) == 3
    assert gold["order_id"].is_unique
    target = gold.set_index("order_id")["delay_flag"].to_dict()
    assert target["same_date"] == 0
    assert target["later_date"] == 1
    assert target["no_payment"] == 0


def test_item_aggregation_does_not_multiply_orders(raw_frames):
    gold = build_gold_v1(raw_frames).set_index("order_id")

    assert gold.loc["same_date", "item_row_count"] == 2
    assert gold.loc["same_date", "distinct_product_count"] == 2
    assert gold.loc["same_date", "distinct_seller_count"] == 2
    assert gold.loc["same_date", "item_price_total"] == pytest.approx(20.0)
    assert gold.loc["same_date", "freight_value_total"] == pytest.approx(5.0)


def test_payment_left_join_preserves_missing_payment_order(raw_frames):
    gold = build_gold_v1(raw_frames).set_index("order_id")

    missing = gold.loc["no_payment"]
    assert missing["payment_data_missing"]
    assert missing["payment_row_count"] == 0
    assert missing["distinct_payment_type_count"] == 0
    assert missing["payment_value_total"] == pytest.approx(0.0)
    assert missing["max_payment_installments"] == 0
    assert missing["primary_payment_type"] == "__missing_payment__"


def test_coordinate_duplicates_are_removed_before_deterministic_median(raw_frames):
    geolocation = raw_frames["geolocation"]
    expected = aggregate_geolocation(geolocation).set_index(
        "geolocation_zip_code_prefix"
    )
    shuffled = aggregate_geolocation(
        geolocation.sample(frac=1, random_state=42)
    ).set_index("geolocation_zip_code_prefix")

    assert expected.loc["00001", "zip_latitude"] == pytest.approx(-22.0)
    assert expected.loc["00001", "zip_longitude"] == pytest.approx(-45.0)
    pd.testing.assert_frame_equal(expected, shuffled)


def test_spain_like_coordinate_is_excluded():
    geolocation = pd.DataFrame(
        [
            {
                "geolocation_zip_code_prefix": "83252",
                "geolocation_lat": "42.184003",
                "geolocation_lng": "-8.723762",
            }
        ]
    )

    result = aggregate_geolocation(geolocation)

    assert result.empty


def test_zip_with_invalid_and_valid_coordinate_uses_only_valid_one():
    geolocation = pd.DataFrame(
        [
            {
                "geolocation_zip_code_prefix": "12345",
                "geolocation_lat": "42.184003",
                "geolocation_lng": "-8.723762",
            },
            {
                "geolocation_zip_code_prefix": "12345",
                "geolocation_lat": "-23.5",
                "geolocation_lng": "-46.6",
            },
        ]
    )

    result = aggregate_geolocation(geolocation).set_index(
        "geolocation_zip_code_prefix"
    )

    assert result.loc["12345", "zip_latitude"] == pytest.approx(-23.5)
    assert result.loc["12345", "zip_longitude"] == pytest.approx(-46.6)


def test_zip_with_only_invalid_coordinates_has_no_representative_coordinate():
    geolocation = pd.DataFrame(
        [
            {
                "geolocation_zip_code_prefix": "83252",
                "geolocation_lat": "42.184003",
                "geolocation_lng": "-8.723762",
            },
            {
                "geolocation_zip_code_prefix": "83252",
                "geolocation_lat": "42.184003",
                "geolocation_lng": "-8.723762",
            },
        ]
    )

    result = aggregate_geolocation(geolocation)

    assert result.empty


def test_order_survives_when_its_zip_loses_all_coordinates(raw_frames):
    geolocation = raw_frames["geolocation"].copy()
    invalid_zip = geolocation["geolocation_zip_code_prefix"].eq("00002")
    geolocation.loc[invalid_zip, "geolocation_lat"] = "42.184003"
    geolocation.loc[invalid_zip, "geolocation_lng"] = "-8.723762"
    raw_frames["geolocation"] = geolocation

    gold = build_gold_v1(raw_frames).set_index("order_id")
    row = gold.loc["later_date"]
    quality = quality_summary(gold.reset_index())

    assert row["customer_geolocation_missing"]
    assert row["seller_customer_distance_missing_count"] == 1
    assert pd.isna(row["seller_customer_distance_km_min"])
    assert pd.isna(row["seller_customer_distance_km_mean"])
    assert pd.isna(row["seller_customer_distance_km_max"])
    assert quality["raw_geolocation_rows_outside_brazil_envelope"] == 1
    assert quality["distinct_coordinate_triples_outside_brazil_envelope"] == 1
    assert quality["zip_prefixes_with_rejected_coordinates"] == 1
    assert quality["zip_prefixes_without_valid_coordinates"] == 1


def test_missing_geolocation_does_not_remove_an_order(raw_frames):
    gold = build_gold_v1(raw_frames).set_index("order_id")

    row = gold.loc["no_payment"]
    assert row["customer_geolocation_missing"]
    assert row["seller_customer_distance_missing_count"] == 1
    assert pd.isna(row["seller_customer_distance_km_mean"])


def test_primary_value_ties_are_deterministic(raw_frames):
    gold = build_gold_v1(raw_frames).set_index("order_id")

    row = gold.loc["same_date"]
    assert row["primary_product_category"] == "Alpha"
    assert row["primary_seller_state"] == "SP"
    assert row["primary_payment_type"] == "credit_card"


def test_missing_product_attributes_use_explicit_fallbacks(raw_frames):
    gold = build_gold_v1(raw_frames).set_index("order_id")

    row = gold.loc["no_payment"]
    assert row["primary_product_category"] == "__missing_category__"
    assert row["product_category_fallback_item_count"] == 1
    assert row["product_measurement_missing_item_count"] == 1
    assert pd.isna(row["product_weight_g_total"])
    assert pd.isna(row["product_volume_cm3_total"])


def test_unmatched_product_fails_fast(raw_frames):
    raw_frames["products"] = raw_frames["products"].loc[
        raw_frames["products"]["product_id"] != "p2"
    ]

    with pytest.raises(ValueError, match="unmatched product"):
        build_gold_v1(raw_frames)


def test_feature_whitelist_excludes_identifiers_leakage_reviews_and_target():
    assert not (set(MODEL_FEATURE_COLUMNS) & FORBIDDEN_FEATURE_COLUMNS)
    assert "delay_flag" not in MODEL_FEATURE_COLUMNS
    assert "olist_order_reviews_dataset.csv" not in RAW_FILES.values()
    assert "archive.zip" not in RAW_FILES.values()


def test_haversine_handles_antipodal_rounding_boundary():
    distance = haversine_km(0.0, 0.0, 0.0, 180.0)

    assert distance is not None
    assert math.isfinite(distance)
    assert distance == pytest.approx(math.pi * 6371.0088)


def test_validation_quality_summary_and_parquet_write(raw_frames, tmp_path):
    gold = build_gold_v1(raw_frames)
    summary = validate_gold_v1(gold)
    quality = quality_summary(gold)
    output = tmp_path / "gold_v1.parquet"

    write_gold_v1(gold, output)

    assert tuple(gold.columns) == OUTPUT_COLUMNS
    assert summary == {
        "rows": 3,
        "unique_order_id": 3,
        "late": 1,
        "on_time": 2,
        "eligible_orders_without_payment": 1,
    }
    assert set(quality["missing_values_by_column"]) == set(OUTPUT_COLUMNS)
    assert quality["orders_missing_customer_coordinates"] == 1
    assert quality["orders_with_no_available_seller_customer_distance"] == 1
    assert output.is_file()
    assert output.stat().st_size > 0
