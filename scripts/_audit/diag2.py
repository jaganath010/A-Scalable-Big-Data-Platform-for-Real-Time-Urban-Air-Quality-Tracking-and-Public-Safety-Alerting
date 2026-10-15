import csv, io, os, sys, collections, datetime as dt, math
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
P=r"E:\Big Data jagan\final_air_quality_dataset_22gb_balanced.csv"
size=os.path.getsize(P); fb=open(P,'rb')
hdr=next(csv.reader(io.TextIOWrapper(io.BytesIO(fb.readline()+b'\n'),encoding='utf-8')))
ix={c:i for i,c in enumerate(hdr)}; n=len(hdr)

# Does the SAME (station, month, day, hour) carry the SAME pm25 across DIFFERENT years?
# That is the signature of "replicate the base file across a 3-year timeline loop".
byslot=collections.defaultdict(dict)   # (station,mm,dd,hh) -> {year: pm25}
yrs=collections.Counter(); dsyear=collections.defaultdict(collections.Counter)
pmvals=collections.Counter(); rows=0
for k in range(16):
    fb.seek(int(size*k/16)); fb.readline()
    buf=[fb.readline() for _ in range(50000)]
    for r in csv.reader(io.TextIOWrapper(io.BytesIO(b''.join(x for x in buf if x)),encoding='utf-8',errors='replace')):
        if len(r)!=n: continue
        rows+=1
        try:
            ts=dt.datetime.strptime(r[ix['from_date']],"%Y-%m-%d %H:%M:%S")
            pm=float(r[ix['pm25']])
        except: continue
        yrs[ts.year]+=1; dsyear[r[ix['data_source']]][ts.year]+=1
        pmvals[round(pm,2)]+=1
        byslot[(r[ix['station_id']],ts.month,ts.day,ts.hour)][ts.year]=pm

print("=== YEAR DISTRIBUTION ===")
for y,c in sorted(yrs.items()): print(f"  {y}: {c:,}")
print("\n  by provenance:")
for ds,cc in dsyear.items():
    print(f"   {ds:20s} years {min(cc)}-{max(cc)}, top: {dict(cc.most_common(5))}")

multi=[v for v in byslot.values() if len(v)>1]
same=sum(1 for v in multi if len(set(round(x,3) for x in v.values()))==1)
print(f"\n=== CROSS-YEAR REPLICATION CHECK ===")
print(f"  (station,month,day,hour) slots seen in >1 year: {len(multi):,}")
print(f"    of these, pm25 IDENTICAL across years       : {same:,} ({100*same/max(1,len(multi)):.2f}%)")
for v in multi[:5]:
    print(f"      e.g. {dict(sorted(v.items()))}")

print(f"\n=== pm25 VALUE REPETITION (information content) ===")
uniq=len(pmvals); tot=sum(pmvals.values())
print(f"  pm25 readings sampled: {tot:,}   distinct values: {uniq:,}  ({100*uniq/tot:.3f}%)")
print(f"  most repeated values: {dict(pmvals.most_common(6))}")
