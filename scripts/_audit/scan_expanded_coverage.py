"""
================================================================================
AUDIT - AQI CO-COVERAGE AND REAL-vs-SYNTHETIC COMPARISON
================================================================================
Project : 23AID302 - Big Data Analytics

Produces the numbers quoted in DATASET_REPORT.docx sections 3.6 and 7:

  - how many of the 7 CPCB AQI pollutants are present SIMULTANEOUSLY per row
    (measured: all 7 in 43.18%, ZERO in 15.72%) - this is what makes the
    three-tier imputation in Phase 3 mandatory rather than optional
  - real vs synthetic pm25 distribution (mean/median/p95/p99/max/sd)
  - per-source-station pm25 missingness, to show the generator copies the
    real station's gap pattern instead of densifying it

IMPORTANT CAVEAT ON THE REAL-vs-SYNTHETIC RESULT
  This is an UNPAIRED aggregate comparison over a byte-offset sample. The two
  groups do not contain the same station mix, so a difference here is NOT by
  itself proof that the generator distorts the distribution. The statistically
  correct test is the PAIRED one in 00d_validate_expansion.py, which compares
  each synthetic station against its own source_station.

  Quote this scan for the co-coverage numbers. For the fidelity claim, quote
  00d_validate_expansion.py.

RUN
    python scan_expanded_coverage.py
================================================================================
"""

import collections
import glob
import os
import statistics

D = r"F:\SEM 5 NOTES\Big Data\Project_Final\airquality_expanded"

OFFSETS, CHUNK = 24, 400_000
POLL = ["pm25", "pm10", "no2", "so2", "co", "o3", "nh3"]


def main():
    files = sorted(glob.glob(os.path.join(D, "part-*.csv")))
    if not files:
        raise SystemExit(f"no part-*.csv under {D}")
    hdr = open(files[0], encoding="utf-8", errors="replace").readline().strip().split(",")
    idx = {c: i for i, c in enumerate(hdr)}
    nc = len(hdr)
    pi = [idx[c] for c in POLL]

    total = all7 = none7 = 0
    npoll = collections.Counter()
    pm25 = {"real": [], "synthetic": []}
    src_cnt = collections.Counter()
    miss_by_src = collections.defaultdict(lambda: [0, 0])

    for f in files:
        sz = os.path.getsize(f)
        with open(f, "rb") as fh:
            for k in range(OFFSETS):
                fh.seek(int(sz * k / OFFSETS))
                if k:
                    fh.readline()
                for ln in fh.read(CHUNK).decode("utf-8", errors="replace").split("\n")[1:-1]:
                    p = ln.rstrip("\r").split(",")
                    if len(p) != nc or p[0] == "station_id":
                        continue
                    total += 1
                    n = sum(1 for i in pi if p[i] != "")
                    npoll[n] += 1
                    if n == 7:
                        all7 += 1
                    if n == 0:
                        none7 += 1
                    ds = p[idx["data_source"]]
                    src_cnt[ds] += 1
                    if p[idx["pm25"]] != "" and ds in pm25:
                        try:
                            pm25[ds].append(float(p[idx["pm25"]]))
                        except ValueError:
                            pass
                    s = p[idx["source_station"]]
                    miss_by_src[s][0] += 1
                    if p[idx["pm25"]] == "":
                        miss_by_src[s][1] += 1

    print(f"rows sampled: {total:,}")
    print("\n=== SIMULTANEOUS 7-POLLUTANT COVERAGE ===")
    print(f"  all 7 present : {all7:,}  ({100.0*all7/total:.2f}%)")
    print(f"  zero present  : {none7:,}  ({100.0*none7/total:.2f}%)")
    for n in sorted(npoll):
        print(f"  {n} pollutant(s): {npoll[n]:9,}  {100.0*npoll[n]/total:5.2f}%")

    print("\n=== REAL vs SYNTHETIC (unpaired - see caveat in header) ===")
    for ds in ("real", "synthetic"):
        v = pm25[ds]
        if not v:
            continue
        v2 = sorted(v)
        q = lambda fr: v2[int(fr * (len(v2) - 1))]
        print(f"  {ds:10} rows={src_cnt[ds]:9,} ({100.0*src_cnt[ds]/total:5.2f}%)  pm25 n={len(v):,}")
        print(f"             mean={statistics.mean(v):7.2f} med={statistics.median(v):7.2f} "
              f"p05={q(.05):6.2f} p95={q(.95):7.2f} p99={q(.99):7.2f} "
              f"max={max(v):7.2f} sd={statistics.pstdev(v):6.2f}")

    print("\n=== pm25 MISSINGNESS PER SOURCE-STATION GROUP (top 12 by rows) ===")
    for s, (n, m) in sorted(miss_by_src.items(), key=lambda kv: -kv[1][0])[:12]:
        print(f"  {s:12} rows={n:8,}  pm25 missing={100.0*m/n:5.2f}%")


if __name__ == "__main__":
    main()
