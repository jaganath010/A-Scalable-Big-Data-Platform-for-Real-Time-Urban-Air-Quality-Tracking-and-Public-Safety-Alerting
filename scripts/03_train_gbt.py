"""
================================================================================
PHASE 5 + 6 - GBT Training, Persistence-Benchmarked Evaluation, Model Export
================================================================================
Project : A Scalable Big Data Platform for Real-Time Urban Air Quality Tracking
Course  : 23AID302 - Big Data Analytics

INPUT   : hdfs:///user/hadoop/lakehouse/features/
OUTPUT  : hdfs:///user/hadoop/models/gbt_pm25_forecaster

--------------------------------------------------------------------------------
WHY THIS SCRIPT EXISTS IN THIS FORM
--------------------------------------------------------------------------------
The previous run reported R2 = 0.58. Measured on this very dataset (479k+ real
consecutive hourly transitions), the PERSISTENCE BASELINE - the one-line rule
"next hour = this hour", no model at all - scores:

        R2 = 0.8056   RMSE = 29.59 ug/m3     (all rows)
        R2 = 0.7328   RMSE = 36.94 ug/m3     (original rows only)
        R2 = 0.8562   RMSE = 24.45 ug/m3     (synthetic_expanded rows)

So R2 = 0.58 was WORSE THAN DOING NOTHING. That is not a weak model - it is a
broken pipeline. A GBT that sees the current pm25 as a feature cannot score below
persistence unless the labels, the split, or the feature vector are wrong.

This script therefore computes the persistence baseline on the SAME test rows as
the model, every run, and refuses to declare success unless the model beats it.
Never report an R2 again without this number next to it.

--------------------------------------------------------------------------------
ALSO NOTE ON THE PREVIOUS "RMSE = 0.57"
--------------------------------------------------------------------------------
Persistence RMSE on raw pm25 is ~29.6 ug/m3. An RMSE of 0.57 is ~50x smaller,
which means the previous run was NOT predicting raw ug/m3 - the target had been
scaled or log-transformed. An RMSE on a transformed target is not comparable to
anything and cannot be defended to a panel. This script reports RMSE and MAE in
raw ug/m3 so the number means "the average miss, in micrograms per cubic metre".

RUN
  spark-submit --master yarn --deploy-mode client \
    --executor-memory 8g --driver-memory 4g \
    --conf spark.sql.shuffle.partitions=400 \
    03_train_gbt.py
================================================================================
"""

import argparse
import importlib
import os

from pyspark.sql import functions as F
from pyspark.ml import Pipeline, PipelineModel
from pyspark.ml.feature import StringIndexer, OneHotEncoder, VectorAssembler
from pyspark.ml.regression import GBTRegressor
from pyspark.ml.evaluation import RegressionEvaluator

import paths

# The feature lists are imported from Phase 4 rather than copied, so the two
# scripts cannot drift apart. The module name starts with a digit, so it needs
# importlib rather than a plain import statement.
_phase4 = importlib.import_module("02_feature_extraction")
NUMERIC_FEATURES = _phase4.NUMERIC_FEATURES
CATEGORICALS     = _phase4.CATEGORICALS

FEATURE_PATH  = paths.FEATURE_PATH
PIPELINE_PATH = paths.PIPELINE_PATH
MODEL_PATH    = paths.MODEL_PATH

LABEL = "target_pm25_next_hour"

# Chronological split fraction. See STEP 2 for why this is not randomSplit.
TRAIN_FRACTION = 0.8

# Cap on TRAINING rows. 0 = no cap.
#
# At full scale the training window holds ~80M rows. Cached with a ~75-dimension
# feature vector that is ~48 GB against 15.7 GB of RAM, so a single machine
# thrashes to disk and the fit takes days. Gradient boosting saturates long
# before this many rows - the trees stop finding new structure while the cost
# keeps scaling linearly - so the cap buys back nearly all the time for very
# little accuracy.
#
# THE CAP APPLIES TO TRAINING ONLY. The hold-out is never sampled: every metric
# is still measured on the complete test window, and the real-rows-only score is
# still measured on every real row in it. Report the sampled row count alongside
# the score - it is a disclosed limitation of single-machine training, not of
# the pipeline, and it disappears when this runs on the cluster.
DEFAULT_TRAIN_CAP = 10_000_000


def metrics(pred_df, label_col, pred_col):
    """R2 / RMSE / MAE on the raw ug/m3 scale."""
    out = {}
    for m in ("r2", "rmse", "mae"):
        out[m] = RegressionEvaluator(
            labelCol=label_col, predictionCol=pred_col, metricName=m
        ).evaluate(pred_df)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--train-cap", type=int, default=DEFAULT_TRAIN_CAP, metavar="N",
                    help=f"cap training rows at N (0 = use all). "
                         f"Default {DEFAULT_TRAIN_CAP:,}. Never affects evaluation.")
    ap.add_argument("--max-iter", type=int, default=300, metavar="N",
                    help="GBT boosting iterations (default 300)")
    args = ap.parse_args()

    spark = paths.spark_session(
        "AirQuality_Phase5_GBT_Training",
        spark__serializer="org.apache.spark.serializer.KryoSerializer",
    )
    spark.sparkContext.setLogLevel("WARN")
    paths.banner()

    # ==========================================================================
    # CHECKPOINT DIRECTORY - REQUIRED, NOT OPTIONAL, FOR A 300-ITERATION GBT
    #
    # GBTRegressor carries checkpointInterval=10 by default, but checkpointing
    # is SILENTLY DISABLED unless a checkpoint directory is set. Without one,
    # each boosting iteration extends the RDD lineage and nothing ever truncates
    # it. By iteration ~290 the chain is deep enough that Spark's recursive
    # serialisation of it overflows the JVM thread stack, and the fit dies with
    # StackOverflowError after hours of work.
    #
    # Setting this lets checkpointInterval do its job: every 10 iterations the
    # lineage is written to disk and truncated, so it never grows without bound.
    # ==========================================================================
    ckpt = os.path.join(os.environ.get("AQ_TMP", paths.PROJECT_ROOT), "checkpoints")
    os.makedirs(ckpt, exist_ok=True)
    spark.sparkContext.setCheckpointDir(ckpt)
    print(f">>> checkpoint dir: {ckpt}")

    df = spark.read.parquet(FEATURE_PATH)

    # ==========================================================================
    # STEP 0 - REBUILD THE FEATURE VECTOR
    #
    # Phase 4 persists the feature COLUMNS, not the assembled vector - writing a
    # ~75-slot dense vector cost 370 bytes/row (~34.5 GB at full scale) because
    # one-hot slots were materialised as explicit doubles and Parquet cannot
    # compress inside a vector. Assembly is cheap; the lag and rolling-window
    # work that is expensive is already materialised upstream.
    #
    # The pipeline loaded here is the one FITTED IN PHASE 4 on the full dataset,
    # so the StringIndexer vocabularies are identical to what was written. Do not
    # refit it here - refitting on a training subset would silently change the
    # one-hot column order and make the saved model's feature indices wrong.
    #
    # Phase 4 already dropped rows that cannot assemble, so this is lossless;
    # the count check below verifies that rather than trusting it.
    # ==========================================================================
    if "features" not in df.columns:
        n_before = df.count()

        try:
            pipe = PipelineModel.load(PIPELINE_PATH)
            print(f">>> feature pipeline loaded from {PIPELINE_PATH}")
        except Exception as e:
            # PipelineModel.load reads its metadata with sc.textFile(...).first(),
            # an RDD operation, which needs a Python worker process. Writing the
            # same metadata in Phase 4 went through the DataFrame API and is
            # JVM-only, which is why saving worked and loading does not.
            #
            # Where the Python worker cannot start (see PYTHON_WORKER_NOTE.md),
            # refit the encoders instead. This is EQUIVALENT, not an
            # approximation: the indexers are fitted here on the full feature
            # dataset before the chronological split - the same rows Phase 4
            # fitted on - so the vocabularies and therefore the one-hot column
            # order come out identical. What would NOT be safe is fitting after
            # the split, on the training subset only.
            print(f">>> PipelineModel.load failed ({type(e).__name__}) - "
                  f"refitting encoders on the full pre-split dataset instead")
            indexers = [StringIndexer(inputCol=c, outputCol=f"{c}_idx",
                                      handleInvalid="keep")
                        for c in CATEGORICALS]
            encoders = [OneHotEncoder(inputCols=[f"{c}_idx" for c in CATEGORICALS],
                                      outputCols=[f"{c}_ohe" for c in CATEGORICALS],
                                      handleInvalid="keep")]
            assembler = VectorAssembler(
                inputCols=NUMERIC_FEATURES + [f"{c}_ohe" for c in CATEGORICALS],
                outputCol="features",
                handleInvalid="skip",
            )
            pipe = Pipeline(stages=indexers + encoders + [assembler]).fit(df)

        df = pipe.transform(df)
        n_after = df.count()
        vec_len = len(df.select("features").first()["features"])
        print(f"    feature vector rebuilt: {n_after:,} rows, {vec_len} dimensions")
        if n_after != n_before:
            print(f"    *** WARNING: assembly dropped {n_before - n_after:,} rows "
                  f"({n_before:,} -> {n_after:,}). Phase 4 should have removed these "
                  f"already - investigate before trusting this run. ***")

    # ==========================================================================
    # STEP 1 - FINAL QUALITY GATE
    #
    # Phase 4 already guarantees a temporally validated label built from measured
    # (never imputed) pm25. This is a belt-and-braces check so a bad upstream run
    # fails loudly here instead of silently producing another R2 = 0.58.
    # ==========================================================================
    before = df.count()
    df = df.filter(
        F.col(LABEL).isNotNull()
        & (F.col(LABEL) >= 0) & (F.col(LABEL) <= 2000)
        & F.col("features").isNotNull()
    )
    after = df.count()
    print(f">>> quality gate: {before:,} -> {after:,} rows "
          f"({100.0 * after / before:.2f}% retained)")

    # ==========================================================================
    # STEP 2 - CHRONOLOGICAL SPLIT, NOT randomSplit
    #
    # The plan doc specifies randomSplit(0.8/0.2). For a TIME SERIES that leaks:
    # hour T lands in train while T+1 lands in test, and the two are ~0.81
    # correlated. The model then scores well on information it should not have,
    # and the number does not survive contact with real deployment - where you
    # only ever have the past.
    #
    # Splitting on time instead means: train on the earlier 80% of history,
    # test on the most recent 20%. This is what the streaming layer will actually
    # face, and it is the defensible choice in front of a panel.
    # ==========================================================================
    cut = df.approxQuantile("ts_unix", [TRAIN_FRACTION], 0.001)[0]
    train = df.filter(F.col("ts_unix") <= cut)
    test  = df.filter(F.col("ts_unix") > cut)

    # --------------------------------------------------------------------------
    # TRAINING-ONLY SUBSAMPLE. `test` is deliberately untouched below this line.
    #
    # Sampled uniformly at random WITHIN the training window, so the real/
    # synthetic mix and the window's time span are both preserved in expectation.
    # The actual sampled mix is printed so the claim is checkable rather than
    # asserted. Seeded, so a rerun trains on the same rows.
    # --------------------------------------------------------------------------
    n_tr_full = train.count()
    sampled = False
    if args.train_cap and n_tr_full > args.train_cap:
        frac = args.train_cap / n_tr_full
        train = train.sample(withReplacement=False, fraction=frac, seed=42)
        sampled = True
        print(f">>> training subsample: {n_tr_full:,} -> ~{args.train_cap:,} rows "
              f"(fraction {frac:.4f}, seed 42)")
        print("    evaluation is NOT sampled - the full test window is scored.")

    train.cache(); test.cache()
    n_tr, n_te = train.count(), test.count()
    span = test.agg(F.min("timestamp").alias("a"), F.max("timestamp").alias("b")).collect()[0]
    print(f">>> chronological split at ts_unix={cut}")
    print(f"    train {n_tr:,} rows | test {n_te:,} rows")
    print(f"    test window: {span['a']} -> {span['b']}")
    if sampled:
        mix = {r["data_source"]: r["count"]
               for r in train.groupBy("data_source").count().collect()}
        print("    sampled train mix: " + "  ".join(
            f"{k} {v:,} ({100.0 * v / n_tr:.2f}%)" for k, v in sorted(mix.items())))

    # ==========================================================================
    # STEP 3 - PERSISTENCE BASELINE ON THE TEST SET
    #
    # "Predict next hour = current hour." No learning. This is the floor.
    # ==========================================================================
    base = test.withColumn("prediction", F.col("pm25"))
    bm = metrics(base, LABEL, "prediction")
    print("-" * 72)
    print(f"  PERSISTENCE BASELINE   R2={bm['r2']:.4f}  RMSE={bm['rmse']:.3f}  MAE={bm['mae']:.3f}")

    # --------------------------------------------------------------------------
    # The same baseline on REAL ROWS ONLY.
    #
    # This is the number that carries scientific weight. The dataset is 88.9%
    # generated, so a metric over all rows is largely a statement about the
    # AR(1) generator, not about air quality. data_source splits the two cleanly
    # (status report section 10), so the honest headline is the real-only score
    # and the all-rows score is reported beside it as the systems-scale figure.
    # --------------------------------------------------------------------------
    test_real = test.filter(F.col("data_source") == "real")
    n_real = test_real.count()
    bm_real = metrics(test_real.withColumn("prediction", F.col("pm25")),
                      LABEL, "prediction") if n_real else None
    if bm_real:
        print(f"  ... on real rows only  R2={bm_real['r2']:.4f}  "
              f"RMSE={bm_real['rmse']:.3f}  MAE={bm_real['mae']:.3f}  (n={n_real:,})")
    else:
        print("  ... no real rows in the test window - real-only scoring skipped")

    # ==========================================================================
    # STEP 4 - TRAIN GBT ON THE DELTA, NOT THE LEVEL
    #
    # Decision trees are piecewise-constant: they cannot express the identity
    # "next hour is roughly this hour" as a function. Asked to predict the LEVEL,
    # GBT burns its entire capacity rebuilding persistence from splits - measured
    # locally, pm25 took a feature importance of 1.25 while nothing else exceeded
    # 0.04, and the model beat persistence by only 5.6% RMSE.
    #
    # Predicting the CHANGE removes that burden: persistence is handled exactly
    # by the +pm25 term, and every tree models the residual dynamics instead.
    #
    #   MEASURED on 3.78M labelled rows, real-rows-only chronological hold-out:
    #     target=level   R2 0.9098   RMSE 20.478   (5.6% better than persistence)
    #     target=delta   R2 0.9201   RMSE 19.240   (11.3% better)  <-- 2x the gain
    #
    # Importances after the switch spread across real physics - pm25_lag_1h 0.178,
    # aqi_current 0.080, pm10 0.079, co 0.047, season 0.030 - instead of one
    # column dominating.
    #
    # maxIter is also raised from the plan's 20 to 300 and maxDepth 5 -> 6.
    # 20 trees is drastically undertrained for ~55 features; the local run needed
    # 400 before early stopping.
    # ==========================================================================
    DELTA_LABEL = "_delta_label"
    train = train.withColumn(DELTA_LABEL, F.col(LABEL) - F.col("pm25"))

    gbt = GBTRegressor(
        featuresCol="features",
        labelCol=DELTA_LABEL,
        maxIter=args.max_iter,
        maxDepth=6,
        stepSize=0.08,
        subsamplingRate=0.8,
        featureSubsetStrategy="sqrt",
        maxBins=64,
        seed=42,
    )

    print(">>> training GBT on delta target ...")
    model = gbt.fit(train.filter(F.col(DELTA_LABEL).isNotNull()))

    # ==========================================================================
    # STEP 5 - EVALUATE AGAINST THE BASELINE
    #
    # The model emits a delta, so add the current level back before scoring.
    # Metrics stay on the raw ug/m3 scale and remain directly comparable to the
    # persistence baseline computed above.
    # ==========================================================================
    pred = (model.transform(test)
                 .withColumnRenamed("prediction", "_delta_pred")
                 .withColumn("prediction", F.col("pm25") + F.col("_delta_pred")))
    mm = metrics(pred, LABEL, "prediction")

    print("=" * 72)
    print("PHASE 6 - EVALUATION (raw ug/m3, chronological hold-out)")
    print("=" * 72)
    print(f"  trained on {n_tr:,} rows"
          + (f" - a seeded sample of the {n_tr_full:,}-row training window"
             if sampled else " - the full training window")
          + f", {args.max_iter} trees")
    print("-" * 72)
    print(f"  ALL TEST ROWS  (n={n_te:,})  - the systems-scale figure")
    print(f"  {'':22s} {'R2':>9s} {'RMSE':>10s} {'MAE':>10s}")
    print(f"  {'persistence baseline':22s} {bm['r2']:>9.4f} {bm['rmse']:>10.3f} {bm['mae']:>10.3f}")
    print(f"  {'GBT model':22s} {mm['r2']:>9.4f} {mm['rmse']:>10.3f} {mm['mae']:>10.3f}")
    lift = 100.0 * (bm["rmse"] - mm["rmse"]) / bm["rmse"]
    print(f"  {'RMSE reduction':22s} {lift:>9.2f}%")

    # The headline. Everything above includes generated rows; this does not.
    mm_real = None
    if bm_real:
        pred_real = pred.filter(F.col("data_source") == "real")
        mm_real = metrics(pred_real, LABEL, "prediction")
        lift_real = 100.0 * (bm_real["rmse"] - mm_real["rmse"]) / bm_real["rmse"]
        print("-" * 72)
        print(f"  REAL ROWS ONLY (n={n_real:,})  - the scientific figure, QUOTE THIS ONE")
        print(f"  {'':22s} {'R2':>9s} {'RMSE':>10s} {'MAE':>10s}")
        print(f"  {'persistence baseline':22s} {bm_real['r2']:>9.4f} "
              f"{bm_real['rmse']:>10.3f} {bm_real['mae']:>10.3f}")
        print(f"  {'GBT model':22s} {mm_real['r2']:>9.4f} "
              f"{mm_real['rmse']:>10.3f} {mm_real['mae']:>10.3f}")
        print(f"  {'RMSE reduction':22s} {lift_real:>9.2f}%")
    print("-" * 72)

    # The gate is applied to the real-rows score when one exists: beating
    # persistence on generated rows proves only that the generator is learnable.
    gate_m, gate_b, gate_on = ((mm_real, bm_real, "real rows")
                               if mm_real else (mm, bm, "all rows"))
    if gate_m["r2"] <= gate_b["r2"]:
        print(f"  (gate evaluated on {gate_on})")
        print("  *** FAIL: the model does NOT beat persistence. DO NOT REPORT THIS RUN. ***")
        print("      Check, in this order:")
        print("        1. is `pm25` (current hour) actually inside the feature vector?")
        print("        2. was the label built from pm25_measured, not imputed pm25?")
        print("        3. did VectorAssembler(handleInvalid='skip') silently drop rows?")
        print("        4. is the label on the raw ug/m3 scale, not scaled/logged?")
    else:
        print(f"  PASS ({gate_on}): model beats persistence by "
              f"{gate_m['r2'] - gate_b['r2']:.4f} R2.")
    print("=" * 72)

    # ==========================================================================
    # STEP 6 - FEATURE IMPORTANCE
    #
    # A sanity check as much as a result: pm25 / pm25_lag_1h / pm25_roll_3h
    # should dominate. If a provenance flag or a one-hot category tops the list,
    # the model is learning the data generator, not the physics.
    # ==========================================================================
    imps = model.featureImportances.toArray()
    print("  top 15 features by importance (index -> importance):")
    for i in sorted(range(len(imps)), key=lambda j: -imps[j])[:15]:
        print(f"    [{i:>3d}] {imps[i]:.5f}")
    print("  (map indices to names via the VectorAssembler input order in "
          "02_feature_extraction.py)")

    # ==========================================================================
    # STEP 7 - PER-CITY BREAKDOWN, and EXPORT
    # ==========================================================================
    print("\n  worst 10 cities by RMSE (where the model struggles):")
    per_city = (pred
        .withColumn("_se", F.pow(F.col("prediction") - F.col(LABEL), 2))
        .groupBy("city")
        .agg(F.sqrt(F.avg("_se")).alias("rmse"), F.count("*").alias("n"))
        .filter(F.col("n") > 500)
        .orderBy(F.col("rmse").desc())
        .limit(10))
    for r in per_city.collect():
        print(f"    {r['city']:<28s} RMSE={r['rmse']:8.2f}  n={r['n']:,}")

    model.write().overwrite().save(MODEL_PATH)
    print(f"\n>>> model saved to {MODEL_PATH}")

    train.unpersist(); test.unpersist()
    spark.stop()


if __name__ == "__main__":
    main()
