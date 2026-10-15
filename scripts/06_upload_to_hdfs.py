r"""
================================================================================
PHASE 3/4 ARTEFACT UPLOAD - local lakehouse -> HDFS
================================================================================
Project : A Scalable Big Data Platform for Real-Time Urban Air Quality Tracking
Course  : 23AID302 - Big Data Analytics

WHY THIS EXISTS
  Phases 3 and 4 ran with AQ_FS=local: they read from F:\ and wrote to
  D:\aq_lakehouse. The 27.5 GiB of raw CSV sits in HDFS, but
  /user/hadoop/lakehouse/clean and /features are empty directories - Spark and
  HDFS have never actually exchanged data.

  This copies the finished Parquet layers into HDFS, so the lakehouse the
  project describes genuinely lives on the cluster.

WHY SPARK RATHER THAN `hdfs dfs -put`
  1. Only F:\airquality_expanded is mounted into the NameNode container, so the
     container cannot see D:\aq_lakehouse at all.
  2. More importantly, this makes SPARK WRITE TO HDFS - which is the Phase 2/3
     integration claim. `hdfs dfs -put` would only demonstrate a file transfer.

  It does NOT demonstrate Spark READING from HDFS. For that, run
  01_clean_select.py with AQ_FS=hdfs afterwards.

REPLICATION
  The derived layers are written at replication 2, not 3:

      clean     9.95 GiB x3 = 29.85 GiB      x2 = 19.90 GiB
      features 19.70 GiB x3 = 59.10 GiB      x2 = 39.40 GiB
      total              x3 = 88.95 GiB      x2 = 59.30 GiB

  There is not 89 GiB free on D:. This is a considered choice rather than a
  workaround: the RAW dataset stays at replication 3 - that is where the
  fault-tolerance demonstration lives - while clean and features are fully
  regenerable from raw by re-running Phases 3 and 4. Fewer copies of
  reproducible derived data is ordinary practice. Override with --replication.

RUN
  env.cmd
  python -u 06_upload_to_hdfs.py                    all layers
  python -u 06_upload_to_hdfs.py --what clean       one layer
  python -u 06_upload_to_hdfs.py --replication 3    if space allows
  python -u 06_upload_to_hdfs.py --dry-run          plan only, copies nothing
================================================================================
"""

import argparse
import os
import sys
import time

BAR = "=" * 78
SUB = "-" * 78


def human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024.0:
            return f"{n:,.2f} {unit}"
        n /= 1024.0
    return f"{n:,.2f} PB"


def local_size(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def copy_tree_jvm(spark, src_local, dst_hdfs):
    """Copy a directory into HDFS using the Hadoop FileSystem API.

    Used for the saved ML models rather than a Spark read/write, because a
    PipelineModel directory is a mix of JSON metadata and Parquet - not a single
    tabular dataset.

    This runs entirely inside the JVM. That matters here: Spark cannot spawn
    Python worker processes on this machine, so the obvious alternative -
    PipelineModel.load() followed by .save() - fails, because load() reads its
    metadata through an RDD operation.
    """
    jvm = spark._jvm
    hconf = spark._jsc.hadoopConfiguration()
    Path = jvm.org.apache.hadoop.fs.Path

    src_fs = jvm.org.apache.hadoop.fs.FileSystem.getLocal(hconf)
    dst_uri = jvm.java.net.URI(dst_hdfs)
    dst_fs = jvm.org.apache.hadoop.fs.FileSystem.get(dst_uri, hconf)

    src_path = Path("file:///" + src_local.replace("\\", "/"))
    dst_path = Path(dst_hdfs)

    if dst_fs.exists(dst_path):
        dst_fs.delete(dst_path, True)

    jvm.org.apache.hadoop.fs.FileUtil.copy(
        src_fs, src_path, dst_fs, dst_path, False, True, hconf
    )
    return dst_fs.getContentSummary(dst_path).getLength()


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--local-lake", default=os.environ.get("AQ_LAKE", r"D:\aq_lakehouse"),
                    help="local lakehouse root (default: AQ_LAKE or D:\\aq_lakehouse)")
    ap.add_argument("--hdfs-uri", default="hdfs://localhost:9000",
                    help="NameNode URI (default: hdfs://localhost:9000)")
    ap.add_argument("--hdfs-lake", default="/user/hadoop",
                    help="lakehouse root inside HDFS (default: /user/hadoop)")
    ap.add_argument("--what", choices=("clean", "features", "models", "all"),
                    default="all", help="which layer to upload (default: all)")
    ap.add_argument("--replication", type=int, default=2,
                    help="HDFS replication for the derived layers (default: 2)")
    ap.add_argument("--dry-run", action="store_true",
                    help="report the plan and copy nothing")
    args = ap.parse_args()

    layers = []
    if args.what in ("clean", "all"):
        layers.append(("clean", os.path.join(args.local_lake, "clean"),
                       f"{args.hdfs_uri}{args.hdfs_lake}/lakehouse/clean"))
    if args.what in ("features", "all"):
        layers.append(("features", os.path.join(args.local_lake, "features"),
                       f"{args.hdfs_uri}{args.hdfs_lake}/lakehouse/features"))

    models = []
    if args.what in ("models", "all"):
        mroot = os.path.join(args.local_lake, "models")
        for name in ("feature_pipeline", "gbt_pm25_forecaster", "rf_pm25_forecaster"):
            src = os.path.join(mroot, name)
            if os.path.isdir(src):
                models.append((name, src, f"{args.hdfs_uri}{args.hdfs_lake}/models/{name}"))

    # ------------------------------------------------------------------ plan
    print(BAR)
    print("  UPLOAD PLAN - local lakehouse -> HDFS")
    print(BAR)
    print(f"  source      : {args.local_lake}")
    print(f"  destination : {args.hdfs_uri}{args.hdfs_lake}")
    print(f"  replication : {args.replication}  (raw dataset stays at 3)")
    print(SUB)

    planned = 0
    for name, src, dst in layers:
        if not os.path.isdir(src):
            print(f"  {name:20s} MISSING at {src}")
            continue
        sz = local_size(src)
        planned += sz * args.replication
        print(f"  {name:20s} {human(sz):>12s}  x{args.replication} = "
              f"{human(sz * args.replication):>12s}")
    for name, src, dst in models:
        sz = local_size(src)
        planned += sz * args.replication
        print(f"  {name:20s} {human(sz):>12s}  x{args.replication} = "
              f"{human(sz * args.replication):>12s}")
    if not layers and not models:
        print("  nothing to upload")
        return
    print(SUB)
    print(f"  TOTAL HDFS SPACE REQUIRED : {human(planned)}")
    print(BAR)

    if args.dry_run:
        print("\n  --dry-run: nothing copied.")
        return

    # --------------------------------------------------------------- session
    # Light footprint: this is a copy, not a computation. dfs.replication is set
    # on the Hadoop client configuration, so it governs every write below.
    from pyspark.sql import SparkSession

    spark = (SparkSession.builder
             .appName("AirQuality_UploadToHDFS")
             .master(f"local[{os.environ.get('AQ_CORES', '4')}]")
             .config("spark.driver.memory", os.environ.get("AQ_DRIVER_MEM", "4g"))
             .config("spark.sql.shuffle.partitions", "32")
             .config("spark.hadoop.dfs.replication", str(args.replication))
             .config("spark.sql.parquet.compression.codec", "snappy")
             .config("spark.local.dir", os.environ.get("AQ_TMP", r"D:\aq_sparktmp"))
             .getOrCreate())
    spark.sparkContext.setLogLevel("WARN")

    print(f"\n>>> Spark {spark.version} | dfs.replication="
          f"{spark.conf.get('spark.hadoop.dfs.replication')}\n")

    results = []

    # ------------------------------------------------------- tabular layers
    for name, src, dst in layers:
        if not os.path.isdir(src):
            continue
        print(BAR)
        print(f"  UPLOADING {name.upper()}")
        print(BAR)
        t0 = time.time()

        df = spark.read.parquet(src)
        n_src = df.count()
        print(f"  local rows    : {n_src:,}")
        print(f"  local columns : {len(df.columns)}")
        print(f"  writing to    : {dst}")

        # partitionBy city preserves the layout Phase 3/4 produced, so predicate
        # pushdown still works on the HDFS copy.
        writer = df.write.mode("overwrite").option("compression", "snappy")
        if "city" in df.columns:
            writer = writer.partitionBy("city")
        writer.parquet(dst)

        # Verification: read it back FROM HDFS and count. A copy that cannot be
        # read back is not a copy.
        n_dst = spark.read.parquet(dst).count()
        dt = time.time() - t0

        ok = "MATCH" if n_src == n_dst else "*** MISMATCH ***"
        print(SUB)
        print(f"  rows local    : {n_src:,}")
        print(f"  rows in HDFS  : {n_dst:,}   {ok}")
        print(f"  elapsed       : {dt/60:.1f} min")
        print()
        results.append((name, n_src, n_dst, dt))

    # ---------------------------------------------------------------- models
    for name, src, dst in models:
        print(BAR)
        print(f"  UPLOADING MODEL {name}")
        print(BAR)
        t0 = time.time()
        print(f"  {src}\n    -> {dst}")
        try:
            written = copy_tree_jvm(spark, src, dst)
            dt = time.time() - t0
            print(f"  copied {human(written)} in {dt:.1f}s")
            results.append((name, None, None, dt))
        except Exception as e:
            print(f"  *** FAILED: {type(e).__name__}: {str(e)[:200]}")
        print()

    # --------------------------------------------------------------- summary
    print(BAR)
    print("  UPLOAD COMPLETE")
    print(BAR)
    for name, a, b, dt in results:
        if a is None:
            print(f"  {name:22s} copied in {dt:.1f}s")
        else:
            flag = "OK" if a == b else "MISMATCH"
            print(f"  {name:22s} {a:>14,} rows -> {b:>14,} rows  [{flag}]  "
                  f"{dt/60:.1f} min")
    print(SUB)
    print("  Verify from the cluster side:")
    print("    docker exec aq-namenode hdfs dfs -du -s -h /user/hadoop/lakehouse/clean")
    print("    docker exec aq-namenode hdfs dfs -du -s -h /user/hadoop/lakehouse/features")
    print("    docker exec aq-namenode hdfs fsck /user/hadoop/lakehouse/clean")
    print(BAR)

    spark.stop()


if __name__ == "__main__":
    main()
