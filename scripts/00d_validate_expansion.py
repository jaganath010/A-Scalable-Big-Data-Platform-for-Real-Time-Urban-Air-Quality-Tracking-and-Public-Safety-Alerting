"""
================================================================================
PHASE 0d - EXPANSION VALIDATOR  (run this every time; treat FAIL as blocking)
================================================================================
Compares the SYNTHETIC rows against the REAL rows on the properties that a
generator can silently get wrong. The old rig would have failed test 1 outright.

  1. PERSISTENCE R2      <- THE test. If synthetic rows are easier to predict
                            than real ones, every metric you report is inflated
                            by the synthetic majority. Old rig: 0.856 vs 0.733.
  2. LAG-1..6 AUTOCORRELATION of log PM2.5  <- catches i.i.d. noise, which
                            decorrelates, and interpolation, which over-smooths.
  3. MARGINAL QUANTILES  <- p5/p25/p50/p75/p95 must line up; catches drift and
                            variance inflation.
  4. MISSINGNESS RATE    <- synthetic must be exactly as sparse as real.
                            Densifying is the subtlest way to fake easy data.
  5. CROSS-CORRELATION   <- pm25~pm10 and pm25~no2; catches per-column noise
                            that destroys the relationships between pollutants.

RUN
    python 00d_validate_expansion.py --dir E:\\airquality_expanded
    python 00d_validate_expansion.py --dir E:\\airquality_expanded --max-rows 8000000
================================================================================
"""

import argparse
import collections
import csv
import datetime as dt
import glob
import math
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TOL_PERSIST = 0.05   # |R2_syn - R2_real|
TOL_ACF     = 0.05
TOL_QUANT   = 0.12   # relative
TOL_MISS    = 0.02   # absolute fraction
TOL_XCORR   = 0.08


def f(v):
    v = (v or "").strip()
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def r2_rmse(pairs):
    if len(pairs) < 200:
        return None, None
    ys = [b for _, b in pairs]
    m = sum(ys) / len(ys)
    sst = sum((y - m) ** 2 for y in ys)
    ssr = sum((b - a) ** 2 for a, b in pairs)
    if sst <= 0:
        return None, None
    return 1 - ssr / sst, math.sqrt(ssr / len(pairs))


def corr(pairs):
    n = len(pairs)
    if n < 200:
        return None
    ma = sum(a for a, _ in pairs) / n
    mb = sum(b for _, b in pairs) / n
    cov = sum((a - ma) * (b - mb) for a, b in pairs)
    va = sum((a - ma) ** 2 for a, _ in pairs)
    vb = sum((b - mb) ** 2 for _, b in pairs)
    if va <= 0 or vb <= 0:
        return None
    return cov / math.sqrt(va * vb)


def quantiles(xs, qs=(0.05, 0.25, 0.5, 0.75, 0.95)):
    if not xs:
        return {}
    s = sorted(xs)
    return {q: s[min(len(s) - 1, int(q * len(s)))] for q in qs}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--stations", type=int, default=10,
                    help="number of PARENT stations to compare (paired sample)")
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.dir, "part-*.csv")))
    if not files:
        sys.exit(f"no part-*.csv found in {args.dir}")

    # --------------------------------------------------------------------------
    # PAIRED SAMPLING - this must compare like with like.
    #
    # Every parent station emits 1 real series and N synthetic siblings, so a
    # naive "read the first K rows of each group" walks MUCH further through the
    # station list for real rows than for synthetic ones, and ends up comparing
    # different stations. Station composition dominates every statistic here
    # (pm25 distribution, sparsity and persistence all vary hugely by station),
    # so that comparison is meaningless.
    #
    # Instead: pick a fixed set of PARENT stations via `source_station`, and take
    # ALL their rows - real and synthetic alike. A station's rows are written by
    # a single worker and are contiguous, so reading whole files keeps each
    # selected station complete.
    # --------------------------------------------------------------------------
    selected = set()
    tracks = collections.defaultdict(list)
    miss = collections.Counter()
    tot = collections.Counter()
    grp_stations = collections.defaultdict(set)

    for path in files:
        with open(path, newline="", encoding="utf-8", errors="replace") as fh:
            for r in csv.DictReader(fh):
                src = r.get("source_station", "")
                if src not in selected:
                    if len(selected) >= args.stations:
                        continue
                    selected.add(src)
                grp = "real" if r.get("data_source", "") == "real" else "synthetic"
                tot[grp] += 1
                grp_stations[grp].add(r.get("station_id", ""))
                pm = f(r.get("pm25"))
                if pm is None:
                    miss[grp] += 1
                try:
                    ts = int(dt.datetime.strptime(
                        r["from_date"], "%Y-%m-%d %H:%M:%S").timestamp())
                except Exception:
                    continue
                tracks[(grp, r["station_id"])].append(
                    (ts, pm, f(r.get("pm10")), f(r.get("no2"))))
        if len(selected) >= args.stations:
            break

    if tot["synthetic"] == 0:
        sys.exit("no synthetic rows found - was the expander run with --real-only?")
    if tot["real"] == 0:
        sys.exit("no real rows found in the sampled files")

    pers = collections.defaultdict(list)
    acf = collections.defaultdict(lambda: collections.defaultdict(list))
    vals = collections.defaultdict(list)
    xc = collections.defaultdict(lambda: collections.defaultdict(list))

    for (grp, _), seq in tracks.items():
        seq.sort(key=lambda x: x[0])
        by_ts = {t: (a, b, c) for t, a, b, c in seq}
        for t, pm, p10, n2 in seq:
            if pm is not None:
                vals[grp].append(pm)
                if p10 is not None:
                    xc[grp]["pm25~pm10"].append((math.log(max(pm, .01)), math.log(max(p10, .01))))
                if n2 is not None:
                    xc[grp]["pm25~no2"].append((math.log(max(pm, .01)), math.log(max(n2, .01))))
            for lag in (1, 2, 3, 6):
                nxt = by_ts.get(t + 3600 * lag)
                if pm is not None and pm > 0 and nxt and nxt[0] is not None and nxt[0] > 0:
                    acf[grp][lag].append((math.log(pm), math.log(nxt[0])))
                    if lag == 1:
                        pers[grp].append((pm, nxt[0]))

    print("=" * 74)
    print("EXPANSION VALIDATION")
    print("=" * 74)
    print(f"  paired on {len(selected)} parent station(s): "
          f"{', '.join(sorted(selected)[:8])}{' ...' if len(selected) > 8 else ''}")
    print(f"  rows sampled   real={tot['real']:,} ({len(grp_stations['real'])} series)"
          f"   synthetic={tot['synthetic']:,} ({len(grp_stations['synthetic'])} series)")
    print("-" * 74)

    failures = []

    # ---- 1. persistence -----------------------------------------------------
    rr, rrm = r2_rmse(pers["real"])
    sr, srm = r2_rmse(pers["synthetic"])
    print("  1. PERSISTENCE R2  (predict pm25(t+1) = pm25(t))")
    if rr is None or sr is None:
        print("     insufficient consecutive pairs - INCONCLUSIVE")
        failures.append("persistence: inconclusive")
    else:
        d = abs(sr - rr)
        ok = d <= TOL_PERSIST
        print(f"     real      R2={rr:7.4f}  RMSE={rrm:8.3f}  n={len(pers['real']):,}")
        print(f"     synthetic R2={sr:7.4f}  RMSE={srm:8.3f}  n={len(pers['synthetic']):,}")
        print(f"     |delta| = {d:.4f}  (tolerance {TOL_PERSIST})   "
              f"{'PASS' if ok else 'FAIL'}")
        if not ok:
            failures.append(f"persistence R2 differs by {d:.4f}")
            if sr > rr:
                print("     -> synthetic is EASIER than real. Lower --sigma or check that")
                print("        missingness is being preserved (densified data reads as easy).")
            else:
                print("     -> synthetic is HARDER than real. --sigma is too high.")

    # ---- 2. autocorrelation -------------------------------------------------
    print("\n  2. AUTOCORRELATION of log pm25")
    for lag in (1, 2, 3, 6):
        cr = corr(acf["real"][lag])
        cs = corr(acf["synthetic"][lag])
        if cr is None or cs is None:
            continue
        d = abs(cs - cr)
        ok = d <= TOL_ACF
        print(f"     lag {lag}h : real={cr:6.4f}  syn={cs:6.4f}  |d|={d:6.4f}  "
              f"{'PASS' if ok else 'FAIL'}")
        if not ok:
            failures.append(f"ACF lag{lag} differs by {d:.4f}")

    # ---- 3. marginals -------------------------------------------------------
    print("\n  3. MARGINAL QUANTILES of pm25 (ug/m3)")
    qr, qs = quantiles(vals["real"]), quantiles(vals["synthetic"])
    for q in (0.05, 0.25, 0.5, 0.75, 0.95):
        a, b = qr.get(q), qs.get(q)
        if a is None or b is None or a == 0:
            continue
        rel = abs(b - a) / a
        ok = rel <= TOL_QUANT
        print(f"     p{int(q*100):<3} real={a:9.2f}  syn={b:9.2f}  rel={rel:6.3f}  "
              f"{'PASS' if ok else 'FAIL'}")
        if not ok:
            failures.append(f"quantile p{int(q*100)} off by {rel:.3f}")

    # ---- 4. missingness -----------------------------------------------------
    print("\n  4. MISSINGNESS of pm25")
    mr = miss["real"] / max(1, tot["real"])
    ms = miss["synthetic"] / max(1, tot["synthetic"])
    d = abs(ms - mr)
    ok = d <= TOL_MISS
    print(f"     real={100*mr:6.2f}%   synthetic={100*ms:6.2f}%   |d|={100*d:.2f}pp  "
          f"{'PASS' if ok else 'FAIL'}")
    if not ok:
        failures.append(f"missingness differs by {100*d:.2f}pp")
        print("     -> the generator is filling gaps. Synthetic must be exactly as sparse.")

    # ---- 5. cross-correlation ----------------------------------------------
    print("\n  5. CROSS-CORRELATION between pollutants (log space)")
    for k in ("pm25~pm10", "pm25~no2"):
        cr, cs = corr(xc["real"][k]), corr(xc["synthetic"][k])
        if cr is None or cs is None:
            continue
        d = abs(cs - cr)
        ok = d <= TOL_XCORR
        print(f"     {k:<12} real={cr:6.4f}  syn={cs:6.4f}  |d|={d:6.4f}  "
              f"{'PASS' if ok else 'FAIL'}")
        if not ok:
            failures.append(f"{k} correlation differs by {d:.4f}")

    print("=" * 74)
    if failures:
        print(f"  RESULT: FAIL  ({len(failures)} check(s))")
        for x in failures:
            print(f"    - {x}")
        print("\n  Do NOT use this output. Fix the generator and regenerate.")
        return 1
    print("  RESULT: PASS")
    print("  Synthetic rows are statistically indistinguishable from real ones on")
    print("  predictability, temporal structure, distribution, sparsity and")
    print("  inter-pollutant relationships. Safe to use for scale-out - and still")
    print("  evaluate on data_source='real' only.")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())
