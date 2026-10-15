"""
================================================================================
DAILY LIVE CYCLE - the operational job behind the alerting system
================================================================================
Project : 23AID302 - Big Data Analytics

WHAT THIS IS FOR
  The project's deliverable is not a one-off demo: it is a system that watches
  air quality and warns people. That means this cycle has to run on a schedule,
  every day, unattended.

  This script is the BATCH half of that. It refreshes both live feeds, enriches
  them into the schema the model consumes, and lands the result in the HDFS
  directory the streaming job is already watching.

      1. fetch CAMS air quality (live)   -> local disk, verbatim JSON
      2. fetch weather          (live)   -> local disk, verbatim JSON
      3. upload both + city_profiles     -> HDFS
      4. LiveEnrichment on YARN          -> 32-column CSV in HDFS
      5. hand the CSV to stream/input    -> AirQualityStream scores it,
                                            fires alerts above AQI 150
      6. re-export from Hive + rebuild    -> dashboard/dashboard.html

  Step 5's consumer (AirQualityStream) is a SEPARATE long-running service. It
  does not need restarting each day - it is already watching the directory, so
  dropping a file there is the entire handoff.

WHY BOTH FEEDS ARE RE-FETCHED TOGETHER
  They must cover the SAME hours. An air-quality pull from last week joined
  against weather pulled today shares zero hours, and the inner join silently
  produces an empty result - which is exactly what happened the first time this
  ran. Fetching both in the same cycle is what keeps their windows aligned.

SCHEDULING
  Windows Task Scheduler, daily:
      python run_daily_live_cycle.py --all
  The cluster must be up. To also bring Docker up/down around the run, wrap
  this in a .bat that starts Docker Desktop first (see docs/ARCHITECTURE.md).

RUN
    python run_daily_live_cycle.py --all
    python run_daily_live_cycle.py --steps fetch,upload,enrich,handoff
================================================================================
"""

import argparse
import os
import shlex
import subprocess
import sys
import time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)

# --- local staging -----------------------------------------------------------
EXPANDED = r"F:\SEM 5 NOTES\Big Data\Project_Final\airquality_expanded"
CAMS_DIR = os.path.join(EXPANDED, "live_cams")
WX_DIR = os.path.join(EXPANDED, "live_weather")
PROFILES = r"F:\SEM 5 NOTES\Big Data\Project_Final\Dataset final\city_profiles.csv"

# --- cluster -----------------------------------------------------------------
NN = "aq-namenode"
SPARK = "aq-spark"
HDFS_ROOT = "hdfs://namenode:9000/user/hadoop"
HDFS_CAMS = "/user/hadoop/raw/live_cams"
HDFS_WX = "/user/hadoop/raw/live_weather"
HDFS_REF = "/user/hadoop/ref/city_profiles.csv"
HDFS_ENRICHED = "/user/hadoop/lakehouse/live_enriched"
HDFS_STREAM_IN = "/user/hadoop/lakehouse/stream/input"
JAR = "/jars/scala-2.12/airquality-streaming_2.12-1.0.jar"

# How much history each feed pulls. 2 days gives the streaming job enough
# preceding hours to populate lag/rolling features for the newest rows.
DAYS = int(os.environ.get("LIVE_DAYS", "2"))


def run(cmd, check=True, capture=False):
    print(f"    $ {cmd if isinstance(cmd, str) else ' '.join(cmd)}", flush=True)
    r = subprocess.run(cmd, shell=isinstance(cmd, str),
                       capture_output=capture, text=True)
    if capture and r.stdout:
        print(r.stdout.rstrip())
    if check and r.returncode != 0:
        if capture and r.stderr:
            print(r.stderr.rstrip(), file=sys.stderr)
        raise RuntimeError(f"command failed ({r.returncode})")
    return r


def step_fetch():
    print("\n[1/4] fetching both live feeds (same window, on purpose)")
    # The fetchers are resumable and skip files that already exist. For a LIVE refresh that
    # is wrong: it silently reused the October weather next to a fresh 2-day air-quality
    # pull (found in the end-to-end run). Start from empty folders so both feeds are new.
    import shutil
    for d in (CAMS_DIR, WX_DIR):
        shutil.rmtree(d, ignore_errors=True)
    run([sys.executable, "-u", os.path.join(HERE, "00e_fetch_semistructured_json.py"),
         "--out", CAMS_DIR, "--days", str(DAYS), "--sleep", "0.4"])
    run([sys.executable, "-u", os.path.join(HERE, "00g_fetch_live_weather.py"),
         "--out", WX_DIR,
         "--manifest", os.path.join(CAMS_DIR, "manifest.json"),
         "--days", str(DAYS)])


def step_upload():
    print("\n[2/4] uploading feeds to HDFS")
    # container-local staging, then put into HDFS
    for local, tmp, dest in ((CAMS_DIR, "/tmp/lc", HDFS_CAMS),
                             (WX_DIR, "/tmp/lw", HDFS_WX)):
        run(f'docker exec {NN} rm -rf {tmp}', check=False)
        run(f'docker cp "{local}" {NN}:{tmp}')
        run(f'docker exec {NN} hdfs dfs -rm -r -f {dest}', check=False)
        run(f'docker exec {NN} hdfs dfs -put {tmp} {dest}')
    run(f'docker cp "{PROFILES}" {NN}:/tmp/city_profiles.csv')
    run(f'docker exec {NN} hdfs dfs -mkdir -p /user/hadoop/ref', check=False)
    run(f'docker exec {NN} hdfs dfs -put -f /tmp/city_profiles.csv {HDFS_REF}')


def step_enrich():
    print("\n[3/4] LiveEnrichment on YARN")
    submit = (
        f"HADOOP_CONF_DIR=/opt/hadoop-conf /opt/spark/bin/spark-submit "
        f"--master yarn --deploy-mode client "
        f"--num-executors 3 --executor-memory 1500m --executor-cores 1 "
        f"--driver-memory 1500m "
        f"--class LiveEnrichment {JAR} "
        f"{HDFS_ROOT}/raw/live_cams/raw_json "
        f"{HDFS_ROOT}/raw/live_weather/raw_json "
        f"{HDFS_ROOT}/ref/city_profiles.csv "
        f"{HDFS_ROOT}/lakehouse/live_enriched"
    )
    # argv list, NOT a shell string: on Windows the outer shell is cmd.exe,
    # which does not honour POSIX single-quoting, so shlex.quote() here
    # produces "Unterminated quoted string" inside the container. Passing a
    # list keeps `submit` as one argv element and no shell touches it.
    run(["docker", "exec", SPARK, "sh", "-c", submit])


def step_handoff():
    print("\n[4/4] handing the enriched CSV to the stream")
    # LiveEnrichment coalesces to a single part file; give it a dated name so
    # the stream treats each day as its own micro-batch and the file is
    # traceable back to the run that produced it.
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = f"{HDFS_STREAM_IN}/live_{stamp}.csv"
    # same argv-list reasoning as step_enrich - the awk/$ quoting cannot
    # survive a trip through cmd.exe
    r = run(["docker", "exec", NN, "sh", "-c",
             f"hdfs dfs -ls {HDFS_ENRICHED}/part-*.csv | awk '{{print $NF}}' | head -1"],
            capture=True)
    part = (r.stdout or "").strip().splitlines()[-1].strip() if r.stdout.strip() else ""
    if not part:
        raise RuntimeError("no part-*.csv produced by LiveEnrichment")
    run(f'docker exec {NN} hdfs dfs -mkdir -p {HDFS_STREAM_IN}', check=False)
    run(f'docker exec {NN} hdfs dfs -cp {part} {target}')
    print(f"    delivered -> {target}")
    print("    AirQualityStream will pick this up on its next 10s trigger.")


def step_dashboard():
    """Phase 10: re-export the serving layer and rebuild the dashboard page.

    Runs AFTER handoff so the stream has had a chance to score today's file
    and write today's alerts - otherwise the dashboard would show yesterday's.
    The wait is a fixed 90 s: the stream triggers every 10 s and a 16k-row
    live batch scored in ~23 s in testing, so 90 s is generous without being
    a long stall in an unattended job.
    """
    print("\n[5/5] refreshing the dashboard from the serving layer")
    time.sleep(90)
    dash_dir = os.path.join(PROJECT, "dashboard")
    run(["docker", "cp", dash_dir, f"{SPARK}:/dashboard"])
    export = (
        "/opt/spark/bin/spark-submit --master 'local[2]' --driver-memory 2g "
        "--conf spark.sql.catalogImplementation=hive "
        "--conf spark.sql.warehouse.dir=hdfs://namenode:9000/user/hadoop/hive "
        "--conf 'spark.driver.extraJavaOptions=-Dderby.system.home=/scratch/metastore_db' "
        "--conf spark.local.dir=/scratch "
        "/dashboard/export_dashboard_data.py /tmp/dashboard_data.json"
    )
    run(["docker", "exec", SPARK, "sh", "-c", export])
    run(["docker", "cp", f"{SPARK}:/tmp/dashboard_data.json",
         os.path.join(dash_dir, "dashboard_data.json")])
    run([sys.executable, os.path.join(dash_dir, "build_dashboard.py")])
    print(f"    dashboard -> {os.path.join(dash_dir, 'dashboard.html')}")


STEPS = {"fetch": step_fetch, "upload": step_upload,
         "enrich": step_enrich, "handoff": step_handoff,
         "dashboard": step_dashboard}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true", help="run every step in order")
    ap.add_argument("--steps", default="",
                    help="comma-separated subset: fetch,upload,enrich,handoff,dashboard")
    args = ap.parse_args()

    order = ["fetch", "upload", "enrich", "handoff", "dashboard"]
    chosen = order if args.all else [s.strip() for s in args.steps.split(",") if s.strip()]
    if not chosen:
        ap.error("pass --all or --steps ...")

    t0 = time.time()
    print("=" * 74)
    print(f"  DAILY LIVE CYCLE  {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"  steps: {', '.join(chosen)}")
    print("=" * 74)
    for s in chosen:
        if s not in STEPS:
            raise SystemExit(f"unknown step {s!r}")
        STEPS[s]()
    print(f"\nDONE in {(time.time()-t0)/60:.1f} min")


if __name__ == "__main__":
    main()
