import csv, io, os, sys, collections, datetime as dt, math
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
P=r"E:\Big Data jagan\final_air_quality_dataset_22gb_balanced.csv"
size=os.path.getsize(P); fb=open(P,'rb')
hdr=next(csv.reader(io.TextIOWrapper(io.BytesIO(fb.readline()+b'\n'),encoding='utf-8')))
ix={c:i for i,c in enumerate(hdr)}; n=len(hdr)

def r2(pairs):
    if len(pairs)<50: return None,None,len(pairs)
    ys=[b for a,b in pairs]; m=sum(ys)/len(ys)
    ss_t=sum((y-m)**2 for y in ys); ss_r=sum((b-a)**2 for a,b in pairs)
    rmse=math.sqrt(ss_r/len(pairs))
    return (1-ss_r/ss_t if ss_t>0 else None), rmse, len(pairs)

pers=collections.defaultdict(list)     # data_source -> (pm25_t, pm25_t+1)
ident=collections.Counter(); noised=collections.Counter()
sib=collections.defaultdict(list)      # same (station,ts) different variation
rowcount=collections.Counter()
tsperstation=collections.defaultdict(set)

for k in range(14):
    fb.seek(int(size*k/14)); fb.readline()
    buf=[fb.readline() for _ in range(60000)]
    rows=[r for r in csv.reader(io.TextIOWrapper(io.BytesIO(b''.join(x for x in buf if x)),encoding='utf-8',errors='replace')) if len(r)==n]
    tracks=collections.defaultdict(list); bykey=collections.defaultdict(list)
    for r in rows:
        try:
            ts=dt.datetime.strptime(r[ix['from_date']],"%Y-%m-%d %H:%M:%S")
            vb=int(round(float(r[ix['variation_id']])))
        except: continue
        v=r[ix['pm25']]
        try: pm=float(v)
        except: pm=None
        ds=r[ix['data_source']]
        rowcount[ds]+=1
        tsperstation[r[ix['station_id']]].add(ts)
        tracks[(r[ix['station_id']],vb,ds)].append((ts,pm))
        bykey[(r[ix['station_id']],ts)].append((vb,pm,ds))
    for (st,vb,ds),seq in tracks.items():
        seq.sort(key=lambda x:x[0])
        for i in range(len(seq)-1):
            if (seq[i+1][0]-seq[i][0]).total_seconds()==3600 and seq[i][1] is not None and seq[i+1][1] is not None:
                pers[ds].append((seq[i][1],seq[i+1][1]))
                pers['ALL'].append((seq[i][1],seq[i+1][1]))
    for key,lst in bykey.items():
        vals=[p for _,p,_ in lst if p is not None]
        if len(vals)>1:
            sib[len(vals)].append(vals)
            if len(set(vals))==1: ident[len(vals)]+=1
            else: noised[len(vals)]+=1

print("=== ROWS BY PROVENANCE (sampled) ===")
tot=sum(rowcount.values())
for d,c in rowcount.most_common(): print(f"  {d:20s} {c:>9,}  ({100*c/tot:5.2f}%)")

print("\n=== PERSISTENCE BASELINE: predict pm25(t+1) = pm25(t) ===")
print("    This is the floor any real forecaster must beat.")
for ds in ['original','synthetic_expanded','ALL']:
    v,rm,cnt=r2(pers[ds])
    if v is None: print(f"  {ds:20s} insufficient pairs ({cnt})"); continue
    print(f"  {ds:20s} R2={v:7.4f}   RMSE={rm:8.3f} ug/m3   n={cnt:,}")

print("\n=== ARE THE VARIATION COPIES IDENTICAL OR NOISED? ===")
for cnt in sorted(sib):
    ex=sib[cnt][:3]
    print(f"  {cnt} copies of same (station,timestamp): identical={ident[cnt]:,}  differing={noised[cnt]:,}")
    for e in ex: print(f"      e.g. {e}")

ns=[len(v) for v in tsperstation.values()]
print(f"\n=== distinct timestamps per station in sample: min={min(ns)} max={max(ns)} mean={sum(ns)/len(ns):.0f}")
