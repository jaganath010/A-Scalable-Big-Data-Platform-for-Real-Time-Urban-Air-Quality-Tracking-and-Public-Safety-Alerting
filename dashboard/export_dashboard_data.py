"""
================================================================================
PHASE 10 (data) - EXPORT THE SERVING LAYER FOR THE DASHBOARD
================================================================================
Project : 23AID302 - Big Data Analytics

Runs INSIDE the aq-spark container against the Hive serving layer and writes
one JSON document the dashboard embeds. This is the standard production shape:
the dashboard never queries 154M rows on page load - it reads pre-aggregated
results the serving layer materialised.

Every figure the dashboard shows comes from here, from real tables. Nothing is
typed into the HTML by hand except the model metrics, which come from the
training log (docs/run_logs/trackB_train_fullscale.summary.log) and are
recorded below with that provenance.

RUN (inside the container):
    /opt/spark/bin/spark-submit --master 'local[2]' --driver-memory 2g \
        --conf spark.sql.catalogImplementation=hive \
        --conf spark.sql.warehouse.dir=hdfs://namenode:9000/user/hadoop/hive \
        --conf 'spark.driver.extraJavaOptions=-Dderby.system.home=/scratch/metastore_db' \
        --conf spark.local.dir=/scratch \
        /dashboard/export_dashboard_data.py /tmp/dashboard_data.json
================================================================================
"""
import json
import sys
from datetime import datetime, timezone

from pyspark.sql import SparkSession, functions as F

out_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/dashboard_data.json"

spark = (SparkSession.builder.appName("dashboard_export")
         .enableHiveSupport().getOrCreate())
spark.sparkContext.setLogLevel("WARN")
spark.sql("USE airquality")


def rows(df):
    """DataFrame -> list of plain dicts, timestamps as ISO strings."""
    out = []
    for r in df.collect():
        d = r.asDict()
        for k, v in d.items():
            if hasattr(v, "isoformat"):
                d[k] = v.isoformat(sep=" ")
        out.append(d)
    return out


data = {"generated_utc": datetime.now(timezone.utc).isoformat()}

# ---- 1. headline scale, by data model -----------------------------------------
data["volume"] = rows(spark.sql("""
    SELECT source_format, data_source, COUNT(*) AS rows_,
           COUNT(DISTINCT city) AS cities,
           MIN(`timestamp`) AS from_ts, MAX(`timestamp`) AS to_ts
    FROM unified_airquality
    GROUP BY source_format, data_source
    ORDER BY source_format, data_source"""))

# ---- 2. live: latest reading per city, with coordinates for the map -----------
# ONE time basis for the whole page. An earlier version took "now" from
# v_live_latest (the unified table's live partition, last fetched in AUGUST)
# while the warnings came from the streaming run over 4-7 SEPTEMBER - so a card
# could pair a three-week-old "right now" reading with a September forecast.
# Everything "now" therefore comes from the streaming predictions table, which
# was written by the same run that produced the alerts.
from pyspark.sql import Window

PRED = "hdfs://namenode:9000/user/hadoop/lakehouse/stream/predictions"
pred = spark.read.parquet(PRED)

w_latest = Window.partitionBy("city").orderBy(F.desc("observed_at"))
latest = (pred.withColumn("_rn", F.row_number().over(w_latest)).filter("_rn = 1")
              .select("city", F.col("observed_at").alias("latest_hour"),
                      F.col("pm25_now").alias("pm25"), F.col("aqi_current").alias("aqi_now"),
                      "aqi_forecast"))
coords = spark.sql("""SELECT city, state, latitude, longitude FROM v_live_latest
                      WHERE latitude IS NOT NULL""")
data["live_latest"] = rows(latest.join(coords, "city")
                                 .select("city", "state", "latitude", "longitude",
                                         "latest_hour", "pm25", "aqi_now", "aqi_forecast")
                                 .orderBy(F.desc("pm25")))

# the real time span of this run - the banner quotes this, not the unified table
data["run_window"] = rows(pred.agg(
    F.min("observed_at").alias("observed_from"), F.max("observed_at").alias("observed_to"),
    F.min("forecast_for").alias("forecast_from"), F.max("forecast_for").alias("forecast_to"),
    F.countDistinct("city").alias("cities")))[0]

# ---- 3. alerts: the thing the platform exists to produce ----------------------
# Per city, the PEAK alert row: its observed hour, forecast hour, PM2.5 then and
# forecast, and its true dominant pollutant. (The old "cause" was
# MAX(aqi_dominant_pollutant) - the alphabetically last string, not the driver.)
alerts = spark.table("stream_alerts")
w_peak = Window.partitionBy("city").orderBy(F.desc("aqi_forecast"), F.desc("forecast_for"))
peak = (alerts.withColumn("_rn", F.row_number().over(w_peak)).filter("_rn = 1")
              .select("city",
                      F.col("observed_at").alias("peak_observed_at"),
                      F.col("forecast_for").alias("peak_forecast_for"),
                      F.col("pm25_now").alias("peak_pm25_now"),
                      F.col("pm25_forecast").alias("peak_pm25_forecast"),
                      F.col("aqi_dominant_pollutant").alias("peak_driver")))
summary = spark.sql("""
    SELECT city, alert_count, worst_forecast_aqi, first_alert, last_alert, severity_levels
    FROM v_alert_summary""")
data["alert_summary"] = rows(summary.join(peak, "city").orderBy(F.desc("worst_forecast_aqi")))

data["alerts_recent"] = rows(spark.sql("""
    SELECT city, station_id, observed_at, forecast_for,
           pm25_now, pm25_forecast, aqi_current, aqi_forecast,
           aqi_band, aqi_dominant_pollutant, severity, message
    FROM stream_alerts
    ORDER BY aqi_forecast DESC, forecast_for DESC
    LIMIT 60"""))

# every alert in the last 48 h of forecast hours - what the hourly dispatcher
# (scripts/send_alerts.py --mode window) picks from, relative to the clock
data["alerts_window"] = rows(spark.sql("""
    SELECT city, station_id, observed_at, forecast_for, pm25_now, pm25_forecast,
           aqi_forecast, aqi_band, aqi_dominant_pollutant, severity
    FROM stream_alerts
    WHERE forecast_for >= (SELECT MAX(forecast_for) - INTERVAL 24 HOURS FROM stream_alerts)"""))

data["severity_mix"] = rows(spark.sql("""
    SELECT severity, COUNT(*) AS n FROM stream_alerts
    GROUP BY severity ORDER BY n DESC"""))

data["driver_mix"] = rows(spark.sql("""
    SELECT aqi_dominant_pollutant AS pollutant, COUNT(*) AS n FROM stream_alerts
    GROUP BY aqi_dominant_pollutant ORDER BY n DESC"""))

# alerts over time - hourly, for the timeline
data["alerts_by_hour"] = rows(spark.sql("""
    SELECT DATE_FORMAT(forecast_for, 'yyyy-MM-dd HH:00') AS hour, COUNT(*) AS n
    FROM stream_alerts GROUP BY 1 ORDER BY 1"""))

# ---- 4. seasonal signal - the reason 13 years of history is kept --------------
data["delhi_seasonal"] = rows(spark.sql("""
    SELECT MONTH(`timestamp`) AS month, COUNT(*) AS readings,
           ROUND(AVG(pm25_measured), 1) AS avg_pm25
    FROM clean_airquality
    WHERE city = 'Delhi' AND pm25_measured IS NOT NULL
    GROUP BY MONTH(`timestamp`) ORDER BY month"""))

# ---- 5. measured vs imputed - honesty in SQL ---------------------------------
data["imputation"] = rows(spark.sql("""
    SELECT city, COUNT(*) AS rows_,
           SUM(CASE WHEN pm25_measured IS NOT NULL THEN 1 ELSE 0 END) AS measured,
           ROUND(100.0 * SUM(CASE WHEN pm25_measured IS NULL THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_imputed
    FROM clean_airquality GROUP BY city ORDER BY rows_ DESC LIMIT 12"""))

# ---- 6. structured vs semi-structured, per city --------------------------------
data["structured_vs_cams"] = rows(spark.sql("""
    SELECT city, structured_rows, semistructured_rows,
           ROUND(avg_pm25_cpcb, 1) AS avg_pm25_cpcb, ROUND(avg_pm25_cams, 1) AS avg_pm25_cams
    FROM v_structured_vs_live
    WHERE avg_pm25_cpcb IS NOT NULL AND avg_pm25_cams IS NOT NULL
    ORDER BY ABS(avg_pm25_cpcb - avg_pm25_cams) DESC LIMIT 12"""))

# ---- 7. model metrics - from the training log, recorded with provenance -------
data["model"] = {
    "source": "docs/run_logs/trackB_train_fullscale.summary.log (6 Sep 2026)",
    "config": {"trees": 300, "max_depth": 6, "step_size": 0.08, "cities": 241,
               "train_rows": 10000552, "test_rows": 18671121, "real_test_rows": 2074569},
    "real_rows": {"persistence": {"r2": 0.8587, "rmse": 24.831, "mae": 9.937},
                  "gbt":         {"r2": 0.8910, "rmse": 21.806, "mae": 8.926},
                  "rmse_reduction_pct": 12.18},
    "all_rows":  {"persistence": {"r2": 0.8563, "rmse": 25.443, "mae": 10.357},
                  "gbt":         {"r2": 0.8884, "rmse": 22.429, "mae": 9.353},
                  "rmse_reduction_pct": 11.85},
}

# ---- 8. cross-validation - from crossval.log, recorded with provenance -------
data["crossval"] = {
    "source": "docs/run_logs/crossval.log (6 Sep 2026), 1,152,707 matched city-hours",
    "rows": [
        {"pollutant": "pm25", "corr": 0.565, "bias": 8.55,   "rmse": 50.75},
        {"pollutant": "pm10", "corr": 0.558, "bias": 44.89,  "rmse": 97.18},
        {"pollutant": "o3",   "corr": 0.361, "bias": -48.54, "rmse": 67.17},
        {"pollutant": "no2",  "corr": 0.219, "bias": -2.07,  "rmse": 35.24},
        {"pollutant": "so2",  "corr": 0.083, "bias": -10.05, "rmse": 43.32},
    ],
}

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=1, default=str)

print("wrote", out_path)
for k, v in data.items():
    n = len(v) if isinstance(v, list) else "-"
    print(f"  {k:20} {n}")
spark.stop()
