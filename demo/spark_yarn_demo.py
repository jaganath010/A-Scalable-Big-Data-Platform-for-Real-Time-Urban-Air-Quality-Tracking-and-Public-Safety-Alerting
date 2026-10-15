"""
================================================================================
REVIEW DEMO - a real Spark job, scheduled by YARN, reading data from HDFS
================================================================================
Project : 23AID302 - Big Data Analytics

WHAT THIS PROVES ON SCREEN
  HDFS   the data is read from hdfs://namenode:9000/... (the 4-DataNode cluster)
  YARN   the job appears as an APPLICATION in the ResourceManager UI (:8088),
         with containers spread across the NodeManagers
  Spark  the stages / tasks / executors are visible in the Spark UI, reached
         through the YARN "ApplicationMaster" link

  It runs the same kind of query the Hive layer answers - rows per data source
  across the 154.6M-row unified table - but as a distributed Spark job.

RUN (inside the aq-spark container; demo/start_demo.ps1 does this for you):
    /opt/spark/bin/spark-submit --master yarn --deploy-mode client \
        --num-executors 3 --executor-memory 1500m --executor-cores 1 \
        /demo/spark_yarn_demo.py
================================================================================
"""
import time

from pyspark.sql import SparkSession, functions as F

spark = (SparkSession.builder.appName("AirQuality_Review_Demo").getOrCreate())
sc = spark.sparkContext
sc.setLogLevel("WARN")

UNIFIED = "hdfs://namenode:9000/user/hadoop/lakehouse/unified_merged"

print("=" * 72)
print("  REVIEW DEMO  -  Spark on YARN, reading from HDFS")
print(f"  master     : {sc.master}")
print(f"  app id     : {sc.applicationId}")
print(f"  tracking   : see the YARN UI at http://localhost:8088")
print("=" * 72)

t0 = time.time()
df = spark.read.parquet(UNIFIED)

# Partition pruning, shown rather than claimed: the plan reads only the
# partitions the filter needs.
print("\n[1] The unified table is partitioned by source_format:")
parts = [r[0] for r in df.select("source_format").distinct().collect()]
print("    partitions found:", sorted(parts))

print("\n[2] Rows per data source (distributed count over 154.6M rows):")
counts = (df.groupBy("source_format", "data_source")
            .agg(F.count("*").alias("rows"),
                 F.countDistinct("city").alias("cities"))
            .orderBy("source_format", "data_source"))
counts.show(truncate=False)

total = sum(r["rows"] for r in counts.collect())
print(f"    TOTAL rows: {total:,}   (expected 154,583,979 -> {total == 154583979})")

print("\n[3] Average PM2.5 by data source - structured CPCB vs semi-structured CAMS:")
(df.filter(F.col("pm25").isNotNull())
   .groupBy("data_source")
   .agg(F.round(F.avg("pm25"), 2).alias("avg_pm25"), F.count("*").alias("measured_rows"))
   .orderBy("data_source")
   .show(truncate=False))

print("\n[4] Worst live cities right now (live_api partition only - pruned read):")
(df.filter(F.col("source_format") == "semistructured_json")
   .filter(F.col("data_source") == "live_api")
   .groupBy("city")
   .agg(F.round(F.max("aqi_us"), 0).alias("peak_aqi"), F.round(F.avg("pm25"), 1).alias("avg_pm25"))
   .orderBy(F.desc("peak_aqi"))
   .show(8, truncate=False))

print(f"\nDONE in {time.time() - t0:.1f}s  -  queries finished; the application stays RUNNING in the YARN UI while it is held open, then moves to FINISHED")
# Hold the application open briefly so the Spark UI / YARN UI can be shown
# while it is still RUNNING. Set DEMO_HOLD=0 to skip.
import os
hold = int(os.environ.get("DEMO_HOLD", "90"))
if hold:
    print(f"holding the application open for {hold}s so the UIs can be shown...")
    time.sleep(hold)
spark.stop()
