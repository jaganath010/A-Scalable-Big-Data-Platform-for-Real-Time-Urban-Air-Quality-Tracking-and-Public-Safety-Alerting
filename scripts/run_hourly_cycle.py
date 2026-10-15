"""
HOURLY ALERT LOOP - score the forecast every few hours, alert every hour, never twice
================================================================================
Project : 23AID302 - Big Data Analytics

TWO CADENCES, ON PURPOSE
  SCORE     fetch -> enrich on YARN -> stream scoring -> export -> website
            Heavy (needs the cluster). The CAMS source itself only refreshes a few
            times a day, so this runs every --score-every hours (default 6).
  DISPATCH  pick the warnings for the next hours from the already-scored
            forecast, de-duplicate, message people.
            Light (reads one JSON). Runs EVERY hour: as the clock moves, a new
            forecast hour becomes "next", so an alert can fire without refetching.

  The score stage only hands the stream hours NEWER than the last scored hour
  (watermark in scripts/stream_watermark.txt), so a re-fetch never scores the
  same hour twice or duplicates alerts.

DOCKER
  --manage-docker starts Docker Desktop + the cluster when a score stage needs
  it and stops them afterwards (only if this script started them). Dispatch
  never needs Docker.

USAGE
    python run_hourly_cycle.py --once score            # one scoring cycle
    python run_hourly_cycle.py --once dispatch         # one alert pass
    python run_hourly_cycle.py --loop --manage-docker  # run forever, hourly
  Windows Task Scheduler alternative (hourly):
    schtasks /Create /SC HOURLY /TN AirWatchDispatch /TR "python <path>\\run_hourly_cycle.py --once dispatch"
  Set TELEGRAM_BOT_TOKEN (and sign people up with /city <name> to the bot) for real delivery.
================================================================================
"""
import argparse
import csv
import os
import subprocess
import sys
import time
from datetime import datetime

os.environ.setdefault("LIVE_DAYS", "2")          # 2 days of history per fetch, before the daily module is imported
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_daily_live_cycle as daily             # noqa: E402  reuse the fetch / upload / enrich steps

PROJECT = os.path.dirname(HERE)
WATERMARK = os.path.join(HERE, "stream_watermark.txt")
COMPOSE_DIR = os.path.join(PROJECT, "hadoop")
COMPOSE = ["-f", "docker-compose.yml", "-f", "docker-compose.yarn.yml", "-f", "docker-compose.spark.yml"]
NN, SPARK = daily.NN, daily.SPARK
STREAM_LOG = "/tmp/stream_live.log"
SPARK_SQL = ("--master 'local[2]' --driver-memory 2g --conf spark.sql.catalogImplementation=hive "
             "--conf spark.sql.warehouse.dir=hdfs://namenode:9000/user/hadoop/hive "
             "--conf 'spark.driver.extraJavaOptions=-Dderby.system.home=/scratch/metastore_db' --conf spark.local.dir=/scratch")


def sh(cmd, capture=False, check=True):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)[:120]} -> {r.returncode}: {(r.stderr or r.stdout)[-300:]}")
    return r


def docker_up():
    return subprocess.run(["docker", "info"], capture_output=True).returncode == 0


def start_docker():
    print("Docker is not running - starting Docker Desktop and the cluster")
    subprocess.Popen([r"C:\Program Files\Docker\Docker\Docker Desktop.exe"])
    for _ in range(40):
        if docker_up():
            break
        time.sleep(10)
    else:
        raise RuntimeError("Docker did not come up")
    subprocess.run(["docker", "compose", *COMPOSE, "down", "--remove-orphans"], cwd=COMPOSE_DIR, capture_output=True)
    subprocess.run(["docker", "compose", *COMPOSE, "up", "-d"], cwd=COMPOSE_DIR, capture_output=True)
    for _ in range(40):
        r = subprocess.run(["docker", "exec", NN, "hdfs", "dfsadmin", "-safemode", "get"], capture_output=True, text=True)
        if "OFF" in (r.stdout or ""):
            return
        time.sleep(5)
    raise RuntimeError("HDFS stayed in safe mode")


def stop_docker():
    print("stopping the cluster and Docker Desktop (this script started them)")
    subprocess.run(["docker", "compose", *COMPOSE, "stop"], cwd=COMPOSE_DIR, capture_output=True)
    subprocess.run(["taskkill", "/IM", "Docker Desktop.exe", "/F"], capture_output=True)
    subprocess.run(["wsl", "--shutdown"], capture_output=True)


def read_watermark():
    if os.path.exists(WATERMARK):
        return open(WATERMARK).read().strip()
    import json                                   # first run: continue after the last scored hour in the dashboard export
    d = json.load(open(os.path.join(PROJECT, "dashboard", "dashboard_data.json"), encoding="utf-8"))
    return str(d["run_window"]["observed_to"])[:19]


def handoff_new_hours():
    """Copy only hours newer than the watermark into the stream's input folder."""
    wm = read_watermark()
    part = sh(["docker", "exec", NN, "sh", "-c",
               f"hdfs dfs -ls {daily.HDFS_ENRICHED}/part-*.csv | awk '{{print $NF}}' | head -1"]).stdout.strip().splitlines()[-1].strip()
    work = os.path.join(PROJECT, "dashboard", "_hourly_tmp")
    os.makedirs(work, exist_ok=True)
    src, dst = os.path.join(work, "enriched.csv"), os.path.join(work, "new_hours.csv")
    sh(["docker", "exec", NN, "sh", "-c", f"rm -f /tmp/enr.csv; hdfs dfs -get {part} /tmp/enr.csv"])
    sh(["docker", "cp", f"{NN}:/tmp/enr.csv", src])
    n_in = n_out = 0
    newest = wm
    with open(src, newline="", encoding="utf-8") as f, open(dst, "w", newline="", encoding="utf-8") as g:
        rd = csv.reader(f)
        wr = csv.writer(g)
        header = next(rd)
        wr.writerow(header)
        i = header.index("from_date")
        for row in rd:
            n_in += 1
            if row[i] > wm:
                wr.writerow(row)
                n_out += 1
                newest = max(newest, row[i])
    print(f"enriched rows: {n_in:,}   newer than watermark {wm}: {n_out:,}")
    if n_out == 0:
        print("no new forecast hours - nothing to score this cycle")
        return None
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = f"{daily.HDFS_STREAM_IN}/live_{stamp}.csv"
    sh(["docker", "cp", dst, f"{NN}:/tmp/new_hours.csv"])
    sh(["docker", "exec", NN, "hdfs", "dfs", "-mkdir", "-p", daily.HDFS_STREAM_IN], check=False)
    sh(["docker", "exec", NN, "hdfs", "dfs", "-put", "-f", "/tmp/new_hours.csv", target])
    print(f"delivered -> {target}")
    return newest


def ensure_stream():
    r = sh(["docker", "exec", SPARK, "sh", "-c", "pgrep -f AirQualityStream | head -1"], check=False)
    if r.stdout.strip():
        return
    print("starting the streaming job (history + checkpoint persist on HDFS, so it resumes)")
    cmd = (f"AQ_LAKE={daily.HDFS_ROOT} AQ_SHUFFLE_PARTITIONS=64 /opt/spark/bin/spark-submit --class AirQualityStream "
           f"--master 'local[2]' --driver-memory 4g --conf spark.local.dir=/scratch {daily.JAR} > {STREAM_LOG} 2>&1")
    subprocess.Popen(["docker", "exec", "-d", SPARK, "sh", "-c", cmd])
    time.sleep(30)


def batches_done():
    r = sh(["docker", "exec", SPARK, "sh", "-c", f"grep -a -c 'rows in=' {STREAM_LOG} 2>/dev/null || echo 0"], check=False)
    try:
        return int(r.stdout.strip().splitlines()[-1])
    except Exception:
        return 0


def refresh_site():
    print("exporting from Hive and rebuilding the website")
    sh(["docker", "exec", SPARK, "sh", "-c",
        f"/opt/spark/bin/spark-sql {SPARK_SQL} -e 'USE airquality; MSCK REPAIR TABLE stream_alerts'"], check=False)
    dash = os.path.join(PROJECT, "dashboard")
    sh(["docker", "cp", dash, f"{SPARK}:/dashboard"])
    sh(["docker", "exec", SPARK, "sh", "-c",
        f"/opt/spark/bin/spark-submit {SPARK_SQL} /dashboard/export_dashboard_data.py /tmp/dashboard_data.json"])
    sh(["docker", "cp", f"{SPARK}:/tmp/dashboard_data.json", os.path.join(dash, "dashboard_data.json")])
    sh([sys.executable, os.path.join(dash, "_src", "build_dashboard.py")])


def score_stage(manage_docker):
    started = False
    if not docker_up():
        if not manage_docker:
            raise SystemExit("Docker is not running (use --manage-docker to start it automatically)")
        start_docker()
        started = True
    try:
        print("\n=== SCORE ===")
        daily.step_fetch()
        daily.step_upload()
        daily.step_enrich()
        ensure_stream()
        before = batches_done()
        newest = handoff_new_hours()
        if newest:
            for _ in range(90):                       # up to 15 min for the stream to finish the batch
                if batches_done() > before:
                    break
                time.sleep(10)
            else:
                raise RuntimeError("stream did not finish the new batch in 15 min - watermark NOT advanced")
            open(WATERMARK, "w").write(newest)
            refresh_site()
        print("score stage done")
    finally:
        if started:
            stop_docker()


def dispatch_stage():
    print("\n=== DISPATCH ===")
    args = [sys.executable, os.path.join(HERE, "send_alerts.py")]
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        args.append("--poll-subscribers")
    subprocess.run(args)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--once", choices=["score", "dispatch", "both"])
    ap.add_argument("--loop", action="store_true", help="dispatch every hour; score every --score-every hours")
    ap.add_argument("--score-every", type=int, default=6)
    ap.add_argument("--manage-docker", action="store_true")
    a = ap.parse_args()
    if a.once:
        if a.once in ("score", "both"):
            score_stage(a.manage_docker)
        if a.once in ("dispatch", "both"):
            dispatch_stage()
        return
    if not a.loop:
        ap.print_help()
        return
    tick = 0
    while True:
        t0 = time.time()
        try:
            if tick % a.score_every == 0:
                score_stage(a.manage_docker)
            dispatch_stage()
        except Exception as e:                      # one bad hour must not kill the loop
            print(f"[{datetime.now():%H:%M}] cycle failed: {e}", file=sys.stderr)
            try:
                dispatch_stage()                    # still alert from the last good forecast
            except Exception:
                pass
        tick += 1
        time.sleep(max(60, 3600 - (time.time() - t0)))


if __name__ == "__main__":
    main()
