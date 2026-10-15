import csv, io, os, sys, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
P = r"E:\Big Data jagan\final_air_quality_dataset_22gb_balanced.csv"
size=os.path.getsize(P); fb=open(P,'rb')
hdr=next(csv.reader(io.TextIOWrapper(io.BytesIO(fb.readline()+b'\n'),encoding='utf-8')))
ix={c:i for i,c in enumerate(hdr)}; n=len(hdr)

rush=collections.Counter(); hum_over=collections.Counter(); tr_over=collections.Counter()
key=collections.Counter(); varid=collections.Counter(); rows=0
oob_rush=0
CH,PER=150,3000
for k in range(CH):
    off=int(size*k/CH)
    if k: fb.seek(off); fb.readline()
    buf=[fb.readline() for _ in range(PER)]
    for r in csv.reader(io.TextIOWrapper(io.BytesIO(b''.join(x for x in buf if x)),encoding='utf-8',errors='replace')):
        if len(r)!=n: continue
        rows+=1
        ds=r[ix['data_source']]
        v=r[ix['is_rush_hour']]
        try: fv=float(v)
        except: fv=None
        if fv is not None and fv not in (0.0,1.0):
            oob_rush+=1; rush[ds]+=1
        try:
            if float(r[ix['dynamic_humidity_percent']])>100: hum_over[ds]+=1
        except: pass
        try:
            if float(r[ix['traffic_index']])>100: tr_over[ds]+=1
        except: pass
        key[(r[ix['station_id']], r[ix['from_date']])]+=1
        varid[r[ix['variation_id']]]+=1

print("ROWS:",rows)
print(f"\nis_rush_hour NOT in {{0,1}}: {oob_rush} ({100*oob_rush/rows:.2f}%)  by data_source -> {dict(rush)}")
print(f"dynamic_humidity_percent > 100 : by data_source -> {dict(hum_over)}")
print(f"traffic_index > 100            : by data_source -> {dict(tr_over)}")
print(f"\nvariation_id distinct: {len(varid)} -> {dict(varid.most_common(8))}")
dup=sum(1 for v in key.values() if v>1)
print(f"\n(station_id, from_date) distinct keys in sample: {len(key)}")
print(f"  keys appearing >1 time: {dup} ({100*dup/max(1,len(key)):.2f}% of keys)")
print(f"  max repeats for one key: {max(key.values())}")
print(f"  examples: {[ (k,v) for k,v in key.most_common(5) ]}")
