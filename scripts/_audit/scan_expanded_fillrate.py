"""
================================================================================
AUDIT - STRATIFIED FILL-RATE / RANGE SCAN OF THE EXPANDED DATASET
================================================================================
Project : 23AID302 - Big Data Analytics

Produces every per-column number quoted in DATASET_REPORT.docx section 3.3
(fill %, min, max, mean, median, distinct count) plus the categorical
breakdowns, year distribution, and the duplicate-key measurement.

METHOD
  The dataset is 27.48 GB across 23 CSV part files - too large to read whole
  for an audit. This takes a STRATIFIED sample: 24 evenly spaced byte offsets
  per file, reading a 400 KB chunk at each. The first (partial) line after each
  seek is discarded so no malformed row enters the sample.

  Byte-offset sampling is used rather than random row sampling because the
  files are sorted by station; offset sampling therefore spreads the sample
  across stations and time rather than concentrating it.

  Measured sample size: ~1.09 million rows.

CAVEAT
  Because the sample is spread by BYTE offset and stations vary in row width,
  the real/synthetic split of the sample (13.81% / 86.19%) does not exactly
  match the whole-file split (11.1% / 88.9%). Aggregate fill rates and ranges
  are stable at this sample size; the real-vs-synthetic comparison in
  scan_expanded_coverage.py is a SAMPLE statistic and is labelled as such.

RUN
    python scan_expanded_fillrate.py
================================================================================
"""

import collections
import glob
import os
import statistics

D = r"F:\SEM 5 NOTES\Big Data\Project_Final\airquality_expanded"

OFFSETS = 24          # sample points per file
CHUNK = 400_000       # bytes read at each sample point

CATCOL = {"state", "city", "weather_condition", "season", "climate_type", "data_source"}
NUMCOL = {"pm25", "pm10", "no2", "so2", "co", "o3", "nh3", "wd_degree",
          "solar_radiation", "pressure", "temperature_c", "humidity_percent",
          "wind_speed_ms", "rainfall_mm", "traffic_index", "is_rush_hour",
          "urbanization_index", "year", "hour"}


def main():
    files = sorted(glob.glob(os.path.join(D, "part-*.csv")))
    if not files:
        raise SystemExit(f"no part-*.csv under {D}")
    hdr = open(files[0], encoding="utf-8", errors="replace").readline().strip().split(",")
    nc = len(hdr)
    idx = {c: i for i, c in enumerate(hdr)}

    filled = [0] * nc
    numvals = collections.defaultdict(list)
    cats = collections.defaultdict(collections.Counter)
    years = collections.Counter()
    dup_probe = collections.Counter()
    stations, srcstations, cities, states = set(), set(), set(), set()
    total = badcols = 0

    for f in files:
        sz = os.path.getsize(f)
        with open(f, "rb") as fh:
            for k in range(OFFSETS):
                fh.seek(int(sz * k / OFFSETS))
                if k:
                    fh.readline()                      # discard partial line
                data = fh.read(CHUNK).decode("utf-8", errors="replace")
                for ln in data.split("\n")[1:-1]:
                    p = ln.rstrip("\r").split(",")
                    if len(p) != nc:
                        badcols += 1
                        continue
                    if p[0] == "station_id":
                        continue
                    total += 1
                    stations.add(p[idx["station_id"]])
                    srcstations.add(p[idx["source_station"]])
                    cities.add(p[idx["city"]])
                    states.add(p[idx["state"]])
                    years[p[idx["year"]]] += 1
                    dup_probe[(p[idx["station_id"]], p[idx["from_date"]])] += 1
                    for i, v in enumerate(p):
                        if v == "":
                            continue
                        filled[i] += 1
                        c = hdr[i]
                        if c in NUMCOL:
                            try:
                                numvals[c].append(float(v))
                            except ValueError:
                                pass
                        elif c in CATCOL:
                            cats[c][v] += 1

    print(f"SAMPLED ROWS: {total:,}   malformed: {badcols}")
    print(f"distinct station_id: {len(stations):,}  source_station: {len(srcstations):,}  "
          f"cities: {len(cities)}  states: {len(states)}\n")

    print("=== FILL RATE / RANGE ===")
    print(f"{'column':22} {'fill%':>7}  {'min':>10} {'max':>10} {'mean':>10} {'median':>10} {'distinct':>9}")
    for i, c in enumerate(hdr):
        pct = 100.0 * filled[i] / total if total else 0.0
        if c in numvals and numvals[c]:
            v = numvals[c]
            print(f"{c:22} {pct:7.2f}  {min(v):10.2f} {max(v):10.2f} "
                  f"{statistics.mean(v):10.2f} {statistics.median(v):10.2f} {len(set(v)):9,}")
        else:
            print(f"{c:22} {pct:7.2f}")

    print("\n=== CATEGORICALS ===")
    for c in ("data_source", "season", "weather_condition", "climate_type"):
        tot = sum(cats[c].values())
        print(f"\n{c}  ({len(cats[c])} distinct)")
        for v, n in cats[c].most_common(15):
            print(f"   {v:28} {n:9,}  {100.0*n/tot:5.2f}%")

    print("\n=== TOP STATES ===")
    tot = sum(cats["state"].values())
    for v, n in cats["state"].most_common(12):
        print(f"   {v:28} {n:9,}  {100.0*n/tot:5.2f}%")

    print("\n=== YEARS ===")
    for y in sorted(years):
        print(f"   {y}: {years[y]:,}  ({100.0*years[y]/total:5.2f}%)")

    print("\n=== DUPLICATE (station_id, from_date) IN SAMPLE ===")
    mult = collections.Counter(dup_probe.values())
    tk = len(dup_probe)
    dk = sum(n for k, n in mult.items() if k > 1)
    print(f"   distinct keys: {tk:,}   keys appearing >1x: {dk:,} ({100.0*dk/tk:.2f}%)")
    for k in sorted(mult):
        print(f"   {k} row(s) per key: {mult[k]:,} keys")


if __name__ == "__main__":
    main()
