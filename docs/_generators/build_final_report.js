// ============================================================================
// FULL PROJECT REPORT (Word) - 23AID302 Big Data Analytics, Group A14
// Every number is a measured value from docs/run_logs (named in section 8).
// Build:  IMG=<dir with figures> node build_final_report.js   (needs the 'docx' npm package)
// ============================================================================
const fs = require("fs");
const path = require("path");
const D = require("docx");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun, Header, Footer, AlignmentType, LevelFormat,
  HeadingLevel, BorderStyle, WidthType, ShadingType, PageNumber, PageBreak, TableOfContents, TabStopType } = D;

const IMG = process.env.IMG || "img";
const CH = process.env.CHARTS || "charts";
const OUT = process.env.OUT || "Project_Report.docx";
const BLUE = "0B5F8A", INK = "1A1A1A", GREY = "5A6673", LIGHT = "EAF2F8", LINE = "C8D0D8";
const W = 9026;                                       // A4 content width in DXA (1" margins)
const GH = "https://github.com/jaganath010/A-Scalable-Big-Data-Platform-for-Real-Time-Urban-Air-Quality-Tracking-and-Public-Safety-Alerting";
const WS = "https://jaganath010.github.io/A-Scalable-Big-Data-Platform-for-Real-Time-Urban-Air-Quality-Tracking-and-Public-Safety-Alerting/";

// ------------------------------------------------------------------ helpers
const run = (t, o = {}) => new TextRun({ text: t, font: "Calibri", size: 22, color: INK, ...o });
const P = (t, o = {}) => new Paragraph({ spacing: { after: 120, line: 288 }, alignment: AlignmentType.JUSTIFIED, ...o.p,
  children: (Array.isArray(t) ? t : [t]).map((x) => (typeof x === "string" ? run(x, o.r) : x)) });
const B = (t) => new Paragraph({ numbering: { reference: "bul", level: 0 }, spacing: { after: 60, line: 276 },
  children: (Array.isArray(t) ? t : [t]).map((x) => (typeof x === "string" ? run(x) : x)) });
const N = (t, ref = "num") => new Paragraph({ numbering: { reference: ref, level: 0 }, spacing: { after: 60, line: 276 }, children: [run(t)] });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: true, children: [new TextRun({ text: t })] });
const H1n = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: t })] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun({ text: t })] });
const H3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun({ text: t })] });
const bold = (t) => run(t, { bold: true });
const mono = (t) => new TextRun({ text: t, font: "Consolas", size: 19 });

const bd = { style: BorderStyle.SINGLE, size: 4, color: LINE };
const borders = { top: bd, bottom: bd, left: bd, right: bd };
function cell(t, w, o = {}) {
  const kids = (Array.isArray(t) ? t : [t]).map((x) => new Paragraph({ spacing: { after: 20 }, alignment: o.align || AlignmentType.LEFT,
    children: [typeof x === "string" ? new TextRun({ text: x, font: "Calibri", size: o.size || 19, bold: !!o.bold, color: o.color || INK }) : x] }));
  return new TableCell({ borders, width: { size: w, type: WidthType.DXA }, margins: { top: 50, bottom: 50, left: 90, right: 90 },
    shading: o.fill ? { fill: o.fill, type: ShadingType.CLEAR, color: "auto" } : undefined, children: kids });
}
function table(header, rows, widths, o = {}) {
  const total = widths.reduce((a, b) => a + b, 0);
  const hdr = new TableRow({ tableHeader: true, children: header.map((h, i) => cell(h, widths[i], { fill: BLUE, color: "FFFFFF", bold: true })) });
  const body = rows.map((r, ri) => new TableRow({ children: r.map((c, i) => {
    const hi = o.boldRows && o.boldRows.includes(ri);
    return cell(c, widths[i], { fill: hi ? LIGHT : ri % 2 ? "F7F9FB" : undefined, bold: hi, size: o.size });
  }) }));
  return [new Table({ width: { size: total, type: WidthType.DXA }, columnWidths: widths, rows: [hdr, ...body] }),
    new Paragraph({ spacing: { after: 160 }, children: [] })];
}
function pngSize(file) { const b = fs.readFileSync(file); return [b.readUInt32BE(16), b.readUInt32BE(20)]; }
let figN = 0, tabN = 0;
function fig(file, caption, maxW = 560) {
  const [w, h] = pngSize(file);
  const r = Math.min(maxW / w, 1);
  figN += 1;
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 }, keepNext: true,
      children: [new ImageRun({ type: "png", data: fs.readFileSync(file), transformation: { width: Math.round(w * r), height: Math.round(h * r) },
        altText: { title: caption, description: caption, name: "fig" + figN } })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [run(`Figure ${figN}. ${caption}`, { italics: true, size: 19, color: GREY })] }),
  ];
}
const img = (n) => path.join(IMG, n);
const ch = (n) => path.join(CH, n);
const cap = (t) => new Paragraph({ spacing: { before: 60, after: 80 }, keepNext: true, children: [run(`Table ${++tabN}. ${t}`, { bold: true, size: 20, color: BLUE })] });
const code = (lines) => lines.map((l, i) => new Paragraph({ spacing: { after: 0, line: 240 }, shading: { fill: "F2F5F7", type: ShadingType.CLEAR, color: "auto" },
  indent: { left: 120, right: 120 }, children: [mono(l || " ")] }));
const link = (t, url) => new D.ExternalHyperlink({ link: url, children: [new TextRun({ text: t, style: "Hyperlink", font: "Calibri", size: 22 })] });

// ------------------------------------------------------------------ content
const body = [];

// ---- cover
body.push(
  new Paragraph({ spacing: { before: 1200, after: 200 }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: "23AID302 — BIG DATA ANALYTICS", font: "Calibri", size: 26, bold: true, color: BLUE })] }),
  new Paragraph({ spacing: { after: 100 }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Final Project Report", font: "Calibri", size: 24, color: GREY })] }),
  new Paragraph({ spacing: { before: 400, after: 400 }, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "A Scalable Big Data Platform for Real-Time Urban Air Quality Tracking and Public Safety Alerting", font: "Calibri", size: 44, bold: true })] }),
  new Paragraph({ spacing: { after: 300 }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Group A14", font: "Calibri", size: 28, bold: true, color: BLUE })] }),
  ...table(["Team member", "Register number"], [["Sangeeth S", "CB.AI.U4AID24050"], ["Jaganath R", "CB.AI.U4AID24021"], ["Niranjan S", "CB.AI.U4AID24035"], ["PL Kowshik", "CB.AI.U4AID24036"]], [4500, 4526], { size: 22 }),
  new Paragraph({ spacing: { before: 200, after: 60 }, children: [bold("Faculty: "), run("________________________________")] }),
  new Paragraph({ spacing: { after: 60 }, children: [bold("Date: "), run("October 2026")] }),
  new Paragraph({ spacing: { after: 60 }, children: [bold("GitHub: "), link(GH, GH)] }),
  new Paragraph({ spacing: { after: 60 }, children: [bold("Website: "), link(WS, WS)] }),
);

// ---- abstract
body.push(H1("Abstract"),
  P("Urban air pollution is a public-health problem that needs low-latency analytics rather than overnight batch reports. Published air-quality models predict accurately but run on a single machine and stop at prediction: none turns a forecast into an automated public warning. This project builds the distributed platform they lack and runs it end to end."),
  P("A 1-NameNode / 4-DataNode HDFS cluster with YARN and Spark 3.5 holds a 154,583,979-row, 33 GB lakehouse that unifies structured CPCB station data (flat CSV) with semi-structured CAMS data (nested JSON). Scala jobs clean and impute the data, engineer 86 features and score a live feed; a PySpark MLlib Gradient-Boosted-Trees model (300 trees) forecasts each city's PM₂.₅ one hour ahead. On 2,074,569 real test rows it reaches R² = 0.8910 against 0.8587 for the persistence baseline, a 12.18 % reduction in RMSE."),
  P("Spark Structured Streaming scores live data in 10-second micro-batches and an alert engine converts the forecast to a CPCB AQI and raises a warning when it exceeds 150. In a live run covering 1–15 October 2026 (82,800 rows, 230 cities) the system raised 27,543 warnings across 221 cities. Results are served through Hive and a public warning board, and delivered by a de-duplicated alert loop (Telegram / e-mail). The report documents the design, the measured results, the validation of a dataset that is 88.9 % synthetic, eleven defects found by running the code, and the evidence for each claim."),
  P([bold("Keywords: "), run("Hadoop, HDFS, YARN, Apache Spark, Scala, Structured Streaming, Gradient Boosted Trees, Hive, air quality, AQI, alerting.")]));

// ---- contents
body.push(new Paragraph({ children: [new PageBreak()] }), new Paragraph({ spacing: { after: 200 }, children: [new TextRun({ text: "Contents", font: "Calibri", size: 34, bold: true, color: BLUE })] }),
  new TableOfContents("Contents", { hyperlink: true, headingStyleRange: "1-2" }));

// ---- 1 introduction
body.push(H1("1. Introduction"), H2("1.1 Problem statement"),
  P("Three gaps separate what exists from what a city needs. First, scale: existing air-quality models run on a single machine, while a city-wide, multi-year deployment produces hundreds of millions of readings that no single machine can hold in memory. Second, latency: batch analytics report after the fact, but a pollution spike is a health event that is happening now and a warning delivered tomorrow has no value. Third, automation: published frameworks stop at prediction and do not close the loop by turning a forecast into an actionable public-safety alert."),
  H2("1.2 Objectives"),
  ...table(["#", "Objective", "Success criterion", "Final result"], [
    ["1", "Fault-tolerant HDFS cluster", "≥ 2 DataNodes, 3× replication, 0 corrupt blocks", "4 DataNodes; fsck HEALTHY, 0 missing / corrupt"],
    ["2", "Distributed compute on the cluster", "Spark running under YARN", "Jobs ran as YARN applications on 4 NodeManagers"],
    ["3", "Ingest into distributed storage", "Split into 128 MB blocks", "232 raw blocks, 696 replicas; all layers 33 GB"],
    ["4", "Preprocessing in Scala", "Reads HDFS, cleans, writes back to HDFS", "146,276,379 rows → 10.0 GB Parquet, 241 partitions"],
    ["5", "Spatial-temporal features", "T+1 target, rolling history, CPCB AQI", "93,216,105 labelled rows, 86-dim vector"],
    ["6", "Distributed GBT forecaster", "Must beat the persistence baseline", "R² 0.8910 vs 0.8587, RMSE − 12.18 %"],
    ["7", "Streaming speed layer", "Structured Streaming micro-batches", "10 s trigger, ≈ 7 s latency per batch"],
    ["8", "Close the loop with alerts", "Warning when forecast AQI > 150", "27,543 warnings, 221 cities (Oct 2026)"],
  ], [400, 2500, 2800, 3326], { size: 18 }),
  H2("1.3 Why big data is needed"),
  P("The dataset is 154.6 million rows and 33 GB, on a development host with 15.7 GB of RAM: it fits only if it is partitioned and processed in a distributed way. The live feed must be scored every ten seconds. The sources come in two data models (flat CSV and nested JSON). And 88.9 % of the structured rows are synthetic expansion, so the truthfulness of the data has to be established by computation rather than assumed. These correspond to the five V's, summarised in the table below and demonstrated in Section 3.6."),
  cap("The five V's in this project"),
  ...table(["V", "Meaning here", "Measured evidence"], [
    ["Volume", "Too large for one machine", "154,583,979 rows, 33 GB, 232 blocks per raw copy, 4 DataNodes"],
    ["Variety", "Structured + semi-structured", "Flat CSV and nested JSON on one 17-column schema, read by native Spark readers"],
    ["Velocity", "Live data, low latency", "10 s micro-batches, ≈ 7 s latency; hourly alert loop"],
    ["Veracity", "Can the data be trusted?", "5 paired tests, CPCB-vs-CAMS cross-check, 11 defects fixed, every imputed value flagged"],
    ["Value", "Does it help people?", "12.18 % lower error; 27,543 warnings issued one hour ahead with health advice"],
  ], [1300, 2700, 5026], { size: 18 }));

// ---- 2 literature
body.push(H1n("2. Literature Survey and Gap"),
  P("The primary base paper is “Air Quality Prediction using Multi-Source Remote Sensing Data Integration with Hybrid Deep Learning Framework (MAST-Net)”, published in Nature Scientific Reports in December 2025. Its contribution is that fusing several environmental data streams — remote sensing, meteorology and ground sensors — improves accuracy over single-source models."),
  P("The gap this project addresses is architectural rather than statistical. The framework is built on a localised, single-machine design with no distributed infrastructure for high-volume, multi-city scaling and no streaming mechanism for immediate warnings. This project ports the multi-source fusion idea onto Hadoop and Spark (CPCB stations, CAMS reanalysis and live weather), adds Structured Streaming for latency, and closes the loop with an alert engine that turns a forecast into a warning message."),
  P("Supporting foundations are the Resilient Distributed Dataset abstraction (Zaharia et al., NSDI 2012), the Hadoop Distributed File System (Shvachko et al., MSST 2010) and Friedman's gradient boosting machine (Annals of Statistics, 2001), on which the forecaster is based."));

// ---- 3 dataset
body.push(H1("3. Dataset"), H2("3.1 The three data layers"),
  P("The project combines three layers, each with one job. The structured layer trains the model because it is the only one with the label and thirteen years of seasonality. The semi-structured CAMS history is an independent source on the same cities and hours, used to validate the data. The live CAMS and weather feed is what makes alerting possible."),
  cap("Data layers"),
  ...table(["Layer", "Source", "Format", "Rows", "Size", "Period"], [
    ["Structured", "CPCB stations (+ validated synthetic expansion)", "Flat CSV", "146,276,379", "27.5 GB", "2010–2023"],
    ["Semi-structured", "CAMS reanalysis via Open-Meteo (history)", "Nested JSON", "8,263,440", "458 MB", "2022-08 → 2026-09"],
    ["Semi-structured", "CAMS + weather, live (keyless, CC-BY 4.0)", "Nested JSON", "82,800 per refresh", "≈ 20 MB", "1–15 Oct 2026"],
  ], [1400, 2700, 1200, 1500, 900, 1326], { size: 17 }),
  P("No API key is needed anywhere: Open-Meteo serves CAMS data and weather without authentication. The unified table (next table) has one 17-column schema and is partitioned by source format."),
  cap("Rows by data source in the unified table (distributed count on YARN)"),
  ...table(["data_source", "format", "rows", "cities"], [
    ["synthetic", "structured_csv", "130,023,448", "241"], ["real", "structured_csv", "16,252,931", "241"],
    ["cams_history", "semistructured_json", "8,263,440", "230"], ["live_api", "semistructured_json", "44,160", "230"],
    ["TOTAL", "", "154,583,979", ""]], [2400, 2600, 2400, 1626], { boldRows: [4], size: 18 }),
  H2("3.2 Key attributes"),
  B("Identity and time: station_id, city, state, hourly timestamp."),
  B("Pollutants: pm25, pm10, no2, so2, co, o3, nh3 — the seven pollutants of the CPCB National AQI. They give the AQI and the label (next-hour PM₂.₅)."),
  B("Weather: temperature, humidity, wind speed and direction, pressure, rainfall, solar radiation."),
  B("Context: traffic_index, urbanization_index, climate_type, is_rush_hour."),
  B("Provenance: data_source, source_format and one *_was_imputed flag per imputed column, so measured and estimated values are never confused."),
  P("After cleaning the table has 44 columns; feature engineering produces 54 numeric features and a 32-wide one-hot encoding, a vector of 86 dimensions."),
  H2("3.3 The CAMS coverage finding"),
  P("The brief asked for semi-structured data covering 2010–2023. This was tested before anything was built. The source rejects requests before 2013-01-01, and for 2013-01 through 2022-07 it returns timestamps with every value null (0 % fill). Real data begins in August 2022 (89.7 % fill) and is about 99.8 % filled from September 2022 (ammonia is 0 % throughout). Delivering 2010–2023 would have produced ten years of rows that look like coverage and contain nothing, so coverage starts in August 2022 and the reason is stated. 230 of 241 cities resolved to coordinates; 11 small localities had no geocode and were excluded rather than given invented coordinates."),
  H2("3.4 Synthetic expansion and its validation (veracity)"),
  P("88.9 % of the structured rows (130,023,448 of 146,276,379) are a synthetic expansion of 16,252,931 real station-hours. Because accuracy claims would be meaningless if the synthetic rows were easier to predict than real ones, every synthetic station is tested against its own real parent with five paired tests, and a FAIL blocks the run."),
  cap("The five paired veracity tests"),
  ...table(["#", "Test", "The failure it catches"], [
    ["1", "Persistence R² (synthetic vs real parent)", "Fake data that is easier to predict than real data"],
    ["2", "Autocorrelation at lags 1–6 h", "Random noise or over-smoothing"],
    ["3", "Quantiles p5–p95", "Drift and inflated variance"],
    ["4", "Missingness rate", "Gaps filled in to make the data look easy"],
    ["5", "Cross-correlation between pollutants", "Noise that breaks physical links between pollutants"],
  ], [500, 4300, 4226], { size: 18 }),
  P("The first generator scored 0.856 persistence R² on synthetic data against 0.733 on real data on test 1: it would have failed, and was replaced. The final generator passes all five tests. Independently, the CPCB station data was compared with CAMS on 1,152,707 matched city-hours (Section 7.2)."),
  H2("3.5 Live feed"),
  P("The live feed is CAMS air quality and Open-Meteo weather for 230 cities, fetched in the same cycle so that their time windows align (an earlier mismatch joined to zero rows). Raw CAMS JSON carries only 28 of the model's 54 numeric features, so a Scala job (LiveEnrichment) adds weather, derived features, city profiles and provenance flags (Section 5.7)."),
  H2("3.6 The five V's demonstrated"),
  P("Volume: 154.6 M rows and 33 GB, replicated three times across four DataNodes. Variety: the Spark readers ingest flat CSV and nested JSON natively and union them on one schema in a single job. Velocity: the streaming job processes micro-batches every ten seconds. Veracity: five paired tests, a cross-check against an independent source, eleven defects found and fixed, and a provenance flag on every filled value — the model even ranks the pm25_was_imputed flag sixth of 86 features, evidence that it learned to discount estimated values. Value: a forecast 12.18 % more accurate than the honest baseline, converted into warnings delivered an hour ahead."));

// ---- 4 architecture
body.push(H1("4. System Architecture"),
  P("The system is Lambda-style: a batch layer trains the model on thirteen years of history, and a speed layer scores live data against the same model, both sharing one HDFS lakehouse. Figure 1 shows the components; the model is stored in HDFS and loaded by the streaming job."),
  ...fig(img("architecture.png"), "System architecture: sources, ingest, HDFS storage, Spark on YARN (batch and speed layers), serving and alerting", 600),
  cap("Components and their roles"),
  ...table(["Component", "Technology", "Role"], [
    ["Storage", "Hadoop HDFS 3.3.6 (1 NameNode + 4 DataNodes)", "128 MB blocks, 3× replication (derived layers 2×), Parquet + Snappy"],
    ["Resource management", "Hadoop YARN (1 ResourceManager + 4 NodeManagers)", "Schedules Spark applications; each NodeManager 3 GB, 2 vcores"],
    ["Batch compute", "Apache Spark 3.5.6, Scala 2.12.18", "CleanSelect (clean, impute) and FeatureExtraction (86 features, label)"],
    ["Machine learning", "PySpark MLlib GBTRegressor", "Trains and evaluates the forecaster; model saved to HDFS"],
    ["Speed layer", "Spark Structured Streaming (Scala)", "LiveEnrichment and AirQualityStream: 10 s micro-batches, alert engine"],
    ["Serving", "Apache Hive (external tables), HiveServer2", "SQL over the Parquet lake; export to the dashboard"],
    ["Alerting", "Python dispatcher (Telegram / e-mail)", "De-duplicated delivery of warnings"],
    ["Deployment", "Docker Compose (11 containers)", "Cluster runs on one development host"],
  ], [1800, 3200, 4026], { size: 17 }),
  P("Scala 2.12.18 is not a free choice: it is the version Spark 3.5.6 is built against, and a 2.13 or 3.x build compiles but fails at run time with NoSuchMethodError. Scala is used for the latency-critical and cluster-side jobs; PySpark is used for model training and analytics."));

// ---- 5 implementation
body.push(H1("5. Implementation"), H2("5.1 HDFS cluster"),
  P("A cluster of one NameNode and four DataNodes runs in Docker. Four DataNodes, not the minimum two or three, because with three nodes and replication 3 every node must hold every block, so nothing distributes and a failed node has nowhere to re-replicate. The raw 27.5 GB dataset is split into 232 blocks of at most 128 MB (the number of blocks per file is ceil(filesize / 128 MB)), giving 696 replicas and 82.4 GB on disk. fsck reports the filesystem HEALTHY with no missing, corrupt or under-replicated blocks."),
  ...fig(img("s7_1.png"), "dfsadmin report: 4 live DataNodes", 560),
  ...fig(img("s8_1.png"), "fsck of the raw layer: HEALTHY, 232 blocks, replication 3.0, 0 missing / corrupt", 440),
  H2("5.2 YARN and Spark"),
  P("Spark runs on YARN with four NodeManagers (3 GB and 2 vcores each; maximum container 2,560 MB). A distributed count over the unified table was run as a YARN application and reproduced the known total of 154,583,979 rows. Phase 4 ran in Spark local mode because four 3 GB NodeManagers advertise 12 GB on a 15.7 GB host and YARN executors were killed (exit 137) under memory pressure; YARN execution is demonstrated by the live-enrichment and recount applications."),
  ...fig(img("hdfs_dn_crop.png"), "HDFS NameNode UI: DataNodes in service", 440),
  ...fig(img("yarn_nodes_crop.png"), "YARN ResourceManager: four NodeManagers, all RUNNING", 500),
  ...fig(img("yarn_apps.png"), "YARN applications: the Spark recount job, FINISHED / SUCCEEDED", 560),
  H2("5.3 Preprocessing (CleanSelect.scala)"),
  P("CleanSelect reads the raw CSV from HDFS, applies ten operations and writes snappy-compressed Parquet partitioned by city. It ran on all 146,276,379 rows in about 28 minutes and shrank the data 2.75 times (27.5 GB to 10.0 GB)."),
  N("Explicit 32-column schema, no inference."), N("Type casting; unparseable values become null."), N("Timestamp parsing; rows with unparseable timestamps are dropped."),
  N("Binary flags repaired to strictly 0 / 1."), N("Physical range clamping (for example humidity to 0–100)."), N("Anomaly removal: readings outside sensor-plausible limits are nulled."),
  N("Three-tier median imputation: station/month/hour, then city/month, then global."), N("Provenance flags: one *_was_imputed column per imputed column."),
  N("Label protection: pm25_measured keeps the pre-imputation value so the model is never trained on an imputed label."), N("Columnar write: Snappy Parquet, partitioned by city (241 directories)."),
  P("Only about 46 % of rows carry all seven pollutants, so imputation is necessary; every filled value is flagged."),
  cap("Share of values imputed per column"),
  ...table(["Column", "Imputed", "Measured", "Column", "Imputed", "Measured"], [
    ["pm25", "27.17 %", "72.83 %", "nh3", "41.72 %", "58.28 %"], ["pm10", "34.20 %", "65.80 %", "solar_radiation", "40.76 %", "59.24 %"],
    ["no2", "21.58 %", "78.42 %", "pressure", "55.28 %", "44.72 %"], ["so2", "25.50 %", "74.50 %", "wd_degree", "28.77 %", "71.23 %"],
    ["co", "25.28 %", "74.72 %", "o3", "26.89 %", "73.11 %"]], [1500, 1400, 1500, 1800, 1400, 1426], { size: 18 }),
  ...fig(img("s10_1.png"), "CleanSelect at full scale: 146,276,379 rows in, 146,276,379 out", 440),
  ...fig(img("s11_1.png"), "Processed layer in HDFS: one directory per city (241)", 420),
  H2("5.4 Spark workflow: DAG, partitioning and caching"),
  P("The jobs use the DataFrame API; Catalyst compiles it to RDD stages, and MLlib's GBT works on RDDs internally (training issued over 1,300 Spark jobs). The feature-engineering job is a chain of six steps: read Parquet (232 parallel tasks, one per block), remove duplicates (a shuffle by station and hour), add rolling-history features (a window shuffle), attach the next-hour label, assemble the 86-dimensional vector, and write one directory per city (a shuffle by city). Rows go 146.3 M → 128.7 M → 93.2 M and the job takes 73.5 minutes."),
  cap("Partitioning and caching choices"),
  ...table(["Topic", "Choice", "Reason"], [
    ["HDFS blocks", "128 MB blocks", "232 input splits = 232 parallel tasks for the raw copy"],
    ["Disk partitioning", "partitionBy(city) = 241 directories", "A query for one city reads one directory. Partitioning by year/month produced 5,237 tiny files (244 KB median) and was rejected"],
    ["Unified table", "partitionBy(source_format) = 2", "Prunes the structured or semi-structured side"],
    ["Shuffle partitions", "400 / 200 / 120 / 64 / 16 by job", "Sized to each job's data and the host memory"],
    ["Write layout", "repartition(city) before write", "A few large files per city instead of many small ones"],
    ["Broadcast joins", "median tables t1 and t2", "Turns two shuffle joins into map-side joins"],
    ["Caching", "cleaning table, GBT train/test sets, stream predictions", "Each is reused several times; unpersist() frees memory afterwards"],
    ["Checkpointing", "GBT checkpoint directory", "Breaks long lineage; an earlier full-scale run died with a StackOverflow at 3 h 50 m"],
  ], [1700, 3000, 4326], { size: 17 }),
  H2("5.5 Feature engineering (FeatureExtraction.scala)"),
  P("Features are computed per station over time-ordered windows. Rolling windows use rangeBetween on the timestamp value rather than on row position, so a missing hour shortens the window instead of silently reaching further back in time; this makes the rolling features gap-safe."),
  ...code(['val dedupW = Window.partitionBy("station_id","variation_bucket","ts_unix")', '                   .orderBy(col("pm25").desc_nulls_last)', 'df = df.withColumn("_rn", row_number().over(dedupW)).filter(col("_rn")===1)', '', 'def hoursBack(n: Int) = Window.partitionBy("station_id","variation_bucket")', '  .orderBy("ts_unix").rangeBetween(-(n-1).toLong * Hour, 0L)   // value-based, gap-safe', 'df = df.withColumn(s"${p}_avg${h}h", avg(col(p)).over(hoursBack(h)))']),
  new Paragraph({ spacing: { after: 120 }, children: [] }),
  P("The feature groups are: the current pollutants; history (lag_1h, rolling 3/6/24 h means, std_6h, delta_1h, surge_ratio); CPCB sub-indices and rolling AQI (24 h averages for PM, NO₂, SO₂, NH₃ and 8 h for CO and O₃); weather; time of day as sin/cos; traffic and urbanization context; and the provenance flags."),
  P("The label is the next-hour PM₂.₅, defined only when the next record is exactly one hour later (next_ts = ts + 3600 s). An earlier positional lead() would have mislabelled 8.69 % of targets across gaps; 12.3 % of rows have no genuine next hour and are dropped rather than guessed."),
  H2("5.6 The forecasting model"),
  P("The forecaster is Spark MLlib's GBTRegressor. Gradient boosting builds one small tree at a time; each new tree is fitted to the errors (residuals) the ensemble still makes, and its output is added scaled by a small step size, so the forecast is the sum of the trees. It captures non-linear interactions (wind, temperature and humidity together), needs no feature scaling, copes with mixed units and one-hot flags, is native to MLlib so training distributes across the data partitions, and yields feature importance."),
  cap("GBT configuration"),
  ...table(["Setting", "Value", "Why"], [
    ["Trees (maxIter)", "300", "Small steps need many rounds; the plan's default of 20 was far too few"],
    ["Depth (maxDepth)", "6", "Up to 64 leaves per tree"],
    ["Step size (η)", "0.08", "Gradual correction of errors"],
    ["Row subsampling", "0.8", "Decorrelates the trees"],
    ["Feature subset", "sqrt (≈ 9 of 86)", "A random handful of features per split"],
    ["Max bins", "64", "Histogram split search: speed and memory"],
    ["Target", "PM₂.₅(t+1) − PM₂.₅(t)", "Predict the change, then add the current value back"],
    ["Training rows", "10,000,552", "Seeded 13.41 % sample of 74,544,984 (RAM ceiling)"],
    ["Test rows", "18,671,121", "Not sampled: every row of the hold-out is scored"],
  ], [2200, 2600, 4226], { size: 17 }),
  P([bold("Delta target. "), run("Trees are piecewise-constant: asked for the level they spend capacity re-deriving “about the same as now”. Predicting the change removes that burden. In a controlled local reproduction the level target gave R² 0.9098 (5.6 % better than persistence) and the change target R² 0.9201 (11.3 % better) with the same trees and features.")]),
  P([bold("Chronological split. "), run("A random split leaks on a time series: consecutive hours correlate at about 0.81, so hour T in the training set and T+1 in the test set means the model has effectively seen the answer. Training uses the earlier part of the history; the test window is 2022-07-01 to 2023-03-31, the most recent.")]),
  P([bold("Persistence gate. "), run("Every run computes the “next hour = this hour” baseline on the same test rows and prints *** FAIL *** if the model does not beat it, so a model can never be reported without that comparison.")]),
  H2("5.7 Live enrichment (LiveEnrichment.scala)"),
  P("Raw CAMS JSON lacks 26 of the model's 54 numeric features and the provenance flags. One Spark job on YARN joins CAMS, the weather feed and the city profiles: eight weather features come from the Open-Meteo weather API, five derived features (ventilation, scrub factor, stagnation, temperature×humidity, is_raining) are computed once weather exists, three context features come from city_profiles.csv, and ten *_was_imputed flags record whether the API returned a value. Two unit conversions were measured, not assumed: CO from µg/m³ to mg/m³ (divide by 1000; unconverted, structured CO averages 0.95 against 566 for CAMS) and pressure from hPa to mmHg (× 0.750062; the result 753.81 matches the structured median of 753)."),
  P("The October run joined 82,800 rows (230 cities × 360 hours, 2026-10-01 to 2026-10-15) with no nulls in the model-critical columns."),
  H2("5.8 Structured Streaming speed layer (AirQualityStream.scala)"),
  P("AirQualityStream watches an HDFS directory with the file source and a 10-second trigger. A micro-batch alone cannot see a station's previous 24 hours, so each batch is unioned with a persisted 30-hour history table on HDFS, features are computed over the union, predictions are emitted only for the new rows, and the history is then updated. A persisted table was chosen over in-memory state because it survives job restarts. The GBT pipeline and model are loaded from HDFS (MLlib's on-disk format is language-neutral)."),
  ...code(['val raw = spark.readStream.schema(InputSchema).option("header","true")', '  .option("maxFilesPerTrigger","1").csv(StreamInput)        // HDFS file source', 'raw.writeStream.option("checkpointLocation", CheckpointDir)', '  .foreachBatch { (batch: DataFrame, id: Long) =>', '     // union with 30 h history -> features -> GBT -> AQI -> alerts.write.partitionBy("city")', '  }.trigger(Trigger.ProcessingTime("10 seconds")).start()']),
  new Paragraph({ spacing: { after: 120 }, children: [] }),
  H2("5.9 Alert engine and delivery"),
  P("The forecast PM₂.₅ is converted to a CPCB National AQI (the maximum sub-index over the pollutants) with the band and the dominant pollutant, and a warning is written when the forecast AQI exceeds 150. Delivery is a separate step (send_alerts.py) that picks, per city, the worst forecast hour in the next six hours and applies de-duplication: a city is messaged only if it is newly under warning, if its severity got worse, or after a six-hour cooldown while still warned. When a city leaves warning its state is cleared, so a later recurrence alerts again. Delivery channels are Telegram (people subscribe by messaging the bot “/city Hisar”) and e-mail, with an always-on outbox log. Without credentials it runs as a dry run and never claims a message reached a phone."),
  P("An hourly loop (run_hourly_cycle.py) separates two cadences: scoring (fetch, enrich, stream, export) every six hours, because the CAMS source refreshes only a few times a day, and dispatch every hour from the already-scored forecast. Only forecast hours newer than the last scored hour are handed to the stream. A replay of the real October forecast showed the rule working: at 20:00 two cities were messaged, at 21:00 those two were suppressed while two others were messaged, and the next morning no city was under warning."),
  H2("5.10 Hive serving layer"),
  P("Three external tables (unified_airquality, clean_airquality, stream_alerts) and three views are defined over the Parquet already in HDFS, exposed through HiveServer2. Because the tables are external they add SQL over 154 million rows at no storage cost and dropping a table removes only metadata. All six demonstration queries return real results; one of them shows Delhi's seasonal cycle (Section 6.6)."),
  H2("5.11 Public warning board"),
  P("A single static HTML page is built from a Hive export: Hive tables are queried by an export job into one JSON, which is embedded in the page. It opens without a server or internet access. Each warning card shows the message residents would receive (forecast AQI, the hour, the cause, CPCB health advice and what to do), with search, a severity filter, a map, warnings per hour, a WhatsApp share button and an “Alert me” browser-notification panel."),
  ...fig(img("site_top.png"), "Public warning board (October 1–15, 2026 run): 221 cities under warning", 480));

// ---- 6 results
body.push(H1("6. Results"), H2("6.1 Forecast accuracy"),
  P("The headline figure is quoted on real rows: the synthetic rows are easier to predict, so the blended number would flatter the model. On 2,074,569 real station-hours the GBT reaches R² 0.8910 against 0.8587 for persistence, and cuts RMSE from 24.831 to 21.806 µg/m³ (12.18 %). On all 18,671,121 test rows the figures are R² 0.8884 against 0.8563 (RMSE 22.429 against 25.443, 11.85 % lower). Persistence is an honest bar: doing nothing already scores 0.8587."),
  cap("Evaluation results"),
  ...table(["Test rows", "Model", "R²", "RMSE", "MAE"], [
    ["Real (n = 2,074,569)", "Persistence baseline", "0.8587", "24.831", "9.937"], ["Real (n = 2,074,569)", "GBT forecaster", "0.8910", "21.806", "8.926"],
    ["All (n = 18,671,121)", "Persistence baseline", "0.8563", "25.443", "10.357"], ["All (n = 18,671,121)", "GBT forecaster", "0.8884", "22.429", "9.353"],
  ], [2500, 2500, 1200, 1400, 1426], { boldRows: [1], size: 18 }),
  ...fig(ch("rmse.png"), "RMSE of the persistence baseline and the GBT on real rows", 380),
  H2("6.2 Model comparison and tuning"),
  P("Tuning was done by controlled experiments rather than a blind grid search: tree count (20, 120, 300) and level versus delta target. A pilot on 19 cities with 120 trees gave a 5.67 % RMSE reduction; scaling to all 241 cities and 300 trees roughly doubled it to 12.18 %."),
  cap("Experiments and RMSE reduction against persistence"),
  ...table(["Experiment", "RMSE reduction"], [["Persistence (next hour = this hour)", "baseline"], ["Pilot: 19 cities, 120 trees", "5.67 %"], ["Local reproduction: level target", "5.6 %"], ["Local reproduction: delta target", "11.3 %"], ["Full: 241 cities, 300 trees, delta target", "12.18 %"]], [6000, 3026], { boldRows: [4], size: 18 }),
  H2("6.3 What the model learned"),
  P("Where a station is now (pm25) and which way it is moving (pm25_delta_1h, pm25_surge_ratio) matter most. The pm25_was_imputed provenance flag ranks sixth of 86 inputs: the model learned to discount filled-in readings, direct evidence that flagging every imputed value was the right design."),
  ...fig(ch("importance.png"), "Top-10 feature importances of the trained GBT", 470),
  H2("6.4 Streaming performance"),
  P("After the JVM warms up, 120-row replay batches take about 7 seconds end to end (10.8, 7.8, 7.0 and 6.9 s for batches 0–3). The October batch scored 82,800 rows in one pass in 57.8 seconds with no history (a cold start)."),
  ...fig(ch("latency.png"), "Latency per micro-batch", 400),
  H2("6.5 October 2026 live run"),
  P("The October 1–15 run scored 82,800 live rows and raised 27,543 warnings across 221 of the 230 monitored cities; 32 cities were forecast Severe (AQI above 400). The worst forecasts were in Haryana and Punjab (Hisar, Bhiwani, Fatehabad, Kaithal, Karnal, Patiala, all AQI 500 driven by coarse dust PM₁₀), the post-monsoon dust and stubble-burning belt. The cause mix is 44 % ozone and 36 % coarse dust, which implies different advice: avoid midday exertion for ozone, wear a mask for dust."),
  ...fig(ch("severity.png"), "October 2026 warnings by CPCB severity and by dominant pollutant", 540),
  H2("6.6 Seasonality"),
  P("Delhi's measured PM₂.₅ swings 5.5 times between the August monsoon low (38.8 µg/m³) and the November peak (213.6 µg/m³). This is why thirteen years of history are kept: a model trained on one season would not generalise."),
  ...fig(ch("delhi.png"), "Delhi monthly mean PM2.5, measured values only (Hive query)", 460),
  H2("6.7 Business insight"),
  B("A warning reaches residents one hour ahead, with CPCB health advice and the cause."),
  B("Alerts can be targeted: the Haryana–Punjab dust belt needs a different message from the ozone-driven warnings elsewhere."),
  B("Because every filled value is flagged and accuracy is quoted on real rows, the figures can be defended."));

// ---- 7 validation
body.push(H1("7. Validation and Testing"), H2("7.1 Defects found by running the code"),
  P("Eleven defects were found, four in the data and seven in code that had been written but never run. Two gave plausible wrong answers with no error at all, which is more dangerous than a crash: 16,560 live rows went into a stage and zero came out, and a Hive table returned correct counts next to NULL timestamps. The habit that caught them was to reconcile every output count against an independently known number."),
  cap("The eleven defects"),
  ...table(["Defect", "How it was caught / fix"], [
    ["Flags not binary (24,725 distinct values)", "Round to 0 / 1"],
    ["T+1 label via lead(): 8.69 % wrong horizon", "Require next_ts = ts + 3600 s"],
    ["Impossible values (humidity 104.999 %)", "Clamp to physical range"],
    ["Only 43 % of rows have all 7 pollutants", "Three-tier imputation, every fill flagged"],
    ["Substring join double-counted Mumbai / Noida", "44,544 ≠ 44,160 rows; exact-basename join"],
    ["Streaming used ts_unix before it existed", "Alerts printed then the stream stalled; derive ts_unix once"],
    ["VectorAssembler silently dropped every live row", "16,560 in, 0 out; fill after flagging provenance"],
    ["paths.py built hdfs:////host (four slashes)", "Printed the resolved path; fixed the join"],
    ["HDFS write died: no spare DataNode", "Replication 2 for derived layers, replace-datanode policy NEVER, 180 s timeouts"],
    ["numpy missing in the Spark image", "Training failed at import; installed"],
    ["Hive table referenced a column that does not exist", "NULL timestamps with correct counts; table fixed"],
  ], [4500, 4526], { boldRows: [6, 10], size: 17 }),
  H2("7.2 Independent cross-validation against CAMS"),
  P("The CPCB station data was compared with CAMS on 1,152,707 matched city-hours. Particulates track moderately (PM₂.₅ r = 0.565, PM₁₀ r = 0.558), ozone and NO₂ less (0.361, 0.219) and SO₂ shows essentially no agreement (0.083). The result is mixed and is reported as mixed. A synthetic-versus-CAMS comparison was also run and discarded: city-hour averaging cancels the synthetic perturbation, so the test cannot tell synthetic from real."),
  ...fig(ch("crossval.png"), "Pearson correlation between CPCB and CAMS by pollutant", 380));

// ---- 8 evidence
body.push(H1("8. Evidence"),
  P("Every claim traces to a preserved log in docs/run_logs, a screenshot of the running cluster, or a script that reproduces it. The table below maps the key claims to their proof."),
  cap("Claim to evidence"),
  ...table(["Claim", "Where the proof is"], [
    ["154,583,979 rows, one schema", "spark_on_yarn_demo.log; merge_run.log"],
    ["4 DataNodes, replication 3, HEALTHY", "dfsadmin and fsck screenshots (Section 5.1)"],
    ["Spark job on YARN reading HDFS", "YARN UI screenshots; spark_on_yarn_demo.log"],
    ["146,276,379 rows cleaned, 241 city partitions", "CleanSelect run and HDFS browse (Section 5.3)"],
    ["93,216,105 labelled rows, 86 features, 73.5 min", "phase4_fullscale.log"],
    ["R² 0.8910 vs 0.8587, RMSE − 12.18 %", "trackB_train_fullscale.summary.log"],
    ["CPCB vs CAMS cross-validation", "crossval.log; scripts/04_cross_validate_overlap.py"],
    ["October 2026: 82,800 rows, 27,543 alerts, 221 cities", "october_live_cycle.log; october_stream_scoring.log"],
    ["De-duplicated alert dispatch", "hourly_dedupe_demo.log; scripts/send_alerts.py"],
    ["Hive tables and the Delhi seasonal query", "hive_create.log; hive_queries.log"],
    ["Every number reproducible", "scripts/_audit (15 scripts); docs/WORK_LOG.md"],
  ], [4300, 4726], { size: 17 }),
  P("Verbatim evaluation block of the 300-tree training run (trackB_train_fullscale.summary.log):"),
  ...code(["train 10,000,552 rows | test 18,671,121 rows", "test window: 2022-07-01 -> 2023-03-31", "PERSISTENCE BASELINE  R2=0.8563 RMSE=25.443", "trained on 10,000,552 rows, 300 trees", "REAL ROWS ONLY (n=2,074,569)", "  persistence baseline  0.8587  24.831  9.937", "  GBT model             0.8910  21.806  8.926", "  RMSE reduction        12.18%", "PASS (real rows): beats persistence by 0.0323 R2"]),
  new Paragraph({ spacing: { after: 120 }, children: [] }),
  P("Phase 4 summary (phase4_fullscale.log) and the October streaming batch (october_stream_scoring.log):", { p: { alignment: AlignmentType.LEFT } }),
  ...code(["rows in            : 146,276,379", "rows after dedupe  : 128,660,967", "rows with T+1 label: 93,216,105", "FEATURE VECTOR DIM : 86      partitioned by: city      elapsed: 4411.0 s", "", "[batch 0] no history yet - first run", "[batch 0] *** 27543 ALERTS ***", "[batch 0] rows in=82,800  predicted=82,800  alerts=27,543  latency=57,820 ms"]),
  new Paragraph({ spacing: { after: 120 }, children: [] }));

// ---- 9 challenges
body.push(H1("9. Challenges and Limitations"),
  cap("Challenges, causes and resolutions"),
  ...table(["Challenge", "Root cause", "Resolution"], [
    ["Spark could not write to HDFS from the host", "The NameNode returns container-internal DataNode addresses", "Run Spark inside the cluster network"],
    ["Full-scale write died after computing", "DataNodes unresponsive under memory pressure; no spare node at replication 3", "Driver 7 → 5 GB, replication 2, replace-datanode policy NEVER, 180 s timeouts"],
    ["YARN executors killed (exit 137)", "4 × 3 GB NodeManagers advertise 12 GB on a 15.7 GB host", "Phase 4 in local mode; YARN proven by the enrichment job"],
    ["Shuffle spill filled the C: drive", "Scratch volume lives in the WSL2 disk (peaked at 65 GB)", "Guard job kills below 30 GB free; never tripped"],
    ["Live rows silently dropped", "VectorAssembler skip and an always-null CAMS ammonia column", "Fill after flagging provenance"],
    ["Live feeds shared zero hours", "Fetched weeks apart", "Fetch both in one cycle; window report added"],
    ["Stale weather reused in a refresh", "Resumable fetcher skipped existing files", "Staging folders are cleared before each fetch"],
  ], [2600, 3200, 3226], { size: 17 }),
  H2("9.1 Limitations"),
  B("88.9 % of the structured rows are synthetic. Results are therefore reported on real rows only."),
  B("The model was trained on a seeded 10 M-row sample of 74.5 M rows because of single-host RAM; evaluation is not sampled."),
  B("CAMS is a model product, not a sensor feed, and refreshes only a few times a day; SO₂ agreement with CPCB is poor (r = 0.083). Real-time CPCB station data needs an API key."),
  B("The October result is a snapshot of one run scored as a single batch with a cold-start history; the page does not update itself."),
  B("Telegram and e-mail delivery are built and dry-run tested but no live message was sent (no bot token configured); SMS needs a paid gateway. The full scoring stage of the hourly loop was run end to end, but the hand-off to the stream was not exercised because there were no new forecast hours."),
  B("230 of 241 cities have live coverage."));

// ---- 10 conclusion
body.push(H1("10. Conclusion and Future Work"),
  P("The platform does what its title says. A fault-tolerant four-node HDFS lakehouse holds 154.6 million rows; Spark on YARN runs the Scala cleaning and feature jobs and a 300-tree GBT forecaster that is 12.18 % more accurate than the honest baseline on real rows; Structured Streaming scores live data in ten-second micro-batches; and the alert engine turned an October run into 27,543 warnings with health advice, served through Hive, a public warning board and a de-duplicated delivery loop. The contribution is not only a model but a measured, reproducible and honest pipeline: every filled value is flagged, accuracy is quoted on real rows, and eleven defects were found by running the code."),
  H2("10.1 Future work"),
  B("Schedule the hourly loop on a small always-on server and connect a paid SMS gateway; scale Telegram sign-up."),
  B("Compare against Random Forest and XGBoost baselines."),
  B("Add neighbour-station features (a GraphX station network)."),
  B("Resolve the 11 unmatched localities and add ground-truth SO₂ validation."),
  B("Move to a multi-host cluster so the full 74.5 M training rows can be used, and use a real-time CPCB feed with an API key."));

// ---- 11 reproduce
body.push(H1("11. Repository and How to Reproduce"),
  P([run("The code, logs and this report are in the GitHub repository "), link(GH, GH), run(". The public warning board is at "), link(WS, WS), run(" (GitHub Pages).")]),
  cap("Repository layout"),
  ...table(["Path", "Contents"], [
    ["scala/streaming/src/main/scala/", "CleanSelect, FeatureExtraction, LiveEnrichment, AirQualityStream (1,536 lines of Scala)"],
    ["scripts/", "PySpark: 03_train_gbt.py, data fetchers, merge, cross-validation, run_daily_live_cycle.py, run_hourly_cycle.py, send_alerts.py, _audit/"],
    ["hive/", "External tables, views, demonstration queries"],
    ["hadoop/", "Docker Compose for HDFS, YARN and Spark (11 containers)"],
    ["dashboard/", "Hive export, build script and the static warning board"],
    ["demo/", "Spark-on-YARN demonstration (start_demo.ps1)"],
    ["presentation/", "Final review deck and the first-review deck"],
    ["docs/", "This report, WORK_LOG.md, ARCHITECTURE.md, ALERTING.md, dataset report, run_logs/"],
  ], [3200, 5826], { size: 17 }),
  H2("11.1 Running it"),
  N("Start Docker Desktop and the cluster: docker compose -f docker-compose.yml -f docker-compose.yarn.yml -f docker-compose.spark.yml up -d (in hadoop/).", "num2"),
  N("Run the demonstration: powershell -ExecutionPolicy Bypass -File demo\\start_demo.ps1 (Spark on YARN over HDFS, then the website).", "num2"),
  N("Run the pipeline phases in the order given in RUNBOOK.md (clean, features, train, stream, Hive, dashboard).", "num2"),
  N("Alerting: python scripts\\run_hourly_cycle.py --once dispatch (dry run until TELEGRAM_BOT_TOKEN is set).", "num2"),
  P("The ~33 GB dataset is not stored in the repository; docs/DATASET_REPORT.pdf describes how it is built and scripts/00*.py regenerate it."));

// ---- references
body.push(H1("References"),
  ...[
    "[1] Air Quality Prediction using Multi-Source Remote Sensing Data Integration with Hybrid Deep Learning Framework (MAST-Net). Nature, Scientific Reports, December 2025.",
    "[2] Apache Hadoop 3.3.6 Documentation. The Apache Software Foundation. hadoop.apache.org/docs/r3.3.6/",
    "[3] Apache Spark 3.5.6 Documentation (SQL, MLlib, Structured Streaming). The Apache Software Foundation. spark.apache.org/docs/3.5.6/",
    "[4] Central Pollution Control Board. National Air Quality Index — Report of the Expert Group, 2014. Government of India.",
    "[5] Zaharia, M. et al. Resilient Distributed Datasets: A Fault-Tolerant Abstraction for In-Memory Cluster Computing. NSDI, 2012.",
    "[6] Shvachko, K., Kuang, H., Radia, S., Chansler, R. The Hadoop Distributed File System. IEEE MSST, 2010.",
    "[7] Friedman, J. H. Greedy Function Approximation: A Gradient Boosting Machine. Annals of Statistics 29(5), 2001.",
    "[8] Copernicus Atmosphere Monitoring Service (CAMS), ECMWF, via the Open-Meteo Air Quality API (CC-BY 4.0). open-meteo.com",
    "[9] Apache Hive and Apache Parquet Documentation. hive.apache.org, parquet.apache.org",
  ].map((t) => new Paragraph({ spacing: { after: 100 }, children: [run(t)] })));

// ------------------------------------------------------------------ document
const doc = new Document({
  creator: "Group A14", title: "Final Project Report - Air Quality Big Data Platform",
  styles: {
    default: { document: { run: { font: "Calibri", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 34, bold: true, font: "Calibri", color: BLUE },
        paragraph: { spacing: { before: 240, after: 200 }, outlineLevel: 0, keepNext: true } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 27, bold: true, font: "Calibri", color: "0D3B5E" },
        paragraph: { spacing: { before: 220, after: 120 }, outlineLevel: 1, keepNext: true } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 23, bold: true, font: "Calibri" },
        paragraph: { spacing: { before: 160, after: 80 }, outlineLevel: 2, keepNext: true } },
    ],
  },
  numbering: { config: [
    { reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] },
    { reference: "num", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] },
    { reference: "num2", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] },
  ] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1300, right: 1440, bottom: 1300, left: 1440 } } },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: LINE, space: 4 } },
      children: [new TextRun({ text: "23AID302 Big Data Analytics · Group A14 · Final Project Report", font: "Calibri", size: 17, color: GREY })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ children: ["Page ", PageNumber.CURRENT, " of ", PageNumber.TOTAL_PAGES], font: "Calibri", size: 18, color: GREY })] })] }) },
    children: body,
  }],
});
Packer.toBuffer(doc).then((b) => { fs.writeFileSync(OUT, b); console.log("wrote", OUT, (b.length / 1024).toFixed(0) + " KB"); });
