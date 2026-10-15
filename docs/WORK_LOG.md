# Work Log — Semi-Structured Layer, Unified Dataset, Cross-Validation

**23AID302 — Big Data Analytics**
Everything added in the September 2026 work block, with the script that
produces each number so nothing in the reports is unbacked.

---

## 1. What was added

| Artifact | Location | Size / count |
|---|---|---|
| Semi-structured **live** layer | `airquality_expanded\semistructured_json\` | 230 cities × 192 h = **44,160** records, 6.7 MB |
| Semi-structured **historical** layer | `airquality_expanded\semistructured_history\` | 230 cities × 35,928 h = **8,263,440** records, 458 MB |
| **Unified** dataset (all layers, one schema) | `airquality_expanded\unified_merged\` | **154,583,979** rows, 4.2 GB Parquet |

All three are also in HDFS (verified HEALTHY, 3× replication):

```
/user/hadoop/raw/semistructured_json         44,160 records
/user/hadoop/raw/semistructured_history      456.7 MB, 230 files
/user/hadoop/lakehouse/unified_merged        4.2 GB, _SUCCESS present
/user/hadoop/lakehouse/clean_scala           10.0 GB  (Phase 3 output, earlier)
```

---

## 2. Scripts, and what each one backs

### Data acquisition
| Script | Purpose |
|---|---|
| `scripts/00e_fetch_semistructured_json.py` | Live 7-day CAMS pull. City list now read from `city_profiles.csv` (241 requested, 230 resolved). |
| `scripts/00f_fetch_semistructured_history.py` | Historical CAMS pull, 2022-08-01 → present. Resumable, concurrent, rate-limit aware. |

### Merge and validation
| Script | Purpose |
|---|---|
| `scripts/01c_merge_structured_semistructured.py` | Spark job. Reads structured CSV + nested JSON with native readers, projects both onto one 17-column schema, unions, writes partitioned Parquet. |
| `scripts/04_cross_validate_overlap.py` | Compares structured (CPCB) against semi-structured (CAMS) over the Aug 2022 – Mar 2023 overlap. |

### Audit / evidence (`scripts/_audit/`)
| Script | Backs which claim |
|---|---|
| `scan_expanded_fillrate.py` | Every per-column fill %, min/max/mean/median, categorical splits, year distribution, duplicate-key rate |
| `scan_expanded_coverage.py` | 7-pollutant co-coverage (43.18% all 7, 15.72% none); real-vs-synthetic pm25 distribution |
| `cams_history_availability.py` | **The 2010–2023 impossibility.** Shows the API rejects < 2013 and returns all-null 2013→2022-07 |
| `cams_history_cutoff.py` | Pins the real start to **2022-08** (89.7% fill), 100% from 2022-09 |
| `cams_fullrange_probe.py` | Per-city response size / record count / timing used to plan the full fetch |
| `probe_failed_geocodes.py` | The 11 cities that failed geocoding, and which alternate spellings do/don't resolve |
| `verify_unified_dataset.py` | Independent re-derivation of every unified-dataset claim from a fresh read |

### Dashboard (`dashboard/`)
| File | Purpose |
|---|---|
| `export_dashboard_data.py` | Runs in the Spark container against Hive; writes one pre-aggregated JSON |
| `dashboard_template.html` | The page (Plotly for the India map; CPCB bands as status colours) |
| `build_dashboard.py` | Embeds the JSON into the template -> `dashboard.html` |
| `dashboard.html` | The deliverable - self-contained, opens from disk or as the published artifact |

### Live path + serving (`scripts/`, `hive/`)
| File | Purpose |
|---|---|
| `00g_fetch_live_weather.py` | Live weather ingest (8 fields, m/s requested explicitly) |
| `scala/.../LiveEnrichment.scala` | Spark/YARN job: CAMS JSON + weather JSON + city_profiles -> the 32-col schema the model consumes |
| `run_daily_live_cycle.py` | The schedulable daily job: fetch -> upload -> enrich on YARN -> hand to stream |
| `hive/create_tables.sql` | Hive DB + EXTERNAL tables over the HDFS Parquet, plus 3 views |
| `hive/demo_queries.sql` | 6 queries tied to the project's claims |
| `hive/run_hive_layer.sh` | `create` / `query` / `thrift` (HiveServer2 on :10000) |

### Document generators (`docs/_generators/`)
| Script | Produces |
|---|---|
| `build_cheatsheet.py` | `docs/HADOOP_SPARK_CHEATSHEET.pdf` |

### Run logs (`docs/run_logs/`)
Raw stdout from each real run — the primary evidence behind the numbers above.

| Log | Run |
|---|---|
| `fetch_241_run.log` | Live fetch, 230/241 cities |
| `history_fetch.log` | Historical fetch, 230/230, 8,263,440 records, 37.9 min |
| `merge_run.log` | Three-source unified merge |
| `crossval.log` | Cross-validation over the overlap window |
| `trackA_train.log` | GBT training on the reduced-scale features |

---

## 3. Findings worth defending

**2010–2023 semi-structured data is not obtainable.** Measured, not assumed:
the API rejects any `start_date` before 2013-01-01, and 2013-01 → 2022-07
returns timestamps with **100% null values**. Real data begins 2022-08.
Requesting the full 2010–2023 span would have produced ten years of empty rows
that *look* like coverage. Evidence: `cams_history_availability.py`,
`cams_history_cutoff.py`.

**A real merge bug was caught by row-count reconciliation.** The first merge
joined JSON files to the manifest with a substring match. `navi_mumbai.json`
contains `mumbai.json` as a literal substring (and `greater_noida.json`
contains `noida.json`), so those two cities were double-counted — 384 rows
instead of 192. It surfaced only because the semi-structured total (44,544)
failed to reconcile with the known fetch count (44,160). Fixed to exact
basename equality and re-run. This is why `verify_unified_dataset.py` checks
counts against independently known numbers rather than the job's own log.

**The live and historical layers overlap, and the overlap is not redundant.**
They share 192 hours per city (44,160 rows). For Delhi, 173 of those 192 hours
match exactly but **19 differ** — all at the tail of the live window. That is
CAMS revising *forecast* values into *analysis* values. Both are kept and
tagged (`live_api` vs `cams_history`) rather than deduped, because the
forecast values are what the alerting layer actually sees in real time.

**Cross-validation is a genuinely mixed result — report it as such.**
Over 1,152,707 matched city-hours:

| Pollutant | corr | bias | RMSE |
|---|---|---|---|
| pm25 | 0.565 | +8.55 | 50.75 |
| pm10 | 0.558 | +44.89 | 97.18 |
| o3 | 0.361 | −48.54 | 67.17 |
| no2 | 0.219 | −2.07 | 35.24 |
| so2 | **0.083** | −10.05 | 43.32 |

PM2.5/PM10 track moderately, which is plausible for roadside sensors versus a
coarse model grid. **SO2 shows essentially no agreement**, and O3 has a large
systematic offset. Per-city spread is wide: Kolkata 0.792 and Howrah 0.794 at
the top, Pune −0.209 at the bottom.

Two methodological notes that must travel with those numbers:
- **CO was excluded** from the headline. The structured layer reports CO in
  mg/m³, CAMS in µg/m³; comparing raw would fake a ~1000× disagreement.
- **The `synthetic` vs CAMS comparison is not valid evidence.** It returned
  numerically identical results to `real` vs CAMS (0.564 vs 0.565) because
  averaging to city-hour means averages away the AR(1) perturbation — the test
  cannot distinguish the two by construction. Testing generator fidelity needs
  a station-level comparison; use `00d_validate_expansion.py` instead.

**Timezone alignment verified, not assumed.** Correlation was measured at hour
offsets −3…+3 and peaks at 0h/+1h (0.565 vs 0.566 — within noise), decaying
symmetrically either side. A genuine timezone error would shift the peak
sharply. The IST assumption holds.

---

## 3b. Streaming layer executed for the first time (6 Sep 2026)

Phase 7/8 had been written but **never run against a cluster**. It ran today.

```
[batch 0] rows in=120  predicted=15  alerts=10  latency=10,750 ms
[batch 1] rows in=120  predicted=15  alerts=10  latency= 7,817 ms
[batch 2] rows in=120  predicted=14  alerts=10  latency= 7,019 ms
[batch 3] rows in=120  predicted=12  alerts= 7  latency= 6,894 ms
```

Outputs persisted to `/user/hadoop/lakehouse/stream/{alerts,predictions,history,checkpoint}`.
Input batches built by `scripts/_demo/make_stream_batches.py` from **real** rows
of trained cities (copies kept in `docs/demo_data/stream_batches/`).

### A real bug that only a live run could find

Every batch aborted at the history-update step:

```
AnalysisException: [UNRESOLVED_COLUMN.WITH_SUGGESTION]
A column or function parameter with name `ts_unix` cannot be resolved.
```

`combined.agg(max("ts_unix"))` referenced a column that is created *inside*
`buildFeatures` and never propagates back to `combined`. The very next line
already derived it correctly — the reference was one line too early.

Two things made it invisible until now:
1. the alerts printed **before** the failure, so it looked like the stream had
   simply stalled after batch 0 rather than erroring;
2. it can only fire on a batch that has history to merge — so any test that
   ran a single batch would pass.

Fixed in `AirQualityStream.scala` (derive `ts_unix` once into `combinedTs`,
use it for both the cutoff and the trim), recompiled with `sbt package`, and
re-run from a clean checkpoint. This is the concrete argument for why
"the code is written" is not the same as "the phase is done".

---

## 3c. Phase 8b - live enrichment, and Track B (6 Sep 2026)

### Phase 8b: closing the live-alerting gap
The model needs 54 numeric features; raw CAMS JSON supplies 28. `LiveEnrichment.scala`
(Spark, on YARN) joins CAMS JSON + Open-Meteo weather JSON + `city_profiles.csv`
into the 32-column schema the stream already consumes.

  * **16,560 rows across 230 cities**, 0 nulls on model-critical columns
  * ran as YARN application `application_1788670113534_0002`
  * scored live: **16,560 predicted -> 1,130 alerts**

Unit conversions were measured, not assumed:
`co` CAMS ug/m3 -> structured mg/m3 (/1000); `pressure` hPa -> mmHg (x0.750062,
output 753.81 matches the structured median of 753); wind requested from the API
directly in m/s.

`scripts/00g_fetch_live_weather.py` (ingest) + `scripts/run_daily_live_cycle.py`
(the schedulable daily job: fetch -> upload -> enrich on YARN -> hand to stream).

### Track B: full-scale Phase 4
`FeatureExtraction.scala`, 73.5 min, every checkpoint reproducing this project's
own RUNBOOK exactly:

| Stage | Rows |
|---|---|
| loaded | 146,276,379 |
| after dedupe | 128,660,967 |
| T+1 labelled | 93,216,105 |
| assemblable | 93,216,105 (100%) |

Output 19.7 GB, 241 city partitions, **feature vector 86 dims** (54 numeric +
32 one-hot) versus 78 at the 19-city scale - the extra 8 dimensions are the
climate types the reduced model never saw.

---

## 3d. Three more defects found by running the code

**4. `paths.py` mangled every HDFS path.** Its join was
`"/".join(...).replace(":/", ":///", 1)`, which assumes `AQ_LAKE` has no
authority. Given `hdfs://namenode:9000/user/hadoop` - which is exactly what
`docker-compose.spark.yml` supplies - it rewrote the scheme and produced
`hdfs:////namenode:9000/user/hadoop/features`. Four slashes; Spark reads that as
an empty authority, so **every HDFS-mode Python run would have failed to find
its own data**. Fixed by splitting the scheme off before joining, verified
against both the authority and no-authority forms.

**5. Small-cluster write fragility.** The first full-scale Phase 4 computed
everything correctly then died writing 19.7 GB: `Failed to replace a bad
datanode on the existing pipeline`. DataNodes went unresponsive under host
memory pressure and, with 4 nodes at replication 3, there was no spare to swap
in. Fixed by tuning for the cluster's real size - driver 7g->5g, `local[4]`->
`local[3]`, shuffle 200->120, **replication 2** for this derived layer (matching
the precedent already set in `06_upload_to_hdfs.py`), `replace-datanode-on-failure
policy=NEVER`, and 180 s socket timeouts. Re-ran clean.

  > Worth stating in the report: replication 3 is right for the RAW layer, where
  > fault tolerance is being demonstrated. On a 4-node cluster under memory
  > pressure it makes large derived writes fragile, and derived layers are
  > regenerable anyway.

**6. `numpy` missing in the Spark image.** PySpark's `ml` module imports numpy;
`apache/spark:3.5.6` does not ship it, so training aborted at import. Installed
in-container.

### Disk: the documented C: hazard, observed
Spark scratch is a Docker *named volume*, which lives in the WSL2 vhdx on **C:**
- `docker-compose.spark.yml` records an earlier incident where 40+ GB of spill
filled C: and stopped the daemon. Measured during this Phase 4 run: scratch grew
to **65 GB**, C: fell 111 -> 68 GB. A guard was run alongside the job to kill it
if C: dropped below 30 GB. It was not needed - spill plateaued and then released
- but the margin was real. Reclaim with `docker volume rm hadoop_spark_scratch`;
the vhdx itself only shrinks on a manual compact.

---

## 3e. Track B complete + Hive serving layer (6 Sep 2026)

### Full-scale GBT - the headline result

300 trees, 241 cities, ~5h50m, **no StackOverflow** (the previous full-scale
attempt died at 3h50m with exactly that).

| REAL ROWS ONLY (n=2,074,569) - **quote this one** | R2 | RMSE | MAE |
|---|---|---|---|
| persistence baseline | 0.8587 | 24.831 | 9.937 |
| **GBT model** | **0.8910** | **21.806** | **8.926** |
| | | **-12.18%** | |

**PASS - beats persistence by 0.0323 R2.**
All rows (n=18,671,121): R2 0.8884 vs 0.8563, -11.85% RMSE.

Versus Track A (19 cities, 120 trees): RMSE reduction went 5.67% -> **12.18%**,
test set 871K -> **18.7M rows**. The 12.18% finally matches the ~11.3% the
original docs claimed from an sklearn reproduction - but this is a real
distributed Spark GBT on the full dataset, scored on an unsampled test window.

Honest caveat: training used a **seeded 10M-row sample** of the 74.5M-row
training window (RAM limit on a 15.7 GB host). **Evaluation was not sampled** -
all 18,671,121 test rows were scored, so the metric stands.

Model saved to `hdfs:///user/hadoop/models/gbt_pm25_forecaster`
(`maxIter:300, maxDepth:6, stepSize:0.08`, 1.8 MB - replacing the 761 KB
120-tree model, so the live alerting path now covers all 241 cities).

Worst cities by RMSE: Kochi 100.72, Pune 98.41, Byrnihat 78.70 - the same
cities the CPCB-vs-CAMS cross-validation flagged as poorly correlated.

### Phase 9 - Hive serving layer

3 EXTERNAL tables + 3 views registered; all 6 demo queries return real results.

**Q6 is the one to show.** Delhi PM2.5 by month, real measurements only:

| Jan | Apr | Jul | Aug | Nov | Dec |
|---|---|---|---|---|---|
| 180.5 | 86.8 | 44.0 | **38.8** | **213.6** | 199.4 |

A **5.5x swing** between the August monsoon low and the November
stubble-burning peak - the concrete argument for why 13 years of history is
required and a 7-day live window cannot substitute.

Q5 states imputation honestly in SQL rather than in a footnote: Delhi 33.6%
imputed, Pune 53.6%, Hyderabad 19.0%.

### Defect 7 - a Hive DDL that returned plausible wrong answers

`stream_alerts` was first declared with a column called `timestamp`. No such
column exists - `AirQualityStream.scala` writes `observed_at`, `forecast_for`
and `generated_at`. Hive happily created the table and returned **NULL for
every time value while counts and AQI figures looked perfectly correct**. A
silent wrong answer that looks right is worse than an error. Fixed by
declaring the schema verified against `printSchema()` on the actual Parquet,
not against what the DDL author assumed. Re-verified: timestamps populate, and
`aqi_dominant_pollutant` now shows Jaisalmer/Hisar driven by **pm10** (desert
dust), Chandigarh/Ambala by **pm25**, Bathinda by **o3**.

---

## 3f. Phase 10 - dashboard (13 Sep 2026)

`dashboard/dashboard.html` - a single self-contained page, published at
https://claude.ai/code/artifact/de216fdd-ee03-4188-8f0d-9c6ffa738734 and also
openable directly from disk.

**Architecture is the production shape, not a demo shortcut.** The page never
queries 154M rows. `export_dashboard_data.py` runs inside the Spark container
against the Hive serving layer and materialises one JSON document of
pre-aggregated results; `build_dashboard.py` embeds that into the page.
Inlining rather than `fetch()` is deliberate: a page opened from `file://`
cannot fetch a sibling JSON, so embedding is what makes one artifact work
locally, hosted, and as a published artifact alike.

**What it shows, all from real tables:** latest AQI for 230 cities on an India
map (colour = CPCB band, size = PM2.5); the 15 cities warned most; alerts per
forecast hour; dominant pollutant; severity mix; the top-20 alert messages
verbatim; persistence-vs-GBT RMSE with R2; Delhi's 12-month seasonal cycle;
rows by source on a log axis; the CPCB-vs-CAMS correlation; measured-vs-imputed
PM2.5 for the 10 largest cities; and the executed pipeline.

**A finding the dashboard surfaced.** Of the 1,130 alerts in the live window,
**922 (82%) are driven by ozone**, not particulates - a September
photochemical-smog signal. That is visible only because the alert engine
records `aqi_dominant_pollutant`, and it is the kind of thing a public warning
should say ("avoid midday exertion") rather than a generic "air is bad".

**Design choices.** Status colours are the six official CPCB National AQI
bands, kept separate from the page's accent so semantic colour never doubles
as decoration. Numbers are set in a tabular monospace. Light and dark themes
are both defined at the token level. Plotly 2.35.2 is loaded from cdnjs for
the geo map; everything else is plain HTML.

**Wired into operations.** `run_daily_live_cycle.py` gained a fifth step,
`dashboard`, which waits 90 s for the stream to score the day's file, re-runs
the export, and rebuilds the page - so a scheduled `--all` run refreshes the
dashboard automatically.

**Verification caveat, stated honestly.** The page was checked in the local
preview pane, where every non-chart element rendered correctly; the chart
panels were empty there because the pane serves the file as a `data:` URL,
which blocks the Plotly CDN (`ReferenceError: Plotly is not defined`). That
restriction does not apply on the artifact's real origin, where cdnjs is
permitted - but the live render was not visually confirmed from this session.
Open the artifact link to confirm.

---

## 4. State of the pipeline

| Phase | State |
|---|---|
| Phase 3 — clean/impute | ✅ Full scale, 10.0 GB in HDFS |
| Phase 4 — features | ⚠️ Only reduced scale survives (**4,349,178 rows, 19 cities**); full-scale output was lost |
| Phase 5/6 — train/evaluate | ✅ **Full scale** — 300 trees, 241 cities. Real-rows **R² 0.8910 vs persistence 0.8587 — PASS**, 12.18% RMSE reduction on 18.7M unsampled test rows |
| Phase 7/8 — streaming/alerting | ✅ **Executed 6 Sep 2026** (see §3b). ⚠️ consumes the structured 32-col schema, not raw CAMS JSON — see `ARCHITECTURE.md` §3 |
| Phase 9 — Hive serving | ✅ 3 external tables + 3 views, 6 demo queries verified |
| Phase 10 — dashboard | ✅ built, published, wired into the daily cycle (see §3f) |

Against the 5 V's: **Volume, Variety, Veracity, Velocity** are all now
demonstrated — Velocity as of the 6 Sep streaming run. **Value** is partial: a
real model exists and beats persistence, but on 19 cities rather than 241.
Track B (full-scale Phase 4 + 300 trees) closes it.

See `ARCHITECTURE.md` for how the three layers combine, the live-alerting gap
(26 of 54 model features are absent from raw CAMS JSON), and the remaining
work in priority order.

## 3g. October 2026 live refresh (15 Oct 2026)
- Fetched CAMS + weather for 1-15 Oct 2026 (360 h x 230 cities, LIVE_DAYS=14), enriched on YARN: 82,800 rows, 0 nulls on model-critical columns.
- September stream outputs archived in HDFS under stream/archive_sep2026 (alerts, predictions, history, checkpoint, input) so the dashboard shows October only.
- AirQualityStream scored all 82,800 rows in one batch (57.8 s, local[2]): 27,543 warnings, 221 cities. Logs: docs/run_logs/october_*.log.
- First batch has no history table, so the earliest hours per city use a cold start.
- Dashboard re-exported from Hive and rebuilt (AirWatch_India.html). Alert delivery: scripts/send_alerts.py (dry run), website "Alert me" panel.
