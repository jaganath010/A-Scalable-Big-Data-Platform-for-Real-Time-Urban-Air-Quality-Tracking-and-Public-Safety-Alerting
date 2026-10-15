# RUNBOOK — every command, in order

**23AID302 — Big Data Analytics**
A Scalable Big Data Platform for Real-Time Urban Air Quality Tracking

All commands are **cmd.exe** syntax. Run `env.cmd` once per new window before anything Spark-related.

---

## 0. Environment — ALWAYS FIRST

```bat
"F:\SEM 5 NOTES\Big Data\Project_Final\airquality_bigdata_project\airquality_bigdata_project\env.cmd"
```

Should print `java version "1.8.0_421"`.

**If you skip this**, Spark dies with
`UnsupportedOperationException: getSubject is supported only if a security manager is allowed`
— that is Java 23 being picked up instead of JRE 8. It is always this.

Working directory for the Python scripts:

```bat
cd /d "F:\SEM 5 NOTES\Big Data\Project_Final\airquality_bigdata_project\airquality_bigdata_project\scripts"
```

---

## 1. Status — what is already done

| Phase | Status | Artefact |
|---|---|---|
| 0 Dataset rebuild | done | `F:\...\airquality_expanded` — 27.48 GiB, 146,276,379 rows |
| 1 HDFS upload | done | 23 files, 232 blocks, replication 3.0, HEALTHY |
| 2 Spark activation | local only | no YARN yet — see §4 |
| 3 Cleaning | done | `D:\aq_lakehouse\clean` — 9.95 GiB, 241 files |
| 4 Feature engineering | done | `D:\aq_lakehouse\features` — 19.70 GiB, 93,216,105 rows |
| 5/6 Train & export | pending | see §3 |
| 7/8 Streaming + alerts | code written | see §5 |
| 9 Hive | not started | |
| 10 Dashboard | not started | |

---

## 2. Evidence for phases 2, 3, 4

```bat
python show_evidence.py --phase 2
python show_evidence.py --phase 3
python show_evidence.py --phase 4
```

Widen the terminal first — the tables are ~80 characters.

Quick independent check of the feature layer:

```bat
python -c "from pyspark.sql import SparkSession; s=SparkSession.builder.master('local[4]').getOrCreate(); d=s.read.parquet(r'D:\aq_lakehouse\features'); print('rows:', d.count()); print('columns:', len(d.columns))"
```

Expect `rows: 93216105`, `columns: 69`.

---

## 3. Phase 5 + 6 — train the GBT model

```bat
python -u 03_train_gbt.py --max-iter 150
```

`-u` gives live output. Without it, Python buffers and you see nothing for hours.

Useful flags:

| Flag | Meaning |
|---|---|
| `--max-iter 150` | number of boosting trees (300 = spec, ~4 h; 150 ≈ 2 h) |
| `--train-cap 10000000` | cap training rows (default 10 M). `0` = use all ~74.5 M |

**Expected output, in order:**

```
>>> checkpoint dir: D:\aq_sparktmp\checkpoints
>>> quality gate: 93,216,105 -> 93,216,105 rows (100.00% retained)
>>> training subsample: 74,544,984 -> ~10,000,000 rows (fraction 0.1341, seed 42)
>>> chronological split at ts_unix=...
    train 10,000,152 rows | test 18,671,121 rows
  PERSISTENCE BASELINE   R2=0.8563  RMSE=25.443  MAE=10.357
  ... on real rows only  R2=0.8587  RMSE=24.831  MAE=9.937  (n=2,074,569)
>>> training GBT on delta target ...
```

**Sanity check:** the two baselines must come out at **0.8563** and **0.8587**. The split is
deterministic and the subsample is seeded, so different numbers mean something upstream changed —
stop and investigate rather than letting it run.

Then it trains. Confirm boosting is alive:

```bat
dir D:\aq_sparktmp\checkpoints
```

New subdirectories appear every ~10 trees. **This is the fix that matters** — the first attempt
died after 3 h 50 m with a `StackOverflowError` because no checkpoint directory was set, so the
RDD lineage grew unbounded across 300 iterations.

The run **passes** only if the model beats persistence on real rows. The script prints an explicit
`FAIL` with a diagnostic checklist otherwise.

---

## 4. Phase 2 — YARN

**Only after Phase 5 finishes.** 4 NodeManagers × 3 GB on a 15.7 GB host will not coexist with an
11 GB Spark driver.

```bat
cd /d "F:\SEM 5 NOTES\Big Data\Project_Final\airquality_bigdata_project\airquality_bigdata_project\hadoop"
docker compose -f docker-compose.yml -f docker-compose.yarn.yml up -d
```

```bat
docker exec aq-resourcemanager yarn node -list
```

Expect 4 nodes `RUNNING`. Web UI: **http://localhost:8088** — this is the Phase 2 screenshot.

Prove YARN actually schedules work:

```bat
docker exec aq-resourcemanager yarn jar /opt/hadoop/share/hadoop/mapreduce/hadoop-mapreduce-examples-3.3.6.jar pi 4 100
```

Watch it appear in the 8088 UI while it runs.

Shut YARN down again (HDFS keeps running):

```bat
docker compose -f docker-compose.yml -f docker-compose.yarn.yml stop resourcemanager nodemanager1 nodemanager2 nodemanager3 nodemanager4
```

---

## 5. Phases 7 + 8 — Scala streaming and alerts

Needs the Phase 5 model.

### Build

```bat
cd /d "F:\SEM 5 NOTES\Big Data\Project_Final\airquality_bigdata_project\airquality_bigdata_project\scala\streaming"
sbt package
```

First build takes 5–10 minutes (downloads Scala 2.12.18). Output:
`target\scala-2.12\airquality-streaming_2.12-1.0.jar`

Scala **2.12.18** is mandatory — the installed Spark is `spark-core_2.12-3.5.6`, and a 2.13 or 3.x
build compiles then fails at runtime with `NoSuchMethodError`.

### Prepare directories

```bat
docker exec aq-namenode hdfs dfs -mkdir -p /user/hadoop/lakehouse/stream/input /user/hadoop/lakehouse/stream/checkpoint /user/hadoop/lakehouse/stream/alerts /user/hadoop/lakehouse/stream/predictions
```

### Run

Against the local lakehouse (simplest — models are already there):

```bat
set "AQ_LAKE=D:\aq_lakehouse"
spark-submit --class AirQualityStream --master "local[*]" --driver-memory 4g target\scala-2.12\airquality-streaming_2.12-1.0.jar
```

### Feed it

```bat
docker exec aq-namenode bash -c "head -5000 /data/part-7164.csv > /tmp/batch1.csv && hdfs dfs -put /tmp/batch1.csv /user/hadoop/lakehouse/stream/input/"
```

Each file dropped triggers a micro-batch. Console prints rows in, predictions, alerts, latency.

---

## 6. HDFS — verification and evidence

```bat
docker exec aq-namenode hdfs dfs -ls -h /user/hadoop/lakehouse/raw/
docker exec aq-namenode hdfs dfs -du -s -h /user/hadoop/lakehouse/raw
docker exec aq-namenode hdfs fsck /user/hadoop/lakehouse/raw
docker exec aq-namenode hdfs dfsadmin -report | findstr /C:"Hostname" /C:"DFS Used:"
```

Expect: 23 files · `27.5 G / 82.4 G` · **232 blocks** · replication **3.0** · 0 corrupt · HEALTHY ·
~20 GB per DataNode.

Save it all:

```bat
docker exec aq-namenode bash /scripts/verify_cluster.sh > cluster_evidence.txt 2>&1
type cluster_evidence.txt
```

### Fault-tolerance demo (Phase 6.2 evidence)

```bat
docker exec aq-namenode hdfs fsck /user/hadoop/lakehouse/raw | findstr /C:"Under-replicated" /C:"Average block replication"
docker compose stop datanode4
```

Wait 60 s, run the fsck again — under-replicated blocks appear, replication dips below 3.0, then
recovers as HDFS rebuilds onto the surviving nodes.

```bat
docker compose start datanode4
```

This is impossible with three DataNodes: there is nowhere to put the third replica.

---

## 7. Cluster control

```bat
docker compose ps
docker compose logs aq-namenode --tail 50
docker compose stop
docker compose up -d
```

Never `docker compose down -v` — that deletes the NameNode metadata and you would re-ingest 82 GB.

---

## 8. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `getSubject is supported only if a security manager` | Java 23 instead of JRE 8 | run `env.cmd` |
| `HADOOP_HOME and hadoop.home.dir are unset` | winutils not on PATH | run `env.cmd` |
| `Python worker exited unexpectedly` | Python workers cannot spawn on this machine | unavoidable; only affects RDD/UDF operations. Scala jobs are unaffected |
| `PipelineModel.load failed` | same cause | expected — the script refits automatically, which is equivalent |
| `StackOverflowError` in `gbt.fit` | no checkpoint directory | already fixed in `03_train_gbt.py` |
| `port is already allocated` | old containers holding 9000/9870/9864 | `docker stop namenode datanode` |
| `Container is restarting` | check the logs | `docker logs aq-namenode --tail 30` |
| `head`/`grep` not recognised | Unix tools in cmd | run inside the container: `docker exec ... bash -c "..."` |
| No output for hours | Python buffering | always use `python -u` |

---

## 9. Key numbers

| Quantity | Value |
|---|---|
| Dataset | 27.48 GiB · 146,276,379 rows · 32 columns |
| Distinct station-hours | 128,660,967 (12.04 % duplicates removed) |
| Real / synthetic | 16,252,931 (11.11 %) / 130,023,448 (88.89 %) |
| Stations / cities | 4,077 / 241 |
| HDFS | 232 blocks · 696 replicas · 82.4 GB raw |
| Clean layer | 9.95 GiB · 241 files |
| Feature layer | 19.70 GiB · 93,216,105 rows · 69 columns |
| Feature vector | 86 dimensions (54 numeric + 32 one-hot) |
| Persistence baseline | R² 0.8563 all rows · 0.8587 real rows only |
| Phase 3 runtime | 40 min 33 s |
| Phase 4 runtime | 78 min 13 s |
| HDFS ingest | 20 min 12 s |
