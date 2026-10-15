# HDFS Cluster Setup — 1 NameNode + 4 DataNodes

**23AID302 — Big Data Analytics**
Phase 1 (HDFS upload) and Phase 2 (Spark on the cluster) of the project plan.

This builds a real distributed HDFS cluster: five separate Hadoop daemons, each in its own
container with its own storage directory, communicating over a private network. Blocks genuinely
distribute and replicate across them — which is the claim §6 of the status report makes.

---

## Why Docker rather than Hadoop on Windows

Apache stopped shipping usable Windows binaries after 2.x; the `winutils.exe` this project already
uses for Spark is a community rebuild, not an Apache release. More importantly, four "DataNodes" as
four processes on one Windows box share one disk and one OS — they can't demonstrate block
distribution, rack awareness, or node-failure recovery, so the numbers you'd report wouldn't mean
what they say. Five containers give you four independent storage volumes and four independent
daemons that can be individually killed.

---

## Before you start

| Check | Requirement | Why |
|---|---|---|
| Docker Desktop | **running** | The daemon must be up, not just installed |
| Free space on `D:` | **≥ 95 GB** | 27.48 GB × 3 replicas = 82.44 GB, plus headroom |
| RAM available | ~6 GB | 5 daemons × 1 GB heap, plus Docker overhead |
| Time | 30–60 min | Ingesting 27.5 GB across a virtualised filesystem |

> **Do not run this while the Spark pipeline is writing to `D:\aq_lakehouse`.** Both want the same
> disk, and the two together will crawl. Let Phase 3/4 finish first.

Check space:

```bash
df -h /d
```

---

## Step 1 — Start Docker Desktop

Launch it from the Start menu and wait for the whale icon to stop animating. Then confirm the
daemon answers:

```bash
docker info --format "{{.ServerVersion}} | {{.OSType}} | {{.NCPU}} CPUs | {{.MemTotal}} bytes RAM"
```

If this errors with `failed to connect to the docker API`, Docker Desktop is not up yet.

---

## Step 2 — Create the DataNode storage directories

Each DataNode gets its own directory on `D:`. Four separate directories is what makes the four
nodes independent — this is the physical basis of the distribution claim.

```bash
mkdir -p /d/hdfs/dn1 /d/hdfs/dn2 /d/hdfs/dn3 /d/hdfs/dn4 && ls -la /d/hdfs
```

---

## Step 3 — Start the cluster

```bash
cd "F:/SEM 5 NOTES/Big Data/Project_Final/airquality_bigdata_project/airquality_bigdata_project/hadoop" && docker compose up -d
```

First run pulls the `apache/hadoop:3.3.6` image (~600 MB). The NameNode formats itself
automatically on first boot via `ENSURE_NAMENODE_DIR` — there is no manual `hdfs namenode -format`
step, which also means you cannot accidentally reformat a cluster that already holds data.

Watch them come up:

```bash
docker compose ps
```

---

## Step 4 — Confirm all 4 DataNodes registered

Give it ~30 seconds, then:

```bash
docker exec aq-namenode hdfs dfsadmin -report | grep -E "Live datanodes|^Hostname"
```

You want `Live datanodes (4)` and four hostnames. **If you see 0 or fewer than 4**, the usual cause
is DataNode registration being rejected on hostname lookup — `dfs.namenode.datanode.registration.ip-hostname-check`
is already set to `false` in `config/hdfs-site.xml` to prevent that. Check a node's log:

```bash
docker compose logs datanode1 --tail 50
```

Or open the web UI: **http://localhost:9870** → *Datanodes* tab.

---

## Step 5 — Create the HDFS directory layout

```bash
docker exec aq-namenode hdfs dfs -mkdir -p /user/hadoop/lakehouse/raw /user/hadoop/lakehouse/clean /user/hadoop/lakehouse/features /user/hadoop/models
```

```bash
docker exec aq-namenode hdfs dfs -ls -R /user/hadoop
```

---

## Step 6 — Upload the dataset (the long one)

The dataset is bind-mounted into the NameNode container at `/data`, so this streams straight off
`F:` without staging a copy. 27.5 GB in, 82.44 GB written across the four nodes.

```bash
docker exec aq-namenode bash -c "time hdfs dfs -put -f /data/part-*.csv /user/hadoop/lakehouse/raw/"
```

To watch progress from a second terminal:

```bash
docker exec aq-namenode hdfs dfs -du -s -h /user/hadoop/lakehouse/raw
```

If it fails partway, re-run — `-f` overwrites, so it's safe to repeat. To upload one file first as
a smoke test:

```bash
docker exec aq-namenode hdfs dfs -put -f /data/part-7164.csv /user/hadoop/lakehouse/raw/
```

---

## Step 7 — Verify, and capture the evidence for the report

```bash
docker exec aq-namenode bash /scripts/verify_cluster.sh
```

This prints live-node count, the replication and block size actually in force, per-file sizes,
logical vs physical size, total block count, average block replication, under-replicated and
corrupt block counts, and per-node disk usage.

**What the numbers should be**, per §6:

| Quantity | Expected |
|---|---|
| Live DataNodes | 4 |
| `dfs.replication` | 3 |
| `dfs.blocksize` | 134217728 (128 MB) |
| Logical size | ~27.5 GB |
| Physical size | ~82.4 GB |
| Total blocks | ~220 |
| Block replicas | ~660 |
| Per node | ~165 replicas, ~20.6 GB |
| Corrupt / missing | 0 |
| Average block replication | 3.0 |

Block count is `ceil(size / 128 MB)` **per file**, summed over the 23 parts — so expect a few more
than the 220 that dividing the total gives, since each file's last block is partial.

Save the output:

```bash
docker exec aq-namenode bash /scripts/verify_cluster.sh > cluster_evidence.txt 2>&1 && cat cluster_evidence.txt
```

---

## Step 8 — Demonstrate fault tolerance (worth doing for the viva)

This is the payoff of running four nodes instead of three. Kill one and watch HDFS re-replicate
onto the survivors rather than sitting under-replicated:

```bash
docker compose stop datanode4
```

Wait ~30s, then:

```bash
docker exec aq-namenode hdfs fsck /user/hadoop/lakehouse/raw | grep -E "Under-replicated|Average block replication|Live datanodes"
```

Bring it back:

```bash
docker compose start datanode4
```

With only three DataNodes this recovery is impossible — there is nowhere to put the third replica.
That is the argument in §6.1, demonstrated rather than asserted.

---

## Step 9 — Point the Spark pipeline at the cluster

The pipeline scripts read their paths from the environment (see `scripts/paths.py`), so no code
changes are needed:

```bash
$env:AQ_FS = "hdfs"; $env:AQ_DATA = "hdfs://localhost:9000/user/hadoop/lakehouse/raw"; $env:AQ_LAKE = "hdfs://localhost:9000/user/hadoop"
```

Then run Phases 3–6 as normal. Port 9000 is published to the host, so local Spark talks to the
containerised cluster directly.

---

## Shutting down

Stop the daemons, keep the data:

```bash
docker compose stop
```

Remove the containers, keep the data on `D:`:

```bash
docker compose down
```

**Destroy everything including the 82 GB of HDFS data** — only when you're finished:

```bash
docker compose down -v && rm -rf /d/hdfs/dn1 /d/hdfs/dn2 /d/hdfs/dn3 /d/hdfs/dn4
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `failed to connect to the docker API` | Docker Desktop not running | Start it, wait for the icon to settle |
| `Live datanodes (0)` | DataNodes can't register | `docker compose logs datanode1`; confirm the `ip-hostname-check` property is present |
| `NameNode is in safe mode` | Still tallying blocks after restart | Wait, or `docker exec aq-namenode hdfs dfsadmin -safemode leave` |
| Ingest dies partway | `D:` full | `df -h /d`; you need 82.44 GB free plus the 5 GB per-node reserve |
| Very slow ingest | Windows→Linux bind mount overhead | Expected; `/data` is a virtualised mount. Measure once and quote it |
| `Permission denied` on `/user` | UID mismatch host vs container | `dfs.permissions.enabled` is already `false`; confirm the mounted `hdfs-site.xml` is being read |
| Containers exit immediately | Read-only config mount | Config files must be mounted read-write; the entrypoint rewrites them |
