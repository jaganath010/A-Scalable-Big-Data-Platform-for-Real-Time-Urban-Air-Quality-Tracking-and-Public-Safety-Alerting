-- ============================================================================
-- PHASE 9 - HIVE SERVING LAYER
-- 23AID302 - Big Data Analytics
--
-- Exposes everything the pipeline has produced as SQL tables, so the platform
-- can be queried by analysts and dashboards without writing Spark code.
--
-- ALL TABLES ARE **EXTERNAL**. That is deliberate:
--   * no data is copied - the tables point at the Parquet already in HDFS, so
--     the serving layer costs ~0 bytes on top of a 33 GB lakehouse;
--   * DROP TABLE removes only the metadata definition, never the underlying
--     data. On a managed table a careless DROP would delete 154 million rows.
--
-- Partition discovery: Hive does not scan for partitions automatically on an
-- external table, so each one ends with MSCK REPAIR TABLE. Without it the
-- table exists but every query returns zero rows - a confusing failure that
-- looks like missing data rather than missing metadata.
-- ============================================================================

CREATE DATABASE IF NOT EXISTS airquality
  COMMENT 'Air Quality Big Data Platform - serving layer'
  LOCATION 'hdfs://namenode:9000/user/hadoop/hive/airquality.db';

USE airquality;

-- ---------------------------------------------------------------------------
-- 1. UNIFIED - the Variety table: structured CSV + semi-structured JSON on one
--    schema. 154,583,979 rows. Partitioned by source_format so a query that
--    only wants live data never touches the 146M structured rows.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS unified_airquality;
CREATE EXTERNAL TABLE unified_airquality (
  station_id      STRING,
  city            STRING,
  state           STRING,
  latitude        DOUBLE,
  longitude       DOUBLE,
  `timestamp`     TIMESTAMP,
  pm25            DOUBLE,
  pm10            DOUBLE,
  no2             DOUBLE,
  so2             DOUBLE,
  co              DOUBLE,
  o3              DOUBLE,
  nh3             DOUBLE,
  aqi_us          DOUBLE,
  data_source     STRING,
  source_dataset  STRING
)
PARTITIONED BY (source_format STRING)
STORED AS PARQUET
LOCATION 'hdfs://namenode:9000/user/hadoop/lakehouse/unified_merged';

MSCK REPAIR TABLE unified_airquality;

-- ---------------------------------------------------------------------------
-- 2. CLEAN - Phase 3 output, 146,276,379 rows, partitioned by city (241).
--    This is the table to query for "what did station X read in 2019".
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS clean_airquality;
CREATE EXTERNAL TABLE clean_airquality (
  station_id        STRING,
  state             STRING,
  `timestamp`       TIMESTAMP,
  pm25              DOUBLE,
  pm25_measured     DOUBLE,
  pm10              DOUBLE,
  no2               DOUBLE,
  so2               DOUBLE,
  co                DOUBLE,
  o3                DOUBLE,
  nh3               DOUBLE,
  temperature_c     DOUBLE,
  humidity_percent  DOUBLE,
  wind_speed_ms     DOUBLE,
  rainfall_mm       DOUBLE,
  data_source       STRING
)
PARTITIONED BY (city STRING)
STORED AS PARQUET
LOCATION 'hdfs://namenode:9000/user/hadoop/lakehouse/clean_scala';

MSCK REPAIR TABLE clean_airquality;

-- ---------------------------------------------------------------------------
-- 3. ALERTS - what the streaming layer actually fired. This is the table a
--    public-facing dashboard or notification service would read.
-- ---------------------------------------------------------------------------
-- Column list verified against what AirQualityStream.scala actually writes
-- (printSchema on the Parquet), NOT against what it was assumed to write. A
-- first version of this DDL declared a column called `timestamp`; no such
-- column exists, so Hive returned NULL for every time value while the counts
-- and AQI figures looked perfectly correct - a silent, plausible-looking
-- wrong answer. The real time columns are three distinct instants:
--   observed_at  - the hour the input reading belongs to
--   forecast_for - the hour being predicted (observed_at + 1h)
--   generated_at - when the alert was produced
DROP TABLE IF EXISTS stream_alerts;
CREATE EXTERNAL TABLE stream_alerts (
  station_id             STRING,
  state                  STRING,
  observed_at            TIMESTAMP,
  forecast_for           TIMESTAMP,
  pm25_now               DOUBLE,
  pm25_forecast          DOUBLE,
  aqi_current            DOUBLE,
  aqi_forecast           DOUBLE,
  aqi_band               STRING,
  aqi_dominant_pollutant STRING,
  generated_at           TIMESTAMP,
  severity               STRING,
  message                STRING
)
PARTITIONED BY (city STRING)
STORED AS PARQUET
LOCATION 'hdfs://namenode:9000/user/hadoop/lakehouse/stream/alerts';

MSCK REPAIR TABLE stream_alerts;

-- ---------------------------------------------------------------------------
-- 4. VIEWS - the questions this platform exists to answer, pre-written so a
--    dashboard does not have to re-derive them.
-- ---------------------------------------------------------------------------

-- 4a. Current air quality per city, live feed only.
CREATE OR REPLACE VIEW v_live_latest AS
SELECT city, state, latitude, longitude,
       MAX(`timestamp`)                                    AS latest_hour,
       MAX_BY(pm25,   `timestamp`)                         AS pm25,
       MAX_BY(aqi_us, `timestamp`)                         AS aqi_us
FROM unified_airquality
WHERE source_format = 'semistructured_json'
  AND data_source   = 'live_api'
GROUP BY city, state, latitude, longitude;

-- 4b. Alert leaderboard - which cities are being warned most often.
CREATE OR REPLACE VIEW v_alert_summary AS
SELECT city,
       COUNT(*)                     AS alert_count,
       MAX(aqi_forecast)            AS worst_forecast_aqi,
       MIN(forecast_for)            AS first_alert,
       MAX(forecast_for)            AS last_alert,
       COUNT(DISTINCT severity)     AS severity_levels,
       MAX(aqi_dominant_pollutant)  AS sample_driver
FROM stream_alerts
GROUP BY city;

-- 4c. THE VARIETY QUERY - one statement spanning both data models, which is
--     the whole point of the unified table. Structured CPCB history and
--     semi-structured CAMS live data, side by side, per city.
CREATE OR REPLACE VIEW v_structured_vs_live AS
SELECT city,
       SUM(CASE WHEN source_format = 'structured_csv'      THEN 1 ELSE 0 END) AS structured_rows,
       SUM(CASE WHEN source_format = 'semistructured_json' THEN 1 ELSE 0 END) AS semistructured_rows,
       AVG(CASE WHEN data_source = 'real'         THEN pm25 END)              AS avg_pm25_cpcb,
       AVG(CASE WHEN data_source = 'cams_history' THEN pm25 END)              AS avg_pm25_cams
FROM unified_airquality
GROUP BY city;
