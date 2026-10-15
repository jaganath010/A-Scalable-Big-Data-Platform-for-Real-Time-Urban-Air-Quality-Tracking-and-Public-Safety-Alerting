"""
================================================================================
CROSS-VALIDATION - STRUCTURED (CPCB) vs SEMI-STRUCTURED (CAMS) OVERLAP WINDOW
================================================================================
Project : A Scalable Big Data Platform for Real-Time Urban Air Quality Tracking
Course  : 23AID302 - Big Data Analytics

WHAT THIS DOES
  The structured layer runs 2010-01-01 .. 2023-03-31. The semi-structured CAMS
  layer runs 2022-08-01 .. present. They overlap over 2022-08-01 .. 2023-03-31 -
  eight months in which two INDEPENDENT sources describe the same cities over
  the same hours. This is the only window in which the project's own data can
  be checked against an outside reference, so it is the strongest veracity
  evidence available.

  Two comparisons are run:

    real      vs CAMS   Does the project's REAL (CPCB station) data agree with
                        an independent atmospheric reanalysis?
    synthetic vs CAMS   Does the project's SYNTHETIC augmentation behave like
                        reality, or does it drift from it? A generator that
                        tracks CAMS as closely as the real data does is
                        defensible; one that does not is a disclosed weakness.

METHOD, AND WHY
  Join key: (city, timestamp).
    CAMS returns ONE point per city (a city-centroid model cell). The
    structured layer has many stations per city. A 1:1 row join is therefore
    impossible; the structured side is first averaged to a city-hour mean, and
    that mean is compared to the CAMS city-hour value. This is an
    apples-to-apples spatial aggregate, not a station-level match, and results
    should be read that way.

  Only MEASURED values are used from the structured side. A null pm25 in the
  raw layer means "not measured"; those rows are excluded rather than imputed,
  because imputed values are medians and would manufacture agreement.

  Pollutants compared: pm25, pm10, no2, so2, o3 - all reported in ug/m3 by
  BOTH sources.

  CO IS DELIBERATELY EXCLUDED. The structured layer reports CO in mg/m3
  (observed range 0-50) while CAMS reports it in ug/m3 (observed range in the
  hundreds-to-thousands). Comparing them directly would produce a meaningless
  ~1000x disagreement. A converted comparison is printed separately and
  labelled, but it is not part of the headline result.

  NH3 is not compared: CAMS returns null for it across this entire region.

METRICS
  n           matched city-hours
  corr        Pearson correlation (does it track the same ups and downs?)
  bias        mean(structured - CAMS), in ug/m3 (systematic offset)
  mae, rmse   magnitude of disagreement, in ug/m3

  Correlation is the metric that matters most here. Two independent sources -
  one a ground station, one a model reanalysis on a coarse grid - are NOT
  expected to agree in absolute level; a city-centroid model cell smooths away
  the local peak a roadside station sees. Tracking the same temporal pattern
  is the meaningful agreement, and a large constant bias with high correlation
  is an expected, explainable result rather than a failure.

TIMEZONE CHECK
  Both sources are treated as IST. If that assumption were wrong, correlation
  would peak at a non-zero hour offset. The script tests offsets -3..+3 h and
  reports where correlation actually peaks, so the assumption is verified
  rather than asserted.

RUN
    python 04_cross_validate_overlap.py \
        --unified "F:\\...\\airquality_expanded\\unified_merged" \
        --out     "F:\\...\\docs\\cross_validation_results"
================================================================================
"""

import argparse
import os

from pyspark.sql import SparkSession, functions as F, Window

WINDOW_START = "2022-08-01"
WINDOW_END = "2023-04-01"          # exclusive; structured data stops 2023-03-31

# Pollutants reported in ug/m3 by BOTH sources.
SHARED = ["pm25", "pm10", "no2", "so2", "o3"]


def city_hour_agg(df, label):
    """Average the structured layer's many stations down to one value per city-hour."""
    aggs = [F.avg(c).alias(c) for c in SHARED + ["co"]]
    aggs.append(F.count("*").alias("n_station_rows"))
    return df.groupBy("city", "timestamp").agg(*aggs).withColumn("layer", F.lit(label))


def compare(joined, pollutant, label):
    """Correlation / bias / MAE / RMSE for one pollutant, over matched non-null pairs."""
    s, c = f"s_{pollutant}", f"c_{pollutant}"
    d = joined.filter(F.col(s).isNotNull() & F.col(c).isNotNull())
    n = d.count()
    if n == 0:
        return {"layer": label, "pollutant": pollutant, "n": 0}
    stats = d.select(
        F.corr(s, c).alias("corr"),
        F.avg(F.col(s) - F.col(c)).alias("bias"),
        F.avg(F.abs(F.col(s) - F.col(c))).alias("mae"),
        F.sqrt(F.avg(F.pow(F.col(s) - F.col(c), 2))).alias("rmse"),
        F.avg(s).alias("mean_structured"),
        F.avg(c).alias("mean_cams"),
    ).first()
    return {"layer": label, "pollutant": pollutant, "n": n,
            "corr": stats["corr"], "bias": stats["bias"], "mae": stats["mae"],
            "rmse": stats["rmse"], "mean_structured": stats["mean_structured"],
            "mean_cams": stats["mean_cams"]}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--unified", required=True)
    ap.add_argument("--out", default=None, help="Optional directory to write CSV results")
    ap.add_argument("--master", default="local[*]")
    ap.add_argument("--driver-mem", default="6g")
    args = ap.parse_args()

    spark = (SparkSession.builder.appName("cross_validate_overlap")
             .master(args.master)
             .config("spark.driver.memory", args.driver_mem)
             .config("spark.sql.shuffle.partitions", "64")
             .getOrCreate())
    spark.sparkContext.setLogLevel("WARN")

    df = spark.read.parquet(args.unified)
    win = df.filter((F.col("timestamp") >= WINDOW_START) & (F.col("timestamp") < WINDOW_END))

    real = win.filter(F.col("data_source") == "real")
    synth = win.filter(F.col("data_source") == "synthetic")
    cams = win.filter(F.col("data_source") == "cams_history")

    print("=" * 78)
    print("OVERLAP WINDOW:", WINDOW_START, "->", WINDOW_END, "(exclusive)")
    print("=" * 78)
    for name, d in (("real (CPCB)", real), ("synthetic", synth), ("cams_history", cams)):
        print(f"  {name:16} rows={d.count():>12,}  cities={d.select('city').distinct().count()}")

    # ---- sanity: raw magnitudes, so unit mismatches are visible not assumed ----
    print("\n--- mean value by source (unit sanity check) ---")
    print(f"{'pollutant':10} {'real':>12} {'synthetic':>12} {'cams':>12}")
    for p in SHARED + ["co"]:
        r = real.select(F.avg(p)).first()[0]
        s = synth.select(F.avg(p)).first()[0]
        c = cams.select(F.avg(p)).first()[0]
        fmt = lambda x: f"{x:12.2f}" if x is not None else f"{'null':>12}"
        note = "   <-- UNIT MISMATCH (mg/m3 vs ug/m3)" if p == "co" else ""
        print(f"{p:10} {fmt(r)} {fmt(s)} {fmt(c)}{note}")

    # CAMS is already one row per city-hour; structured needs aggregating
    cams_ch = (cams.groupBy("city", "timestamp")
                   .agg(*[F.avg(c).alias(c) for c in SHARED + ["co"]]))
    cams_ren = cams_ch.select("city", "timestamp",
                              *[F.col(c).alias(f"c_{c}") for c in SHARED + ["co"]])

    results = []
    for label, layer in (("real", real), ("synthetic", synth)):
        agg = city_hour_agg(layer, label)
        ren = agg.select("city", "timestamp", "n_station_rows",
                         *[F.col(c).alias(f"s_{c}") for c in SHARED + ["co"]])
        joined = ren.join(cams_ren, ["city", "timestamp"], "inner").cache()
        matched = joined.count()
        print(f"\n--- {label} vs CAMS: {matched:,} matched city-hours ---")
        print(f"{'pollutant':10} {'n':>10} {'corr':>8} {'bias':>10} {'mae':>10} {'rmse':>10} "
              f"{'mean_str':>10} {'mean_cams':>10}")
        for p in SHARED:
            r = compare(joined, p, label)
            results.append(r)
            if r["n"]:
                print(f"{p:10} {r['n']:>10,} {r['corr']:>8.3f} {r['bias']:>10.2f} "
                      f"{r['mae']:>10.2f} {r['rmse']:>10.2f} {r['mean_structured']:>10.2f} "
                      f"{r['mean_cams']:>10.2f}")
            else:
                print(f"{p:10} {'0':>10}  (no overlapping non-null pairs)")

        # CO, unit-corrected, reported separately and labelled
        co = joined.filter(F.col("s_co").isNotNull() & F.col("c_co").isNotNull()) \
                   .withColumn("s_co_ug", F.col("s_co") * 1000.0)
        n_co = co.count()
        if n_co:
            st = co.select(F.corr("s_co_ug", "c_co").alias("corr"),
                           F.avg(F.col("s_co_ug") - F.col("c_co")).alias("bias")).first()
            print(f"{'co*':10} {n_co:>10,} {st['corr']:>8.3f} {st['bias']:>10.2f} "
                  f"{'':>10} {'':>10}   (* structured mg/m3 x1000 -> ug/m3)")

        # timezone sanity: does correlation really peak at 0 h offset?
        print(f"  timezone check ({label}, pm25 corr by hour offset):", end=" ")
        offs = []
        for off in range(-3, 4):
            shifted = cams_ren.withColumn(
                "timestamp", F.col("timestamp") + F.expr(f"INTERVAL {off} HOURS"))
            j = ren.join(shifted, ["city", "timestamp"], "inner")
            c = j.select(F.corr("s_pm25", "c_pm25")).first()[0]
            offs.append((off, c))
            print(f"{off:+d}h={c:.3f}" if c is not None else f"{off:+d}h=na", end="  ")
        best = max((o for o in offs if o[1] is not None), key=lambda x: x[1], default=None)
        print(f"\n    -> peak at {best[0]:+d}h" +
              ("  (0h expected: IST assumption holds)" if best[0] == 0
               else "  *** NOT 0h - timezone assumption may be wrong ***"))
        joined.unpersist()

    # ---- per-city breakdown for pm25, real layer ----
    print("\n--- per-city pm25 correlation (real vs CAMS), worst and best 10 ---")
    agg = city_hour_agg(real, "real")
    ren = agg.select("city", "timestamp", *[F.col(c).alias(f"s_{c}") for c in SHARED])
    j = ren.join(cams_ren, ["city", "timestamp"], "inner") \
           .filter(F.col("s_pm25").isNotNull() & F.col("c_pm25").isNotNull())
    per_city = (j.groupBy("city")
                 .agg(F.count("*").alias("n"),
                      F.corr("s_pm25", "c_pm25").alias("corr"),
                      F.avg(F.col("s_pm25") - F.col("c_pm25")).alias("bias"))
                 .filter(F.col("n") >= 500))
    print("  worst 10:")
    per_city.orderBy("corr").show(10, truncate=False)
    print("  best 10:")
    per_city.orderBy(F.desc("corr")).show(10, truncate=False)

    if args.out:
        os.makedirs(args.out, exist_ok=True)
        spark.createDataFrame(results).coalesce(1).write.mode("overwrite") \
             .option("header", "true").csv(os.path.join(args.out, "summary"))
        per_city.coalesce(1).write.mode("overwrite") \
             .option("header", "true").csv(os.path.join(args.out, "per_city_pm25"))
        print(f"\nwrote results under {args.out}")

    spark.stop()


if __name__ == "__main__":
    main()
