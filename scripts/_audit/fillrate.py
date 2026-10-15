import csv, io, os, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
P = r"E:\Big Data jagan\final_air_quality_dataset_22gb_balanced.csv"
size = os.path.getsize(P)
fb = open(P, 'rb')
hdr = next(csv.reader(io.TextIOWrapper(io.BytesIO(fb.readline()+b'\n'), encoding='utf-8')))
n = len(hdr)
nonnull = [0]*n
rows = 0
CHUNKS, PER = 240, 4000
for k in range(CHUNKS):
    off = int(size * k / CHUNKS)
    if k: 
        fb.seek(off); fb.readline()          # drop partial line
    buf = []
    for _ in range(PER):
        ln = fb.readline()
        if not ln: break
        buf.append(ln)
    txt = io.TextIOWrapper(io.BytesIO(b''.join(buf)), encoding='utf-8', errors='replace')
    for r in csv.reader(txt):
        if len(r) != n: continue
        rows += 1
        for i,v in enumerate(r):
            if v != '' and v.lower() != 'nan':
                nonnull[i] += 1
print("SAMPLED ROWS:", rows)
print(f"{'idx':>4} {'pct_filled':>10}  column")
for i,c in enumerate(hdr):
    print(f"{i:>4} {100*nonnull[i]/rows:>9.3f}%  {c}")
