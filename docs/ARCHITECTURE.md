# Architecture — How the Three Data Layers Work Together

**23AID302 — Big Data Analytics**
Written 6 Sep 2026, after the streaming layer was executed against the cluster
for the first time.

---

## 1. The three layers, and the job each one does

They are **not** three copies of the same thing. Each exists because the others
cannot do its job.

| Layer | What it is | Rows | Its one job |
|---|---|---|---|
| **Structured** | CPCB station CSV → Parquet, 2010-01 → 2023-03 | 146,276,379 | **TRAIN** the model |
| **Semi-structured (history)** | CAMS reanalysis JSON, 2022-08 → 2026-09 | 8,263,440 | **VALIDATE** the structured data against an independent source |
| **Semi-structured (live)** | CAMS live JSON, rolling 7-day window | 44,160 | **ALERT** on what is happening now |

### Why training must use the structured layer
Only it has:
- a **label** — `target_pm25_next_hour`, built from `pm25_measured` with the
  strict `next_ts == ts + 3600` guard
- **13 years of history**, so the model sees every season, every Diwali, every
  monsoon — a 7-day live window cannot teach seasonality
- the **full 54-feature vector** (traffic, weather, station identity)

### Why validation must use the semi-structured history
It is the only **independent** measurement of the same cities over the same
hours. Checking the structured data against itself proves nothing. The overlap
(2022-08 → 2023-03, 8 months) is where the two can be compared at all —
1,341,360 CAMS rows against 2,711,957 real structured rows.

### Why alerting must use the live layer
Alerting is inherently about *now*. Historical data cannot warn anybody.

---

## 2. Where they are joined

Physically, in `unified_merged/` — one Parquet table, one 17-column schema,
154,583,979 rows, partitioned by `source_format`:

```
source_format=structured_csv        146,276,379   (real 16,252,931 + synthetic 130,023,448)
source_format=semistructured_json     8,307,600   (cams_history 8,263,440 + live_api 44,160)
```

Any row's origin is recoverable from `data_source` ∈ {`real`, `synthetic`,
`cams_history`, `live_api`}, so a query can use one layer, two, or all three:

```sql
-- train on measured structured rows only
WHERE data_source = 'real'

-- cross-validate: same city, same hour, two independent sources
WHERE timestamp BETWEEN '2022-08-01' AND '2023-03-31'
  AND data_source IN ('real', 'cams_history')

-- what is happening right now
WHERE data_source = 'live_api'
```

This unified table is what makes **Variety** real rather than decorative: two
genuinely different data models (flat fixed-schema CSV, nested self-describing
JSON) read by their native Spark readers in one job and reconciled onto one
schema — without either being reformatted at source.

---

## 3. The live alerting path — and the gap in it

### What was proven on 6 Sep 2026
The streaming layer ran end-to-end against the live cluster:

```
[batch 0] rows in=120  predicted=15  alerts=10  latency=10,750 ms
[batch 1] rows in=120  predicted=15  alerts=10  latency= 7,817 ms
[batch 2] rows in=120  predicted=14  alerts=10  latency= 7,019 ms
[batch 3] rows in=120  predicted=12  alerts= 7  latency= 6,894 ms
```

Chain: file lands in HDFS → 10 s micro-batch → Phase 4 features rebuilt →
GBT (120 trees, depth 6) predicts PM2.5 **delta** → converted to CPCB AQI →
`AQI > 150` → alert with severity and dominant pollutant.

```
Delhi/DL029: forecast AQI 342 (Very Poor), driven by pm25.
             Forecast PM2.5 173.4 ug/m3 by 2018-03-01 10:00.
```

### ⚠️ The gap, stated plainly
**That demo was fed rows in the STRUCTURED 32-column schema, not live CAMS
JSON.** `AirQualityStream.scala`'s `InputSchema` is the structured schema.

Measured: of the model's **54 numeric features, 26 do not exist in the live
CAMS JSON**.

| Missing group | Count | Where it can really come from |
|---|---|---|
| Weather — `temperature_c`, `humidity_percent`, `wind_speed_ms`, `rainfall_mm`, `solar_radiation`, `pressure`, `wd_sin`, `wd_cos` | 8 | **Open-Meteo Weather API** — same provider as the air-quality feed, free, no key |
| Derived from weather — `ventilation_index`, `is_raining`, `scrub_factor`, `stagnation_index`, `temp_humidity_interaction` | 5 | computed once the 8 above exist |
| City/traffic — `traffic_index`, `is_rush_hour`, `urbanization_index` | 3 | `city_profiles.csv` + clock, using the SAME documented rush-hour multipliers the generator used |
| Provenance flags — `*_was_imputed` × 10 | 10 | 0 where CAMS returned a value, 1 where it returned null (e.g. `nh3`, null for 100% of CAMS rows) |

So the live path is **not yet closed**. Today the model can score a replay of
structured-schema data; it cannot yet score a raw CAMS JSON payload.

### The fix (Phase 8b — not yet built)
A live enrichment step between the CAMS pull and the stream:

```
CAMS air-quality JSON  ─┐
Open-Meteo weather JSON ─┼─→ enrich → 32-col structured schema → existing stream → alerts
city_profiles.csv       ─┘
```

Nothing is invented: pollutants and weather are both real API responses, the
traffic terms come from the project's own published city profiles, and the
imputation flags record honestly which fields the API did not return.

**Alternative, if time runs out:** CAMS already returns `us_aqi` directly, so
you can alert on *current* measured AQI with no model at all. But that reports
conditions rather than forecasting them, which gives up the project's actual
value proposition (an hour of warning). Say so explicitly if you fall back to
it — do not present it as forecasting.

---

## 4. Remaining work, in priority order

| # | Task | Closes | Effort | State |
|---|---|---|---|---|
| 1 | **Live enrichment (Phase 8b)** — weather API + city profiles → structured schema | Makes alerting work on *real live* data, not replay | ~half day | ❌ |
| 2 | **Track B** — rerun Phase 4 at full scale (241 cities), then GBT 300 trees | **Value** — a defensible headline R² | ~5-6 h, mostly unattended | ❌ |
| 3 | **Hive serving layer** (Phase 9) | SQL access over the unified table | ~half day | ❌ 0% |
| 4 | **Dashboard** (Phase 10) | Visual payoff for the demo | ~half day+ | ❌ 0% |
| 5 | Retry the 11 failed-geocode cities | 230 → up to 241 city coverage | ~1 h | ❌ |

### Current status of each phase

| Phase | State |
|---|---|
| 0 — dataset build + validation | ✅ |
| 1 — HDFS ingest | ✅ all layers uploaded, `fsck` HEALTHY |
| 2 — Spark/YARN activation | ✅ both run |
| 3 — clean/impute | ✅ full scale, 10.0 GB in HDFS |
| 4 — feature engineering | ⚠️ **reduced scale only** (4,349,178 rows / 19 cities); full-scale output was lost |
| 5/6 — train + evaluate | ⚠️ model exists and passes its gate, but trained on the reduced set |
| 7/8 — streaming + alerting | ✅ **executed 6 Sep 2026**; ⚠️ consumes structured schema, not raw CAMS (see §3) |
| 9 — Hive | ❌ |
| 10 — dashboard | ❌ |

### The 5 V's

| V | State |
|---|---|
| **Volume** | ✅ 154.6M rows, 33 GB, 4 DataNodes, real block distribution |
| **Variety** | ✅ flat CSV + nested JSON, native readers, one unified schema |
| **Veracity** | ✅ 4 defects found and fixed, independent cross-validation run, results reported honestly including where they are weak |
| **Velocity** | ✅ **demonstrated 6 Sep 2026** — 10 s micro-batches, ~7 s latency, alerts fired |
| **Value** | ⚠️ real model beating persistence (R² 0.8855 vs 0.8714), but on 19 cities — Track B closes this |

---

## 5. Model currently in use

| | |
|---|---|
| Path | `lakehouse_smoke/models/gbt_pm25_forecaster` (also in HDFS at `/user/hadoop/models/`) |
| Trained on | 3,477,690 rows, 19 cities, chronological split |
| Config | GBT, 120 trees, depth 6, delta target |
| Real-rows score | **R² 0.8855, RMSE 20.436** vs persistence **0.8714 / 21.665** |
| Gate | **PASS** — beats persistence by 0.0142 R² |

Quote this as a **reduced-scale** result. It is weaker than the 11.3% RMSE
reduction from the earlier sklearn reproduction because it uses less data,
fewer trees and fewer cities — all three are expected to improve under Track B.
