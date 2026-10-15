import glob, os, sys, time, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
# Exact single pass. Binary line iteration + byte split (no per-line decode)
# keeps this I/O-bound rather than CPU-bound.
st2city={}; st2state={}; rows=0; t0=time.time()
files=sorted(glob.glob(r"E:\airquality_expanded\part-*.csv"))
for i,fp in enumerate(files,1):
    with open(fp,'rb',buffering=1<<22) as f:
        f.readline()
        for line in f:
            p=line.split(b',',3)
            if len(p)<3: continue
            rows+=1
            s=p[0]
            if s not in st2city:
                st2city[s]=p[2]; st2state[s]=p[1]
    print(f"  [{i}/{len(files)}] {os.path.basename(fp)}  rows={rows:,}  "
          f"stations={len(st2city):,}  {time.time()-t0:.0f}s", flush=True)

cities={c for c in st2city.values()}
states={s for s in st2state.values()}
real=[s for s in st2city if b'~' not in s]
syn=[s for s in st2city if b'~' in s]
real_cities={st2city[s] for s in real}
city_st=collections.defaultdict(set)
state_city=collections.defaultdict(set)
for s,c in st2city.items():
    city_st[c].add(s); state_city[st2state[s]].add(c)
d=lambda b:b.decode('utf-8','replace')
print("="*58)
print(f"rows scanned            : {rows:,}   ({time.time()-t0:.0f}s)")
print(f"DISTINCT CITIES         : {len(cities)}")
print(f"DISTINCT STATES / UTs   : {len(states)}")
print(f"real stations           : {len(real):,}")
print(f"synthetic stations      : {len(syn):,}")
print(f"total station-series    : {len(st2city):,}")
print(f"cities w/ a real station: {len(real_cities)}")
print("="*58)
print("top 12 cities by station-series:")
for c,s in sorted(city_st.items(), key=lambda kv:-len(kv[1]))[:12]:
    nr=len([x for x in s if b'~' not in x])
    print(f"   {d(c):<26} {len(s):>4} series  ({nr} real)")
print("\ntop 10 states by city count:")
for s,cs in sorted(state_city.items(), key=lambda kv:-len(kv[1]))[:10]:
    print(f"   {d(s):<26} {len(cs):>4} cities")
one=[c for c,s in city_st.items() if len([x for x in s if b'~' not in x])==1]
print(f"\ncities served by exactly ONE real station: {len(one)}")
