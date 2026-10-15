import csv, io, sys, collections, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
P=r"E:\Big Data jagan\final_air_quality_dataset_22gb_balanced.csv"
f=open(P, newline='', encoding='utf-8', errors='replace')
rd=csv.reader(f); hdr=next(rd)
ix={c:i for i,c in enumerate(hdr)}
I_ST,I_FD,I_DS,I_VI,I_PM = ix['station_id'],ix['from_date'],ix['data_source'],ix['variation_id'],ix['pm25']
n=len(hdr)
rows=0; ds=collections.Counter(); adj_dup=0; adj_dup_orig=0
prev=None; stations=set(); unsorted_jumps=0
orig_rows=0; orig_adjacent_runs=collections.Counter()
run_key=None; run_len=0
t0=time.time()
for r in rd:
    if len(r)!=n: continue
    rows+=1
    st=r[I_ST]; fd=r[I_FD]; d=r[I_DS]
    ds[d]+=1
    stations.add(st)
    if d=='original': orig_rows+=1
    key=(st,fd)
    if prev is not None:
        if key==prev:
            adj_dup+=1
            if d=='original': adj_dup_orig+=1
        elif st==prev[0] and fd<prev[1]:
            unsorted_jumps+=1
    if key==run_key: run_len+=1
    else:
        if run_key is not None: orig_adjacent_runs[run_len]+=1
        run_key=key; run_len=1
    prev=key
    if rows%5_000_000==0:
        print(f"  ...{rows:,} rows  {time.time()-t0:.0f}s", flush=True)
orig_adjacent_runs[run_len]+=1
print("="*60)
print(f"TOTAL ROWS          : {rows:,}")
print(f"elapsed             : {time.time()-t0:.0f}s")
print(f"distinct station_id : {len(stations):,}")
print(f"adjacent duplicate (station,from_date) pairs : {adj_dup:,} ({100*adj_dup/rows:.2f}%)")
print(f"   of which tagged original                  : {adj_dup_orig:,}")
print(f"out-of-order timestamps within a station     : {unsorted_jumps:,}")
print("\nrows by data_source:")
for d,c in ds.most_common(): print(f"   {d:22s} {c:>12,}  ({100*c/rows:5.2f}%)")
print("\ndistribution of run-lengths for identical (station,from_date):")
for L,c in sorted(orig_adjacent_runs.items())[:10]:
    print(f"   run length {L:>3}: {c:>12,} groups")
print(f"\n=> DISTINCT (station,from_date) groups approx: {sum(orig_adjacent_runs.values()):,}")
