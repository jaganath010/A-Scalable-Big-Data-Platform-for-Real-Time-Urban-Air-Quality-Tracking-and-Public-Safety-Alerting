"""
================================================================================
PHASE 0c - HONEST EXPANSION OF YOUR OWN DATASET
================================================================================
Project : A Scalable Big Data Platform for Real-Time Urban Air Quality Tracking
Course  : 23AID302 - Big Data Analytics

Rebuilds a 20+ GB dataset from YOUR real CPCB rows only. No external source.
The output is simultaneously EXPANDED and REPAIRED.

--------------------------------------------------------------------------------
WHAT WAS WRONG WITH THE OLD RIG, AND WHAT THIS DOES INSTEAD
--------------------------------------------------------------------------------
  old: noise applied to EVERY numeric column        -> is_rush_hour got 24,725
                                                       distinct values, and
                                                       variation_id got 29,918
  new: only continuous PHYSICAL measurements are perturbed. Flags, IDs,
       categories and timestamps are copied or recomputed, never sampled.

  old: independent (i.i.d.) noise per row           -> changed the temporal
                                                       structure; synthetic rows
                                                       ended up EASIER to predict
                                                       than real ones
                                                       (persistence R2 0.856 vs 0.733)
  new: AR(1) perturbation in continuous time. The noise itself is
       autocorrelated with the same decay as the data, so the lag-1..6
       autocorrelation of the synthetic series matches the real one. This is
       THE fix - it is what makes synthetic rows exactly as hard as real ones.

  old: no bounds check                              -> humidity 104.999%,
                                                       traffic index 110.2
  new: every perturbed value is clamped to its physical range.

  old: gaps were filled, making synthetic data denser than reality
  new: THE MISSINGNESS PATTERN IS PRESERVED EXACTLY. If the real row had no
       PM2.5 reading, neither does its synthetic counterpart. Densifying the
       series is the subtlest way to make fake data look easy.

  old: synthetic rows interleaved with real ones under the same station_id
  new: each synthetic series is a SEPARATE SYNTHETIC STATION with its own id
       (e.g. AP001~S03). Real and synthetic never share a time series, so the
       T+1 window never mixes them, and "test on real only" is a one-line filter.

--------------------------------------------------------------------------------
WHY TWO PASSES
--------------------------------------------------------------------------------
The source file is NOT sorted by station. Measured: a 900k-row slice holds only
12 distinct stations but 9,071 station-runs - rows round-robin between stations
(AP001, AP002, AP003, AP001, AP002, ...). A single streaming pass that flushed
on "station changed" would chop every station into ~100-row fragments, and each
fragment would get its own independent AR(1) state - destroying exactly the
temporal continuity this generator exists to preserve.

  PASS 1  stream the source, repair each real row, append it to a per-station
          spill file. Gives the EXACT real row count, so the scale factor is
          computed rather than estimated.
  PASS 2  each station's spill file is a complete series. Sort it by timestamp,
          then emit the real rows plus N synthetic siblings. Workers run one
          station each, so memory stays at one station.

--------------------------------------------------------------------------------
THE METHOD
--------------------------------------------------------------------------------
For each real station S with hourly series x(t):
  1. estimate phi = lag-1 autocorrelation of log x(t)   [from S's own data]
  2. for each synthetic sibling k = 1..N:
         eps(t) = phi^dt * eps(t-1) + sqrt(1 - phi^(2dt)) * sigma * z
         where dt is the ACTUAL gap in hours, so gaps decorrelate correctly
     emit x_syn(t) = clamp( x(t) * exp(sigma*eps) )  [concentrations]
                     x(t) + scale*eps                [temperature, pressure]
                     circular wrap                   [wind direction]
                     zero-preserving                 [rainfall]
  3. copy timestamps, flags, categories unchanged; repair the corrupted ones.

A disclosed generative model fitted to your real data - the same idea as a
TPC-H scale factor. Scientific claims rest on the real subset; the synthetic
scale-out demonstrates systems scalability. Two claims, both honest, separated
by the `data_source` column.

RUN
    python 00c_expand_dataset.py --src "E:\\Big Data jagan\\final_air_quality_dataset_22gb_balanced.csv" \
                                 --out E:\\airquality_expanded --target-gb 22
    python 00d_validate_expansion.py --dir E:\\airquality_expanded    # MUST PASS
================================================================================
"""

import argparse
import csv
import datetime as dt
import glob
import math
import os
import random
import shutil
import sys
import time
from multiprocessing import Pool

# ------------------------------------------------------------------------------
# OUTPUT SCHEMA - already pruned to the columns that survived the audit,
# already repaired. See COLUMN_DECISION_REPORT.md.
# ------------------------------------------------------------------------------
OUT_COLS = [
    "station_id", "state", "city", "from_date",
    "pm25", "pm10", "no2", "so2", "co", "o3", "nh3",
    "wd_degree", "solar_radiation", "pressure",
    "temperature_c", "humidity_percent", "wind_speed_ms", "rainfall_mm",
    "weather_condition", "traffic_index", "is_rush_hour",
    "year", "month", "day", "hour", "day_of_week", "is_weekend", "season",
    "climate_type", "urbanization_index",
    "data_source", "source_station",
]
CI = {c: i for i, c in enumerate(OUT_COLS)}

# Perturbation mode + physical bounds. Anything not listed is copied verbatim.
#   lognorm  : strictly positive concentration, multiplicative noise
#   additive : can be zero or negative, additive noise
#   bounded  : additive noise then hard clamp
#   circular : wraps at 360
#   zeroinfl : dry hours stay exactly dry
PERTURB = {
    "pm25":             ("lognorm",    0.0, 2000.0),
    "pm10":             ("lognorm",    0.0, 3000.0),
    "no2":              ("lognorm",    0.0, 1000.0),
    "so2":              ("lognorm",    0.0, 2000.0),
    "co":               ("lognorm",    0.0,  100.0),
    "o3":               ("lognorm",    0.0, 1000.0),
    "nh3":              ("lognorm",    0.0, 2000.0),
    "solar_radiation":  ("lognorm",    0.0, 1500.0),
    "traffic_index":    ("lognorm",    0.0,  100.0),
    "wind_speed_ms":    ("lognorm",    0.0,   60.0),
    "temperature_c":    ("additive", -30.0,   60.0),
    "pressure":         ("additive", 700.0, 1100.0),
    "humidity_percent": ("bounded",    0.0,  100.0),
    "wd_degree":        ("circular",   0.0,  360.0),
    "rainfall_mm":      ("zeroinfl",   0.0,  500.0),
}
PERTURB_IDX = [(CI[c], c, m, lo, hi) for c, (m, lo, hi) in PERTURB.items()]

ADDITIVE_SCALE = {"temperature_c": 1.5, "pressure": 2.0,
                  "humidity_percent": 3.0, "wd_degree": 12.0}

SIGMA_DEFAULT = 0.08
PHI_FLOOR, PHI_CEIL = 0.55, 0.97

_W = {}


def f(v):
    if v is None:
        return None
    v = v.strip()
    if v == "" or v.lower() in ("nan", "none", "null"):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def fmt(v):
    if v is None:
        return ""
    return f"{v:.4f}".rstrip("0").rstrip(".")


# ==============================================================================
# PASS 1 - spill writer with a bounded set of open handles
# ==============================================================================
class Spiller:
    """Appends rows to spill/<station>.csv, keeping at most `cap` files open."""

    def __init__(self, root, cap=200):
        self.root = root
        self.cap = cap
        self.open = {}
        self.counts = {}
        os.makedirs(root, exist_ok=True)

    def _path(self, sid):
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in sid)
        return os.path.join(self.root, f"{safe}.csv")

    def write(self, sid, row):
        fh = self.open.get(sid)
        if fh is None:
            if len(self.open) >= self.cap:
                k, v = next(iter(self.open.items()))
                v.close()
                del self.open[k]
            fh = open(self._path(sid), "a", newline="", encoding="utf-8")
            self.open[sid] = fh
        fh.write(row)
        self.counts[sid] = self.counts.get(sid, 0) + 1

    def close(self):
        for fh in self.open.values():
            fh.close()
        self.open.clear()


# ==============================================================================
# PASS 2 - per-station generation
# ==============================================================================
def estimate_phi(series):
    """Lag-1 autocorrelation of log pm25 over genuinely consecutive hours,
    estimated from the station's OWN data so the perturbation inherits the real
    decay rate instead of a hard-coded guess."""
    xs = [(t, math.log(v)) for t, v in series if v is not None and v > 0]
    if len(xs) < 50:
        return 0.90
    pairs = [(xs[i][1], xs[i + 1][1]) for i in range(len(xs) - 1)
             if xs[i + 1][0] - xs[i][0] == 3600]
    if len(pairs) < 30:
        return 0.90
    n = len(pairs)
    ma = sum(a for a, _ in pairs) / n
    mb = sum(b for _, b in pairs) / n
    cov = sum((a - ma) * (b - mb) for a, b in pairs)
    va = sum((a - ma) ** 2 for a, _ in pairs)
    vb = sum((b - mb) ** 2 for _, b in pairs)
    if va <= 0 or vb <= 0:
        return 0.90
    return max(PHI_FLOOR, min(PHI_CEIL, cov / math.sqrt(va * vb)))


def _init(out_dir, sigma, scale, seed):
    pid = os.getpid()
    fh = open(os.path.join(out_dir, f"part-{pid}.csv"), "w",
              newline="", encoding="utf-8")
    fh.write(",".join(OUT_COLS) + "\n")
    _W.update(fh=fh, sigma=sigma, scale=scale, seed=seed, real=0, syn=0)


def _finalize(_):
    if "fh" in _W:
        _W["fh"].flush()
        _W["fh"].close()
    return _W.get("real", 0), _W.get("syn", 0)


def build_station(spill_path):
    fh = _W["fh"]
    sigma = _W["sigma"]
    n_syn = _W["scale"]

    rows = []
    with open(spill_path, newline="", encoding="utf-8", errors="replace") as sf:
        for r in csv.reader(sf):
            if len(r) != len(OUT_COLS):
                continue
            try:
                ts = int(dt.datetime.strptime(
                    r[CI["from_date"]], "%Y-%m-%d %H:%M:%S").timestamp())
            except Exception:
                continue
            rows.append((ts, r))
    if not rows:
        return 0, 0

    # THE FIX: one complete, time-ordered series per station.
    rows.sort(key=lambda x: x[0])

    for _, r in rows:
        fh.write(",".join(r) + "\n")
    _W["real"] += len(rows)

    if n_syn <= 0:
        return len(rows), 0

    i_pm = CI["pm25"]
    phi = estimate_phi([(ts, f(r[i_pm])) for ts, r in rows])
    base_id = rows[0][1][CI["station_id"]]

    for k in range(1, n_syn + 1):
        rng = random.Random((hash(base_id) & 0xFFFFFFFF) ^ (k * 7919) ^ _W["seed"])
        syn_id = f"{base_id}~S{k:02d}"
        eps = {}
        prev_ts = None

        for ts, r in rows:
            out = list(r)
            out[CI["station_id"]] = syn_id
            out[CI["data_source"]] = "synthetic"
            out[CI["source_station"]] = base_id

            dt_h = 0.0 if prev_ts is None else (ts - prev_ts) / 3600.0
            prev_ts = ts

            for idx, col, mode, lo, hi in PERTURB_IDX:
                v = f(r[idx])
                # MISSINGNESS IS PRESERVED. A gap in the real series stays a gap.
                if v is None:
                    continue

                p = eps.get(col)
                if p is None or dt_h <= 0 or dt_h > 72:
                    e = rng.gauss(0.0, 1.0)
                else:
                    d = phi ** dt_h
                    e = d * p + math.sqrt(max(0.0, 1.0 - d * d)) * rng.gauss(0.0, 1.0)
                eps[col] = e

                if mode == "lognorm":
                    nv = v * math.exp(sigma * e)
                elif mode == "additive":
                    nv = v + ADDITIVE_SCALE.get(col, 1.0) * e
                elif mode == "bounded":
                    nv = v + ADDITIVE_SCALE.get(col, 3.0) * e
                elif mode == "circular":
                    out[idx] = fmt((v + ADDITIVE_SCALE.get(col, 12.0) * e) % 360.0)
                    continue
                elif mode == "zeroinfl":
                    # A dry hour stays exactly dry - perturbing zeros would
                    # invent rainfall that never fell.
                    nv = 0.0 if v <= 0.0 else v * math.exp(sigma * e)
                else:
                    continue

                out[idx] = fmt(max(lo, min(hi, nv)))

            fh.write(",".join(out) + "\n")
        _W["syn"] += len(rows)

    return len(rows), len(rows) * n_syn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="your existing 23 GB CSV")
    ap.add_argument("--out", required=True, help="output directory")
    ap.add_argument("--target-gb", type=float, default=22.0)
    ap.add_argument("--scale", type=int, default=-1,
                    help="synthetic siblings per real station (overrides --target-gb)")
    ap.add_argument("--sigma", type=float, default=SIGMA_DEFAULT)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 1))
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--real-only", action="store_true")
    ap.add_argument("--keep-spill", action="store_true")
    ap.add_argument("--source-tag", default="original",
                    help="value of data_source marking genuinely real rows")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    spill_root = os.path.join(args.out, "_spill")
    if os.path.isdir(spill_root):
        shutil.rmtree(spill_root)
    src_size = os.path.getsize(args.src)

    fh = open(args.src, newline="", encoding="utf-8", errors="replace")
    rd = csv.reader(fh)
    hdr = next(rd)
    ix = {c: i for i, c in enumerate(hdr)}
    need = ["station_id", "state", "city", "from_date", "pm25", "data_source"]
    miss = [c for c in need if c not in ix]
    if miss:
        sys.exit(f"source is missing required columns: {miss}")

    def g(r, c):
        i = ix.get(c)
        return r[i] if i is not None and i < len(r) else ""

    print(f">>> source : {args.src}  ({src_size / 2**30:.2f} GB)")
    print(f">>> real base: rows tagged data_source='{args.source_tag}'")
    print(f">>> perturbation: AR(1), sigma={args.sigma}, phi estimated per station")
    print(">>> PASS 1 - repair + partition by station ...")

    def make_row(r):
        try:
            ts = dt.datetime.strptime(g(r, "from_date").strip(), "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

        wd = None
        for c in ("wind_direction", "wd_(deg)", "wd_()", "wd_(degree_c)"):
            wd = f(g(r, c))
            if wd is not None:
                break

        h = f(g(r, "dynamic_humidity_percent"))
        ti = f(g(r, "traffic_index"))
        # REPAIR: flags were corrupted by the old rig's blind noise injection.
        rh = f(g(r, "is_rush_hour"))
        we = f(g(r, "is_weekend"))

        def i_(c):
            v = f(g(r, c))
            return "" if v is None else str(int(round(v)))

        return [
            g(r, "station_id"), g(r, "state"), g(r, "city"),
            ts.strftime("%Y-%m-%d %H:%M:%S"),
            fmt(f(g(r, "pm25"))), fmt(f(g(r, "pm10"))), fmt(f(g(r, "no2"))),
            fmt(f(g(r, "so2"))), fmt(f(g(r, "co"))), fmt(f(g(r, "o3"))),
            fmt(f(g(r, "nh3"))),
            fmt(None if wd is None else wd % 360.0),
            fmt(f(g(r, "sr_(w/mt2)"))), fmt(f(g(r, "bp_(mmhg)"))),
            fmt(f(g(r, "dynamic_temperature_c"))),
            fmt(None if h is None else max(0.0, min(100.0, h))),      # REPAIR
            fmt(f(g(r, "dynamic_wind_speed_ms"))), fmt(f(g(r, "rainfall_mm"))),
            g(r, "weather_condition"),
            fmt(None if ti is None else max(0.0, min(100.0, ti))),    # REPAIR
            "0" if rh is None else str(int(round(rh) > 0)),           # REPAIR
            i_("year"), i_("month"), i_("day"), i_("hour"), i_("day_of_week"),
            "0" if we is None else str(int(round(we) > 0)),           # REPAIR
            g(r, "season"), g(r, "climate_type"),
            fmt(f(g(r, "urbanization_index"))),
            "real", g(r, "station_id"),
        ]

    sp = Spiller(spill_root)
    seen = real_rows = real_bytes = 0
    t0 = time.time()
    for r in rd:
        seen += 1
        if g(r, "data_source") != args.source_tag:
            continue
        out = make_row(r)
        if out is None:
            continue
        # commas never appear inside these fields (free-text columns were dropped)
        line = ",".join(out) + "\n"
        sp.write(out[0], line)
        real_rows += 1
        real_bytes += len(line)
        if seen % 5_000_000 == 0:
            print(f"    ...{seen:,} source rows -> {real_rows:,} real "
                  f"({time.time() - t0:.0f}s)", flush=True)
    sp.close()
    fh.close()

    if real_rows == 0:
        sys.exit(f"no rows tagged data_source='{args.source_tag}' were found")

    real_gb = real_bytes / 2**30
    stations = len(sp.counts)

    if args.real_only:
        scale = 0
    elif args.scale >= 0:
        scale = args.scale
    else:
        scale = max(0, math.ceil(args.target_gb / max(real_gb, 1e-9)) - 1)

    print("-" * 72)
    print(f"  source rows read     : {seen:,}")
    print(f"  REAL rows extracted  : {real_rows:,}")
    print(f"  distinct stations    : {stations:,}")
    print(f"  real-only size       : {real_gb:.2f} GB  "
          f"({real_bytes / max(1, real_rows):.0f} bytes/row, {len(OUT_COLS)} cols)")
    print(f"  synthetic per station: {scale}   (scale factor {scale + 1}x)")
    print(f"  projected total      : {real_gb * (scale + 1):.2f} GB")
    print("-" * 72)
    print(">>> PASS 2 - generating ...")

    spill_files = sorted(glob.glob(os.path.join(spill_root, "*.csv")))
    t1 = time.time()
    tot_real = tot_syn = 0
    with Pool(args.workers, initializer=_init,
              initargs=(args.out, args.sigma, scale, args.seed)) as pool:
        for i, (nr, ns) in enumerate(
                pool.imap_unordered(build_station, spill_files, chunksize=1), 1):
            tot_real += nr
            tot_syn += ns
            if i % 50 == 0 or i == len(spill_files):
                print(f"    ...{i}/{len(spill_files)} stations  "
                      f"({time.time() - t1:.0f}s)", flush=True)
        pool.map(_finalize, range(args.workers))

    total = sum(os.path.getsize(p)
                for p in glob.glob(os.path.join(args.out, "part-*.csv")))

    if not args.keep_spill:
        shutil.rmtree(spill_root, ignore_errors=True)

    print("=" * 72)
    print("EXPANSION COMPLETE")
    print("=" * 72)
    print(f"  stations processed : {len(spill_files):,}")
    print(f"  real rows          : {tot_real:,}")
    print(f"  synthetic rows     : {tot_syn:,}")
    print(f"  total rows         : {tot_real + tot_syn:,}")
    print(f"  scale factor       : {scale + 1}x")
    print(f"  output size        : {total / 2**30:.2f} GB")
    print(f"  output dir         : {args.out}")
    print(f"  elapsed            : {time.time() - t0:.0f}s")
    print("-" * 72)
    print("  NEXT - this is not optional:")
    print(f"    python 00d_validate_expansion.py --dir {args.out}")
    print("    If it FAILS, do not use the output.")
    print("=" * 72)


if __name__ == "__main__":
    main()
