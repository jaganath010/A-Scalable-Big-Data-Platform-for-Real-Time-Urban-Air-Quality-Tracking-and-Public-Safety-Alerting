"""
================================================================================
PHASE 4 - Spatial-Temporal Feature Engineering & Vector Assembly
================================================================================
Project : A Scalable Big Data Platform for Real-Time Urban Air Quality Tracking
Course  : 23AID302 - Big Data Analytics

INPUT   : hdfs:///user/hadoop/lakehouse/clean/        (output of 01_clean_select.py)
OUTPUT  : hdfs:///user/hadoop/lakehouse/features/     (features + labels, Parquet)
          hdfs:///user/hadoop/models/feature_pipeline (fitted encoder pipeline)

WHAT THIS SCRIPT BUILDS
  A.  A TEMPORALLY VALIDATED T+1 label       (fixes the defect described below)
  B.  CPCB National AQI, current and T+1     (the number the >150 alert is defined on)
  C.  Rolling / lag history features          (pollution is autocorrelated)
  D.  Cyclical encodings                      (hour 23 -> 0 must be adjacent)
  E.  Physical interaction features           (ventilation, scrubbing)
  F.  One-hot categoricals + VectorAssembler  -> the `features` column

--------------------------------------------------------------------------------
WHY THE LABEL IS NOT BUILT WITH A PLAIN lead()
--------------------------------------------------------------------------------
Project_Phase_Execution_Plan.docx Step 6 specifies:

    Window.partitionBy("station_id").orderBy("from_date")
    lead("pm25", 1).over(windowSpec)

That is wrong here, for two independent reasons measured in the raw file:

  1. (station_id, from_date) IS NOT UNIQUE. 0.94% of keys repeat, up to 3 rows
     per key - the variation_id copies produced by the expansion rig. Ordering
     by a non-unique key is non-deterministic, so lead() can return a SIBLING OF
     THE SAME HOUR instead of the next hour, and the answer changes per run.

  2. lead() IS POSITIONAL, NOT TEMPORAL. pm25 is only 74.26% populated, so gaps
     are everywhere. Where a station skips 5 hours, lead() returns the row 5
     hours later and labels it "next hour". The model trains on a mislabelled
     forecast horizon and the RMSE it reports is meaningless.

The fix below partitions by (station_id, variation_bucket), orders by timestamp,
leads BOTH pm25 and the timestamp, and accepts the label only when the next row
is genuinely 3600 seconds ahead. Rows that fail are dropped, not mislabelled,
and the retention rate is printed so the loss is visible.

RUN
  spark-submit --master yarn --deploy-mode client \
    --executor-memory 8g --driver-memory 4g \
    --conf spark.sql.shuffle.partitions=400 \
    02_feature_extraction.py
================================================================================
"""

from pyspark.sql import functions as F, Window
from pyspark.ml import Pipeline
from pyspark.ml.feature import StringIndexer, OneHotEncoder, VectorAssembler

import paths

CLEAN_PATH    = paths.CLEAN_PATH
FEATURE_PATH  = paths.FEATURE_PATH
PIPELINE_PATH = paths.PIPELINE_PATH

HOUR = 3600  # seconds

# ------------------------------------------------------------------------------
# WHAT GETS PERSISTED, AND WHY IT IS NOT THE ASSEMBLED VECTOR
#
# This script used to write the VectorAssembler output column `features` and
# nothing else numeric. Measured, that cost 370 bytes/row - about 34.5 GB at
# full scale - for two avoidable reasons:
#
#   1. ~21 of the vector's ~75 slots are one-hot indicators. VectorAssembler
#      picks a DENSE representation when most slots are non-zero, so those
#      near-empty indicator columns were written out as explicit doubles.
#   2. Parquet cannot compress inside a vector. As one opaque list-of-doubles
#      the whole block gets almost no columnar encoding; as 54 separate typed
#      columns each one compresses on its own.
#
# So the numeric feature COLUMNS are persisted instead, together with the raw
# categorical strings. The fitted pipeline is still saved to PIPELINE_PATH, and
# 03_train_gbt.py loads it and reassembles `features` on read - the assembly is
# cheap; the lag and rolling-window computations, which are the expensive part,
# stay materialised here and are never recomputed.
#
# These two lists are module-level so 03_train_gbt.py can import them and stay
# in lockstep with what was written.
# ------------------------------------------------------------------------------
CATEGORICALS = ["season", "weather_condition", "climate_type"]

NUMERIC_FEATURES = [
    # current pollutant concentrations (7 CPCB)
    "pm25", "pm10", "no2", "so2", "co", "o3", "nh3",
    # aggregated air-quality state
    "aqi_current", "pm25_avg24h", "pm10_avg24h", "co_avg8h", "o3_avg8h",
    # history / trend
    "pm25_lag_1h", "pm25_delta_1h", "pm25_roll_3h", "pm25_roll_6h",
    "pm25_std_6h", "pm10_roll_6h", "no2_roll_6h", "aqi_roll_6h",
    "pm25_surge_ratio",
    # meteorology
    "temperature_c", "humidity_percent", "wind_speed_ms", "rainfall_mm",
    "solar_radiation", "pressure", "wd_sin", "wd_cos",
    # traffic
    "traffic_index", "is_rush_hour",
    # temporal
    "hour_sin", "hour_cos", "month_sin", "month_cos", "dow_sin", "dow_cos",
    "is_weekend",
    # city descriptor
    "urbanization_index",
    # physical interactions
    "ventilation_index", "is_raining", "scrub_factor", "stagnation_index",
    "temp_humidity_interaction",
    # data-provenance flags: missingness is informative (sensors drop out
    # during extreme events), and these keep measured vs imputed separable.
    "pm25_was_imputed", "pm10_was_imputed", "no2_was_imputed",
    "so2_was_imputed", "co_was_imputed", "o3_was_imputed", "nh3_was_imputed",
    "solar_radiation_was_imputed", "pressure_was_imputed", "wd_degree_was_imputed",
]

# ------------------------------------------------------------------------------
# OUTPUT PARTITIONING
#
# Was (city, year, month). Measured on one part file that produced 5,237 parquet
# files across 674 partitions - median 244 KB, every single one under 1 MB. At
# full scale that is tens of thousands of files.
#
# On local disk that is merely slow. On HDFS it is the small-files problem: each
# file becomes its own block, all far below the 128 MB block size, so the
# "220 blocks, one input split per block" parallelism argument in section 6.2 of
# the status report stops being true and per-file overhead dominates reads.
#
# City alone keeps the predicate pushdown the Hive serving layer needs - one
# directory per city - while producing ~241 well-sized files instead.
# ------------------------------------------------------------------------------
PARTITION_BY = ["city"]

# ------------------------------------------------------------------------------
# CPCB NATIONAL AQI BREAKPOINTS
#
# This table is the reason the 7 pollutants in COLUMN_DECISION_REPORT.md were the
# ones kept. India's National AQI (CPCB, 2014) is the MAXIMUM of the sub-indices
# computed over exactly these pollutants. The project's alert rule - "predicted
# AQI > 150" - is undefined without all seven.
#
# Each tuple: (C_low, C_high, I_low, I_high). Sub-index is linear within a band:
#     I = (I_hi - I_lo) / (C_hi - C_lo) * (C - C_lo) + I_lo
#
# Averaging period per CPCB: 24h for PM2.5/PM10/NO2/SO2/NH3, 8h for CO and O3.
# ------------------------------------------------------------------------------
AQI_BREAKPOINTS = {
    "pm25": [(0, 30, 0, 50), (30, 60, 51, 100), (60, 90, 101, 200),
             (90, 120, 201, 300), (120, 250, 301, 400), (250, 1000, 401, 500)],
    "pm10": [(0, 50, 0, 50), (50, 100, 51, 100), (100, 250, 101, 200),
             (250, 350, 201, 300), (350, 430, 301, 400), (430, 1000, 401, 500)],
    "no2":  [(0, 40, 0, 50), (40, 80, 51, 100), (80, 180, 101, 200),
             (180, 280, 201, 300), (280, 400, 301, 400), (400, 1000, 401, 500)],
    "so2":  [(0, 40, 0, 50), (40, 80, 51, 100), (80, 380, 101, 200),
             (380, 800, 201, 300), (800, 1600, 301, 400), (1600, 3000, 401, 500)],
    "co":   [(0, 1, 0, 50), (1, 2, 51, 100), (2, 10, 101, 200),
             (10, 17, 201, 300), (17, 34, 301, 400), (34, 100, 401, 500)],
    "o3":   [(0, 50, 0, 50), (50, 100, 51, 100), (100, 168, 101, 200),
             (168, 208, 201, 300), (208, 748, 301, 400), (748, 1000, 401, 500)],
    "nh3":  [(0, 200, 0, 50), (200, 400, 51, 100), (400, 800, 101, 200),
             (800, 1200, 201, 300), (1200, 1800, 301, 400), (1800, 3000, 401, 500)],
}

# CPCB averaging window per pollutant, in hours.
AQI_WINDOW_H = {"pm25": 24, "pm10": 24, "no2": 24, "so2": 24, "nh3": 24,
                "co": 8, "o3": 8}


def sub_index(col, breakpoints):
    """Piecewise-linear CPCB sub-index for one pollutant concentration column."""
    expr = F.lit(500.0)  # anything above the top band saturates at 500
    for c_lo, c_hi, i_lo, i_hi in reversed(breakpoints):
        expr = F.when(
            col <= c_hi,
            (F.lit(i_hi - i_lo) / F.lit(c_hi - c_lo)) * (col - F.lit(c_lo)) + F.lit(i_lo),
        ).otherwise(expr)
    return F.when(col.isNull(), F.lit(None)).otherwise(expr)


def main():
    spark = paths.spark_session("AirQuality_Phase4_FeatureEngineering")
    spark.sparkContext.setLogLevel("WARN")
    paths.banner()

    df = spark.read.parquet(CLEAN_PATH)
    rows_in = df.count()
    print(f">>> loaded {rows_in:,} cleaned rows")

    # ==========================================================================
    # STEP 0 - MAKE THE TIME SERIES WELL-FORMED
    #
    # Every window below orders by time. That ordering is only meaningful if one
    # (station, variation-track, hour) maps to one row. Dedupe first: without
    # this, both the rolling averages and the T+1 label are non-deterministic.
    # ==========================================================================
    df = df.withColumn("ts_unix", F.col("timestamp").cast("long"))

    dedup_w = Window.partitionBy("station_id", "variation_bucket", "ts_unix") \
                    .orderBy(F.col("pm25").desc_nulls_last())
    df = (df.withColumn("_rn", F.row_number().over(dedup_w))
            .filter(F.col("_rn") == 1)
            .drop("_rn"))

    rows_dedup = df.count()
    print(f">>> after dedupe on (station_id, variation_bucket, hour): {rows_dedup:,} "
          f"({100.0 * rows_dedup / rows_in:.2f}% retained)")

    # The one true ordering used by every time-aware feature in this script.
    track = Window.partitionBy("station_id", "variation_bucket").orderBy("ts_unix")

    def hours_back(n):
        """Time-ranged window covering the trailing n hours, inclusive of now.

        rangeBetween operates on the VALUE of ts_unix, not on row position, so a
        missing hour shortens the window instead of silently reaching further
        back in time. This is what makes the rolling features gap-safe."""
        return (Window.partitionBy("station_id", "variation_bucket")
                      .orderBy("ts_unix")
                      .rangeBetween(-(n - 1) * HOUR, 0))

    # ==========================================================================
    # STEP B(i) - CPCB ROLLING AVERAGES + CURRENT AQI
    # AQI is defined on averaged concentrations, not instantaneous ones.
    # ==========================================================================
    for p, h in AQI_WINDOW_H.items():
        df = df.withColumn(f"{p}_avg{h}h", F.avg(F.col(p)).over(hours_back(h)))

    for p in AQI_BREAKPOINTS:
        df = df.withColumn(
            f"si_{p}", sub_index(F.col(f"{p}_avg{AQI_WINDOW_H[p]}h"), AQI_BREAKPOINTS[p])
        )

    # National AQI = worst sub-index. Also record WHICH pollutant is responsible -
    # the alert message needs to name it ("AQI 187, driven by PM2.5").
    df = df.withColumn("aqi_current",
                       F.greatest(*[F.col(f"si_{p}") for p in AQI_BREAKPOINTS]))

    si_pairs = F.array(*[F.struct(F.col(f"si_{p}").alias("v"), F.lit(p).alias("p"))
                         for p in AQI_BREAKPOINTS])
    df = df.withColumn("aqi_dominant_pollutant",
                       F.sort_array(si_pairs, asc=False).getItem(0).getField("p"))

    # ==========================================================================
    # STEP A - THE T+1 LABEL, TEMPORALLY VALIDATED
    # ==========================================================================
    # NOTE the label is taken from pm25_measured, NOT the imputed pm25. A label
    # that is a station/month/hour median is unlearnable from the features and
    # directly suppresses R2. Roughly 26% of pm25 values are imputed, so this is
    # the difference between training on truth and training on 26% fabrication.
    df = (
        df
        .withColumn("_next_ts",   F.lead("ts_unix", 1).over(track))
        .withColumn("_next_pm25", F.lead("pm25_measured", 1).over(track))
        .withColumn("_next_aqi",  F.lead("aqi_current", 1).over(track))
        # THE GUARD: accept the label only if the next row really is +1 hour.
        .withColumn("_gap_ok", (F.col("_next_ts") - F.col("ts_unix")) == F.lit(HOUR))
    )

    rows_before_label = df.count()
    df = df.filter(F.col("_gap_ok") & F.col("_next_pm25").isNotNull())

    df = (df
          .withColumnRenamed("_next_pm25", "target_pm25_next_hour")
          .withColumnRenamed("_next_aqi",  "target_aqi_next_hour")
          .drop("_next_ts", "_gap_ok"))

    rows_labelled = df.count()
    print(f">>> rows with a VALID +1h label: {rows_labelled:,} "
          f"({100.0 * rows_labelled / rows_before_label:.2f}% of dedup rows)")
    print("    the remainder were dropped rather than mislabelled - a plain "
          "lead() would have kept them with a wrong horizon.")

    # ==========================================================================
    # STEP C - HISTORY FEATURES
    # Next-hour pollution is dominated by current pollution and its recent trend.
    # Without these, GBT has to infer persistence from weather alone.
    # ==========================================================================
    df = (
        df
        .withColumn("_lag_ts",   F.lag("ts_unix", 1).over(track))
        .withColumn("_lag_pm25", F.lag("pm25", 1).over(track))
        # Same temporal guard as the label: a lag is only a "1 hour ago" value if
        # the previous row is actually 1 hour behind.
        .withColumn("pm25_lag_1h",
                    F.when((F.col("ts_unix") - F.col("_lag_ts")) == F.lit(HOUR),
                           F.col("_lag_pm25")).otherwise(F.col("pm25")))
        .drop("_lag_ts", "_lag_pm25")
        .withColumn("pm25_delta_1h", F.col("pm25") - F.col("pm25_lag_1h"))
        .withColumn("pm25_roll_3h",  F.avg("pm25").over(hours_back(3)))
        .withColumn("pm25_roll_6h",  F.avg("pm25").over(hours_back(6)))
        .withColumn("pm25_std_6h",   F.stddev("pm25").over(hours_back(6)))
        .withColumn("pm10_roll_6h",  F.avg("pm10").over(hours_back(6)))
        .withColumn("no2_roll_6h",   F.avg("no2").over(hours_back(6)))
        .withColumn("aqi_roll_6h",   F.avg("aqi_current").over(hours_back(6)))
        # Ratio > 1 means the last 3 hours are dirtier than the last 24 -
        # a compact "surge in progress" signal, which is precisely what the
        # alert engine exists to catch.
        .withColumn("pm25_surge_ratio",
                    F.col("pm25_roll_3h") / (F.col("pm25_avg24h") + F.lit(1e-6)))
        .fillna(0.0, subset=["pm25_std_6h", "pm25_delta_1h"])
    )

    # ==========================================================================
    # STEP D - CYCLICAL ENCODINGS
    # hour=23 and hour=0 are one hour apart, but as raw integers they are 23 apart.
    # Sin/cos pairs restore the true adjacency. Same for month, weekday, and wind
    # direction (359 deg and 1 deg are 2 deg apart).
    # ==========================================================================
    two_pi = 2.0 * 3.141592653589793

    def cyc(col, period, name):
        ang = (F.col(col) / F.lit(float(period))) * F.lit(two_pi)
        return [F.sin(ang).alias(f"{name}_sin"), F.cos(ang).alias(f"{name}_cos")]

    df = df.select(
        "*",
        *cyc("hour", 24, "hour"),
        *cyc("month", 12, "month"),
        *cyc("day_of_week", 7, "dow"),
    )
    wd_rad = F.radians(F.col("wd_degree"))
    df = df.withColumn("wd_sin", F.sin(wd_rad)).withColumn("wd_cos", F.cos(wd_rad))

    # ==========================================================================
    # STEP E - PHYSICAL INTERACTION FEATURES
    # Trees split on one variable at a time, so a ratio that matters physically
    # is expensive for them to reconstruct. Handing it over directly is cheap.
    # ==========================================================================
    df = (
        df
        # Ventilation: emission load divided by the wind that disperses it.
        # High traffic + dead air is the classic trapping condition.
        .withColumn("ventilation_index",
                    F.col("traffic_index") / (F.col("wind_speed_ms") + F.lit(0.5)))
        # Rain physically scrubs PM out of the air; this is why rainfall_mm was
        # a required keep. Binary + intensity, because the first mm does most
        # of the washout.
        .withColumn("is_raining", (F.col("rainfall_mm") > 0.1).cast("int"))
        .withColumn("scrub_factor", F.log1p(F.col("rainfall_mm")))
        # Warm, dry, still air holds particulates near the surface.
        .withColumn("stagnation_index",
                    (F.lit(100.0) - F.col("humidity_percent"))
                    / (F.col("wind_speed_ms") + F.lit(0.5)))
        .withColumn("temp_humidity_interaction",
                    F.col("temperature_c") * F.col("humidity_percent") / F.lit(100.0))
    )

    # ==========================================================================
    # STEP F - CATEGORICAL ENCODING + VECTOR ASSEMBLY
    #
    # `city` (241 values) and `station_id` (453) are deliberately NOT one-hot
    # encoded. At that cardinality one-hot would add 694 sparse columns, inflate
    # every tree split search, and teach the model to memorise locations instead
    # of learning the physics. `climate_type` (14) + `urbanization_index`
    # (continuous) carry the same city-level signal in 15 columns.
    # ==========================================================================
    indexers = [StringIndexer(inputCol=c, outputCol=f"{c}_idx", handleInvalid="keep")
                for c in CATEGORICALS]
    encoders = [OneHotEncoder(inputCols=[f"{c}_idx" for c in CATEGORICALS],
                              outputCols=[f"{c}_ohe" for c in CATEGORICALS],
                              handleInvalid="keep")]

    assembler = VectorAssembler(
        inputCols=NUMERIC_FEATURES + [f"{c}_ohe" for c in CATEGORICALS],
        outputCol="features",
        handleInvalid="skip",
    )

    # The pipeline is fitted here - the StringIndexers must learn their category
    # vocabularies from the full dataset, not from whatever subset Phase 5 later
    # trains on - and saved. 03_train_gbt.py loads it to build `features`.
    pipeline = Pipeline(stages=indexers + encoders + [assembler])
    model = pipeline.fit(df)
    model.write().overwrite().save(PIPELINE_PATH)

    # ==========================================================================
    # DROP UNASSEMBLABLE ROWS **HERE**, VISIBLY.
    #
    # VectorAssembler(handleInvalid="skip") silently discards any row with a null
    # in any input column - failure cause 4 of the R2=0.58 post-mortem, and rule
    # 3 of the README. Rows at the start of each station's series legitimately
    # have null lags and rolling windows.
    #
    # Since assembly now happens in Phase 5, those rows would be dropped AFTER
    # the train/test split, making the split fractions wrong and the loss
    # invisible. So they are removed now, and the retention rate is printed.
    # Phase 5's assembly is then lossless by construction.
    # ==========================================================================
    before_assemble = df.count()
    df = df.na.drop(subset=NUMERIC_FEATURES)
    after_assemble = df.count()
    print(f">>> rows assemblable into a complete feature vector: {after_assemble:,} "
          f"({100.0 * after_assemble / before_assemble:.2f}% of labelled rows)")
    if after_assemble < before_assemble:
        print(f"    dropped {before_assemble - after_assemble:,} rows with a null in "
              f"at least one of the {len(NUMERIC_FEATURES)} numeric features "
              f"(mostly series-start lags and rolling windows).")

    out = df

    # ==========================================================================
    # STEP G - PERSIST
    #
    # The identity columns are carried alongside `features` on purpose: the
    # streaming alert engine in Phase 6 needs to name the city and station in the
    # warning, and Hive needs them for the ad-hoc analytics queries. Keeping them
    # here means the serving layer never has to re-join back to the clean layer.
    # ==========================================================================
    # Identity, labels and serving-layer columns. `pm25` and `aqi_current` are
    # already in NUMERIC_FEATURES, so the dict-free dedupe below keeps one copy.
    CARRIED = [
        "station_id", "state", "city", "timestamp", "ts_unix", "year", "month", "hour",
        "target_pm25_next_hour", "target_aqi_next_hour",
        "aqi_dominant_pollutant",
        # data_source is what makes "evaluate on real rows only" a single filter.
        "data_source",
    ]

    # Order: identity/labels, then the model inputs. Deduplicated while
    # preserving order, so a column named in both lists is written once.
    select_cols = list(dict.fromkeys(CARRIED + NUMERIC_FEATURES + CATEGORICALS))
    final = out.select(*select_cols)

    # One output file per city rather than per (city, year, month). See
    # PARTITION_BY at the top of this file for the measurement behind this.
    (final.repartition(*[F.col(c) for c in PARTITION_BY])
          .write
          .mode("overwrite")
          .partitionBy(*PARTITION_BY)
          .option("compression", "snappy")
          .parquet(FEATURE_PATH))

    # ==========================================================================
    # SUMMARY
    # ==========================================================================
    n_num = len(NUMERIC_FEATURES)
    # The one-hot width is the OneHotEncoderModel's categorySizes, NOT the count
    # of StringIndexer labels. With handleInvalid="keep", Spark ignores dropLast
    # and emits categorySizes slots per column - one more than the label count,
    # for the unseen/null bucket. Reporting the label count instead understates
    # the true feature-vector width by one per categorical column.
    _ohe = model.stages[len(CATEGORICALS)]
    n_cat = sum(_ohe.categorySizes)
    n_labels = sum(len(model.stages[i].labels) for i in range(len(CATEGORICALS)))
    print("=" * 72)
    print("PHASE 4 COMPLETE")
    print("=" * 72)
    print(f"  rows in            : {rows_in:,}")
    print(f"  rows after dedupe  : {rows_dedup:,}")
    print(f"  rows with T+1 label: {rows_labelled:,}")
    print(f"  rows assemblable   : {after_assemble:,}")
    print(f"  numeric features   : {n_num}  (persisted as columns, not a vector)")
    print(f"  one-hot width      : {n_cat} ({n_labels} labels + 1 unseen bucket per "
          f"column, over {', '.join(CATEGORICALS)})")
    print(f"  FEATURE VECTOR DIM : {n_num + n_cat}  (assembled at train time)")
    print(f"  partitioned by     : {', '.join(PARTITION_BY)}")
    print(f"  labels             : target_pm25_next_hour, target_aqi_next_hour")
    print(f"  output             : {FEATURE_PATH}")
    print(f"  pipeline           : {PIPELINE_PATH}")
    print("=" * 72)

    spark.stop()


if __name__ == "__main__":
    main()
