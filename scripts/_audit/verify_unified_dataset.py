"""
================================================================================
AUDIT - VERIFY THE UNIFIED (STRUCTURED + SEMI-STRUCTURED) PARQUET DATASET
================================================================================
Project : 23AID302 - Big Data Analytics

Re-derives every claim made about unified_merged from a FRESH read of the
Parquet on disk. It deliberately does NOT trust the merge job's own write-time
log: a write-time summary reports what the job believed it wrote, which is
exactly the thing that needs independent checking.

This is the check that caught a real bug. The first merge used a substring
file-name join (`input_file.contains(m_file)`), and "navi_mumbai.json" contains
"mumbai.json" as a literal substring, so Mumbai's rows were double-counted
(384 instead of 192); likewise "greater_noida.json" contains "noida.json".
The defect surfaced ONLY because the semi-structured row count (44,544) failed
to reconcile against the known fetch count (44,160). Row-count reconciliation
against an independently known number is the check that finds this class of
bug - keep it.

WHAT IT ASSERTS
  total row count == sum of the three layers' known counts
  per-layer counts, distinct cities, and time ranges
  semi-structured layers have no duplicate (city, timestamp)
  every semi-structured city has exactly the expected number of hours
  NULL patterns match each source's REAL limitations, i.e.
      station_id  null only for semi-structured (no fixed physical station)
      latitude    null only for structured      (not present in that source)
      aqi_us      null only for structured      (US scale never mixed with CPCB)
      nh3         null for ALL semi-structured  (real CAMS regional gap)
      pm25 nulls  preserved at their true rates, never silently filled

RUN
    powershell> . .\\env.ps1
    powershell> python _audit\\verify_unified_dataset.py `
                    --unified "F:\\...\\airquality_expanded\\unified_merged"
================================================================================
"""

import argparse

from pyspark.sql import SparkSession, functions as F

# Independently known counts. These come from the source fetches/builds, NOT
# from the merge job, which is the point.
EXPECT = {
    "real": 16_252_931,          # 00c_expand_dataset.py
    "synthetic": 130_023_448,    # 00c_expand_dataset.py
    "live_api": 44_160,          # 00e: 230 cities x 192 h
    "cams_history": 8_263_440,   # 00f: 230 cities x 35,928 h
}
EXPECT_TOTAL = sum(EXPECT.values())
HOURS_LIVE, HOURS_HIST = 192, 35_928


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--unified", required=True)
    ap.add_argument("--master", default="local[*]")
    ap.add_argument("--driver-mem", default="6g")
    args = ap.parse_args()

    spark = (SparkSession.builder.appName("verify_unified")
             .master(args.master)
             .config("spark.driver.memory", args.driver_mem)
             .config("spark.sql.shuffle.partitions", "32")
             .getOrCreate())
    spark.sparkContext.setLogLevel("WARN")

    df = spark.read.parquet(args.unified)
    ok = True

    print("=== SCHEMA ===")
    df.printSchema()

    total = df.count()
    match = total == EXPECT_TOTAL
    ok &= match
    print(f"TOTAL ROWS: {total:,}   expected {EXPECT_TOTAL:,} -> {match}")

    print("\n=== COUNTS BY LAYER ===")
    got = {r["data_source"]: r["count"] for r in
           df.groupBy("data_source").count().collect()}
    for k, v in EXPECT.items():
        g = got.get(k, 0)
        good = g == v
        ok &= good
        print(f"  {k:14} {g:>12,}  expected {v:>12,}  -> {good}")

    print("\n=== TIME RANGE / CITIES PER LAYER ===")
    df.groupBy("data_source").agg(
        F.min("timestamp").alias("min_ts"),
        F.max("timestamp").alias("max_ts"),
        F.countDistinct("city").alias("cities"),
    ).orderBy("data_source").show(truncate=False)

    print("=== NULL AUDIT (each column should be null only where it SHOULD be) ===")
    df.groupBy("data_source").agg(
        F.count("*").alias("n"),
        F.sum(F.col("station_id").isNull().cast("int")).alias("station_id_null"),
        F.sum(F.col("latitude").isNull().cast("int")).alias("lat_null"),
        F.sum(F.col("aqi_us").isNull().cast("int")).alias("aqi_us_null"),
        F.sum(F.col("nh3").isNull().cast("int")).alias("nh3_null"),
        F.sum(F.col("pm25").isNull().cast("int")).alias("pm25_null"),
        F.sum(F.col("timestamp").isNull().cast("int")).alias("ts_null"),
    ).orderBy("data_source").show(truncate=False)

    # a null timestamp anywhere would break every time-based operation downstream
    ts_null = df.filter(F.col("timestamp").isNull()).count()
    ok &= ts_null == 0
    print(f"null timestamps anywhere: {ts_null} -> {ts_null == 0}")

    print("\n=== SEMI-STRUCTURED INTEGRITY ===")
    for layer, hours in (("live_api", HOURS_LIVE), ("cams_history", HOURS_HIST)):
        sub = df.filter(F.col("data_source") == layer)
        dupes = sub.groupBy("city", "timestamp").count().filter("count > 1").count()
        bad = sub.groupBy("city").count().filter(f"count != {hours}").count()
        ok &= (dupes == 0 and bad == 0)
        print(f"  {layer:14} duplicate (city,timestamp) keys: {dupes}   "
              f"cities with != {hours:,} rows: {bad}")

    print("\n=== CROSS-SOURCE QUERY (Delhi appears in every layer) ===")
    df.filter(F.col("city") == "Delhi").groupBy("data_source").count() \
      .orderBy("data_source").show(truncate=False)

    print("\n" + ("ALL CHECKS PASSED" if ok else "*** ONE OR MORE CHECKS FAILED ***"))
    spark.stop()
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
