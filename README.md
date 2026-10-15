# A Scalable Big Data Platform for Real-Time Urban Air Quality Tracking and Public Safety Alerting
23AID302 Big Data Analytics, Group A14 (Sangeeth S, Jaganath R, Niranjan S, PL Kowshik)

## Final review materials
| What | Where |
|---|---|
| Final presentation (10 slides + evidence appendix) | `presentation/Final_Review_10_Slides.pptx` |
| First review presentation | `presentation/1st_Review_Presentation.pptx` |
| Project report | `docs/PROJECT_REPORT.pdf` |
| Public warning board (open in a browser, no server needed) | `dashboard/AirWatch_India.html` |
| Scala jobs (cleaning, features, live enrichment, streaming) | `scala/streaming/src/main/scala/` |
| PySpark (GBT training, validation, fetchers, alert dispatch) | `scripts/` |
| Hive serving layer | `hive/` |
| Run logs and evidence | `docs/run_logs/` |
| Alerting design (hourly loop + de-duplication) | `docs/ALERTING.md` |

Large data (about 33 GB), build output and local runtime state are not in the repo; see `.gitignore` and `RUNBOOK.md`.

---

# Air Quality Big Data Platform — Code Package

**23AID302 — Big Data Analytics**
A Scalable Big Data Platform for Real-Time Urban Air Quality Tracking and Public Safety Alerting

This package contains every script needed to build the dataset, run the pipeline and train the
model. **The dataset itself is not included** (27.48 GB) — `00c_expand_dataset.py` regenerates it.

---

## 1. Quick facts

| | |
|---|---|
| Dataset built | `F:\SEM 5 NOTES\Big Data\Project_Final\airquality_expanded` — 27.48 GB, 146,276,379 rows, 32 columns |
| Cities / states | **241 cities**, 31 states & UTs |
| Stations | 4,077 total (453 real + 3,624 synthetic) |
| Real rows | 16,252,931 (11.1%) |
| Semi-structured layer | `airquality_expanded\semistructured_json\` — 230/241 cities, live JSON, Open-Meteo/CAMS, no fabricated values |
| Unified dataset | `airquality_expanded\unified_merged\` — **146,320,539 rows**, Parquet, structured + semi-structured on one schema |
| Model result | **R² = 0.9201** vs persistence baseline **0.8984** (real rows only) |
| Cluster target | 1 NameNode + **4 DataNodes**, 220 blocks, 3× replication |

---

## 2. Prerequisites

| Component | Version | Needed for |
|---|---|---|
| Python | 3.10+ | all scripts |
| Java | **8, 11 or 17** | Spark 3.5. Java 21+ is NOT supported |
| PySpark | 3.5.6 | Phases 3–6 |
| winutils.exe + hadoop.dll | Hadoop 3.3.x build | Spark **writes** on Windows |
| Hadoop / HDFS | 3.x | Phases 1–2 (cluster only) |
| numpy, pandas, scikit-learn | any recent | `03b_local_run.py` only |
| xgboost | optional | model comparison only |

The dataset builder (`00c_`) and validator (`00d_`) use the standard library only — no installs.

### This machine — already configured

`pyspark==3.5.6` is installed. The machine's default JDK is **23**, which Spark 3.5 does not
support, so the pipeline pins the `jre1.8.0_421` that is also installed. `winutils.exe` and
`hadoop.dll` (cdarlint/winutils, hadoop-3.3.5 build) are in `C:\hadoop\bin` — without them every
Parquet write and model save fails with `HADOOP_HOME and hadoop.home.dir are unset`.

All of that is set by dot-sourcing the env script, which changes **nothing globally**:

```bash
. .\env.ps1
```

---

## 3. Run order

### Local mode vs cluster mode

Paths are no longer hardcoded. [`scripts/paths.py`](scripts/paths.py) resolves them from the
environment, so the same scripts run both ways:

| Variable | Default | Meaning |
|---|---|---|
| `AQ_FS` | `local` | `local` or `hdfs` |
| `AQ_DATA` | the `airquality_expanded` dir | input CSVs |
| `AQ_LAKE` | `<project>\lakehouse` | output root (`hdfs:///user/hadoop` in hdfs mode) |
| `AQ_CORES`, `AQ_DRIVER_MEM`, `AQ_SHUFFLE_PARTITIONS` | `*`, `8g`, `64` | local tuning |

Switch the whole pipeline to the cluster with `$env:AQ_FS = "hdfs"`.

### Step 1 — Build the dataset (~17 min, writes 27.5 GB)

```bash
python 00c_expand_dataset.py \
    --src "final_air_quality_dataset_22gb_balanced.csv" \
    --out "F:\SEM 5 NOTES\Big Data\Project_Final\airquality_expanded" \
    --target-gb 22
```

Useful flags: `--scale N` forces a scale factor · `--real-only` emits just the 2.7 GB repaired real
data · `--sigma` tunes perturbation strength (0.08 is the validated value).

Already built — skip unless regenerating.

### Step 2 — Validate the dataset (mandatory)

```bash
python 00d_validate_expansion.py --dir "F:\SEM 5 NOTES\Big Data\Project_Final\airquality_expanded" --stations 22
```

Compares synthetic against real on persistence R², autocorrelation, marginal distribution,
missingness and inter-pollutant correlation. **Treat any FAIL as blocking — do not use output that
fails this.**

### Step 3 — Clean, impute and convert to Parquet (Phase 3)

```bash
python 01_clean_select.py
```

Reads the expanded CSVs, range-guards, runs three-tier median imputation, emits `pm25_measured`
and the `*_was_imputed` flags, writes Parquet partitioned by `(city, year, month)`.

`--limit-files N` reads only the first N of the 23 parts, for a smoke run. It reads **whole files**
rather than sampling rows — sampling would punch holes in each station's series and corrupt the T+1
label. `--source legacy` runs the original 139→32 column pruning against the old 23.44 GB file
instead; that path is kept for auditability only.

### Step 3b — Add the semi-structured layer and build the unified dataset (Variety)

The main dataset above is entirely flat, fixed-schema CSV — structured data only. Two
scripts add a genuinely semi-structured source alongside it and merge both into one
queryable dataset, without touching, reformatting or perturbing either source.

```bash
python 00e_fetch_semistructured_json.py \
    --out "F:\SEM 5 NOTES\Big Data\Project_Final\airquality_expanded\semistructured_json" \
    --days 7
```

Pulls **real, live** hourly air-quality JSON for every city in `city_profiles.csv` (241
requested) from Open-Meteo's public Air Quality API (Copernicus CAMS data) — free, no API
key, no account. Saves each response verbatim (nested `hourly` struct-of-arrays, its own
`hourly_units` schema) to `raw_json/<city>.json`, plus `manifest.json` (provenance) and
`semistructured_flat.csv` (convenience join view). Result: **230/241 cities** — 11 small
localities (e.g. `Byrnihat`, `Vatva`) got a genuine geocoder miss and were skipped rather
than assigned invented coordinates; see `semistructured_json/README.md` for the full list
and rationale. 44,160 hourly records (230 × 192h), ~6.7 MB.

```bash
python 01c_merge_structured_semistructured.py \
    --structured "F:\SEM 5 NOTES\Big Data\Project_Final\airquality_expanded" \
    --semistructured "F:\SEM 5 NOTES\Big Data\Project_Final\airquality_expanded\semistructured_json" \
    --out "F:\SEM 5 NOTES\Big Data\Project_Final\airquality_expanded\unified_merged"
```

Spark reads the structured CSVs and the nested JSON with its native readers (genuine
schema-on-read across two data models in one job), projects both onto one 17-column common
schema, and unions them — writing partitioned Parquet (`source_format=structured_csv` /
`source_format=semistructured_json`). Values are never blended or imputed across sources;
a row is tagged by where it actually came from. Verified result: **146,320,539 rows**
(16,252,931 real + 130,023,448 synthetic + 44,160 live), 4.2 GB, 0 duplicate keys, all 230
cities exactly 192 rows, structured row count reconciles exactly against the source. See
`unified_merged`'s row-count table and the null-audit in the file reference below.

**Honesty notes carried into the schema:**
- Structured rows have no `latitude`/`longitude` (not in that dataset) and no `aqi_us`
  (raw CPCB pollutants only, no precomputed AQI) — left `NULL`, not guessed.
- Semi-structured rows have no `station_id` (city-centroid API pulls, not fixed physical
  stations) — `NULL`, not invented.
- Semi-structured `nh3` is `NULL` for all 44,160 rows — CAMS has no NH3 coverage for this
  region. A real source limitation, not a processing artifact.
- `aqi_us` (US EPA AQI, 0–500) is a separate column from any CPCB AQI computed later in
  Phase 4 — the two scales must never be conflated.
- The two layers do **not** overlap in time (structured: 2010–2023, semi-structured: live,
  Aug 2026) — framed as batch-historical + streaming-style-live, which fits this project's
  real-time-alerting premise better than a backfill would.

### Step 4 — Feature engineering (Phase 4)

```bash
python 02_feature_extraction.py
```

### Step 5 — Train and evaluate (Phases 5–6)

```bash
python 03_train_gbt.py
```

Prints the persistence baseline next to the model score, on **all rows** and on **real rows only**,
and fails loudly if the model does not beat persistence on the real rows.

### On the cluster

Same scripts, with `$env:AQ_FS = "hdfs"` set first:

```bash
hdfs dfs -mkdir -p /user/hadoop/lakehouse/raw
hdfs dfs -put "F:\SEM 5 NOTES\Big Data\Project_Final\airquality_expanded\part-*.csv" /user/hadoop/lakehouse/raw/
```

```bash
spark-submit --master yarn --deploy-mode client --executor-memory 8g --driver-memory 4g --conf spark.sql.shuffle.partitions=400 01_clean_select.py
```

### Optional — Prove the pipeline locally without Spark

```bash
python 03b_local_run.py --dir "F:\SEM 5 NOTES\Big Data\Project_Final\airquality_expanded" --max-rows 6000000 --target delta
```

Runs identical logic in pandas + scikit-learn. Useful for verifying correctness before submitting
to the cluster.

---

## 4. File reference

### Dataset construction
| File | Purpose |
|---|---|
| `00c_expand_dataset.py` | Builds the 27.48 GB dataset from real rows. Repairs all four data defects. Two-pass: partition by station, then sort and generate. |
| `00d_validate_expansion.py` | Five-test statistical validator. Paired sampling on `source_station`. |

### Spark pipeline
| File | Purpose |
|---|---|
| `paths.py` | Shared path/session config. Resolves `local` vs `hdfs` from the environment — the reason the scripts are no longer hardcoded to a cluster that does not exist yet. |
| `01_clean_select.py` | Phase 3. Range-guard, three-tier median imputation, `pm25_measured`, Parquet conversion. `--source expanded` (default) or `legacy`. |
| `02_feature_extraction.py` | T+1 target (temporally validated), CPCB AQI, rolling/lag history, cyclical encodings, physical interactions, VectorAssembler |
| `03_train_gbt.py` | Chronological split, persistence-benchmarked GBT on the delta target, raw µg/m³ metrics on all rows **and real rows only**, per-city error breakdown |

### Structured + semi-structured (Variety)
| File | Purpose |
|---|---|
| `00e_fetch_semistructured_json.py` | Pulls real, live hourly air-quality JSON per city from Open-Meteo (CAMS), no API key. City list defaults to this project's own `city_profiles.csv`. Writes raw JSON + `manifest.json` + a flattened CSV view. |
| `01c_merge_structured_semistructured.py` | Spark job. Reads structured CSV and nested semi-structured JSON with native readers, projects both onto one common schema, unions them, writes partitioned Parquet (`unified_merged/`). |

> An earlier version of this README called `01_clean_select.py` redundant. It is not: `02_feature_extraction.py`
> reads its output and depends on `pm25_measured` and the `*_was_imputed` flags, which only this
> script produces. What *is* redundant on the expanded source is the 139→32 column pruning.

### Alternative all-real path (not currently used)
| File | Purpose |
|---|---|
| `00_fetch_real_data.py` | Downloads ~27 GB of real US EPA hourly measurements (verified available, no API key) |
| `01b_build_wide_table.py` | Pivots EPA long format to the wide schema |

### Local verification
| File | Purpose |
|---|---|
| `03b_local_run.py` | Single-machine reproduction of Phases 4–6 (pandas + sklearn) |

### Documentation
| File | Purpose |
|---|---|
| `COLUMN_DECISION_REPORT.md` | Column-by-column justification with measured fill rates; the R²=0.58 diagnosis |
| `HONEST_SCALING.md` | Expansion methodology, validation results, and how to defend the synthetic fraction |

### Audit scripts (`_audit/`)
Every number quoted in the reports is reproducible from these. They read the **original** CSV.

| File | Measures |
|---|---|
| `fillrate.py` | Per-column fill rate across 960k sampled rows |
| `probe.py` | Coalesce coverage, value ranges, categorical cardinality |
| `probe2.py` | Flag corruption, impossible values, timestamp uniqueness |
| `fullscan.py` | Exact row/station counts over all 48.6M rows |
| `diag.py` | **Persistence baseline** — the measurement that proved the old model was broken |
| `diag2.py` | Cross-year replication and value-repetition leakage checks |
| `validate.py` | CPCB AQI math against published reference points; T+1 mislabelling rate |
| `cityexact.py` | Exact city/state/station counts on the built dataset |

---

## 5. Three rules that must not be broken

These are the fixes for the failure that produced R² = 0.58. Breaking any one reintroduces it.

1. **Never build the label from imputed PM2.5.** Use `pm25_measured`. About 26% of PM2.5 values are
   imputed; a label that is a median is unlearnable and caps R² hard.
2. **Never use a positional `lead()` for the T+1 target.** Require `next_ts == ts + 3600`. Measured,
   a plain `lead()` mislabels 8.69% of rows with the wrong forecast horizon.
3. **Never split a time series randomly.** Split chronologically, and always print the persistence
   baseline next to your R². A model that does not beat persistence is broken, not weak.

---

## 6. Status

**Complete:** dataset audit, rebuild and validation · feature engineering logic · model training and
evaluation · model selection study · semi-structured JSON layer (230/241 cities, live, real) ·
unified structured+semi-structured merge (146,320,539 rows, Spark-verified, 0 duplicate keys).

**Remaining:** Phase 1 (HDFS upload) · Phase 2 (Spark activation) · distributed runs of Phases 3–6 ·
streaming speed layer · closed-loop alert engine · Hive serving layer · dashboard · Random Forest
comparison baseline.

See `PROJECT_STATUS_REPORT.docx` for the full phase-by-phase breakdown.
