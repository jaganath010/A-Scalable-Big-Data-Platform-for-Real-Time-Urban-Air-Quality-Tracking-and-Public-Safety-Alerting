"""
================================================================================
PHASE 3 - Distributed Data Cleaning, Column Pruning & Parquet Conversion
================================================================================
Project : A Scalable Big Data Platform for Real-Time Urban Air Quality Tracking
Course  : 23AID302 - Big Data Analytics

INPUT   : the rebuilt expanded dataset - 23 part-*.csv files
          27.48 GB | 146,276,379 rows | 32 columns
          (path resolved by paths.py; see --source for the legacy alternative)

OUTPUT  : <lakehouse>/clean/
          Snappy-compressed Parquet, partitioned by (city, year, month)

TWO INPUT SOURCES
  --source expanded   (DEFAULT) the rebuilt dataset produced by
                      00c_expand_dataset.py and signed off by
                      00d_validate_expansion.py. It arrives ALREADY pruned to
                      the 32 kept columns and with defects 1 and 3 already
                      repaired at generation time, so this script's job reduces
                      to range-guarding, imputation and Parquet conversion.

  --source legacy     the original 23.44 GB / 139-column
                      final_air_quality_dataset_22gb_balanced.csv. Kept so the
                      full 139 -> 32 pruning and defect repair remains
                      reproducible and auditable. The status report condemns
                      this file as 66.6% synthetic with four measured defects -
                      do not use it for results.

WHAT THIS SCRIPT DOES
  1. Reads the CSV with an EXPLICIT schema (no inferSchema - that costs a full
     extra pass over tens of GB).
  2. legacy only: prunes 139 columns -> 32. Justification for every drop is in
     COLUMN_DECISION_REPORT.md.
  3. Repairs the measured data-quality defects (see DEFECT 1..4 below). On the
     expanded source these are already clean; the repairs stay in as guards
     because the streaming layer will feed unvalidated live frames through this
     same code path.
  4. Three-tier median imputation for the 7 AQI pollutants, with a
     *_was_imputed flag per pollutant so measured and filled values stay
     distinguishable downstream.
  5. Writes columnar Parquet partitioned for predicate pushdown.

RUN
  local:
    . .\\env.ps1
    python 01_clean_select.py                     # expanded, all 23 parts
    python 01_clean_select.py --limit-files 2     # quick smoke run

  cluster:
    $env:AQ_FS = "hdfs"
    spark-submit --master yarn --deploy-mode client \
      --executor-memory 8g --driver-memory 4g \
      --conf spark.sql.shuffle.partitions=400 \
      01_clean_select.py
================================================================================
"""

import argparse

from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType

import paths

# Reinstate the sparse *measured* weather columns alongside the dynamic ones.
# See COLUMN_DECISION_REPORT.md section 3.3 for the trade-off.
KEEP_RAW_MET  = False

# Reinstate benzene + toluene as auxiliary (non-AQI) traffic tracers.
# See COLUMN_DECISION_REPORT.md section 3.5.
KEEP_ORGANICS = False

# ------------------------------------------------------------------------------
# THE 32 COLUMNS OF THE EXPANDED DATASET, IN FILE ORDER.
# Verified against the header of part-7164.csv. This is the output contract of
# 00c_expand_dataset.py and matches section 3.1 of the status report exactly.
# ------------------------------------------------------------------------------
EXPANDED_HEADER = [
    "station_id", "state", "city", "from_date",
    "pm25", "pm10", "no2", "so2", "co", "o3", "nh3",
    "wd_degree", "solar_radiation", "pressure",
    "temperature_c", "humidity_percent", "wind_speed_ms", "rainfall_mm",
    "weather_condition", "traffic_index", "is_rush_hour",
    "year", "month", "day", "hour", "day_of_week", "is_weekend",
    "season", "climate_type", "urbanization_index",
    "data_source", "source_station",
]

# ------------------------------------------------------------------------------
# THE 139 COLUMNS, IN FILE ORDER.
# Declared explicitly so Spark never has to infer, and so the duplicate-suffixed
# columns (bp_(mmhg).1 .. .7) parse without collision.
# ------------------------------------------------------------------------------
HEADER = [
    "station_id", "state", "city", "agency", "station_location", "from_date", "to_date",
    "pm25", "pm10", "no", "no2", "nox_(ppb)", "nh3", "so2", "co", "o3", "benzene", "toluene",
    "temperature", "humidity", "wind_speed", "wd_(deg)", "sr_(w/mt2)", "bp_(mmhg)", "vws_(m/s)",
    "xylene", "rainfall", "ambient_temperature", "eth-benzene_(ug/m3)", "mp-xylene_(ug/m3)",
    "o_xylene_(ug/m3)", "vws_(degree)", "wind_direction", "temp_()", "rf_()", "no_(mg/m3)",
    "at_()", "co_(mg/nm3)", "rf_(m/s)", "sr_(ug/m3)", "mp-xylene_()", "ch4_(ug/m3)",
    "nmhc_(ug/m3)", "thc_(ug/m3)", "gust_(km/hr)", "variance_(n)", "power_(w)", "co2_(mg/m3)",
    "ozone_(ppb)", "gust_(kl/h)", "gust_(m/s)", "ws_()", "spm_(ug/m3)", "mh_(m)", "hcho_(ug/m3)",
    "hg_(ug/m3)", "co_(ug/m3)", "toluene_()", "co_(ng/m3)", "nox", "wd_(degree_c)", "benzene_()",
    "sr_()", "temp_(ug/m3)", "wd_()", "so2_()", "rh_()", "bp_()", "eth-benzene_()", "xylene_()",
    "ch4_()", "nh3_()", "at_(degree)",
    "bp_(mmhg).1", "bp_(mmhg).2", "bp_(mmhg).3", "bp_(mmhg).4", "bp_(mmhg).5", "bp_(mmhg).6",
    "bp_(mmhg).7",
    "rf_(mm).1", "rf_(mm).2", "rf_(mm).3", "rf_(mm).4", "rf_(mm).5", "rf_(mm).6", "rf_(mm).7",
    "no_()", "ozone_()", "ws_(ug/m3)", "at_(ug/m3)", "nmhc_()", "thc_()", "rh_(w/mt2)",
    "rh_(degree)", "no_(ppb)", "no_(ppm)", "benzene_(mg/m3)", "bp_(mg/m3)", "nox_(ppm)",
    "nh3_(ppb)", "bp_(w/mt2)",
    "year", "month", "day", "hour", "day_of_week", "is_weekend", "season", "climate_type",
    "temperature_mean_c", "temperature_variation_c", "summer_temperature_c",
    "winter_temperature_c", "humidity_mean_percent", "rainfall_factor", "monsoon_intensity",
    "wind_speed_mean_ms", "traffic_base_index", "morning_rush_multiplier",
    "evening_rush_multiplier", "weekend_traffic_multiplier", "rain_traffic_multiplier",
    "night_traffic_multiplier", "morning_rush_start", "morning_rush_end", "evening_rush_start",
    "evening_rush_end", "urbanization_index", "dynamic_temperature_c",
    "dynamic_humidity_percent", "rainfall_mm", "weather_condition", "is_rush_hour",
    "traffic_index", "traffic_level", "dynamic_wind_speed_ms", "data_source", "variation_id",
]

# The 7 pollutants that define the CPCB National AQI. These are both model
# features and the source of the prediction label.
AQI_POLLUTANTS = ["pm25", "pm10", "no2", "so2", "co", "o3", "nh3"]

# Output partitioning. See STEP 5 for the measurement behind dropping year/month.
PARTITION_BY = ["city"]

# Physically valid ranges. Anything outside is a sensor fault, not a reading.
# Upper bounds are set well above the observed maxima so real extremes survive.
VALID_RANGE = {
    "pm25":  (0.0, 2000.0),
    "pm10":  (0.0, 3000.0),
    "no2":   (0.0, 1000.0),
    "so2":   (0.0, 2000.0),
    "co":    (0.0,  100.0),   # mg/m3
    "o3":    (0.0, 1000.0),
    "nh3":   (0.0, 2000.0),
    "sr":    (0.0, 1500.0),   # W/m2
    "bp":    (700.0, 1100.0), # mmHg-scaled instrument range
}


def read_expanded(spark, args):
    """Read the rebuilt 32-column dataset and map it onto the Phase 3 contract.

    No pruning is needed - 00c_expand_dataset.py already emitted exactly the 32
    kept columns. The work here is type casting and reconciling two naming
    differences against the legacy path:

      from_date  -> timestamp        (the legacy branch renames it the same way)
      (none)     -> variation_bucket

    On variation_bucket: the legacy expansion rig produced up to 3 noise-variant
    COPIES of a row sharing one station_id, so downstream windows had to
    partition by (station_id, variation_bucket) to avoid ordering siblings of the
    same hour against each other. The rebuild does not do this - section 3.2 of
    the status report: synthetic series are separate stations carrying a ~Snn
    suffix, never interleaved with real rows under the same identifier. So each
    station_id is already a single clean track and a constant 0 is correct here.
    It is emitted rather than dropped so 02_feature_extraction.py needs no
    change and keeps working against both sources.
    """
    src = paths.EXPANDED_GLOB
    schema = StructType([StructField(c, StringType(), True) for c in EXPANDED_HEADER])

    reader = (spark.read
              .option("header", "true")
              .option("mode", "PERMISSIVE")
              .option("multiLine", "false")
              .option("escape", '"')
              .schema(schema))

    if args.limit_files:
        # Smoke-run mode: read N whole part files rather than sampling rows, so
        # every station in those files keeps a complete time series. Sampling
        # rows would punch holes in the series and corrupt the T+1 label.
        import glob as _glob
        files = sorted(_glob.glob(src))[: args.limit_files]
        if not files:
            raise SystemExit(f"no files matched {src}")
        print(f">>> --limit-files {args.limit_files}: reading "
              f"{len(files)} of {len(sorted(_glob.glob(src)))} parts")
        raw = reader.csv(files)
    else:
        raw = reader.csv(src)

    return raw.select(
        F.col("station_id"),
        F.col("state"),
        F.col("city"),
        F.to_timestamp(F.col("from_date"), "yyyy-MM-dd HH:mm:ss").alias("timestamp"),

        *[F.col(p).cast("double").alias(p) for p in AQI_POLLUTANTS],

        F.col("wd_degree").cast("double").alias("wd_degree"),
        F.col("solar_radiation").cast("double").alias("solar_radiation"),
        F.col("pressure").cast("double").alias("pressure"),

        F.col("temperature_c").cast("double").alias("temperature_c"),
        F.col("humidity_percent").cast("double").alias("humidity_percent"),
        F.col("wind_speed_ms").cast("double").alias("wind_speed_ms"),
        F.col("rainfall_mm").cast("double").alias("rainfall_mm"),
        F.col("weather_condition"),

        F.col("traffic_index").cast("double").alias("traffic_index"),
        F.col("is_rush_hour").cast("double").alias("_is_rush_hour_raw"),
        F.col("year").cast("int").alias("year"),
        F.col("month").cast("int").alias("month"),
        F.col("day").cast("int").alias("day"),
        F.col("hour").cast("int").alias("hour"),
        F.col("day_of_week").cast("int").alias("day_of_week"),
        F.col("is_weekend").cast("double").alias("_is_weekend_raw"),
        F.col("season"),

        F.col("climate_type"),
        F.col("urbanization_index").cast("double").alias("urbanization_index"),

        # Provenance. data_source is the honesty column that makes
        # "evaluate on real rows only" a single filter; source_station names the
        # real parent a synthetic sibling was derived from.
        F.col("data_source"),
        F.col("source_station"),
        F.lit(0.0).alias("_variation_id_raw"),
    )


def read_legacy(spark, args):
    """Read the original 23.44 GB / 139-column file and prune it to 32.

    Retained for auditability only. See the module docstring.
    """
    schema = StructType([StructField(c, StringType(), True) for c in HEADER])

    raw = (
        spark.read
        .option("header", "true")
        .option("mode", "PERMISSIVE")
        .option("multiLine", "false")
        .option("escape", '"')
        .schema(schema)
        .csv(paths.LEGACY_RAW)
    )

    print(">>> RAW loaded. Columns:", len(raw.columns))

    # ==========================================================================
    # COLUMN PRUNING: 139 -> 32
    #
    # Only the columns named below survive. Everything else is dropped because it
    # is empty (69 cols at <3% fill, 22 of them at exactly 0%), mechanically
    # duplicated (14 cols of bp_(mmhg).N / rf_(mm).N, all at an identical 0.351%),
    # a constant per city (15 city-profile cols that generated the dynamic ones),
    # or non-predictive metadata (agency, station_location, to_date, traffic_level).
    #
    # Full justification with measured fill rates: COLUMN_DECISION_REPORT.md
    # ==========================================================================
    return raw.select(
        # --- keys / identity -------------------------------------------------
        F.col("station_id"),
        F.col("state"),
        F.col("city"),
        F.to_timestamp(F.col("from_date"), "yyyy-MM-dd HH:mm:ss").alias("timestamp"),

        # --- the 7 CPCB AQI pollutants ---------------------------------------
        *[F.col(p).cast("double").alias(p) for p in AQI_POLLUTANTS],

        # --- meteorology with no dynamic equivalent --------------------------
        # DEFECT 2 (partial): wind direction is split across four sparsely
        # populated aliases from the 453-station merge. Coalescing lifts coverage
        # from 41.25% (best single column) to 74.77%. All four are degrees on the
        # same 0-360 scale, so unlike the CO/O3 unit-variants this coalesce is
        # dimensionally safe.
        F.coalesce(
            F.col("wind_direction").cast("double"),
            F.col("wd_(deg)").cast("double"),
            F.col("wd_()").cast("double"),
            F.col("wd_(degree_c)").cast("double"),
        ).alias("wd_degree"),
        F.col("sr_(w/mt2)").cast("double").alias("solar_radiation"),
        F.col("bp_(mmhg)").cast("double").alias("pressure"),

        # --- dynamic environment (100% filled) -------------------------------
        F.col("dynamic_temperature_c").cast("double").alias("temperature_c"),
        F.col("dynamic_humidity_percent").cast("double").alias("humidity_percent"),
        F.col("dynamic_wind_speed_ms").cast("double").alias("wind_speed_ms"),
        F.col("rainfall_mm").cast("double").alias("rainfall_mm"),
        F.col("weather_condition"),

        # --- traffic + temporal ----------------------------------------------
        F.col("traffic_index").cast("double").alias("traffic_index"),
        F.col("is_rush_hour").cast("double").alias("_is_rush_hour_raw"),
        F.col("year").cast("int").alias("year"),
        F.col("month").cast("int").alias("month"),
        F.col("day").cast("int").alias("day"),
        F.col("hour").cast("int").alias("hour"),
        F.col("day_of_week").cast("int").alias("day_of_week"),
        F.col("is_weekend").cast("double").alias("_is_weekend_raw"),
        F.col("season"),

        # --- city descriptors -------------------------------------------------
        F.col("climate_type"),
        F.col("urbanization_index").cast("double").alias("urbanization_index"),

        # --- audit only (never enters the feature vector) ---------------------
        F.col("data_source"),
        # No parent-station provenance exists in the legacy file; emitted as a
        # typed NULL so both sources produce an identical output schema.
        F.lit(None).cast("string").alias("source_station"),
        F.col("variation_id").cast("double").alias("_variation_id_raw"),

        # --- optional blocks --------------------------------------------------
        *([F.col("temperature").cast("double").alias("temperature_measured"),
           F.col("humidity").cast("double").alias("humidity_measured"),
           F.col("wind_speed").cast("double").alias("wind_speed_measured")]
          if KEEP_RAW_MET else []),
        *([F.col("benzene").cast("double").alias("benzene"),
           F.col("toluene").cast("double").alias("toluene")]
          if KEEP_ORGANICS else []),
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", choices=("expanded", "legacy"), default="expanded",
                    help="which dataset to clean (default: expanded)")
    ap.add_argument("--limit-files", type=int, default=0, metavar="N",
                    help="expanded only: read just the first N part files, for "
                         "smoke runs. Whole files, never sampled rows.")
    args = ap.parse_args()

    spark = paths.spark_session(
        f"AirQuality_Phase3_Clean_{args.source}",
        spark__sql__sources__partitionOverwriteMode="dynamic",
    )
    spark.sparkContext.setLogLevel("WARN")

    paths.banner()
    print(f"  source       {args.source}")
    print("=" * 72)

    # ==========================================================================
    # STEP 1+2 - READ, AND (legacy only) PRUNE
    # Every field is read as StringType, then cast deliberately. Reading straight
    # to DoubleType would make Spark null out any malformed cell silently; casting
    # ourselves lets us count what fails.
    # ==========================================================================
    if args.source == "expanded":
        df = read_expanded(spark, args)
    else:
        df = read_legacy(spark, args)

    # ==========================================================================
    # STEP 3 - REPAIR THE MEASURED DEFECTS
    #
    # On --source expanded these are already satisfied at generation time: the
    # rebuild only perturbs continuous physical measurements and clamps every one
    # to its physical range, so is_rush_hour is strict 0/1 and humidity cannot
    # exceed 100. The repairs are kept unconditionally because they are cheap,
    # they make the two sources produce identical output, and the streaming layer
    # will push unvalidated live sensor frames through this same code path.
    # ==========================================================================

    # --- DEFECT 1: binary flags and IDs corrupted by the noise injection ------
    # is_rush_hour is documented as 0/1 but carries 24,725 distinct values
    # (e.g. 1.0282169444321818); variation_id has 29,918 distinct where it should
    # have 3. The +/-3% Gaussian noise from the expansion rig was applied to every
    # numeric column without excluding flags. Affects BOTH data_source values, so
    # it cannot be filtered by provenance - it has to be rounded back.
    df = (
        df
        .withColumn("is_rush_hour", (F.round(F.col("_is_rush_hour_raw")) > 0).cast("int"))
        .withColumn("is_weekend",   (F.round(F.col("_is_weekend_raw"))   > 0).cast("int"))
        .withColumn("variation_bucket", F.round(F.col("_variation_id_raw")).cast("int"))
        .drop("_is_rush_hour_raw", "_is_weekend_raw", "_variation_id_raw")
    )

    # --- DEFECT 3: physically impossible values in the dynamic block ----------
    # Same root cause: noise applied without bound checks.
    #   dynamic_humidity_percent observed max 104.999 (RH cannot exceed 100)
    #   traffic_index            observed max 110.209 (documented 0-100 scale)
    df = (
        df
        .withColumn("humidity_percent", F.least(F.greatest(F.col("humidity_percent"), F.lit(0.0)), F.lit(100.0)))
        .withColumn("traffic_index",    F.least(F.greatest(F.col("traffic_index"),    F.lit(0.0)), F.lit(100.0)))
        .withColumn("wd_degree",        F.col("wd_degree") % 360.0)
        .withColumn("rainfall_mm",      F.greatest(F.col("rainfall_mm"), F.lit(0.0)))
        .withColumn("wind_speed_ms",    F.greatest(F.col("wind_speed_ms"), F.lit(0.0)))
    )

    # --- Out-of-range sensor readings -> NULL (then imputed in step 4) --------
    # The Phase 3 spec calls for dropping negative concentrations. The scan found
    # zero negatives and zero unparseable cells across all 7 pollutants, so this
    # is a cheap guard rather than a live filter - but it stays in, because the
    # streaming layer will feed unvalidated live sensor frames through this same
    # code path where negatives DO occur.
    for p in AQI_POLLUTANTS:
        lo, hi = VALID_RANGE[p]
        df = df.withColumn(p, F.when(F.col(p).between(lo, hi), F.col(p)).otherwise(F.lit(None)))

    for c, k in (("solar_radiation", "sr"), ("pressure", "bp")):
        lo, hi = VALID_RANGE[k]
        df = df.withColumn(c, F.when(F.col(c).between(lo, hi), F.col(c)).otherwise(F.lit(None)))

    # Rows with no usable timestamp cannot be windowed or partitioned.
    df = df.filter(F.col("timestamp").isNotNull())

    # ==========================================================================
    # STEP 4 - THREE-TIER MEDIAN IMPUTATION  (DEFECT 4)
    #
    # Only 45.78% of rows carry all 7 pollutants. Dropping incomplete rows would
    # discard ~26.4M rows and destroy the Volume claim, so imputation is
    # mandatory. Tiers, most specific first:
    #     T1  median by (station_id, month, hour)  <- captures the station's own
    #                                                 diurnal + seasonal cycle
    #     T2  median by (city, month)              <- for thin stations
    #     T3  global median                        <- last resort
    #
    # A *_was_imputed flag is emitted per pollutant. This matters for the defence:
    # it lets you state exactly how much of any result is measured vs synthesised,
    # and it gives GBT a legitimate signal (missingness is rarely random - sensors
    # drop out during extreme events).
    # ==========================================================================
    impute_cols = AQI_POLLUTANTS + ["solar_radiation", "pressure", "wd_degree"]

    # ---------------------------------------------------------------------
    # NEVER IMPUTE THE LABEL.
    #
    # pm25 is both a feature and the source of target_pm25_next_hour. If the
    # target is a station/month/hour median, the model is being asked to predict
    # a constant it cannot derive from the features - unlearnable noise that
    # drags R2 down hard. pm25 is 74.26% measured, so ~26% of labels would be
    # fabricated.
    #
    # pm25_measured preserves the pre-imputation truth. Features may use the
    # imputed pm25; the LABEL is built only from pm25_measured in Phase 4.
    # ---------------------------------------------------------------------
    df = df.withColumn("pm25_measured", F.col("pm25"))

    for c in impute_cols:
        df = df.withColumn(f"{c}_was_imputed", F.col(c).isNull().cast("int"))

    # Cache: the three median aggregations below each scan df once.
    df.cache()

    med = lambda c: F.expr(f"percentile_approx({c}, 0.5, 1000)")

    t1 = df.groupBy("station_id", "month", "hour").agg(
        *[med(c).alias(f"{c}__t1") for c in impute_cols])
    t2 = df.groupBy("city", "month").agg(
        *[med(c).alias(f"{c}__t2") for c in impute_cols])
    t3 = df.agg(*[med(c).alias(f"{c}__t3") for c in impute_cols]).collect()[0].asDict()

    # 453 stations x 12 months x 24 hours ~= 130k rows, and 241 cities x 12 months
    # ~= 2.9k rows. Both are small enough to broadcast, which turns two shuffle
    # joins into map-side joins over the 48.6M-row fact table.
    df = (
        df.join(F.broadcast(t1), ["station_id", "month", "hour"], "left")
          .join(F.broadcast(t2), ["city", "month"], "left")
    )

    for c in impute_cols:
        df = df.withColumn(c, F.coalesce(
            F.col(c),
            F.col(f"{c}__t1"),
            F.col(f"{c}__t2"),
            F.lit(t3[f"{c}__t3"]),
        )).drop(f"{c}__t1", f"{c}__t2")

    # ==========================================================================
    # STEP 5 - WRITE PARTITIONED PARQUET
    #
    # Partitioning by city is what makes predicate pushdown work: a query for one
    # city reads one directory instead of the whole dataset.
    #
    # It used to be (city, year, month). That was measured to produce 5,237
    # parquet files from a SINGLE part file - median 244 KB, every one under
    # 1 MB - because 241 cities x 14 years x 12 months is ~40,000 partitions
    # holding a few hundred KB each. On HDFS every one of those becomes its own
    # block, all far under the 128 MB block size, which is the small-files
    # problem and directly contradicts the "220 blocks, one input split per
    # block" parallelism claim in section 6.2 of the status report.
    #
    # City alone gives ~241 directories of ~40 MB, which is the right order of
    # magnitude for a 128 MB block and keeps the pushdown benefit.
    # ==========================================================================
    out = df.repartition(*[F.col(c) for c in PARTITION_BY])

    (out.write
        .mode("overwrite")
        .partitionBy(*PARTITION_BY)
        .option("compression", "snappy")
        .parquet(paths.CLEAN_PATH))

    # ==========================================================================
    # STEP 6 - AUDIT SUMMARY  (numbers to quote in the Phase 3 defence)
    # ==========================================================================
    total = df.count()
    cols_in = len(EXPANDED_HEADER) if args.source == "expanded" else len(HEADER)
    print("=" * 72)
    print("PHASE 3 COMPLETE")
    print("=" * 72)
    print(f"  source  : {args.source}")
    print(f"  columns : {cols_in} -> {len(out.columns)}")
    print(f"  rows    : {total:,}")
    print(f"  output  : {paths.CLEAN_PATH}")
    print("-" * 72)
    print("  provenance split (the basis of 'evaluate on real rows only'):")
    for r in df.groupBy("data_source").count().collect():
        print(f"    {str(r['data_source']):20s} {r['count']:>14,}  "
              f"{100.0 * r['count'] / total:5.2f}%")
    print("-" * 72)
    print("  imputation rate per column (fraction of values filled, not measured):")
    rates = df.agg(*[F.avg(f"{c}_was_imputed").alias(c) for c in impute_cols]).collect()[0]
    for c in impute_cols:
        print(f"    {c:20s} {100 * rates[c]:6.2f}%")
    print("=" * 72)

    df.unpersist()
    spark.stop()


if __name__ == "__main__":
    main()
