# Phase 7 + 8 — Real-Time Speed Layer (Scala)

Spark Structured Streaming job that watches an HDFS directory, forecasts PM2.5 one hour
ahead using the model trained by Phase 5, and raises alerts when the forecast AQI exceeds 150.

Written in Scala per the project specification: *"Real-Time Speed Layer (Spark Structured
Streaming / Scala): Written natively in Scala to maximize native JVM thread execution speeds."*

---

## Why Scala matters here beyond the spec

Spark cannot spawn Python worker processes on this machine — a bare
`sc.parallelize([1,2,3]).map(...)` fails. A PySpark streaming job with UDFs would not run at all.
This job is pure JVM and needs no Python worker, so writing it in Scala **removes** the blocker
rather than working around it.

The models load without conversion: MLlib's on-disk format is language-neutral, so the
`PipelineModel` and `GBTRegressionModel` produced by the PySpark pipeline are read directly.

---

## Build

```bash
cd "F:\SEM 5 NOTES\Big Data\Project_Final\airquality_bigdata_project\airquality_bigdata_project\scala\streaming"
```

```bash
sbt package
```

First build downloads Scala 2.12.18 and the Spark jars (~5–10 min). Output:
`target/scala-2.12/airquality-streaming_2.12-1.0.jar` — small, a few hundred KB, because Spark is
declared `provided`.

**Scala 2.12.18 is not a free choice.** The installed Spark is `spark-core_2.12-3.5.6`, and Scala
does not maintain binary compatibility across major versions. A 2.13 or 3.x build compiles and
then fails at runtime with `NoSuchMethodError`.

`project/build.properties` pins sbt 1.9.9 even though sbt 2.0.4 is installed — sbt 2 uses Scala 3
build definitions and its Spark tooling is not yet settled. sbt downloads the pinned launcher
itself, so nothing needs uninstalling.

---

## Run

Create the stream directories first:

```bash
docker exec aq-namenode hdfs dfs -mkdir -p /user/hadoop/lakehouse/stream/input /user/hadoop/lakehouse/stream/checkpoint /user/hadoop/lakehouse/stream/alerts /user/hadoop/lakehouse/stream/predictions
```

The models must be in HDFS (Phase 5 currently writes them to `D:\aq_lakehouse`):

```bash
docker exec aq-namenode hdfs dfs -mkdir -p /user/hadoop/models
```

Then submit:

```bash
spark-submit --class AirQualityStream --master "local[*]" --driver-memory 4g target/scala-2.12/airquality-streaming_2.12-1.0.jar
```

Set `AQ_LAKE` first if the lakehouse is not at the default
`hdfs://localhost:9000/user/hadoop` — for a local test:

```bash
$env:AQ_LAKE = "D:\aq_lakehouse"
```

---

## Feed it

The job watches for new CSV files with the 32-column schema. Simulate live sensors by dropping
one in:

```bash
docker exec aq-namenode bash -c "head -5000 /data/part-7164.csv > /tmp/batch1.csv && hdfs dfs -put /tmp/batch1.csv /user/hadoop/lakehouse/stream/input/"
```

Each drop triggers a micro-batch. The console prints rows in, predictions made, alerts raised,
and latency in milliseconds.

---

## What it writes

| Path | Contents |
|---|---|
| `stream/predictions` | Every forecast: station, city, current and forecast PM2.5 and AQI |
| `stream/alerts` | Only forecast AQI > 150, partitioned by city, with a plain-English message |
| `stream/history` | Rolling 30h per station — the state that makes lag features possible |
| `stream/checkpoint` | Structured Streaming offsets, for restartability |

Read the alerts back:

```bash
docker exec aq-namenode hdfs dfs -ls -R /user/hadoop/lakehouse/stream/alerts
```

---

## Two design decisions worth defending

**Why `foreachBatch` and a history table.** The model needs lag and rolling-window features, and
Structured Streaming does not support `lag()` over a streaming DataFrame — those need unbounded
ordered history. Inside `foreachBatch` each micro-batch is an ordinary batch DataFrame where
window functions work. But a micro-batch alone cannot see a station's previous 24 hours, so each
batch is unioned with a persisted history table, features are computed over the union, and
predictions are emitted only for the new rows.

The alternative, `flatMapGroupsWithState`, keeps history in executor memory and is faster, but
loses everything on restart. For an alerting system, surviving a restart matters more than
shaving latency.

**Why the forecast AQI is an approximation, stated openly.** The model forecasts PM2.5 only. The
National AQI is the maximum sub-index across all seven pollutants, so the forecast index combines
the forecast PM2.5 sub-index with the *current* sub-indices of the other six — assuming they hold
steady for an hour. This can only under-state a rise driven by another pollutant, never invent
one, which is the correct conservative direction for a public-health alert.
