import csv, io, os, sys, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
P = r"E:\Big Data jagan\final_air_quality_dataset_22gb_balanced.csv"
size = os.path.getsize(P); fb = open(P,'rb')
hdr = next(csv.reader(io.TextIOWrapper(io.BytesIO(fb.readline()+b'\n'), encoding='utf-8')))
ix = {c:i for i,c in enumerate(hdr)}; n=len(hdr)

def num(r,c):
    v=r[ix[c]]
    if v=='' or v.lower()=='nan': return None
    try: return float(v)
    except: return 'BAD'

groups = {
 'wind_dir  [wind_direction|wd_(deg)|wd_()|wd_(degree_c)]': ['wind_direction','wd_(deg)','wd_()','wd_(degree_c)'],
 'temp_raw  [temperature|ambient_temperature|at_()|temp_()]': ['temperature','ambient_temperature','at_()','temp_()'],
 'rain_raw  [rainfall|rf_()]': ['rainfall','rf_()'],
 'co_all    [co|co_(ug/m3)|co_(mg/nm3)]': ['co','co_(ug/m3)','co_(mg/nm3)'],
 'o3_all    [o3|ozone_(ppb)|ozone_()]': ['o3','ozone_(ppb)','ozone_()'],
 'nox_all   [nox_(ppb)|nox|nox_(ppm)]': ['nox_(ppb)','nox','nox_(ppm)'],
}
gc = collections.Counter(); rows=0
core = ['pm25','pm10','no2','so2','co','o3','nh3']
corecnt = collections.Counter(); neg = collections.Counter(); bad = collections.Counter()
rng = {c:[1e18,-1e18] for c in core+['dynamic_temperature_c','dynamic_humidity_percent','dynamic_wind_speed_ms','rainfall_mm','traffic_index']}
cats = {c:collections.Counter() for c in ['season','weather_condition','traffic_level','data_source','climate_type','is_rush_hour','is_weekend']}
allcore=0; pm25_and_feats=0

CH,PER=200,3000
for k in range(CH):
    off=int(size*k/CH)
    if k: fb.seek(off); fb.readline()
    buf=[fb.readline() for _ in range(PER)]
    for r in csv.reader(io.TextIOWrapper(io.BytesIO(b''.join(x for x in buf if x)),encoding='utf-8',errors='replace')):
        if len(r)!=n: continue
        rows+=1
        for g,cs in groups.items():
            if any(num(r,c) not in (None,'BAD') for c in cs): gc[g]+=1
        got=0
        for c in core:
            v=num(r,c)
            if v=='BAD': bad[c]+=1; continue
            if v is None: continue
            corecnt[c]+=1; got+=1
            if v<0: neg[c]+=1
            rng[c][0]=min(rng[c][0],v); rng[c][1]=max(rng[c][1],v)
        if got==len(core): allcore+=1
        if num(r,'pm25') not in (None,'BAD'): pm25_and_feats+=1
        for c in ['dynamic_temperature_c','dynamic_humidity_percent','dynamic_wind_speed_ms','rainfall_mm','traffic_index']:
            v=num(r,c)
            if v not in (None,'BAD'): rng[c][0]=min(rng[c][0],v); rng[c][1]=max(rng[c][1],v)
        for c in cats: cats[c][r[ix[c]]]+=1

print("ROWS:",rows)
print("\n--- COALESCED COVERAGE (any one of the group present) ---")
for g in groups: print(f"  {100*gc[g]/rows:7.3f}%  {g}")
print("\n--- CORE POLLUTANT COVERAGE / RANGE / NEGATIVES ---")
for c in core:
    print(f"  {c:6} filled={100*corecnt[c]/rows:6.2f}%  min={rng[c][0]:<12.3f} max={rng[c][1]:<14.3f} negatives={neg[c]} unparseable={bad[c]}")
print(f"\n  rows with ALL 7 core pollutants present: {100*allcore/rows:.2f}%")
print(f"  rows with pm25 (label source) present  : {100*pm25_and_feats/rows:.2f}%")
print("\n--- ENRICHED FEATURE RANGES ---")
for c in ['dynamic_temperature_c','dynamic_humidity_percent','dynamic_wind_speed_ms','rainfall_mm','traffic_index']:
    print(f"  {c:26} min={rng[c][0]:.3f}  max={rng[c][1]:.3f}")
print("\n--- CATEGORICAL CARDINALITY ---")
for c,cnt in cats.items():
    print(f"  {c}: {len(cnt)} distinct -> {dict(cnt.most_common(6))}")
