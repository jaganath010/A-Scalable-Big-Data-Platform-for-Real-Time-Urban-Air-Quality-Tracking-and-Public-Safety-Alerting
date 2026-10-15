"""
================================================================================
LOCAL REPRODUCTION OF PHASES 4-6  (no Spark - pandas + sklearn)
================================================================================
Runs the SAME logic as 02_feature_extraction.py + 03_train_gbt.py on a subset of
the expanded dataset, so the pipeline can be proven correct on this laptop before
being submitted to the cluster.

It reproduces, identically:
  - dedupe on (station_id, timestamp)
  - T+1 label built ONLY from measured pm25, accepted ONLY when the next row is
    genuinely +3600s   (the fix for the R2=0.58 failure)
  - time-based rolling windows (gap-safe), not positional
  - CPCB AQI from correctly-averaged concentrations
  - cyclical encodings, physical interactions
  - CHRONOLOGICAL split, never random
  - persistence baseline computed on the SAME test rows as the model
  - evaluation on data_source='real' rows only

RUN
  <python312> 03b_local_run.py --dir E:\\airquality_expanded --max-rows 3000000
================================================================================
"""

import argparse
import glob
import os
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

HOUR = 3600

AQI_BP = {
    "pm25": [(0, 30, 0, 50), (30, 60, 51, 100), (60, 90, 101, 200),
             (90, 120, 201, 300), (120, 250, 301, 400), (250, 1000, 401, 500)],
    "pm10": [(0, 50, 0, 50), (50, 100, 51, 100), (100, 250, 101, 200),
             (250, 350, 201, 300), (350, 430, 301, 400), (430, 1000, 401, 500)],
    "no2":  [(0, 40, 0, 50), (40, 80, 51, 100), (80, 180, 101, 200),
             (180, 280, 201, 300), (280, 400, 301, 400), (400, 1000, 401, 500)],
    "so2":  [(0, 40, 0, 50), (40, 80, 51, 100), (80, 380, 101, 200),
             (380, 800, 201, 300), (800, 1600, 301, 400), (1600, 3000, 401, 500)],
    "co":   [(0, 1, 0, 50), (1, 2, 51, 100), (2, 10, 101, 200),
             (10, 17, 201, 300), (17, 34, 301, 400), (34, 100, 401, 500)],
    "o3":   [(0, 50, 0, 50), (50, 100, 51, 100), (100, 168, 101, 200),
             (168, 208, 201, 300), (208, 748, 301, 400), (748, 1000, 401, 500)],
    "nh3":  [(0, 200, 0, 50), (200, 400, 51, 100), (400, 800, 101, 200),
             (800, 1200, 201, 300), (1200, 1800, 301, 400), (1800, 3000, 401, 500)],
}
AQI_WIN = {"pm25": 24, "pm10": 24, "no2": 24, "so2": 24, "nh3": 24, "co": 8, "o3": 8}


def sub_index(x, bps):
    """Piecewise-linear CPCB sub-index. Mirrors sub_index() in
    02_feature_extraction.py so the two pipelines agree."""
    v = np.asarray(x, dtype=float)
    out = np.full(v.shape, np.nan)
    for lo, hi, ilo, ihi in bps:
        m = (v > lo) & (v <= hi)
        out[m] = (ihi - ilo) / (hi - lo) * (v[m] - lo) + ilo
    out[v <= bps[0][0]] = bps[0][2]        # at/below the bottom of band 1
    out[v > bps[-1][1]] = 500.0            # above the top band saturates
    out[np.isnan(v)] = np.nan
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--max-rows", type=int, default=3_000_000)
    ap.add_argument("--synthetic-keep", default="~S01,~S02",
                    help="which synthetic siblings to load (keeps memory sane)")
    ap.add_argument("--train-frac", type=float, default=0.8)
    ap.add_argument("--target", choices=["level", "delta"], default="delta",
                    help="'level' predicts pm25(t+1) directly; 'delta' predicts "
                         "pm25(t+1)-pm25(t) and adds it back. Trees cannot "
                         "extrapolate a linear identity, so 'delta' lets every "
                         "split model the CHANGE instead of re-deriving "
                         "persistence.")
    ap.add_argument("--max-iter", type=int, default=400)
    ap.add_argument("--model", choices=["hgb", "xgb"], default="hgb",
                    help="hgb = sklearn HistGradientBoosting (stands in for "
                         "Spark MLlib GBTRegressor); xgb = XGBoost")
    args = ap.parse_args()

    keep_suffix = tuple(s for s in args.synthetic_keep.split(",") if s)
    files = sorted(glob.glob(os.path.join(args.dir, "part-*.csv")))
    if not files:
        raise SystemExit(f"no part-*.csv in {args.dir}")

    usecols = ["station_id", "city", "from_date", "pm25", "pm10", "no2", "so2",
               "co", "o3", "nh3", "wd_degree", "solar_radiation", "pressure",
               "temperature_c", "humidity_percent", "wind_speed_ms", "rainfall_mm",
               "weather_condition", "traffic_index", "is_rush_hour", "hour",
               "month", "day_of_week", "is_weekend", "season", "climate_type",
               "urbanization_index", "data_source"]

    t0 = time.time()
    print(">>> loading ...")
    parts, n = [], 0
    for path in files:
        for ch in pd.read_csv(path, usecols=usecols, chunksize=500_000,
                              low_memory=False):
            m = (ch["data_source"] == "real") | \
                ch["station_id"].str.endswith(keep_suffix, na=False)
            ch = ch[m]
            parts.append(ch)
            n += len(ch)
            if n >= args.max_rows:
                break
        if n >= args.max_rows:
            break
    df = pd.concat(parts, ignore_index=True)
    del parts
    print(f"    {len(df):,} rows loaded in {time.time()-t0:.0f}s "
          f"(real={int((df.data_source=='real').sum()):,})")

    df["timestamp"] = pd.to_datetime(df["from_date"], errors="coerce")
    df = df.dropna(subset=["timestamp"])
    # NOTE: pandas 3.x stores datetime64 at MICROsecond resolution, so a bare
    # .astype("int64") returns microseconds, not nanoseconds. Casting to
    # datetime64[s] first makes this resolution-independent - without it, hourly
    # gaps collapse to 3 and every T+1 label is silently rejected.
    df["ts_unix"] = df["timestamp"].astype("datetime64[s]").astype("int64")

    # ---- dedupe + one true ordering ---------------------------------------
    # Mirrors Spark's orderBy(pm25.desc_nulls_last()) + row_number()==1:
    # keep the row with the largest non-null pm25 for each (station, hour).
    before = len(df)
    df = (df.sort_values(["station_id", "ts_unix", "pm25"],
                         ascending=[True, True, False], na_position="last")
            .drop_duplicates(["station_id", "ts_unix"], keep="first")
            .sort_values(["station_id", "ts_unix"])
            .reset_index(drop=True))
    print(f">>> dedupe: {before:,} -> {len(df):,}")

    # ---- CPCB rolling averages (TIME-based, so gaps shorten the window) -----
    # df is sorted by (station_id, ts_unix) and groupby sorts groups the same
    # way, so the grouped-rolling result lines up positionally with df.
    print(">>> rolling windows ...")
    idx = df.set_index("timestamp")
    for p, h in AQI_WIN.items():
        roll = (idx.groupby("station_id", sort=True)[p]
                   .rolling(f"{h}h", min_periods=1).mean()
                   .reset_index(level=0, drop=True))
        assert len(roll) == len(df), "grouped-rolling misalignment"
        df[f"{p}_avg{h}h"] = roll.to_numpy()
    for w in (3, 6):
        df[f"pm25_roll_{w}h"] = (idx.groupby("station_id", sort=True)["pm25"]
                                 .rolling(f"{w}h", min_periods=1).mean()
                                 .reset_index(level=0, drop=True).to_numpy())
    del idx

    # ---- AQI ----------------------------------------------------------------
    si = {p: sub_index(df[f"{p}_avg{AQI_WIN[p]}h"], AQI_BP[p]) for p in AQI_BP}
    df["aqi_current"] = np.nanmax(np.vstack([si[p] for p in AQI_BP]), axis=0)

    # ---- T+1 LABEL, temporally validated ------------------------------------
    g = df.groupby("station_id", sort=False)
    df["_next_ts"] = g["ts_unix"].shift(-1)
    df["_next_pm25"] = g["pm25"].shift(-1)     # source column is measured-only
    df["_prev_ts"] = g["ts_unix"].shift(1)
    df["_prev_pm25"] = g["pm25"].shift(1)

    gap_ok = (df["_next_ts"] - df["ts_unix"]) == HOUR
    before = len(df)
    df["target_pm25_next_hour"] = np.where(gap_ok, df["_next_pm25"], np.nan)
    df = df[gap_ok & df["target_pm25_next_hour"].notna()].copy()
    print(f">>> valid +1h labels: {len(df):,} / {before:,} "
          f"({100*len(df)/before:.2f}%)")

    lag_ok = (df["ts_unix"] - df["_prev_ts"]) == HOUR
    df["pm25_lag_1h"] = np.where(lag_ok, df["_prev_pm25"], df["pm25"])
    df["pm25_delta_1h"] = df["pm25"] - df["pm25_lag_1h"]
    df["pm25_surge_ratio"] = df["pm25_roll_3h"] / (df["pm25_avg24h"] + 1e-6)

    # ---- cyclical + interactions -------------------------------------------
    for col, period, name in (("hour", 24, "hour"), ("month", 12, "month"),
                              ("day_of_week", 7, "dow")):
        a = 2 * np.pi * df[col].astype(float) / period
        df[f"{name}_sin"], df[f"{name}_cos"] = np.sin(a), np.cos(a)
    wr = np.radians(df["wd_degree"].astype(float))
    df["wd_sin"], df["wd_cos"] = np.sin(wr), np.cos(wr)

    df["ventilation_index"] = df["traffic_index"] / (df["wind_speed_ms"] + 0.5)
    df["is_raining"] = (df["rainfall_mm"] > 0.1).astype(int)
    df["scrub_factor"] = np.log1p(df["rainfall_mm"].clip(lower=0))
    df["stagnation_index"] = (100 - df["humidity_percent"]) / (df["wind_speed_ms"] + 0.5)
    df["temp_humidity_interaction"] = df["temperature_c"] * df["humidity_percent"] / 100

    FEATURES = [
        "pm25", "pm10", "no2", "so2", "co", "o3", "nh3",
        "aqi_current", "pm25_avg24h", "pm10_avg24h", "co_avg8h", "o3_avg8h",
        "pm25_lag_1h", "pm25_delta_1h", "pm25_roll_3h", "pm25_roll_6h",
        "pm25_surge_ratio",
        "temperature_c", "humidity_percent", "wind_speed_ms", "rainfall_mm",
        "solar_radiation", "pressure", "wd_sin", "wd_cos",
        "traffic_index", "is_rush_hour",
        "hour_sin", "hour_cos", "month_sin", "month_cos", "dow_sin", "dow_cos",
        "is_weekend", "urbanization_index",
        "ventilation_index", "is_raining", "scrub_factor", "stagnation_index",
        "temp_humidity_interaction",
    ]
    for c in ("season", "weather_condition", "climate_type"):
        df[c] = df[c].astype("category").cat.codes
        FEATURES.append(c)

    # ---- CHRONOLOGICAL split ------------------------------------------------
    cut = df["ts_unix"].quantile(args.train_frac)
    train = df[df["ts_unix"] <= cut]
    test = df[df["ts_unix"] > cut]
    test_real = test[test["data_source"] == "real"]
    print(f">>> split at {pd.to_datetime(cut, unit='s')}")
    print(f"    train={len(train):,}  test={len(test):,}  "
          f"test_real={len(test_real):,}")

    X = train[FEATURES].to_numpy(dtype=np.float32)
    y_level = train["target_pm25_next_hour"].to_numpy(dtype=np.float32)
    base_tr = train["pm25"].to_numpy(dtype=np.float32)
    y = y_level if args.target == "level" else (y_level - base_tr)
    fit_mask = ~np.isnan(y)

    print(f">>> training {args.model}, target={args.target} ...")
    t1 = time.time()
    Xf, yf = X[fit_mask], y[fit_mask]

    if args.model == "hgb":
        model = HistGradientBoostingRegressor(
            max_iter=args.max_iter, max_depth=6, learning_rate=0.08,
            min_samples_leaf=40, l2_regularization=1.0,
            early_stopping=True, validation_fraction=0.1, random_state=42)
        model.fit(Xf, yf)
        n_trees = model.n_iter_
    else:
        import xgboost as xgb
        # chronological validation carve-out for early stopping - the rows are
        # already time-ordered within the training block, so the tail is future
        # relative to the head. A random split here would leak.
        cutv = int(len(Xf) * 0.9)
        model = xgb.XGBRegressor(
            n_estimators=max(args.max_iter, 800), max_depth=8,
            learning_rate=0.05, subsample=0.8, colsample_bytree=0.8,
            min_child_weight=20, reg_lambda=2.0, tree_method="hist",
            n_jobs=-1, early_stopping_rounds=40, eval_metric="rmse",
            random_state=42)
        model.fit(Xf[:cutv], yf[:cutv],
                  eval_set=[(Xf[cutv:], yf[cutv:])], verbose=False)
        n_trees = model.best_iteration + 1
    print(f"    fitted {n_trees} trees in {time.time()-t1:.0f}s")

    def report(name, sub):
        if len(sub) < 100:
            print(f"  {name}: too few rows"); return
        yt = sub["target_pm25_next_hour"].to_numpy(dtype=np.float32)
        base = sub["pm25"].to_numpy(dtype=np.float32)
        raw = model.predict(sub[FEATURES].to_numpy(dtype=np.float32))
        # delta mode predicts the CHANGE, so add the current level back before
        # scoring - metrics stay on the raw ug/m3 scale either way.
        pred = raw if args.target == "level" else base + raw
        ok = ~np.isnan(base) & ~np.isnan(pred)
        yt, base, pred = yt[ok], base[ok], pred[ok]
        ok = np.ones(len(yt), dtype=bool)
        print(f"\n  {name}   (n={len(sub):,})")
        print(f"    {'':22s} {'R2':>9s} {'RMSE':>10s} {'MAE':>10s}")
        b_r2 = r2_score(yt[ok], base[ok])
        b_rm = mean_squared_error(yt[ok], base[ok]) ** 0.5
        b_ma = mean_absolute_error(yt[ok], base[ok])
        m_r2 = r2_score(yt, pred)
        m_rm = mean_squared_error(yt, pred) ** 0.5
        m_ma = mean_absolute_error(yt, pred)
        print(f"    {'persistence baseline':22s} {b_r2:>9.4f} {b_rm:>10.3f} {b_ma:>10.3f}")
        print(f"    {'GBT model':22s} {m_r2:>9.4f} {m_rm:>10.3f} {m_ma:>10.3f}")
        print(f"    {'RMSE reduction':22s} {100*(b_rm-m_rm)/b_rm:>8.2f}%")
        print(f"    {'verdict':22s} "
              f"{'PASS - beats persistence' if m_r2 > b_r2 else '*** FAIL ***'}")

    print("=" * 72)
    print("EVALUATION (raw ug/m3, chronological hold-out)")
    print("=" * 72)
    report("TEST - REAL ROWS ONLY  <- the honest number", test_real)
    report("TEST - all rows (real + synthetic)", test)

    imp = getattr(model, "feature_importances_", None)
    if imp is None:
        from sklearn.inspection import permutation_importance
        sub = test_real.sample(min(20000, len(test_real)), random_state=0)
        pi = permutation_importance(
            model, sub[FEATURES].to_numpy(dtype=np.float32),
            sub["target_pm25_next_hour"].to_numpy(dtype=np.float32),
            n_repeats=3, random_state=0, n_jobs=-1)
        imp = pi.importances_mean
    order = np.argsort(imp)[::-1][:15]
    print("\n  top 15 features by importance:")
    for i in order:
        print(f"    {FEATURES[i]:28s} {imp[i]:.5f}")
    print("=" * 72)
    print(f"total elapsed {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
