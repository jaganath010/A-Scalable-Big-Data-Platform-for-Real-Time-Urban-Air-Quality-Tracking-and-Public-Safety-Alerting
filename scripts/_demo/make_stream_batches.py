"""
Build streaming input batches for the AirQualityStream demo.

Takes REAL rows out of the expanded dataset (no values invented) for cities the
trained model actually knows, keeping each station's hours consecutive so the
lag / rolling features the model depends on are meaningful.

Writes batch_1.csv .. batch_N.csv, each with the 32-column header, to be
dropped into the stream input directory one at a time.
"""
import csv
import glob
import os
import collections

SRC = r"F:\SEM 5 NOTES\Big Data\Project_Final\airquality_expanded"
OUT = r"C:\Users\jagan\AppData\Local\Temp\claude\F--SEM-5-NOTES-Big-Data-Project-Final-airquality-bigdata-project\a458bf7f-a018-4082-b6d9-7806c8c3e697\scratchpad\stream_batches"

# Cities the reduced-scale model was trained on. Feeding a city it has never
# seen would hit an unknown StringIndexer label at scoring time.
TRAINED = {"Anantapur", "Araria", "Bengaluru", "Bhagalpur", "Chennai", "Delhi",
           "Durgapur", "Gandhinagar", "Hyderabad", "Jalandhar", "Lucknow",
           "Motihari", "Mumbai", "Nashik", "Noida", "Panchkula", "Raipur",
           "Sagar", "Varanasi"}

# Only real rows - a demo scoring synthetic rows proves less.
WANT_REAL_ONLY = True
HOURS_PER_STATION = 40          # > 30h so the rolling history window fills
MAX_STATIONS = 12

os.makedirs(OUT, exist_ok=True)
files = sorted(glob.glob(os.path.join(SRC, "part-*.csv")))
hdr = open(files[0], encoding="utf-8", errors="replace").readline().rstrip("\r\n").split(",")
idx = {c: i for i, c in enumerate(hdr)}

by_station = collections.OrderedDict()
scanned = 0

for f in files:
    if len(by_station) >= MAX_STATIONS and all(
            len(v) >= HOURS_PER_STATION for v in by_station.values()):
        break
    with open(f, encoding="utf-8", errors="replace") as fh:
        fh.readline()
        for ln in fh:
            scanned += 1
            if scanned > 40_000_000:
                break
            p = ln.rstrip("\r\n").split(",")
            if len(p) != len(hdr):
                continue
            if p[idx["city"]] not in TRAINED:
                continue
            if WANT_REAL_ONLY and p[idx["data_source"]] != "real":
                continue
            # need pm25 present - it is the label source and the lag feature
            if p[idx["pm25"]] == "":
                continue
            sid = p[idx["station_id"]]
            rows = by_station.setdefault(sid, [])
            if len(rows) < HOURS_PER_STATION:
                rows.append(p)
            if len(by_station) >= MAX_STATIONS and all(
                    len(v) >= HOURS_PER_STATION for v in by_station.values()):
                break

# keep only stations that reached full length
full = {k: v for k, v in by_station.items() if len(v) >= HOURS_PER_STATION}
print(f"scanned {scanned:,} rows -> {len(full)} usable stations")
for k, v in full.items():
    print(f"   {k:12} {v[0][idx['city']]:12} {len(v)} rows  "
          f"{v[0][idx['from_date']]} .. {v[-1][idx['from_date']]}  "
          f"pm25 {v[0][idx['pm25']]}..{v[-1][idx['pm25']]}")

# Batch by TIME SLICE across stations, so each batch looks like "one hour of
# readings arriving from every station", which is what a real feed looks like.
n_batches = 4
per = HOURS_PER_STATION // n_batches
for b in range(n_batches):
    path = os.path.join(OUT, f"batch_{b+1}.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(hdr)
        n = 0
        for sid, rows in full.items():
            for r in rows[b * per:(b + 1) * per]:
                w.writerow(r)
                n += 1
    print(f"wrote {path}  ({n} rows)")
