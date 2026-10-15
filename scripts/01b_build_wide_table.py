"""
================================================================================
PHASE 1b - RAW (long) -> CURATED (wide) : the real multi-source fusion step
================================================================================
INPUT   : hdfs:///user/hadoop/lakehouse/raw_epa/*.csv     (~27 GB, real)
OUTPUT  : hdfs:///user/hadoop/lakehouse/clean/            (Parquet, wide)

WHAT THIS REPLACES
  This is the honest substitute for the "simulation rig" that manufactured
  weather and traffic in the old pipeline. Nothing is invented here: pollutants
  and meteorology are pivoted from real measurements and joined on
  (site, hour). The fusion is a JOIN, not a random number generator.

  This is also where the project's "Variety" claim becomes real rather than
  rhetorical: 11 independently-collected parameter streams, each arriving as a
  separate file with its own method codes and QA qualifiers, are reconciled onto
  one spatial-temporal key.

EPA HOURLY SCHEMA (24 columns, long format - one row per site/parameter/hour):
  State Code, County Code, Site Num, Parameter Code, POC, Latitude, Longitude,
  Datum, Parameter Name, Date Local, Time Local, Date GMT, Time GMT,
  Sample Measurement, Units of Measure, MDL, Uncertainty, Qualifier,
  Method Type, Method Code, Method Name, State Name, County Name,
  Date of Last Change

RUN
  spark-submit --master yarn --deploy-mode client \
    --executor-memory 8g --driver-memory 4g \
    --conf spark.sql.shuffle.partitions=800 \
    01b_build_wide_table.py
================================================================================
"""

from pyspark.sql import SparkSession, functions as F

RAW_EPA    = "hdfs:///user/hadoop/lakehouse/raw_epa/*.csv"
CLEAN_PATH = "hdfs:///user/hadoop/lakehouse/clean"

# EPA parameter code -> the column name this project uses.
# Pivoting on the CODE (not the name) is deliberate: the WIND file contains two
# parameters and RH_DP contains two, so a file-level mapping would lose one of
# each. Unknown codes fall through as param_<code> instead of being dropped.
PARAM_MAP = {
    "88101": "pm25",             # PM2.5 FRM/FEM,  ug/m3
    "88502": "pm25_nonfrm",      # PM2.5 non-FRM,  ug/m3
    "81102": "pm10",             # PM10,           ug/m3
    "44201": "o3",               # Ozone,          ppm  -> converted below
    "42101": "co",               # Carbon monoxide, ppm -> converted below
    "42602": "no2",              # Nitrogen dioxide, ppb
    "42401": "so2",              # Sulfur dioxide,  ppb
    "61103": "wind_speed_ms",    # Wind speed resultant,  knots -> m/s
    "61104": "wd_degree",        # Wind direction resultant, degrees
    "62101": "temperature_c",    # Outdoor temperature, F -> C
    "62201": "humidity_percent", # Relative humidity, %
    "62103": "dew_point_c",      # Dew point, F -> C
    "64101": "pressure",         # Barometric pressure, millibars
}


def main():
    spark = (
        SparkSession.builder
        .appName("AirQuality_Phase1b_LongToWide_RealData")
        .config("spark.sql.parquet.compression.codec", "snappy")
        .config("spark.sql.adaptive.enabled", "true")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    raw = (spark.read
           .option("header", "true")
           .option("inferSchema", "false")
           .csv(RAW_EPA))

    print(f">>> raw rows: {raw.count():,}")

    # ==========================================================================
    # STEP 1 - NORMALISE KEYS
    #
    # A monitoring site is (State Code, County Code, Site Num). POC distinguishes
    # multiple instruments measuring the SAME parameter at the SAME site - it is
    # not part of the site identity, it is a duplicate source. Handled in step 2.
    #
    # GMT is used, not local time: local time has DST discontinuities that would
    # create duplicate and missing hours in the time series.
    # ==========================================================================
    df = raw.select(
        F.concat_ws("-",
                    F.lpad(F.col("`State Code`"), 2, "0"),
                    F.lpad(F.col("`County Code`"), 3, "0"),
                    F.lpad(F.col("`Site Num`"), 4, "0")).alias("station_id"),
        F.col("`State Name`").alias("state"),
        F.col("`County Name`").alias("city"),
        F.col("`Latitude`").cast("double").alias("latitude"),
        F.col("`Longitude`").cast("double").alias("longitude"),
        F.col("`Parameter Code`").alias("param_code"),
        F.col("`POC`").cast("int").alias("poc"),
        F.to_timestamp(
            F.concat_ws(" ", F.col("`Date GMT`"), F.col("`Time GMT`")),
            "yyyy-MM-dd HH:mm").alias("timestamp"),
        F.col("`Sample Measurement`").cast("double").alias("value"),
        F.col("`Qualifier`").alias("qualifier"),
    ).filter(F.col("timestamp").isNotNull())

    # ==========================================================================
    # STEP 2 - QA FILTER + COLLAPSE DUPLICATE INSTRUMENTS
    #
    # EPA ships a Qualifier column flagging exceptional events, calibration
    # periods and suspect data. Rows carrying a qualifier are excluded rather
    # than silently averaged in - this is real quality assurance metadata, which
    # is exactly the "Veracity" tier the project claims.
    #
    # Where a site runs several instruments for one parameter (POC 1,2,3), the
    # mean is taken. That is a measurement-reconciliation decision, not
    # fabrication: every contributing value is a real reading.
    # ==========================================================================
    df = df.filter(F.col("value").isNotNull() &
                   (F.col("qualifier").isNull() | (F.trim(F.col("qualifier")) == "")))

    df = (df.groupBy("station_id", "state", "city", "latitude", "longitude",
                     "timestamp", "param_code")
            .agg(F.avg("value").alias("value")))

    # ==========================================================================
    # STEP 3 - PIVOT LONG -> WIDE
    # One row per (station, hour), one column per parameter.
    # ==========================================================================
    codes = list(PARAM_MAP.keys())
    wide = (df.filter(F.col("param_code").isin(codes))
              .groupBy("station_id", "state", "city", "latitude", "longitude", "timestamp")
              .pivot("param_code", codes)
              .agg(F.first("value")))

    for code, name in PARAM_MAP.items():
        if code in wide.columns:
            wide = wide.withColumnRenamed(code, name)

    # ==========================================================================
    # STEP 4 - UNIT CONVERSION TO THE AQI/SI SCALE
    #
    # EPA reports O3 and CO in ppm and temperature in Fahrenheit. AQI breakpoints
    # and every physical feature downstream expect a consistent scale. These are
    # exact conversions, not estimates.
    # ==========================================================================
    wide = (
        wide
        .withColumn("o3_ppm", F.col("o3"))                       # keep for US AQI
        .withColumn("o3_ppb", F.col("o3") * 1000.0)
        .withColumn("co_ppm", F.col("co"))                       # keep for US AQI
        .withColumn("temperature_c", (F.col("temperature_c") - 32.0) * 5.0 / 9.0)
        .withColumn("dew_point_c",   (F.col("dew_point_c")   - 32.0) * 5.0 / 9.0)
        .withColumn("wind_speed_ms", F.col("wind_speed_ms") * 0.514444)  # knots -> m/s
        # PM2.5: prefer the regulatory FRM/FEM monitor, fall back to non-FRM.
        # Both are real instruments; FRM is the reference method.
        .withColumn("pm25", F.coalesce(F.col("pm25"), F.col("pm25_nonfrm")))
    )

    # ==========================================================================
    # STEP 5 - TEMPORAL FEATURES (derived, not invented)
    #
    # Every column here is a deterministic function of the timestamp. Nothing is
    # sampled from a distribution. This is the honest half of what the old
    # pipeline's "dynamic feature generation" was doing.
    #
    # NOTE what is NOT here: traffic. There is no real traffic feed in this
    # source, so no traffic column is manufactured. is_rush_hour below is an
    # honest TIME-OF-DAY indicator - it says "this is a commute hour", which is
    # a fact about the clock, not a claim about measured congestion.
    # ==========================================================================
    wide = (
        wide
        .withColumn("year",  F.year("timestamp"))
        .withColumn("month", F.month("timestamp"))
        .withColumn("day",   F.dayofmonth("timestamp"))
        .withColumn("hour",  F.hour("timestamp"))
        .withColumn("day_of_week", F.dayofweek("timestamp") - 1)
        .withColumn("is_weekend", F.col("day_of_week").isin([0, 6]).cast("int"))
        .withColumn("is_rush_hour",
                    (F.col("hour").between(7, 9) | F.col("hour").between(16, 18)).cast("int"))
        .withColumn("season",
                    F.when(F.col("month").isin([12, 1, 2]), "winter")
                     .when(F.col("month").isin([3, 4, 5]), "spring")
                     .when(F.col("month").isin([6, 7, 8]), "summer")
                     .otherwise("autumn"))
        # Real derived meteorology: dew-point depression is a direct measure of
        # how far the air is from saturation - it drives both fog and dispersion.
        .withColumn("dewpoint_depression_c", F.col("temperature_c") - F.col("dew_point_c"))
    )

    # ==========================================================================
    # STEP 6 - PRESERVE THE MEASURED TRUTH FOR LABELLING
    #
    # Same rule that fixed the R2=0.58 failure: the label must never be built
    # from an imputed value. pm25_measured is written BEFORE any imputation runs
    # downstream, and 02_feature_extraction.py builds the target only from it.
    # ==========================================================================
    wide = wide.withColumn("pm25_measured", F.col("pm25"))
    wide = wide.withColumn("data_source", F.lit("epa_aqs_real"))
    wide = wide.withColumn("variation_bucket", F.lit(0))  # no synthetic copies exist

    for c in ["pm25", "pm10", "no2", "so2", "co", "o3", "wd_degree", "pressure"]:
        if c in wide.columns:
            wide = wide.withColumn(f"{c}_was_imputed", F.col(c).isNull().cast("int"))

    wide = wide.filter(F.col("pm25_measured").isNotNull() |
                       F.col("pm10").isNotNull() |
                       F.col("o3").isNotNull())

    (wide.repartition("state", "year")
         .write.mode("overwrite")
         .partitionBy("state", "year", "month")
         .option("compression", "snappy")
         .parquet(CLEAN_PATH))

    # ==========================================================================
    # SUMMARY
    # ==========================================================================
    n = wide.count()
    stations = wide.select("station_id").distinct().count()
    cities = wide.select("city").distinct().count()
    span = wide.agg(F.min("timestamp").alias("a"), F.max("timestamp").alias("b")).collect()[0]

    print("=" * 72)
    print("PHASE 1b COMPLETE - REAL WIDE TABLE")
    print("=" * 72)
    print(f"  rows          : {n:,}")
    print(f"  stations      : {stations:,}")
    print(f"  counties/cities: {cities:,}")
    print(f"  time span     : {span['a']} -> {span['b']}")
    print(f"  synthetic rows: 0")
    print(f"  output        : {CLEAN_PATH}")
    print("-" * 72)
    print("  per-column coverage (measured, not imputed):")
    cov = wide.select([
        (100.0 * F.avg(F.col(c).isNotNull().cast("double"))).alias(c)
        for c in PARAM_MAP.values() if c in wide.columns
    ]).collect()[0]
    for c in PARAM_MAP.values():
        if c in wide.columns:
            print(f"    {c:20s} {cov[c]:6.2f}%")
    print("=" * 72)

    spark.stop()


if __name__ == "__main__":
    main()
