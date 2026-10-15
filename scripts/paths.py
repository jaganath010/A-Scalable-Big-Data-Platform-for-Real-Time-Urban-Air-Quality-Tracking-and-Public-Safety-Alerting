"""
================================================================================
Shared path configuration for Phases 3-6
================================================================================
Project : A Scalable Big Data Platform for Real-Time Urban Air Quality Tracking
Course  : 23AID302 - Big Data Analytics

The pipeline scripts used to hardcode hdfs:/// paths, which meant they could not
be run at all until a Hadoop cluster existed. This module resolves every path
from the environment instead, so the SAME scripts run in two modes:

    AQ_FS=local   ->  native filesystem, single-machine Spark  (default)
    AQ_FS=hdfs    ->  hdfs:///user/hadoop/...                  (cluster)

Nothing else in the pipeline needs to change between the two.

ENVIRONMENT VARIABLES
  AQ_FS     "local" | "hdfs"          default "local"
  AQ_DATA   expanded CSV directory    default F:\\...\\airquality_expanded
  AQ_LAKE   lakehouse root            default <project>\\lakehouse  (local mode)
                                              hdfs:///user/hadoop   (hdfs mode)

`. .\\env.ps1` in the project root sets AQ_DATA for you.

WINDOWS NOTE
  Local paths are passed to Spark as NATIVE Windows paths (F:\\dir\\file), not
  file:/// URIs. This is deliberate: it is verified to work, including for
  directories containing spaces, and it avoids having to percent-encode the
  project path.
================================================================================
"""

import os

# ------------------------------------------------------------------------------
# Repository layout. This file lives in <project>\scripts\, so the project root
# is one level up - resolved from __file__ so it survives being run from any cwd.
# ------------------------------------------------------------------------------
_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(_SCRIPTS)

FS = os.environ.get("AQ_FS", "local").strip().lower()
if FS not in ("local", "hdfs"):
    raise ValueError(f"AQ_FS must be 'local' or 'hdfs', got {FS!r}")

# ------------------------------------------------------------------------------
# The rebuilt 27.48 GB dataset: 23 part-*.csv files, 146,276,379 rows, 32 columns.
#
# NOTE the report and the older script docstrings say E:\airquality_expanded.
# The data now lives on F:. Override with AQ_DATA if it moves again.
# ------------------------------------------------------------------------------
_DEFAULT_DATA = r"F:\SEM 5 NOTES\Big Data\Project_Final\airquality_expanded"

if FS == "local":
    EXPANDED_DIR = os.environ.get("AQ_DATA", _DEFAULT_DATA)
    EXPANDED_GLOB = os.path.join(EXPANDED_DIR, "part-*.csv")
    LAKE = os.environ.get("AQ_LAKE", os.path.join(PROJECT_ROOT, "lakehouse"))
    _join = os.path.join
else:
    EXPANDED_DIR = os.environ.get("AQ_DATA", "hdfs:///user/hadoop/lakehouse/raw")
    EXPANDED_GLOB = EXPANDED_DIR.rstrip("/") + "/part-*.csv"
    LAKE = os.environ.get("AQ_LAKE", "hdfs:///user/hadoop")

    def _join(*p):
        """Join HDFS path components without mangling the scheme.

        The previous implementation was
            "/".join(s.strip("/") for s in p).replace(":/", ":///", 1)
        which assumed LAKE had NO authority (i.e. "hdfs:///user/hadoop"). Given
        an authority - which is what docker-compose.spark.yml actually supplies,
        AQ_LAKE="hdfs://namenode:9000/user/hadoop" - the replace() rewrote the
        "hdfs:/" of the scheme and produced

            hdfs:////namenode:9000/user/hadoop/features

        Four slashes. Spark reads that as an empty authority with a path of
        "/namenode:9000/...", so every HDFS-mode Python run failed to find its
        own data. Measured, not theorised: paths.FEATURE_PATH printed exactly
        that inside the container.

        Splitting the scheme off first, joining only the path part, and
        re-attaching the scheme keeps both forms correct.
        """
        head, sep, rest = p[0].partition("://")
        if sep:                                  # scheme://authority/path
            prefix = head + sep                  # e.g. "hdfs://"
            body = rest
        else:                                    # bare path, e.g. /user/hadoop
            prefix = ""
            body = p[0]
        parts = [body.rstrip("/")] + [s.strip("/") for s in p[1:]]
        return prefix + "/".join(x for x in parts if x != "")

# ------------------------------------------------------------------------------
# Pipeline artefacts
# ------------------------------------------------------------------------------
CLEAN_PATH    = _join(LAKE, "clean")                    # 01 -> 02
FEATURE_PATH  = _join(LAKE, "features")                 # 02 -> 03
PIPELINE_PATH = _join(LAKE, "models", "feature_pipeline")
MODEL_PATH    = _join(LAKE, "models", "gbt_pm25_forecaster")
RF_MODEL_PATH = _join(LAKE, "models", "rf_pm25_forecaster")

# ------------------------------------------------------------------------------
# The legacy 23.44 GB file, kept only so 01 --source legacy still resolves.
# This is the dataset the status report condemns as 66.6% synthetic with four
# measured defects. It is NOT the default input any more.
# ------------------------------------------------------------------------------
LEGACY_RAW = os.environ.get(
    "AQ_LEGACY_RAW",
    r"F:\SEM 5 NOTES\Big Data\Project_Final\Dataset final\final_air_quality_dataset_22gb_balanced.csv"
    if FS == "local" else
    "hdfs:///user/hadoop/lakehouse/raw/final_air_quality_dataset_22gb_balanced.csv",
)


def spark_session(app_name, **conf):
    """SparkSession configured identically across the pipeline.

    In local mode this also pins driver memory and a sane shuffle-partition
    count, so the scripts are runnable on one machine without spark-submit
    flags. On the cluster those come from spark-submit and are not overridden.
    """
    # Driver JVM options must be set BEFORE the JVM is launched, and pyspark
    # launches it at getOrCreate() using PYSPARK_SUBMIT_ARGS. Setting them via
    # builder.config() is too late to take effect.
    #
    # -Xss64m raises the thread stack from the ~1 MB default. Spark serialises
    # long RDD lineage chains and tree ensembles by RECURSING through nested
    # scala List structures, and 300 boosting iterations overflow the default
    # stack with a StackOverflowError inside List$SerializationProxy.readObject.
    # Measured: this killed a 300-tree GBT fit after ~3h50m, at roughly tree 290.
    if "PYSPARK_SUBMIT_ARGS" not in os.environ:
        os.environ["PYSPARK_SUBMIT_ARGS"] = (
            '--driver-java-options "-Xss64m" pyspark-shell')

    from pyspark.sql import SparkSession

    b = SparkSession.builder.appName(app_name)
    if FS == "local":
        cores = os.environ.get("AQ_CORES", "*")
        b = (b.master(f"local[{cores}]")
              .config("spark.driver.memory", os.environ.get("AQ_DRIVER_MEM", "8g"))
              .config("spark.sql.shuffle.partitions",
                      os.environ.get("AQ_SHUFFLE_PARTITIONS", "64"))
              .config("spark.local.dir", os.environ.get("AQ_TMP",
                      os.path.join(PROJECT_ROOT, "_sparktmp"))))
    b = (b.config("spark.sql.parquet.compression.codec", "snappy")
          .config("spark.sql.adaptive.enabled", "true"))
    for k, v in conf.items():
        b = b.config(k.replace("__", "."), v)
    return b.getOrCreate()


def banner():
    """Print the resolved configuration. Every script calls this on startup so a
    run's output records which data it actually touched."""
    print("=" * 72)
    print(f"  AQ_FS        {FS}")
    print(f"  input        {EXPANDED_GLOB}")
    print(f"  lakehouse    {LAKE}")
    print("=" * 72)
