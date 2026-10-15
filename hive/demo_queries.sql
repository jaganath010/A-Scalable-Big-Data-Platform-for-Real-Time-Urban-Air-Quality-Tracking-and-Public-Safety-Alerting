-- ============================================================================
-- PHASE 9 - demonstration queries against the Hive serving layer
-- 23AID302 - Big Data Analytics
--
-- Each query is here because it answers a question the project claims to
-- answer. Run with:
--     docker exec aq-spark bash /hive/run_hive_layer.sh query
-- ============================================================================

USE airquality;

-- ---------------------------------------------------------------------------
-- Q1. Scale of the platform, broken down by data model.
--     This is the Volume + Variety claim as a single SQL result.
-- ---------------------------------------------------------------------------
SELECT '--- Q1: rows by source ---' AS q;

SELECT source_format,
       data_source,
       COUNT(*)                 AS rows,
       COUNT(DISTINCT city)     AS cities,
       MIN(`timestamp`)         AS from_ts,
       MAX(`timestamp`)         AS to_ts
FROM unified_airquality
GROUP BY source_format, data_source
ORDER BY source_format, data_source;

-- ---------------------------------------------------------------------------
-- Q2. Partition pruning in action.
--     Only the live partition is touched; the 146M structured rows are never
--     read. On a 154M-row table this is the difference between a dashboard
--     that responds and one that times out.
-- ---------------------------------------------------------------------------
SELECT '--- Q2: current live readings, worst 15 cities ---' AS q;

SELECT city, state,
       ROUND(pm25, 1)   AS pm25,
       ROUND(aqi_us, 0) AS aqi_us,
       latest_hour
FROM v_live_latest
ORDER BY aqi_us DESC NULLS LAST
LIMIT 15;

-- ---------------------------------------------------------------------------
-- Q3. What the alerting layer actually fired.
--     This is the table a public warning service would read from.
-- ---------------------------------------------------------------------------
SELECT '--- Q3: alert leaderboard ---' AS q;

SELECT city, alert_count,
       ROUND(worst_forecast_aqi, 0) AS worst_aqi,
       first_alert, last_alert
FROM v_alert_summary
ORDER BY alert_count DESC
LIMIT 15;

-- ---------------------------------------------------------------------------
-- Q4. THE VARIETY QUERY - one statement reading structured CPCB history and
--     semi-structured CAMS data together, per city.
--     Cities where the two disagree most are the ones worth investigating;
--     that disagreement is quantified properly in 04_cross_validate_overlap.py.
-- ---------------------------------------------------------------------------
SELECT '--- Q4: structured vs semi-structured, per city ---' AS q;

SELECT city,
       structured_rows,
       semistructured_rows,
       ROUND(avg_pm25_cpcb, 1)                      AS avg_pm25_cpcb,
       ROUND(avg_pm25_cams, 1)                      AS avg_pm25_cams,
       ROUND(avg_pm25_cpcb - avg_pm25_cams, 1)      AS gap
FROM v_structured_vs_live
WHERE avg_pm25_cpcb IS NOT NULL
  AND avg_pm25_cams IS NOT NULL
ORDER BY ABS(avg_pm25_cpcb - avg_pm25_cams) DESC
LIMIT 15;

-- ---------------------------------------------------------------------------
-- Q5. The honest-reporting query: measured vs imputed.
--     ~26% of PM2.5 in the structured layer is imputed, and the platform can
--     say so in SQL rather than in a footnote. pm25_measured is NULL exactly
--     where the reading was filled.
-- ---------------------------------------------------------------------------
SELECT '--- Q5: measured vs imputed PM2.5, 10 largest cities ---' AS q;

SELECT city,
       COUNT(*)                                                        AS rows,
       SUM(CASE WHEN pm25_measured IS NOT NULL THEN 1 ELSE 0 END)      AS measured,
       ROUND(100.0 * SUM(CASE WHEN pm25_measured IS NULL THEN 1 ELSE 0 END)
             / COUNT(*), 1)                                            AS pct_imputed
FROM clean_airquality
GROUP BY city
ORDER BY rows DESC
LIMIT 10;

-- ---------------------------------------------------------------------------
-- Q6. Seasonal signal - the reason 13 years of history is worth keeping.
--     A 7-day live window cannot produce this.
-- ---------------------------------------------------------------------------
SELECT '--- Q6: Delhi PM2.5 by month, real measurements only ---' AS q;

SELECT MONTH(`timestamp`)          AS month,
       COUNT(*)                    AS readings,
       ROUND(AVG(pm25_measured),1) AS avg_pm25_measured
FROM clean_airquality
WHERE city = 'Delhi'
  AND pm25_measured IS NOT NULL
GROUP BY MONTH(`timestamp`)
ORDER BY month;
