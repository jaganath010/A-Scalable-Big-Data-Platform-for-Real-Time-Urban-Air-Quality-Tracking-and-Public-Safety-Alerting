import csv, io, os, sys, collections, datetime as dt
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------- 1. CPCB sub-index: mirror of sub_index() in 02_feature_extraction.py
BP = {
 "pm25":[(0,30,0,50),(30,60,51,100),(60,90,101,200),(90,120,201,300),(120,250,301,400),(250,1000,401,500)],
 "pm10":[(0,50,0,50),(50,100,51,100),(100,250,101,200),(250,350,201,300),(350,430,301,400),(430,1000,401,500)],
 "no2":[(0,40,0,50),(40,80,51,100),(80,180,101,200),(180,280,201,300),(280,400,301,400),(400,1000,401,500)],
 "so2":[(0,40,0,50),(40,80,51,100),(80,380,101,200),(380,800,201,300),(800,1600,301,400),(1600,3000,401,500)],
 "co":[(0,1,0,50),(1,2,51,100),(2,10,101,200),(10,17,201,300),(17,34,301,400),(34,100,401,500)],
 "o3":[(0,50,0,50),(50,100,51,100),(100,168,101,200),(168,208,201,300),(208,748,301,400),(748,1000,401,500)],
 "nh3":[(0,200,0,50),(200,400,51,100),(400,800,101,200),(800,1200,201,300),(1200,1800,301,400),(1800,3000,401,500)],
}
def sub_index(c, bps):
    if c is None: return None
    out = 500.0
    for clo,chi,ilo,ihi in reversed(bps):
        if c <= chi: out = (ihi-ilo)/(chi-clo)*(c-clo)+ilo
    return out

print("=== CPCB SUB-INDEX CHECK (against published CPCB reference points) ===")
checks = [
 ("pm25",  30, 50,   "PM2.5 30 ug/m3 = top of 'Good'"),
 ("pm25",  60, 100,  "PM2.5 60 = top of 'Satisfactory'"),
 ("pm25",  90, 200,  "PM2.5 90 = top of 'Moderate'"),
 ("pm10", 100, 100,  "PM10 100 = top of 'Satisfactory'"),
 ("pm10", 250, 200,  "PM10 250 = top of 'Moderate'"),
 ("co",     1,  50,  "CO 1 mg/m3 = top of 'Good'"),
 ("co",    10, 200,  "CO 10 mg/m3 = top of 'Moderate'"),
 ("no2",   80, 100,  "NO2 80 = top of 'Satisfactory'"),
 ("o3",   168, 200,  "O3 168 = top of 'Moderate'"),
 ("nh3",  400, 100,  "NH3 400 = top of 'Satisfactory'"),
]
ok=True
for p,c,exp,label in checks:
    got = sub_index(c, BP[p])
    good = abs(got-exp) < 0.5
    ok &= good
    print(f"  [{'PASS' if good else 'FAIL'}] {label:42s} -> {got:7.2f} (expect {exp})")
# midpoint interpolation sanity
mid = sub_index(45, BP["pm25"])
print(f"  [{'PASS' if abs(mid-75.5)<0.6 else 'FAIL'}] PM2.5 45 interpolates mid-band            -> {mid:7.2f} (expect ~75.5)")
print(f"  AQI>150 alert threshold corresponds to PM2.5 24h avg of ~{60+ (150-100)*(90-60)/(200-100):.1f} ug/m3")
print("  overall:", "ALL PASS" if ok else "FAILURES PRESENT")

# ---------- 2. T+1 temporal guard on REAL contiguous rows
P = r"E:\Big Data jagan\final_air_quality_dataset_22gb_balanced.csv"
size=os.path.getsize(P); fb=open(P,'rb')
hdr=next(csv.reader(io.TextIOWrapper(io.BytesIO(fb.readline()+b'\n'),encoding='utf-8')))
ix={c:i for i,c in enumerate(hdr)}; n=len(hdr)

print("\n=== T+1 LABEL GUARD ON REAL DATA (contiguous blocks, 12 offsets) ===")
tot=naive=valid=0; gaps=collections.Counter(); dupkey=0
for k in range(12):
    fb.seek(int(size*k/12));  fb.readline()
    buf=[fb.readline() for _ in range(40000)]
    rows=[r for r in csv.reader(io.TextIOWrapper(io.BytesIO(b''.join(x for x in buf if x)),encoding='utf-8',errors='replace')) if len(r)==n]
    # group into (station, variation_bucket) tracks, ordered by ts
    tracks=collections.defaultdict(list)
    for r in rows:
        try:
            ts=dt.datetime.strptime(r[ix['from_date']],"%Y-%m-%d %H:%M:%S")
            vb=int(round(float(r[ix['variation_id']])))
        except: continue
        pm=r[ix['pm25']]
        tracks[(r[ix['station_id']],vb)].append((ts, pm if pm not in ('','nan') else None))
    for key,seq in tracks.items():
        seq.sort(key=lambda x:x[0])
        seen=set()
        for i in range(len(seq)-1):
            if seq[i][0] in seen: dupkey+=1
            seen.add(seq[i][0])
            tot+=1
            if seq[i+1][1] is not None: naive+=1          # plain lead(): any next row
            d=int((seq[i+1][0]-seq[i][0]).total_seconds())
            gaps[d]+=1
            if d==3600 and seq[i+1][1] is not None: valid+=1   # guarded
print(f"  transitions examined      : {tot:,}")
print(f"  plain lead() would label  : {naive:,}  ({100*naive/tot:.2f}%)")
print(f"  temporally VALID (+1h)    : {valid:,}  ({100*valid/tot:.2f}%)")
print(f"  >>> MISLABELLED by plain lead(): {naive-valid:,} ({100*(naive-valid)/max(1,naive):.2f}% of its labels)")
print(f"  duplicate timestamps within a track: {dupkey:,}")
print("  top gap sizes between consecutive rows (seconds -> count):")
for d,c in gaps.most_common(6):
    print(f"    {d:>9,}s ({d/3600:>7.2f}h) -> {c:,}")
