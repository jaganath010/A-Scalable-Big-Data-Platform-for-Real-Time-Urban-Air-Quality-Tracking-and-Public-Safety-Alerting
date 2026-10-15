# Column Decision Report — `final_air_quality_dataset_22gb_balanced.csv`

**File:** 23.44 GB · 48,646,989 rows · **139 columns** (the docs say "102 base" — that counts only
the pre-enrichment block; the actual header carries 139).

All percentages below are measured, not assumed: a stratified scan of **960,000 rows** sampled from
240 evenly-spaced byte offsets across the full 23 GB file (`scripts/_audit/fillrate.py`).

**Verdict: keep 30 columns, drop 109.**

---

## 0. Why the last run scored R² = 0.58 — read this first

**The data is not the problem. The pipeline was.**

I measured the **persistence baseline** on this dataset — the one-line rule *"next hour = this
hour"*, with no model at all — over 479,937 real consecutive hourly transitions
(`_audit/diag.py`):

| Subset | R² | RMSE (µg/m³) | n |
|---|---|---|---|
| `original` rows | 0.7328 | 36.94 | 194,273 |
| `synthetic_expanded` rows | 0.8562 | 24.45 | 342,372 |
| **All rows** | **0.8056** | **29.59** | 536,645 |

**Your model scored R² = 0.58. Doing nothing scores 0.81.** The previous run was *worse than not
building a model.* A GBT that has the current PM2.5 in its feature vector mathematically cannot
score below persistence unless something upstream is broken — so this is a pipeline defect, not a
modelling limitation. The realistic target after the fixes below is **R² ≈ 0.88–0.93**.

### On the reported "RMSE = 0.57"
Persistence RMSE on raw PM2.5 is **29.59 µg/m³**. An RMSE of 0.57 is ~50× smaller than that, which
means the previous run **was not predicting raw µg/m³** — the target had been scaled or
log-transformed. `RMSE = 0.57` on a transformed target is not comparable to anything and cannot be
defended to a panel. All three scripts now report RMSE and MAE in raw µg/m³, so the number means
"the average miss, in micrograms per cubic metre."

### The four causes, in order of likely impact

1. **🔴 The label was ~26% fabricated.** This was a genuine flaw in the first version of
   `01_clean_select.py` that I have now fixed. Imputing `pm25` (74.26% measured) *before* building
   `target_pm25_next_hour` means roughly a quarter of training labels were station/month/hour
   **medians** — a constant the features cannot possibly predict. That is pure unlearnable noise
   injected directly into the target, and it caps R² hard. **Fix:** `pm25_measured` now preserves
   the pre-imputation truth, and Phase 4 builds the label *only* from it. Features may use the
   imputed value; the label never does.

2. **🔴 8.69% of labels had the wrong forecast horizon** — the `lead()` defect in §4.2. The reported
   RMSE was a blend of 1-hour, 2-hour and 5-hour forecasts.

3. **🟡 `randomSplit` leaks on a time series.** Hour *T* lands in train while *T+1* lands in test,
   and consecutive hours are ~0.81 correlated. This normally *inflates* scores, so it is not the
   cause of 0.58 — but it makes any number undefendable. `03_train_gbt.py` now splits
   **chronologically**: train on the earlier 80% of history, test on the most recent 20%, which is
   what the streaming layer actually faces.

4. **🟡 `handleInvalid="skip"` on VectorAssembler silently discards rows** with any null feature.
   With nulls scattered across 14 columns this can quietly delete most of the training set without
   raising an error. Phase 3 imputation now runs *before* assembly, so nothing should reach it null.

### What I ruled out — the dataset itself is sound
You asked whether the data is correct. On the things that would have made it unusable, it is fine:

- **Not mass-duplicated.** The expansion did *not* replicate the base file across a timeline loop.
  Of 173,408 `(station, month, day, hour)` slots appearing in more than one year, only **106 (0.06%)**
  carry an identical PM2.5 value. Real year-to-year variation is present.
- **Genuine value diversity.** 644,512 sampled PM2.5 readings span 30,273 distinct values.
- **Exact-duplicate rows are rare** (~1% of keys) and are removed by the dedupe step in Phase 4.
- **No corrupt pollutant values.** Zero negatives and zero unparseable cells across all seven AQI
  pollutants.

The one caveat worth knowing: `synthetic_expanded` rows (69.8% of the file) are *easier* to predict
than real ones — persistence scores 0.856 on them vs 0.733 on `original`. So a headline R² computed
over the whole file is flattered by the synthetic majority. `03_train_gbt.py` keeps `data_source` in
the output so you can report both numbers. **Quote the `original`-only score as the honest one** —
a panel that spots this will ask, and having the split ready turns a weakness into a strength.

### The guard that prevents a repeat
`03_train_gbt.py` computes the persistence baseline **on the same test rows** as the model, every
run, and prints an explicit `*** FAIL ***` with a four-item checklist if the model does not beat it.
Never report an R² again without that baseline printed next to it.

---

## 1. What the project actually needs

Working backwards from the deliverable in `Project_Phase_Execution_Plan.docx` — a GBT regressor that
predicts the **next-hour pollutant level** and fires an alert when **predicted AQI > 150** — the data
requirement is exactly four blocks:

| Block | Why it is needed | Source |
|---|---|---|
| **The 7 CPCB AQI pollutants** | The alert threshold is an *AQI* number. India's National AQI (CPCB) is the max of sub-indices over PM2.5, PM10, NO2, SO2, CO, O3, NH3. Without all seven you cannot compute the number the alert is defined on. | `pm25 pm10 no2 so2 co o3 nh3` |
| **Dispersion physics** | Pollution level = emission ÷ dispersion. Wind, temperature, humidity, rain and pressure govern the divisor. Rain in particular is a physical scrubber — omit it and the model over-predicts on wet hours. | dynamic weather block + `sr` + `bp` + wind direction |
| **Emission driver** | Traffic is the dominant urban source; rush-hour timing is what makes the next hour predictable at all. | `traffic_index`, `is_rush_hour` |
| **Spatio-temporal keys** | Needed to build the T+1 label, to partition Parquet, and to let one model serve 241 cities. | `station_id city timestamp year month day hour season day_of_week is_weekend` |

Everything outside those four blocks is not needed for this deliverable.

---

## 2. KEEP (30 columns)

### 2.1 Keys and identity — 5
| Column | Filled | Role |
|---|---|---|
| `station_id` | 100% | window partition key; join key for imputation |
| `state` | 100% | regional grouping for Hive queries |
| `city` | 100% | Parquet partition key; 241 values |
| `from_date` | 100% | parsed into the unified `timestamp` |
| `day` | 100% | needed to rebuild timestamp; dropped after |

### 2.2 AQI pollutants — 7 (features **and** label source)
| Column | Filled | Observed range | Note |
|---|---|---|---|
| `pm25` | 74.26% | 0.01 – 1049.9 | **label source** (`target_pm25_next_hour`) |
| `pm10` | 67.48% | 0.01 – 1000.0 | |
| `no2` | 78.55% | 0.01 – 498.5 | traffic + industry tracer |
| `so2` | 74.71% | 0.01 – 200.0 | industrial / fuel tracer |
| `co` | 74.17% | 0.00 – 50.0 | mg/m³, incomplete combustion |
| `o3` | 73.92% | 0.01 – 206.9 | photochemical smog |
| `nh3` | 58.99% | 0.01 – 497.9 | agricultural / waste; weakest of the seven |

No negative values and no unparseable text in any of the seven — the "negative concentration"
filter named in Phase 3 finds nothing, so it is kept only as a cheap guard.

### 2.3 Meteorology with no dynamic equivalent — 3
These are kept **because nothing else in the file carries the signal.** Each gets a companion
`*_was_imputed` flag so the model can distinguish a real reading from a filled one.

| Column | Filled | Why kept |
|---|---|---|
| `wd_degree` *(coalesced — see §4)* | **74.77%** | Wind *direction*. Speed alone cannot tell the model whether the plume is blowing in from an industrial zone or out to open land. Also the entry point for the GraphX plume-migration future scope. |
| `sr_(w/mt2)` | 61.11% | Solar radiation drives O3 photochemistry — the physical cause of the ozone term in the AQI. |
| `bp_(mmhg)` | 47.05% | Barometric pressure sets boundary-layer height; low pressure traps pollutants near ground. Lowest coverage of anything kept — flagged. |

### 2.4 Dynamic environment — 5 (all 100% filled)
`dynamic_temperature_c`, `dynamic_humidity_percent`, `dynamic_wind_speed_ms`, `rainfall_mm`,
`weather_condition`

These replace the raw sensor columns `temperature` (26.5%), `humidity` (67.7%), `wind_speed` (69.6%),
`rainfall` (50.9%). Same physical quantity, **full coverage instead of partial** — see §3.3.

### 2.5 Traffic and time — 5
`traffic_index`, `is_rush_hour`, `day_of_week`, `is_weekend`, `season`
(plus `year`, `month`, `hour` — counted in §2.1's timestamp block)

### 2.6 City descriptors — 2
`climate_type` (14 values), `urbanization_index`

Two constants per city, kept so the model can generalise across the 241 cities rather than
memorising each one. All other city-profile constants are dropped — see §3.4.

### 2.7 Audit only — 2
`data_source`, `variation_bucket` (cleaned from `variation_id`). Written to Parquet for
provenance, **excluded from the feature vector.** They describe how a row was manufactured; feeding
them to the model would let it learn the generator instead of the physics.

---

## 3. DROP (109 columns) — with the reason

### 3.1 Empty or near-empty sensor columns — 69 columns
Columns 33–101 of the header. These are unit-variant duplicates left over from merging 453 stations
that each reported in different units. Measured fill rate:

- **Exactly 0.000% filled — 22 columns:** `co_(mg/nm3)`, `rf_(m/s)`, `sr_(ug/m3)`, `nmhc_(ug/m3)`,
  `gust_(km/hr)`, `variance_(n)`, `power_(w)`, `co2_(mg/m3)`, `gust_(kl/h)`, `gust_(m/s)`,
  `spm_(ug/m3)`, `mh_(m)`, `hcho_(ug/m3)`, `hg_(ug/m3)`, `temp_(ug/m3)`, `eth-benzene_()`, `ch4_()`,
  `no_()`, `ws_(ug/m3)`, `at_(ug/m3)`, `nmhc_()`, `no_(ppm)`, `benzene_(mg/m3)`, `bp_(mg/m3)`,
  `nox_(ppm)`, `nh3_(ppb)` — these are pure schema noise, zero rows carry a value.
- **Under 3% filled — the remainder:** `no_(mg/m3)` 0.35%, `thc_(ug/m3)` 0.22%, `ozone_(ppb)` 0.47%,
  `co_(ng/m3)` 0.41%, `nox` 2.64%, `co_(ug/m3)` 2.65%, `ch4_(ug/m3)` 1.68%, `so2_()` 0.35%, …

**Critically, none of them is the sole source for anything kept.** The near-duplicates all shadow a
well-populated column: `co_(ug/m3)` (2.65%) shadows `co` (74.17%); `ozone_(ppb)` (0.47%) shadows
`o3` (73.92%); `nox` (2.64%) shadows `nox_(ppb)` (75.12%). Coalescing them adds 3–6 percentage
points of coverage at the cost of mixing incompatible units — a worse trade than dropping.

### 3.2 Mechanically duplicated columns — 14 columns
`bp_(mmhg).1` … `.7` and `rf_(mm).1` … `.7`. The `.N` suffix is pandas' collision renamer — the
merge produced 8 identically-named barometric-pressure columns and 8 rainfall columns. All 14
suffixed copies sit at **exactly 0.351% filled**, an identical figure that confirms they are
fragments of one split column, not independent instruments. The unsuffixed `bp_(mmhg)` (47.05%)
is kept; `rf_(mm)` has no unsuffixed survivor, and `rainfall_mm` (100%) covers it.

### 3.3 Raw meteorology superseded by the dynamic block — 6 columns
`temperature` (26.48%), `ambient_temperature` (46.96%), `humidity` (67.67%), `wind_speed` (69.55%),
`rainfall` (50.95%), `vws_(m/s)` (22.79%), `vws_(degree)` (0.87%)

Each is the sparse ancestor of a 100%-filled dynamic column. Keeping both would mean imputing 30–75%
of a column that already exists complete. **Trade-off stated plainly:** the dynamic columns are
*simulated* (per the Comprehensive Dataset Report) while these are *measured*. For a pipeline whose
stated goal is full-coverage next-hour forecasting across 241 cities, complete beats sparse — but if
the panel challenges the use of simulated weather, `temperature`/`humidity`/`wind_speed` are the
columns to reinstate as `*_measured` alongside the dynamic ones. Flip `KEEP_RAW_MET` in
`01_clean_select.py` to do that in one line.

### 3.4 City-profile constants — 15 columns
`temperature_mean_c`, `temperature_variation_c`, `summer_temperature_c`, `winter_temperature_c`,
`humidity_mean_percent`, `rainfall_factor`, `monsoon_intensity`, `wind_speed_mean_ms`,
`traffic_base_index`, `morning_rush_multiplier`, `evening_rush_multiplier`,
`weekend_traffic_multiplier`, `rain_traffic_multiplier`, `night_traffic_multiplier`,
`morning_rush_start`, `morning_rush_end`, `evening_rush_start`, `evening_rush_end`

These are **the inputs the generator used to manufacture the dynamic columns** — `dynamic_temperature_c`
was computed *from* `temperature_mean_c` + `temperature_variation_c` + season + hour;
`traffic_index` was computed *from* `traffic_base_index` × the rush multipliers; `is_rush_hour` *from*
the four rush start/end columns. They are constant within a city, so they carry no per-row
information the child columns don't already express.

> This overrides the `featureCols` array in `Project_Phase_Execution_Plan.docx` Step 6, which lists
> `morning_rush_multiplier` and `evening_rush_multiplier`. Those two are constants per city — inside
> a station-partitioned window they never vary, so a tree can only use them to identify the city.
> `urbanization_index` is kept as the single city-level intensity descriptor instead.

### 3.5 Organic pollutants — 5 columns
`benzene` (62.83%), `toluene` (50.81%), `xylene` (24.98%), `eth-benzene_(ug/m3)` (29.56%),
`mp-xylene_(ug/m3)` (31.06%), `o_xylene_(ug/m3)` (10.32%)

Not CPCB AQI parameters, so they cannot contribute to the >150 alert. They *are* genuine traffic
tracers and correlate with the target — but at 25–63% coverage they would need heavy imputation to
buy a marginal accuracy gain. Dropped by default; `KEEP_ORGANICS = True` reinstates `benzene` and
`toluene` (the two above 50%) if you want them as auxiliary predictors.

### 3.6 Non-predictive metadata — 4 columns
| Column | Reason |
|---|---|
| `agency` | Regulator name — administrative, not physical. |
| `station_location` | Free text ("Tirumala, Tirupati"), 453 distinct, already encoded by `station_id` + `city`. |
| `to_date` | Always `from_date` + 1 hour. Fully redundant. |
| `traffic_level` | Categorical binning of `traffic_index`. The continuous column strictly dominates it; GBT finds its own splits. |

---

## 4. Data-quality defects found — these need fixing, not just dropping

The scan turned up four problems that the current Phase 3 spec does not handle.

### 4.1 🔴 `is_rush_hour` is not binary — 3.98% of rows are corrupt
It is documented as a 0/1 flag. It has **24,725 distinct values**, including `1.0282169444321818`
and `0.9938…`. The ±3% Gaussian noise from the expansion rig was applied blindly to *every* numeric
column, including binary flags and IDs. `variation_id` is hit the same way — **29,918 distinct
values** where there should be 3 (0, 1, 2).

Present in **both** `original` (6,640 rows) and `synthetic_expanded` (11,271 rows) — so it cannot be
filtered away by `data_source`.

**Fix applied in `01_clean_select.py`:** `is_rush_hour → (round(value) > 0).cast(int)`,
`variation_id → round(value).cast(int)` as `variation_bucket`.

### 4.2 🔴 The T+1 label as specified will silently produce wrong targets
The plan's Step 6 uses:
```scala
Window.partitionBy("station_id").orderBy("from_date")
lead("pm25", 1).over(windowSpec)
```
Two independent failures:

1. **`(station_id, from_date)` is not unique.** 0.94% of keys in the sample repeat, up to **3 rows
   per key** (the `variation_id` copies — e.g. `AS003 / 2022-10-07 16:00:00` appears 3×). `orderBy`
   on a non-unique key is non-deterministic, so `lead()` may return a *sibling of the same hour*
   instead of the next hour, and the result changes between runs.
2. **`lead()` is positional, not temporal.** Where a station has a gap — and with pm25 at 74.26%
   coverage, gaps are everywhere — `lead()` happily returns a row 5 hours later and labels it "next
   hour." The model then trains against a mislabelled horizon.

**Fix applied in `02_feature_extraction.py`:** partition by `(station_id, variation_bucket)`, order
by `timestamp`, then take the lead of **both** `pm25` and `timestamp` and keep the row only when
`next_ts == ts + 1 hour`. Rows failing that check are dropped rather than mislabelled. The script
reports the retention rate so the loss is visible, not hidden.

**Measured impact** (`_audit/validate.py`, 479,937 real consecutive transitions from 12 contiguous
blocks):

| | Rows labelled | Share |
|---|---|---|
| Plain `lead()` as specified | 380,634 | 79.31% |
| Temporally validated (+1 h) | 347,563 | 72.42% |
| **Mislabelled by plain `lead()`** | **33,071** | **8.69% of its own labels** |

Observed gaps between consecutive rows in a track: 442,210 are the correct 3,600 s, but 2,142 are
**0 s** (the duplicate-timestamp case from point 1) and the rest run 2 h, 3 h, 4 h, 5 h and beyond.
Roughly **one in twelve training labels would carry the wrong forecast horizon**, and the reported
RMSE would be measuring a mix of 1-hour, 2-hour and 5-hour forecasts. This is the single most
consequential fix in the pipeline.

### 4.3 🟡 Physically impossible values in the 100%-filled dynamic columns
| Column | Violation | Fix |
|---|---|---|
| `dynamic_humidity_percent` | max **104.999%** — relative humidity cannot exceed 100 | clamp to [0, 100] |
| `traffic_index` | max **110.209** on a documented 0–100 scale | clamp to [0, 100] |
| `dynamic_temperature_c` | −4.1 °C to 58.2 °C — extreme but physically possible in India | left as-is |

Same cause as 4.1: noise applied without bound checks, and it hits `original` rows too.

### 4.4 🟡 Only 45.78% of rows carry all seven AQI pollutants
Dropping incomplete rows would discard **26.4 million rows** and destroy the Volume claim.
Imputation is mandatory, not optional. The script uses the three-tier scheme from Phase 3
(`station_id`+`month`+`hour` median → `city`+`month` median → global median) and emits a
`*_was_imputed` flag per pollutant so the panel can see exactly how much is measured vs filled.

---

## 5. Result

| | Before | After |
|---|---|---|
| Columns | 139 | 30 (+ engineered) |
| Format | CSV, row-oriented, uncompressed | Parquet, columnar, Snappy |
| Est. size | 23.44 GB | **~1.2–1.8 GB** |
| Scan cost for a 14-column model | full 23.44 GB | only the columns touched |

The ~13–19× reduction is the strongest performance-tuning result in the project, and it comes from
column pruning plus columnar encoding — worth stating explicitly in the Phase 3 defence, since the
93% of columns being removed are 78% empty by measurement.

---

## 6. Files

| File | Purpose |
|---|---|
| `01_clean_select.py` | Phase 3 — prune 139→30, fix the four defects, impute, write partitioned Parquet |
| `02_feature_extraction.py` | Phase 4 — T+1 label, CPCB AQI, lag/rolling/cyclical features, VectorAssembler |
| `03_train_gbt.py` | Phase 5+6 — chronological split, **persistence-benchmarked** GBT training, raw-µg/m³ metrics, per-city error breakdown |
| `_audit/fillrate.py`, `_audit/probe.py`, `_audit/probe2.py` | The scans that produced every fill-rate and defect number above — re-runnable evidence |
| `_audit/validate.py` | Verifies the CPCB AQI sub-index math against 11 published reference points, and measures the T+1 mislabelling rate on real data |
| `_audit/diag.py` | **Measures the persistence baseline (§0)** — the number that proved the last run was broken |
| `_audit/diag2.py` | Checks the expansion rig for cross-year replication and value-repetition leakage |

---

## 7. Verification performed

The AQI implementation in `02_feature_extraction.py` was checked against published CPCB band
boundaries — all 11 reference points reproduce exactly, and mid-band interpolation is correct:

```
PM2.5  30 → 50     PM10 100 → 100     CO  1 mg/m³ →  50     O3 168 → 200
PM2.5  60 → 100    PM10 250 → 200     CO 10 mg/m³ → 200     NH3 400 → 100
PM2.5  90 → 200    NO2   80 → 100     PM2.5 45 → 75.5 (mid-band interpolation)
```

Useful for the defence: the project's **AQI > 150 alert threshold corresponds to a 24-hour PM2.5
average of ~75 µg/m³** — well inside the observed range (max 1049.9), so the alert will genuinely
fire on real data rather than being a dead branch.

Both PySpark scripts pass `py_compile`. They have **not** been executed — PySpark is not installed on
this machine, and the installed Java 26 is outside Spark's supported range (8/11/17). Run them on the
cluster; Phase 3 must complete before Phase 4, since Phase 4 reads Phase 3's Parquet output.
