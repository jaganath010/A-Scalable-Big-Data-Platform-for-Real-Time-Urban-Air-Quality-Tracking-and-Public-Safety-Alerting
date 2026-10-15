r"""
================================================================================
LIVE EVIDENCE FOR PHASES 2, 3 AND 4
================================================================================
Project : A Scalable Big Data Platform for Real-Time Urban Air Quality Tracking
Course  : 23AID302 - Big Data Analytics

Prints verifiable proof of each phase by reading the artefacts the pipeline
actually produced, rather than replaying the 40- and 78-minute jobs. Designed to
be run in front of an examiner and screenshotted.

RUN
  env.cmd                        (cmd)      -- must be run first
  . .\env.ps1                    (PowerShell)

  python show_evidence.py            all phases
  python show_evidence.py --phase 2  Spark engine activation
  python show_evidence.py --phase 3  cleaning and Parquet conversion
  python show_evidence.py --phase 4  feature engineering

Deliberately light on memory (local[2], 2 GB) so it can run while a training
job holds the rest of the machine.
================================================================================
"""

import argparse
import os
import sys

import paths

BAR = "=" * 78
SUB = "-" * 78


def hdr(title):
    print()
    print(BAR)
    print(f"  {title}")
    print(BAR)


def phase2(spark):
    hdr("PHASE 2 - APACHE SPARK ENGINE ACTIVATION")
    sc = spark.sparkContext
    print(f"  Spark version          : {spark.version}")
    print(f"  Scala/JVM build        : {sc._jvm.scala.util.Properties.versionString()}")
    print(f"  Master                 : {sc.master}")
    print(f"  Application ID         : {sc.applicationId}")
    print(f"  Application name       : {sc.appName}")
    print(f"  Default parallelism    : {sc.defaultParallelism}")
    print(f"  Driver memory          : {sc.getConf().get('spark.driver.memory', 'default')}")
    print(f"  Shuffle partitions     : {spark.conf.get('spark.sql.shuffle.partitions')}")
    print(f"  Adaptive execution     : {spark.conf.get('spark.sql.adaptive.enabled')}")
    print(f"  Spark Web UI           : {sc.uiWebUrl}")
    print(SUB)
    print(f"  Java runtime           : {sc._jvm.System.getProperty('java.version')}")
    print(f"  JAVA_HOME              : {os.environ.get('JAVA_HOME', 'NOT SET')}")
    print(f"  HADOOP_HOME            : {os.environ.get('HADOOP_HOME', 'NOT SET')}")
    print(SUB)
    print("  A live distributed compute engine, executing the job below across")
    print(f"  {sc.defaultParallelism} parallel task slots.")


def phase3(spark):
    from pyspark.sql import functions as F

    hdr("PHASE 3 - DATA CLEANING, IMPUTATION & PARQUET CONVERSION")
    df = spark.read.parquet(paths.CLEAN_PATH)

    n = df.count()
    print(f"  Source            : {paths.CLEAN_PATH}")
    print(f"  Rows              : {n:,}")
    print(f"  Columns           : {len(df.columns)}   (32 input -> 44 output)")
    print(f"  Format            : Snappy-compressed Parquet, partitioned by city")

    print(SUB)
    print("  PROVENANCE SPLIT  - the basis of 'evaluate on real rows only'")
    (df.groupBy("data_source").count()
       .withColumn("percent", F.round(100.0 * F.col("count") / F.lit(n), 2))
       .orderBy(F.col("count").desc()).show(truncate=False))

    print(SUB)
    print("  IMPUTATION FLAGS  - every filled value is marked, so measured and")
    print("                      estimated data stay distinguishable")
    flags = [c for c in df.columns if c.endswith("_was_imputed")]
    rates = df.agg(*[F.avg(F.col(c)).alias(c) for c in flags]).collect()[0]
    print(f"    {'column':24s} {'imputed':>10s} {'measured':>10s}")
    for c in flags:
        pct = 100.0 * rates[c]
        print(f"    {c.replace('_was_imputed',''):24s} {pct:9.2f}% {100-pct:9.2f}%")

    print(SUB)
    print("  ANOMALY ERADICATION - measured ranges after cleaning")
    print("  (humidity clamped to 0-100, traffic index to 0-100, flags to 0/1)")
    df.select(
        F.round(F.min("humidity_percent"), 2).alias("humidity_min"),
        F.round(F.max("humidity_percent"), 2).alias("humidity_max"),
        F.round(F.min("traffic_index"), 2).alias("traffic_min"),
        F.round(F.max("traffic_index"), 2).alias("traffic_max"),
        F.min("is_rush_hour").alias("rush_min"),
        F.max("is_rush_hour").alias("rush_max"),
    ).show(truncate=False)

    print(SUB)
    print("  SAMPLE OF CLEANED DATA")
    df.select("station_id", "city", "timestamp", "pm25", "pm10", "no2",
              "temperature_c", "humidity_percent", "data_source").show(5, truncate=False)


def phase4(spark):
    from pyspark.sql import functions as F

    hdr("PHASE 4 - SPATIAL-TEMPORAL FEATURE ENGINEERING & VECTOR ASSEMBLY")
    df = spark.read.parquet(paths.FEATURE_PATH)

    n = df.count()
    print(f"  Source            : {paths.FEATURE_PATH}")
    print(f"  Rows with T+1 label : {n:,}")
    print(f"  Columns on disk     : {len(df.columns)}")

    import importlib
    p4 = importlib.import_module("02_feature_extraction")
    print(f"  Numeric features    : {len(p4.NUMERIC_FEATURES)}")
    print(f"  Categorical columns : {len(p4.CATEGORICALS)}  {p4.CATEGORICALS}")
    print(f"  One-hot slots       : 32  (season 5 + weather 10 + climate 17)")
    print(f"  FEATURE VECTOR DIM  : {len(p4.NUMERIC_FEATURES) + 32}")

    print(SUB)
    print("  TIME-SHIFT OFFSET - PM2.5 at hour T+1 as the target, accepted only")
    print("                      when the next reading is EXACTLY 3600s later")
    df.select("station_id", "timestamp", "pm25",
              F.col("target_pm25_next_hour").alias("pm25_at_T+1"),
              F.col("aqi_current"),
              F.col("target_aqi_next_hour").alias("aqi_at_T+1")
              ).show(5, truncate=False)

    print(SUB)
    print("  ENGINEERED HISTORY FEATURES - gap-safe rolling windows")
    df.select("pm25", "pm25_lag_1h", "pm25_delta_1h", "pm25_roll_3h",
              "pm25_roll_6h", "pm25_avg24h", "pm25_surge_ratio"
              ).show(5, truncate=False)

    print(SUB)
    print("  CYCLICAL ENCODINGS - hour 23 and hour 0 are adjacent, not 23 apart")
    df.select("hour", "hour_sin", "hour_cos", "month", "month_sin", "month_cos",
              "wd_sin", "wd_cos").show(5, truncate=False)

    print(SUB)
    print("  PHYSICAL INTERACTION FEATURES")
    df.select("ventilation_index", "is_raining", "scrub_factor",
              "stagnation_index", "temp_humidity_interaction").show(5, truncate=False)

    print(SUB)
    print("  CPCB AQI - computed as the maximum of 7 pollutant sub-indices")
    (df.groupBy("aqi_dominant_pollutant").count()
       .orderBy(F.col("count").desc()).show(truncate=False))

    print(SUB)
    print("  SAVED FEATURE PIPELINE (Spark ML) - reused by the Scala streaming job")
    stages = os.path.join(paths.PIPELINE_PATH, "stages")
    if os.path.isdir(stages):
        for s in sorted(os.listdir(stages)):
            print(f"    {s}")
    else:
        print(f"    {paths.PIPELINE_PATH}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", type=int, choices=(2, 3, 4), default=0,
                    help="show one phase only (default: all)")
    args = ap.parse_args()

    # Light footprint on purpose - this is meant to run alongside other jobs.
    os.environ.setdefault("AQ_CORES", "2")
    os.environ.setdefault("AQ_DRIVER_MEM", "2g")
    os.environ.setdefault("AQ_SHUFFLE_PARTITIONS", "8")

    spark = paths.spark_session("AirQuality_Evidence")
    spark.sparkContext.setLogLevel("ERROR")

    try:
        if args.phase in (0, 2):
            phase2(spark)
        if args.phase in (0, 3):
            phase3(spark)
        if args.phase in (0, 4):
            phase4(spark)
        print()
        print(BAR)
        print("  END OF EVIDENCE")
        print(BAR)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
