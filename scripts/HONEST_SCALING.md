# Expanding Your Own Dataset to 20+ GB — Honestly

**Decision: expand your existing CPCB data. No external dataset.**

---

## 1. First, a correction that works in your favour

Your `Comprehensive Dataset Report.docx` states the master dataset held **1,429,563 rows**. A full
scan of all 48,646,989 rows (821 s, `_audit/fullscan.py`) shows that is wrong:

| Measured | Value |
|---|---|
| Total rows | 48,646,989 |
| **Rows tagged `original` (genuinely real)** | **16,252,931 (33.41%)** |
| Rows tagged `synthetic_expanded` | 32,394,058 (66.59%) |
| Distinct stations | 453 |
| Duplicate `(station_id, from_date)` pairs | **15** — in 48.6 M rows |
| Out-of-order timestamps within a station | 459,956 |

**You have 16.25 million real hourly measurements, not 1.43 million — 11× more real data than your
own report claims.** That is a much stronger base than I assumed earlier, and it means you need a
far smaller synthetic multiple to reach 20 GB.

It also means the dataset is *not* mass-duplicated: 15 duplicate pairs out of 48.6 M rows is
effectively zero. The old rig's problem was never duplication — it was *how* it generated the
non-duplicate rows.

---

## 2. What was actually wrong with the old expansion

| Defect | Evidence |
|---|---|
| Noise applied to every numeric column, including flags and IDs | `is_rush_hour`: **24,725** distinct values instead of 2. `variation_id`: **29,918** instead of 3 |
| No physical bounds check | humidity **104.999%**, traffic index **110.2** on a 0–100 scale |
| **Synthetic rows easier to predict than real ones** | persistence R² **0.856** synthetic vs **0.733** real — a gap of **0.123** |
| Gaps were filled | synthetic series denser than reality, which is what made them easy |

The third row is the one that would sink you in a viva. With 66.6% of the file synthetic and the
synthetic half easier, every headline metric is inflated. "What happens if you evaluate only on the
real rows?" is a fair question, and the answer collapses the result.

---

## 3. The new rig — and how it is different

`00c_expand_dataset.py`. Five design rules, each fixing one measured defect:

1. **Only continuous physical measurements are perturbed.** Flags, IDs, categories and timestamps
   are copied or recomputed — never sampled. The corrupted `is_rush_hour` / `is_weekend` /
   humidity / traffic values are *repaired* on the way out.
2. **AR(1) perturbation in continuous time, not i.i.d. noise.**
   `eps(t) = phi^dt · eps(t-1) + sqrt(1-phi^(2dt)) · sigma · z`, with `phi` estimated from *each
   station's own* lag-1 autocorrelation and `dt` the real gap in hours. Because the noise carries
   the same decay as the data, the autocorrelation survives. **This is the fix that makes synthetic
   rows exactly as hard as real ones.**
3. **Physical clamps on every perturbed value.** No more 105% humidity.
4. **Missingness is preserved exactly.** If the real row had no PM2.5, neither does its synthetic
   counterpart. Densifying the series is the subtlest way to fake easy data — and it is what the old
   rig did.
5. **Synthetic series are separate stations** (`AP001~S03`), never interleaved with real rows under
   the same ID. So the T+1 window never mixes real and synthetic, and "evaluate on real only" is
   `WHERE data_source='real'`.

### Why two passes
Your file is **not sorted by station**. A 900k-row slice holds 12 distinct stations but **9,071
station-runs** — rows round-robin between stations. A single streaming pass that flushed on "station
changed" would chop each station into ~100-row fragments, each getting independent AR(1) state,
destroying the very continuity the generator exists to preserve. So:

- **Pass 1** — stream the source, repair each real row, append to a per-station spill file. Yields
  the *exact* real row count, so the scale factor is computed, not estimated.
- **Pass 2** — each spill file is one complete series. Sort by timestamp, emit real rows plus N
  synthetic siblings. One station per worker, so memory stays flat.

---

## 4. Validation — this is the part that makes it defensible

`00d_validate_expansion.py` compares synthetic against real on the five properties a generator can
silently get wrong. **Measured on a 12-station / 1.26 M-row test build:**

| Check | Real | Synthetic | Δ | |
|---|---|---|---|---|
| **Persistence R²** | 0.6228 | 0.6199 | **0.0029** | PASS |
| ACF lag 1h | 0.9290 | 0.9282 | 0.0008 | PASS |
| ACF lag 2h | 0.8637 | 0.8626 | 0.0011 | PASS |
| ACF lag 3h | 0.8207 | 0.8192 | 0.0015 | PASS |
| ACF lag 6h | 0.7449 | 0.7425 | 0.0024 | PASS |
| pm25 p50 | 28.25 | 28.21 | 0.2% | PASS |
| pm25 p95 | 92.50 | 93.52 | 1.1% | PASS |
| **Missingness** | 22.44% | 22.44% | **0.00 pp** | PASS |
| corr(pm25, pm10) | 0.8734 | 0.8647 | 0.0087 | PASS |
| corr(pm25, no2) | 0.3791 | 0.3762 | 0.0029 | PASS |

**Old rig persistence gap: 0.123. New rig: 0.0029 — 42× better.** Missingness matches to the
decimal because gaps are copied rather than filled.

Run the validator every single time. Treat a FAIL as blocking.

---

## 5. The production build — BUILT AND VALIDATED

Actually built on 2026-08-12 from your file. Not projections — measured output:

| | |
|---|---|
| Output directory | `E:\airquality_expanded` (23 × `part-*.csv`, max 1.27 GB each) |
| **Output size** | **27.48 GB** |
| **Total rows** | **146,276,379** |
| Real rows | 16,252,931 (11.1%) |
| Synthetic rows | 130,023,448 |
| Stations | 453 real + 3,624 synthetic = **4,077** |
| Scale factor | **9×** (8 synthetic siblings per real station) |
| Columns | 32, pruned and repaired |
| Build time | **1,038 s** (17 min, pass 1 = 690 s, pass 2 = 292 s) |

Final size overshot the 22 GB target because perturbed values carry more decimal digits than the
originals (many real readings are round numbers like `17`, their siblings are `16.9832`). Overshoot
is harmless — the requirement is a floor.

**Paired validation on the real output — 22 parent stations, 6.7 M rows, ALL PASS:**

| Check | Real | Synthetic | Δ |
|---|---|---|---|
| Persistence R² | 0.8955 | 0.8889 | **0.0065** |
| ACF lag 1h | 0.9344 | 0.9322 | 0.0022 |
| ACF lag 6h | 0.7452 | 0.7420 | 0.0032 |
| pm25 p50 | 46.74 | 46.67 | 0.1% |
| pm25 p95 | 203.75 | 205.19 | 0.7% |
| **Missingness** | 27.46% | 27.46% | **0.00 pp** |
| corr(pm25, pm10) | 0.8715 | 0.8650 | 0.0065 |

### A validator bug worth knowing about
The first validation run **FAILED** (persistence Δ 0.0645, missingness Δ 5.02 pp). The generator was
fine — the validator was wrong. It read files sequentially and truncated each group at a fixed row
count, but every parent emits 8× more synthetic than real, so the synthetic sample walked through
far fewer stations than the real sample. It was comparing *different stations*, and station
composition dominates all of these statistics.

The tell was check 4: the generator copies nulls by construction and *cannot* alter missingness, yet
a gap was reported. An impossible result pointed at the measurement, not the data. Fixed by pairing
on `source_station` — select parent stations, take **all** their rows, real and synthetic together.

Keep this in mind if you ever re-run it: **compare like with like, or the numbers are noise.**

Be upfront about that 12.5%. The claim is not "23 GB of real data" — it is:

> *"A 23 GB benchmark at scale factor 8, generated from 16.25 M real CPCB measurements by a
> disclosed AR(1) model that is validated to reproduce the real data's autocorrelation,
> distribution, sparsity and inter-pollutant correlations. All model evaluation is on real rows
> only."*

That is a legitimate, standard methodology — the same idea as a TPC-H scale factor. The systems
claims (throughput, block distribution, shuffle, spill) rest on the full 23 GB; the scientific
claims rest on the real subset. Two claims, cleanly separated by the `data_source` column.

**Want a higher real fraction?** Keep more of the genuinely-populated real columns in the raw layer
(benzene, toluene, xylene, `no`, `nox`, the raw measured `temperature`/`humidity`/`wind_speed`,
`ambient_temperature`). Those carry real data and were dropped only because the *model* does not
need them — but a raw layer is entitled to keep them. More bytes per real row means fewer synthetic
rows to reach 22 GB.

---

## 6. Run order

Steps 1 and 2 are **already done** — `E:\airquality_expanded` exists and passed validation. You only
need step 3.

```bash
hdfs dfs -mkdir -p /user/hadoop/lakehouse/raw
hdfs dfs -put E:\airquality_expanded\part-*.csv /user/hadoop/lakehouse/raw/
```

To rebuild from scratch, or at a different size:

```bash
python 00c_expand_dataset.py --src "E:\Big Data jagan\final_air_quality_dataset_22gb_balanced.csv" --out E:\airquality_expanded --target-gb 22
python 00d_validate_expansion.py --dir E:\airquality_expanded --stations 22
```

Useful flags: `--scale N` to force a scale factor, `--real-only` to emit just the 2.9 GB repaired
real dataset, `--sigma` to tune perturbation strength (raise it and persistence R² drops below real;
lower it and synthetic becomes too easy — 0.08 is validated).

Downstream, the output is already pruned and repaired, so `01_clean_select.py` is no longer needed —
point `02_feature_extraction.py` at this data. The label rule still holds: **build
`target_pm25_next_hour` only from measured PM2.5**, and split chronologically.

---

## 7. Alternative, if your mam ever wants zero synthetic rows

US EPA AQS publishes pre-generated hourly files — I verified all 110 URLs return HTTP 200 and total
**4.12 GB zipped → ~26.8 GB unzipped** for 2015–2024, covering the same pollutants plus *real*
co-located meteorology. `00_fetch_real_data.py` downloads it. That path is 100% real with no
generative model at all, at the cost of switching from India to US data. Keeping it here as a
fallback, not the recommendation — you asked to expand your own data, and the validated rig does
that.
