"""
================================================================================
PHASE 3b - MERGE STRUCTURED + SEMI-STRUCTURED INTO ONE UNIFIED DATASET
================================================================================
Project : A Scalable Big Data Platform for Real-Time Urban Air Quality Tracking
Course  : 23AID302 - Big Data Analytics

WHAT THIS DOES
  Combines the two source formats built for this project into a single
  unified dataset on a common schema, using Spark's native readers for each:

    STRUCTURED      airquality_expanded/*.csv   (146,276,379 rows, fixed
                     32-column header, CPCB pollutants, 2010-2023, all 4,077
                     stations)
    SEMI-STRUCTURED airquality_semistructured/raw_json/*.json  (20 real
                     live API responses, nested hourly array-of-struct JSON,
                     Aug 2026, 20 cities)

  Spark's `.csv()` reader treats the first as row/column structured data;
  its `.json()` reader treats the second as self-describing nested data
  (struct/array types inferred straight from the JSON, not flattened by us
  beforehand) - i.e. Spark is doing genuine schema-on-read across two
  different data models in one job, which is the actual point of this file.

  Both sides are projected onto ONE common schema and unioned. Values are
  NEVER blended, imputed into each other, or invented - a row is either a
  real structured-CSV row or a real semi-structured-JSON row, tagged as such.

COMMON SCHEMA
  station_id, city, state, latitude, longitude, timestamp,
  pm25, pm10, no2, so2, co, o3, nh3, aqi_us,
  data_source        (real | synthetic | live_api)
  source_format      (structured_csv | semistructured_json)
  source_dataset     (airquality_expanded | airquality_semistructured)

NOTES ON HONESTY
  - Structured rows have no `latitude`/`longitude` (not present in that
    dataset) and no `aqi_us` (that dataset reports raw pollutant
    concentrations, not a precomputed AQI) - both left NULL, not guessed.
  - Semi-structured rows have no `station_id` in the CPCB sense (they are
    city-centroid API pulls, not fixed physical stations) - `station_id` is
    set to NULL for these rows rather than inventing one. `city` fully
    identifies them instead.
  - Semi-structured `nh3` is NULL for every row - a real limitation of the
    CAMS source for this region, not a processing artifact (see
    airquality_semistructured/README.md).
  - Semi-structured `us_aqi` (US EPA AQI, 0-500 scale) is kept in a
    separately-named `aqi_us` column rather than merged into any future CPCB
    AQI column - the two AQI scales are not comparable and must never be
    conflated.

RUN
    powershell> . .\\env.ps1
    powershell> python 01c_merge_structured_semistructured.py `
                    --structured "F:\\...\\airquality_expanded" `
                    --semistructured "F:\\...\\airquality_semistructured" `
                    --out "F:\\...\\airquality_unified"
================================================================================
"""

import argparse
import os

from pyspark.sql import SparkSession, functions as F, types as T


COMMON_COLS = [
    "station_id", "city", "state", "latitude", "longitude", "timestamp",
    "pm25", "pm10", "no2", "so2", "co", "o3", "nh3", "aqi_us",
    "data_source", "source_format", "source_dataset",
]


def build_structured(spark, path):
    df = spark.read.option("header", "true").csv(os.path.join(path, "part-*.csv"))

    ts = F.to_timestamp("from_date", "yyyy-MM-dd HH:mm:ss")

    out = df.select(
        F.col("station_id").alias("station_id"),
        F.col("city").alias("city"),
        F.col("state").alias("state"),
        F.lit(None).cast(T.DoubleType()).alias("latitude"),
        F.lit(None).cast(T.DoubleType()).alias("longitude"),
        ts.alias("timestamp"),
        F.col("pm25").cast(T.DoubleType()).alias("pm25"),
        F.col("pm10").cast(T.DoubleType()).alias("pm10"),
        F.col("no2").cast(T.DoubleType()).alias("no2"),
        F.col("so2").cast(T.DoubleType()).alias("so2"),
        F.col("co").cast(T.DoubleType()).alias("co"),
        F.col("o3").cast(T.DoubleType()).alias("o3"),
        F.col("nh3").cast(T.DoubleType()).alias("nh3"),
        F.lit(None).cast(T.DoubleType()).alias("aqi_us"),
        F.col("data_source").alias("data_source"),          # real | synthetic
        F.lit("structured_csv").alias("source_format"),
        F.lit("airquality_expanded").alias("source_dataset"),
    )
    return out


def build_semistructured(spark, path, data_source="live_api", source_dataset="airquality_semistructured"):
    """Project one semi-structured JSON layer onto the common schema.

    Used for BOTH semi-structured layers, which differ only in tags:

      live      (semistructured_json)    7-day window, forecast values at the
                                          tail - what the alerting layer sees
      history   (semistructured_history) 2022-08 onward, analysis values -
                                          what validation/backtesting uses

    The two overlap by 192 hours per city (44,160 rows). Those are NOT
    duplicates to be deduped away: CAMS revises forecast into analysis, so the
    live tail and the historical record genuinely disagree for the last hours
    of the live window (measured: 19 of 192 hours differ for Delhi). Both are
    kept and tagged so the difference stays visible and queryable.
    """
    json_glob = os.path.join(path, "raw_json", "*.json")
    df = spark.read.option("multiLine", "true").json(json_glob)

    # Attach the source city file name so every row keeps provenance even
    # though city/state/lat/lon are NOT inside the raw API payload itself
    # (Open-Meteo's air-quality endpoint returns only lat/lon + hourly
    # arrays; city/state came from the geocoding step recorded separately
    # in manifest.json). We re-join that here rather than guessing.
    manifest_path = os.path.join(path, "manifest.json")
    manifest_df = spark.read.option("multiLine", "true").json(manifest_path)
    cities = manifest_df.select(F.explode("cities").alias("c")).select(
        F.col("c.city").alias("m_city"),
        F.col("c.state").alias("m_state"),
        F.col("c.latitude").alias("m_lat"),
        F.col("c.longitude").alias("m_lon"),
        F.col("c.file").alias("m_file"),
    )

    # Exact basename match (NOT substring/contains - "navi_mumbai.json" contains
    # "mumbai.json" as a literal substring, and "greater_noida.json" contains
    # "noida.json", so a .contains() join here silently double-matches those
    # files to both the short and long city, duplicating every row of the
    # short city. Extract the literal basename on both sides and compare with
    # exact equality instead.
    df = df.withColumn("input_basename", F.element_at(F.split(F.input_file_name(), r"[\\/]"), -1))
    cities = cities.withColumn("m_basename", F.element_at(F.split(F.col("m_file"), "/"), -1))

    joined = df.join(cities, df.input_basename == cities.m_basename, "left")

    exploded = joined.select(
        "m_city", "m_state", "m_lat", "m_lon",
        F.arrays_zip(
            "hourly.time", "hourly.pm2_5", "hourly.pm10", "hourly.nitrogen_dioxide",
            "hourly.sulphur_dioxide", "hourly.carbon_monoxide", "hourly.ozone",
            "hourly.ammonia", "hourly.us_aqi",
        ).alias("z"),
    ).select(
        "m_city", "m_state", "m_lat", "m_lon", F.explode("z").alias("r"),
    )

    out = exploded.select(
        F.lit(None).cast(T.StringType()).alias("station_id"),
        F.col("m_city").alias("city"),
        F.col("m_state").alias("state"),
        F.col("m_lat").cast(T.DoubleType()).alias("latitude"),
        F.col("m_lon").cast(T.DoubleType()).alias("longitude"),
        F.to_timestamp(F.col("r.time"), "yyyy-MM-dd'T'HH:mm").alias("timestamp"),
        F.col("r.pm2_5").cast(T.DoubleType()).alias("pm25"),
        F.col("r.pm10").cast(T.DoubleType()).alias("pm10"),
        F.col("r.nitrogen_dioxide").cast(T.DoubleType()).alias("no2"),
        F.col("r.sulphur_dioxide").cast(T.DoubleType()).alias("so2"),
        # Open-Meteo reports CO in ug/m3 like the rest; keep as-is (unit
        # differs from the structured layer's mg/m3 CO - see README caveat)
        F.col("r.carbon_monoxide").cast(T.DoubleType()).alias("co"),
        F.col("r.ozone").cast(T.DoubleType()).alias("o3"),
        F.col("r.ammonia").cast(T.DoubleType()).alias("nh3"),
        F.col("r.us_aqi").cast(T.DoubleType()).alias("aqi_us"),
        F.lit(data_source).alias("data_source"),
        F.lit("semistructured_json").alias("source_format"),
        F.lit(source_dataset).alias("source_dataset"),
    )
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--structured", required=True)
    ap.add_argument("--semistructured", required=True,
                    help="Live 7-day semi-structured layer (semistructured_json)")
    ap.add_argument("--semistructured-history", default=None,
                    help="Optional historical semi-structured layer (semistructured_history). "
                         "Tagged data_source=cams_history so it stays distinguishable from the "
                         "live layer, which overlaps it by 192 hours per city.")
    ap.add_argument("--out", required=True)
    ap.add_argument("--master", default="local[*]")
    ap.add_argument("--driver-mem", default="6g")
    args = ap.parse_args()

    spark = (
        SparkSession.builder.appName("merge_structured_semistructured")
        .master(args.master)
        .config("spark.driver.memory", args.driver_mem)
        .config("spark.sql.shuffle.partitions", "64")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    structured = build_structured(spark, args.structured)
    semistructured = build_semistructured(
        spark, args.semistructured,
        data_source="live_api", source_dataset="airquality_semistructured")

    print(f"structured columns  : {structured.columns}")
    print(f"semistructured cols : {semistructured.columns}")
    assert structured.columns == COMMON_COLS
    assert semistructured.columns == COMMON_COLS

    unified = structured.unionByName(semistructured)

    if args.semistructured_history:
        history = build_semistructured(
            spark, args.semistructured_history,
            data_source="cams_history", source_dataset="airquality_semistructured_history")
        assert history.columns == COMMON_COLS
        print(f"history columns     : {history.columns}")
        unified = unified.unionByName(history)

    (
        unified.write.mode("overwrite")
        .partitionBy("source_format")
        .parquet(args.out)
    )

    print("=== DONE ===")
    print("Wrote unified dataset to:", args.out)
    print("Row counts by source_format:")
    unified.groupBy("source_format", "data_source").count().orderBy("source_format", "data_source").show(truncate=False)

    spark.stop()


if __name__ == "__main__":
    main()
