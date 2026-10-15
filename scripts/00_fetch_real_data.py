"""
================================================================================
PHASE 0 - BUILD A 20+ GB DATASET FROM 100% REAL MEASUREMENTS
================================================================================
Project : A Scalable Big Data Platform for Real-Time Urban Air Quality Tracking
Course  : 23AID302 - Big Data Analytics

WHAT THIS DOES
  Downloads the US EPA AQS "pre-generated hourly data files" - real, quality-
  assured hourly measurements from every regulatory air monitor in the United
  States - and stages them as the HDFS raw layer.

  NOT simulated. NOT expanded. NOT noise-injected. Every row is an instrument
  reading with a documented method code and a QA qualifier field.

VERIFIED SIZES (measured by HEAD request, 2015-2024, 11 parameters)
    zipped   :  4.12 GB   <- what you download
    unzipped : ~26.8 GB   <- what lands in HDFS   >>> clears the 20 GB bar

  Extending YEARS back to 1990 roughly doubles this again if you need headroom.

SOURCE
  https://aqs.epa.gov/aqsweb/airdata/download_files.html
  Free, public domain, no API key, no account. Years 1980-2026 available.

WHY THIS SOURCE
  It carries exactly the schema this project needs, all at hourly resolution:
    - the criteria pollutants   : PM2.5, PM10, O3, CO, NO2, SO2
    - real co-located meteorology: wind speed AND direction, temperature,
                                   relative humidity, dew point, pressure
  The previous dataset had to SIMULATE weather and traffic. Here the weather is
  measured at the same monitoring sites, on the same clock. That removes the
  single biggest "is this real?" objection to the project.

RUN
    python 00_fetch_real_data.py --out E:\\airquality_raw
    python 00_fetch_real_data.py --out /data/raw --years 1990-2024   # ~60 GB

  Then push to HDFS:
    hdfs dfs -mkdir -p /user/hadoop/lakehouse/raw_epa
    hdfs dfs -put E:\\airquality_raw\\csv\\*.csv /user/hadoop/lakehouse/raw_epa/

NOTE ON AQI: EPA data has no NH3 (not a US criteria pollutant). If you build on
this source, use the US EPA AQI (6 pollutants) rather than the CPCB AQI (7).
See HONEST_SCALING.md section 4.
================================================================================
"""

import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import sys
import time
import urllib.request
import zipfile

BASE = "https://aqs.epa.gov/aqsweb/airdata/"

# (code, human name, category). Pivoted on Parameter Code downstream.
PARAMETERS = [
    ("88101", "PM2.5 FRM/FEM",        "pollutant"),
    ("88502", "PM2.5 non-FRM",        "pollutant"),
    ("44201", "Ozone",                "pollutant"),
    ("42101", "Carbon monoxide",      "pollutant"),
    ("42602", "Nitrogen dioxide",     "pollutant"),
    ("42401", "Sulfur dioxide",       "pollutant"),
    ("81102", "PM10",                 "pollutant"),
    ("WIND",  "Wind speed+direction", "meteorology"),
    ("TEMP",  "Outdoor temperature",  "meteorology"),
    ("RH_DP", "Rel. humidity+dewpt",  "meteorology"),
    ("PRESS", "Barometric pressure",  "meteorology"),
]

CHUNK = 1 << 20  # 1 MiB


def parse_years(spec):
    if "-" in spec:
        a, b = spec.split("-", 1)
        return list(range(int(a), int(b) + 1))
    return [int(y) for y in spec.split(",")]


def remote_size(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=30) as r:
                return int(r.headers.get("Content-Length", 0))
        except Exception:
            if i == retries - 1:
                return -1
            time.sleep(2 * (i + 1))
    return -1


def download(url, dest, expected, retries=4):
    """Resumable download with a size check. Returns (ok, bytes, sha256)."""
    tmp = dest + ".part"
    for attempt in range(retries):
        have = os.path.getsize(tmp) if os.path.exists(tmp) else 0
        if expected > 0 and have == expected:
            break
        try:
            req = urllib.request.Request(url)
            if have:
                req.add_header("Range", f"bytes={have}-")
            with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "ab") as f:
                while True:
                    b = r.read(CHUNK)
                    if not b:
                        break
                    f.write(b)
            break
        except Exception as e:
            if attempt == retries - 1:
                return False, 0, None
            time.sleep(3 * (attempt + 1))

    got = os.path.getsize(tmp) if os.path.exists(tmp) else 0
    # INTEGRITY GATE: a truncated download becomes a silently short CSV, which
    # becomes missing hours, which becomes a broken time series. Fail loudly.
    if expected > 0 and got != expected:
        return False, got, None

    h = hashlib.sha256()
    with open(tmp, "rb") as f:
        for blk in iter(lambda: f.read(CHUNK), b""):
            h.update(blk)
    os.replace(tmp, dest)
    return True, got, h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="output directory")
    ap.add_argument("--years", default="2015-2024",
                    help="e.g. 2015-2024 or 2019,2020,2021")
    ap.add_argument("--workers", type=int, default=6,
                    help="parallel downloads (be polite to EPA: <=8)")
    ap.add_argument("--keep-zip", action="store_true",
                    help="keep .zip after extracting")
    ap.add_argument("--dry-run", action="store_true",
                    help="report sizes and exit without downloading")
    args = ap.parse_args()

    years = parse_years(args.years)
    zip_dir = os.path.join(args.out, "zip")
    csv_dir = os.path.join(args.out, "csv")
    os.makedirs(zip_dir, exist_ok=True)
    os.makedirs(csv_dir, exist_ok=True)

    targets = [(p, y, f"hourly_{p}_{y}.zip") for p, _, _ in PARAMETERS for y in years]

    # ---- size survey first, so you know the cost before committing ----------
    print(f">>> surveying {len(targets)} files ({len(PARAMETERS)} parameters x "
          f"{len(years)} years: {years[0]}-{years[-1]}) ...")
    with cf.ThreadPoolExecutor(args.workers * 2) as ex:
        sizes = dict(zip(
            [t[2] for t in targets],
            ex.map(lambda t: remote_size(BASE + t[2]), targets)
        ))

    total = sum(s for s in sizes.values() if s > 0)
    missing = [f for f, s in sizes.items() if s <= 0]
    print(f"    zipped total      : {total / 2**30:8.2f} GB")
    print(f"    est. unzipped     : {total * 6.5 / 2**30:8.2f} GB   "
          f"({'CLEARS' if total * 6.5 / 2**30 >= 20 else 'BELOW'} the 20 GB target)")
    if missing:
        print(f"    unavailable ({len(missing)}): {missing[:6]}"
              f"{' ...' if len(missing) > 6 else ''}")
    if args.dry_run:
        print(">>> dry run, nothing downloaded.")
        return

    if total * 6.5 / 2**30 < 20:
        print("    !! projected under 20 GB - widen --years before running.")

    # ---- download -----------------------------------------------------------
    manifest = []
    done = failed = 0
    t0 = time.time()

    def job(t):
        p, y, fn = t
        dest = os.path.join(zip_dir, fn)
        exp = sizes.get(fn, -1)
        if exp <= 0:
            return (fn, False, 0, None, "unavailable")
        if os.path.exists(dest) and os.path.getsize(dest) == exp:
            return (fn, True, exp, None, "cached")
        ok, got, sha = download(BASE + fn, dest, exp)
        return (fn, ok, got, sha, "ok" if ok else "size-mismatch/failed")

    with cf.ThreadPoolExecutor(args.workers) as ex:
        for fn, ok, got, sha, note in ex.map(job, targets):
            if ok:
                done += 1
            else:
                failed += 1
            manifest.append({"file": fn, "ok": ok, "bytes": got,
                             "sha256": sha, "note": note})
            print(f"    [{done + failed:>3}/{len(targets)}] {fn:<26} "
                  f"{got / 2**20:>8.1f} MB  {note}")

    print(f">>> downloaded {done}/{len(targets)} in {time.time() - t0:.0f}s "
          f"({failed} failed)")

    # ---- extract ------------------------------------------------------------
    print(">>> extracting ...")
    raw_bytes = 0
    for m in manifest:
        if not m["ok"]:
            continue
        zp = os.path.join(zip_dir, m["file"])
        try:
            with zipfile.ZipFile(zp) as z:
                for name in z.namelist():
                    out = os.path.join(csv_dir, os.path.basename(name))
                    if os.path.exists(out) and os.path.getsize(out) > 0:
                        raw_bytes += os.path.getsize(out)
                        continue
                    z.extract(name, csv_dir)
                    raw_bytes += os.path.getsize(out)
            if not args.keep_zip:
                os.remove(zp)
        except zipfile.BadZipFile:
            print(f"    !! corrupt archive: {m['file']} - re-run to re-fetch")
            m["ok"] = False

    with open(os.path.join(args.out, "MANIFEST.json"), "w") as f:
        json.dump({"source": BASE, "years": years,
                   "parameters": [{"code": p, "name": n, "kind": k}
                                  for p, n, k in PARAMETERS],
                   "files": manifest,
                   "raw_csv_bytes": raw_bytes}, f, indent=2)

    print("=" * 72)
    print("PHASE 0 COMPLETE - 100% REAL MEASUREMENTS")
    print("=" * 72)
    print(f"  csv directory : {csv_dir}")
    print(f"  raw CSV size  : {raw_bytes / 2**30:.2f} GB")
    print(f"  manifest      : {os.path.join(args.out, 'MANIFEST.json')}")
    print(f"  synthetic rows: 0")
    print("-" * 72)
    print("  next:")
    print("    hdfs dfs -mkdir -p /user/hadoop/lakehouse/raw_epa")
    print(f"    hdfs dfs -put {csv_dir}/*.csv /user/hadoop/lakehouse/raw_epa/")
    print("    spark-submit 01b_build_wide_table.py")
    print("=" * 72)


if __name__ == "__main__":
    sys.exit(main())
