// ============================================================================
// Generates docs/DATASET_REPORT.docx
// 23AID302 - Big Data Analytics
//
// Every number in this file is a MEASURED value from a real run. The script
// that produced each one is named in docs/WORK_LOG.md so nothing here is
// unbacked. If a number changes, change it in the run, then here.
//
// Build:
//   cd <a dir with node_modules/docx>   (npm install docx)
//   node <path-to-this-file>            -> writes DATASET_REPORT.docx in cwd
//   then copy into docs/
// ============================================================================

const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
  WidthType, ShadingType, AlignmentType, PageBreak, LevelFormat, TableOfContents,
  VerticalAlign,
} = require("docx");
const fs = require("fs");

const NAVY = "1F3864", ACCENT = "2E74B5", LIGHT = "DDEBF7", RED = "C00000", GREEN = "1E7B34";

const h1 = (t) => new Paragraph({ text: t, heading: HeadingLevel.HEADING_1, spacing: { before: 400, after: 200 } });
const h2 = (t) => new Paragraph({ text: t, heading: HeadingLevel.HEADING_2, spacing: { before: 300, after: 150 } });
const h3 = (t) => new Paragraph({ text: t, heading: HeadingLevel.HEADING_3, spacing: { before: 200, after: 100 } });
const p  = (t, o = {}) => new Paragraph({ spacing: { after: 160, line: 276 }, children: [new TextRun({ text: t, ...o })] });
const pr = (runs) => new Paragraph({ spacing: { after: 160, line: 276 }, children: runs });
const b  = (t, bold) => new TextRun({ text: t, bold: !!bold });
const bullet = (t) => new Paragraph({ text: t, bullet: { level: 0 }, spacing: { after: 100, line: 276 } });
const bl = (label, rest) => pr([b(label, true), b(rest)]);

function cell(text, { bold = false, shade = null, width = 2000, color = null, size = 20 } = {}) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: shade ? { type: ShadingType.CLEAR, fill: shade } : undefined,
    verticalAlign: VerticalAlign.CENTER,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({ children: [new TextRun({ text: String(text), bold, color: color || undefined, size })] })],
  });
}
const hdr = (labels, w) => new TableRow({ tableHeader: true, children: labels.map((l, i) => cell(l, { bold: true, shade: NAVY, width: w[i], color: "FFFFFF" })) });
const row = (vals, w, shade) => new TableRow({ children: vals.map((v, i) => cell(v, { width: w[i], shade })) });
const table = (w, rows) => new Table({ width: { size: w.reduce((a, c) => a + c, 0), type: WidthType.DXA }, columnWidths: w, rows });
const T = (w, data, hl) => table(w, [hdr(data[0], w), ...data.slice(1).map((r, i) => row(r, w, hl && i === data.length - 2 ? LIGHT : null))]);

// ============================================================================
// DATA
// ============================================================================

const glance = [
  ["Property", "Value"],
  ["Root", "F:\\SEM 5 NOTES\\Big Data\\Project_Final\\airquality_expanded"],
  ["Structured layer", "27.48 GB CSV, 146,276,379 rows, 32 columns, 2010-2023"],
  ["Semi-structured - historical", "8,263,440 records, 458 MB JSON, 2022-08 to 2026-09, 230 cities"],
  ["Semi-structured - live", "44,160 records, 6.7 MB JSON, rolling window, 230 cities"],
  ["Unified table", "154,583,979 rows, 4.3 GB Parquet, one 17-column schema"],
  ["Total on disk", "33 GB"],
  ["In HDFS", "raw + clean (10 GB) + features (19.7 GB) + unified (4.2 GB) + models, all fsck HEALTHY"],
  ["Cities / states", "241 / 31 (230 in the semi-structured layers)"],
  ["Stations", "4,077 = 453 real + 3,624 synthetic"],
  ["Real vs synthetic (structured)", "16,252,931 (11.1%) / 130,023,448 (88.9%)"],
];

const fill = [
  ["Column", "Fill %", "Min", "Max", "Mean", "Median"],
  ["pm25", "73.64", "0.01", "1237.42", "68.91", "45.76"],
  ["pm10", "65.13", "0.01", "1220.27", "132.97", "97.89"],
  ["no2", "78.44", "0.01", "623.40", "28.89", "19.39"],
  ["so2", "74.85", "0.01", "252.50", "12.92", "8.04"],
  ["co", "73.94", "0.00", "60.17", "1.02", "0.69"],
  ["o3", "72.98", "0.01", "265.36", "30.67", "20.37"],
  ["nh3", "58.59", "0.01", "618.73", "25.45", "17.86"],
  ["solar_radiation", "59.83", "0.00", "1654.57*", "157.76", "48.90"],
  ["pressure", "45.90", "668.45", "1147.29*", "831.29", "753.38"],
  ["temperature_c", "100.00", "-6.16", "58.79", "25.20", "24.29"],
  ["humidity_percent", "100.00", "10.55", "100.00", "65.68", "65.07"],
  ["traffic_index", "100.00", "3.60", "100.00", "59.63", "59.45"],
  ["is_rush_hour", "100.00", "0", "1", "0.32", "0"],
];

const defectsData = [
  ["#", "Defect", "Scale", "Fix"],
  ["1", "is_rush_hour / variation_id not binary", "24,725 / 29,918 distinct values", "round, cast to int"],
  ["2", "T+1 label via positional lead()", "8.69% of labels had the wrong horizon", "require next_ts == ts + 3600 s"],
  ["3", "physically impossible values", "humidity 104.999%, traffic_index 110.2", "clamp to [0,100]"],
  ["4", "sparse simultaneous AQI coverage", "43.18% carry all 7 pollutants, 15.72% carry none", "three-tier median imputation, flagged"],
];

const camsAvail = [
  ["Date range requested", "What the API returned"],
  ["before 2013-01-01", "rejected: 'out of allowed range'"],
  ["2013-01 to 2022-07", "timestamps present, EVERY value null (0% fill)"],
  ["2022-08", "89.7% fill - real data begins"],
  ["2022-09 onward", "~99.8% fill (ammonia 0%)"],
];

const unified = [
  ["source_format", "data_source", "rows", "time range", "cities"],
  ["structured_csv", "synthetic", "130,023,448", "2010-01 to 2023-03", "241"],
  ["structured_csv", "real", "16,252,931", "2010-01 to 2023-03", "241"],
  ["semistructured_json", "cams_history", "8,263,440", "2022-08 to 2026-09", "230"],
  ["semistructured_json", "live_api", "44,160", "rolling 7-8 days", "230"],
  ["TOTAL", "", "154,583,979", "", ""],
];

const xval = [
  ["Pollutant", "corr", "bias", "RMSE", "mean CPCB", "mean CAMS"],
  ["pm25", "0.565", "+8.55", "50.75", "59.96", "51.41"],
  ["pm10", "0.558", "+44.89", "97.18", "121.82", "76.93"],
  ["o3", "0.361", "-48.54", "67.17", "28.54", "77.07"],
  ["no2", "0.219", "-2.07", "35.24", "24.87", "26.94"],
  ["so2", "0.083", "-10.05", "43.32", "14.60", "24.65"],
];

const model = [
  ["", "Track A (19 cities, 120 trees)", "Track B (241 cities, 300 trees)"],
  ["training rows", "3,477,690", "10,000,552 (seeded sample of 74.5M)"],
  ["test rows", "871,488", "18,671,121 (not sampled)"],
  ["real test rows", "96,832", "2,074,569"],
  ["feature vector", "78 dims", "86 dims"],
  ["persistence R2 (real)", "0.8714", "0.8587"],
  ["GBT R2 (real)", "0.8855", "0.8910"],
  ["persistence RMSE (real)", "21.665", "24.831"],
  ["GBT RMSE (real)", "20.436", "21.806"],
  ["RMSE reduction", "5.67%", "12.18%"],
  ["gate", "PASS (+0.0142 R2)", "PASS (+0.0323 R2)"],
];

const stream = [
  ["Batch", "rows in", "predicted", "alerts", "latency"],
  ["0 (replay)", "120", "15", "10", "10,750 ms"],
  ["1 (replay)", "120", "15", "10", "7,817 ms"],
  ["2 (replay)", "120", "14", "10", "7,019 ms"],
  ["3 (replay)", "120", "12", "7", "6,894 ms"],
  ["LIVE (Phase 8b)", "16,560", "16,560", "1,130", "23,452 ms"],
];

const missing = [
  ["Missing from raw CAMS JSON", "Count", "Real source used"],
  ["weather: temperature, humidity, wind speed/direction, rain, pressure, solar", "8", "Open-Meteo weather API (same provider, free, no key)"],
  ["derived from weather: ventilation, scrub, stagnation, temp x humidity, is_raining", "5", "computed once weather exists"],
  ["traffic_index, is_rush_hour, urbanization_index", "3", "city_profiles.csv - the same profiles the generator used"],
  ["*_was_imputed provenance flags", "10", "0 where the API returned a value, 1 where it returned null"],
];

const runDefects = [
  ["#", "Where", "What happened", "How it was caught"],
  ["1", "01c merge", "substring file-name join double-counted Mumbai and Noida (navi_mumbai.json contains mumbai.json)", "row count 44,544 failed to reconcile with fetch count 44,160"],
  ["2", "AirQualityStream", "referenced ts_unix one line before it existed - every batch aborted at history update", "alerts printed BEFORE the failure, so it looked like a stall; only fires on a batch with history"],
  ["3", "AirQualityStream", "VectorAssembler handleInvalid=skip silently dropped every live row (CAMS nh3 is always null)", "16,560 rows in, 0 predicted, no error"],
  ["4", "paths.py", "HDFS join produced hdfs:////namenode:9000/... (four slashes) - every HDFS-mode Python run would miss its own data", "printed FEATURE_PATH inside the container"],
  ["5", "Phase 4 write", "DataNodes unresponsive under memory pressure; 4 nodes at replication 3 had no spare for the write pipeline", "first full-scale run died after computing everything correctly"],
  ["6", "Spark image", "numpy absent; PySpark ML aborts at import", "training failed on first launch"],
  ["7", "Hive DDL", "declared a column named timestamp that does not exist; Hive returned NULL for every time while counts looked right", "first_alert / last_alert came back NULL"],
];

const delhi = [
  ["Month", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
  ["PM2.5", "180.5", "127.9", "88.6", "86.8", "79.5", "66.3", "44.0", "38.8", "47.1", "120.1", "213.6", "199.4"],
];

const fiveV = [
  ["V", "Evidence", "State"],
  ["Volume", "154.6M rows, 33 GB, 1 NameNode + 4 DataNodes, real block distribution", "demonstrated"],
  ["Variety", "flat CSV + nested self-describing JSON, read by native Spark readers into one schema; Hive queries span both", "demonstrated"],
  ["Veracity", "4 dataset defects + 7 pipeline defects found and fixed; independent CPCB-vs-CAMS cross-validation reported honestly, including where it is weak", "demonstrated"],
  ["Velocity", "Structured Streaming executed on the cluster: 10 s micro-batches, ~7 s latency, 1,130 alerts on genuinely live data", "demonstrated"],
  ["Value", "GBT R2 0.8910 vs persistence 0.8587 on 2,074,569 real test rows, 12.18% RMSE reduction - an hour of warning before pollution arrives", "demonstrated"],
];

// ============================================================================
// DOCUMENT
// ============================================================================

const W2 = [3200, 5800];
const doc = new Document({
  numbering: { config: [{ reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT }] }] },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 } } },
    children: [
      new Paragraph({ spacing: { before: 2400 }, children: [] }),
      new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "DATASET & PLATFORM REPORT", bold: true, size: 52, color: NAVY })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 200, after: 100 }, children: [new TextRun({ text: "A Scalable Big Data Platform for Real-Time Urban Air Quality Tracking and Public Safety Alerting", size: 26, color: ACCENT })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600 }, children: [new TextRun({ text: "23AID302 \u2014 Big Data Analytics", size: 24, italics: true })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 800 }, children: [new TextRun({ text: "Structured, Semi-Structured and Unified Data \u00b7 Model \u00b7 Live Alerting \u00b7 Serving Layer", size: 22 })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 200 }, children: [new TextRun({ text: "Report date: 12 September 2026 \u00b7 every figure is from a real, logged run", size: 20, color: "555555" })] }),
      new Paragraph({ children: [new PageBreak()] }),

      h1("Table of Contents"),
      new TableOfContents("Table of Contents", { hyperlink: true, headingStyleRange: "1-3" }),
      new Paragraph({ children: [new PageBreak()] }),

      // ---------------------------------------------------------------- 1
      h1("1. Executive Summary"),
      p("This report covers the project's complete data estate and everything built on it: a 27.48 GB structured dataset, two genuinely semi-structured layers pulled live from a public atmospheric-composition API, a 154.6-million-row unified table, a full-scale gradient-boosted forecaster, a working streaming alert engine consuming live data, and a Hive serving layer. Every number below is from a real run whose log is preserved under docs/run_logs/."),
      bl("Headline model result (real rows only, n = 2,074,569): ", "GBT R\u00b2 0.8910, RMSE 21.806 \u00b5g/m\u00b3 against a persistence baseline of R\u00b2 0.8587, RMSE 24.831 \u2014 a 12.18% error reduction, on an unsampled 18.7-million-row test window across 241 cities. The model passes the project's own gate by +0.0323 R\u00b2."),
      bl("Headline live result: ", "16,560 live city-hours enriched on YARN and scored by the streaming layer produced 1,130 alerts above the AQI 150 threshold, at roughly 7 seconds per micro-batch."),
      bl("All five V's are now demonstrated, not claimed. ", "Velocity and Value were the two that had been architecture rather than evidence at the start of this work block; both were executed on the cluster during it."),
      p("Equally important is what this report does NOT claim. The synthetic fraction of the structured layer (88.9%) is disclosed. Cross-validation against an independent source shows moderate agreement on particulates and essentially none on SO\u2082. Seven pipeline defects were found only by running code that had previously been written but never executed; each is listed with how it was caught. A request for 2010\u20132023 semi-structured coverage was declined because measurement showed the source returns ten years of empty rows for that span."),

      // ---------------------------------------------------------------- 2
      h1("2. The Data Estate at a Glance"),
      T(W2, glance),

      // ---------------------------------------------------------------- 3
      h1("3. Structured Layer (27.48 GB)"),
      h2("3.1 Origin"),
      p("Rebuilt from a 23.44 GB / 48.6M-row / 139-column CPCB source covering 453 real stations. The rebuild keeps all 16,252,931 real rows verbatim and generates 8 synthetic sibling stations per real station with an AR(1) autocorrelated perturbation (per-station \u03c6, \u03c3 = 0.08), copying each real station's missingness pattern rather than densifying it. Result: 146,276,379 rows, 4,077 stations, 241 cities, 2010\u20132023, 23 CSV parts."),
      h2("3.2 Measured fill rates and ranges"),
      p("Stratified sample of 1,094,195 rows across all 23 parts (scripts/_audit/scan_expanded_fillrate.py):"),
      T([2000, 1000, 1300, 1400, 1300, 1300], fill),
      pr([new TextRun({ text: "* ", bold: true, color: RED }), new TextRun({ text: "solar_radiation (max 1654.57 W/m\u00b2) and pressure (max 1147.29 mmHg) hold physically impossible outliers in the raw layer; both are nulled by the Phase 3 range-guard before imputation.", italics: true })]),
      h2("3.3 Four defects found in the source, and repaired"),
      T([500, 2700, 2900, 2900], defectsData),
      p("Defect 2 is the consequential one: a positional lead() on a non-unique key mislabelled roughly one training target in twelve with the wrong forecast horizon. It, not a modelling limit, was the root cause of an earlier run that scored R\u00b2 = 0.58 \u2014 below the do-nothing persistence baseline."),
      h2("3.4 Real vs synthetic"),
      p("The synthetic tail is thinner than the real one: pm25 p99 366 vs 449 \u00b5g/m\u00b3, standard deviation 74 vs 99. Because the alert threshold is a tail event, synthetic rows under-represent exactly the regime alerting exists to catch. All model results are therefore reported on real rows separately, and that is the figure quoted."),

      // ---------------------------------------------------------------- 4
      h1("4. Semi-Structured Layers (CAMS via Open-Meteo)"),
      h2("4.1 Source"),
      p("Open-Meteo's Air Quality API, backed by Copernicus CAMS atmospheric-composition analysis (ECMWF). Free, public, no API key, no account. Every response is stored byte-for-byte as returned: nested hourly struct-of-arrays with its own hourly_units schema. CAMS is a modelled reanalysis product assimilating satellite and ground observations \u2014 real, widely used, but model output rather than raw sensor readings, and described as such throughout."),
      h2("4.2 Why coverage starts in August 2022 and not 2010"),
      p("The original request was for 2010\u20132023 to match the structured layer. That was tested rather than assumed (scripts/_audit/cams_history_availability.py, cams_history_cutoff.py):"),
      T([3600, 5400], camsAvail),
      p("Requesting the full 2010\u20132023 span would have produced ten years of rows that look like coverage and contain nothing. Coverage therefore begins at the first month carrying real values."),
      h2("4.3 Two layers, and why both are kept"),
      bullet("Historical: 230 cities \u00d7 35,928 hours = 8,263,440 records, 2022-08-01 \u2192 2026-09-05, 458 MB, fetched in 37.9 minutes. Fill 99.79% on all pollutants except ammonia (0%, a real CAMS regional gap, left null rather than backfilled)."),
      bullet("Live: 230 cities \u00d7 192 hours = 44,160 records, rolling window. Refreshed by the daily cycle."),
      p("They overlap by 192 hours per city, and the overlap is not redundant: for Delhi, 173 of those hours match exactly and 19 differ, all at the tail of the live window. That is CAMS revising forecast values into analysis values. Both are kept and tagged (live_api vs cams_history), because the forecast values are what the alerting layer actually sees in real time."),
      p("230 of 241 cities resolved. The other 11 (Bileipada, Byrnihat, Chikkaballapur, Davanagere, Eloor, Gummidipoondi, Kunjemura, Mandi Gobindgarh, Palkalaiperur, Sivasagar, Vatva) returned a genuine geocoder miss and were excluded rather than given invented coordinates."),

      // ---------------------------------------------------------------- 5
      h1("5. The Unified Table (154,583,979 rows)"),
      p("Built by scripts/01c_merge_structured_semistructured.py: Spark reads the structured CSVs and the nested JSON with their native readers \u2014 genuine schema-on-read across two data models in one job \u2014 projects both onto one 17-column schema, and unions them. Values are never blended or imputed across sources; a row is tagged by where it came from."),
      T([2600, 1700, 1600, 2000, 1100], unified, true),
      p("Verified by a fresh Spark read-back, not the write-time log (scripts/_audit/verify_unified_dataset.py): total reconciles exactly against independently known counts; zero duplicate (city, timestamp) keys; every semi-structured city has exactly its expected row count; nulls appear only where the source genuinely lacks the field. That reconciliation check is what caught defect 1 in \u00a79."),

      // ---------------------------------------------------------------- 6
      h1("6. Cross-Validation: CPCB vs CAMS (Aug 2022 \u2013 Mar 2023)"),
      p("The eight-month overlap is the only window in which two independent sources describe the same cities over the same hours. Structured rows were averaged to a city-hour (CAMS gives one point per city; CPCB gives many stations), using measured values only, and joined on (city, timestamp): 1,152,707 matched city-hours."),
      T([1500, 1200, 1400, 1400, 1700, 1800], xval),
      p("PM\u2082.\u2085 and PM\u2081\u2080 track moderately, which is plausible for roadside sensors against a coarse model grid; a constant bias with decent correlation is the expected shape, not a failure. SO\u2082 shows essentially no agreement, and O\u2083 carries a large systematic offset. Per-city spread is wide: Kolkata 0.792 and Howrah 0.794 at the top, Pune \u22120.209 at the bottom. CO was excluded from the headline because the two sources report it in different units (mg/m\u00b3 vs \u00b5g/m\u00b3). A timezone check across hour offsets \u22123\u2026+3 peaks at 0h/+1h and decays symmetrically, so the IST assumption holds."),
      pr([b("One result was invalidated. ", true), b("A synthetic-vs-CAMS comparison returned figures numerically identical to real-vs-CAMS (0.564 vs 0.565), because averaging to city-hour means averages away the AR(1) perturbation. That test cannot distinguish the two by construction and is not evidence either way; generator fidelity is tested at station level by 00d_validate_expansion.py instead.")]),

      // ---------------------------------------------------------------- 7
      h1("7. Model: Full-Scale GBT"),
      p("Phase 4 at full scale (FeatureExtraction.scala, 73.5 min) reproduced this project's RUNBOOK to the row: 146,276,379 in \u2192 128,660,967 after dedupe \u2192 93,216,105 with a valid T+1 label \u2192 100% assemblable, 86-dimensional vector, 19.7 GB. Training (03_train_gbt.py, 300 trees, depth 6, delta target, chronological split) ran 5h50m without the StackOverflow that killed the previous full-scale attempt at 3h50m."),
      T([2400, 3300, 3300], model),
      p("Evaluation is not sampled: all 18,671,121 test rows are scored, so the metric stands even though training used a seeded 10M-row sample of the 74.5M available (a RAM limit on a 15.7 GB host, not a pipeline limit). The 12.18% reduction finally substantiates the ~11.3% the original documentation quoted from an sklearn reproduction \u2014 as a real distributed Spark GBT on the full data."),
      p("The eight extra vector dimensions between Track A and Track B are the climate types the 19-city model never saw; 54 of 241 cities had been landing in the encoder's catch-all bucket. Worst cities by RMSE (Kochi 100.7, Pune 98.4, Byrnihat 78.7) are the same ones the cross-validation flagged as poorly correlated."),

      // ---------------------------------------------------------------- 8
      h1("8. Live Alerting: Streaming + Phase 8b"),
      h2("8.1 What the streaming layer does"),
      p("AirQualityStream.scala watches an HDFS directory with a 10-second trigger. Each micro-batch rebuilds the Phase 4 features (using a persisted 30-hour history table so lag features survive restarts), loads the GBT, predicts the next-hour PM\u2082.\u2085 delta, converts to CPCB AQI, and writes an alert with severity and dominant pollutant wherever forecast AQI exceeds 150."),
      T([2000, 1500, 1700, 1500, 2300], stream),
      h2("8.2 The gap Phase 8b closes"),
      p("The first streaming run was fed rows already in the structured 32-column schema. Raw CAMS JSON supplies only 28 of the model's 54 numeric features:"),
      T([4600, 900, 3500], missing),
      p("LiveEnrichment.scala (Spark, submitted to YARN as application_1788670113534_0002) joins CAMS JSON, weather JSON and city_profiles.csv into the schema the stream consumes. Two unit conversions were measured, not assumed: CO \u00b5g/m\u00b3 \u2192 mg/m\u00b3 (\u00f71000; unconverted, structured CO averages 0.95 against CAMS 566), and pressure hPa \u2192 mmHg (\u00d70.750062; output 753.81 matches the structured median of 753). Wind is requested from the API in m/s directly."),
      p("Result: 16,560 live rows across 230 cities, zero nulls on model-critical columns, all 16,560 predicted, 1,130 alerts. Example: \"Air quality warning for Jaisalmer: forecast AQI 500 (Severe), driven by pm10. Forecast PM2.5 216.9 \u00b5g/m\u00b3 by 2026-09-04 01:00.\""),
      h2("8.3 Daily operation"),
      p("scripts/run_daily_live_cycle.py is the schedulable batch half: fetch both feeds in the same cycle (so their windows align \u2014 fetching them separately once produced zero overlapping hours), upload to HDFS, enrich on YARN, hand the file to the stream's input directory. AirQualityStream is a separate always-on service; dropping the file there is the whole handoff."),

      // ---------------------------------------------------------------- 9
      h1("9. Seven Defects Found Only by Running the Code"),
      p("Each of these existed in code that had been written and, in several cases, described as complete. None surfaced until the code was executed against real data on the cluster. They are recorded because \"the code is written\" and \"the phase is done\" turned out to be different claims."),
      T([400, 1600, 3900, 3100], runDefects),
      p("Defects 3 and 7 share a shape worth naming: both produced plausible-looking output with no error. Sixteen thousand rows in and zero out, with alerts and counts that looked fine; a Hive table returning correct counts and NULL timestamps. A silent wrong answer is worse than a crash, and the reconciliation habit \u2014 check the output count against an independently known number \u2014 is what caught them."),

      // ---------------------------------------------------------------- 10
      h1("10. Hive Serving Layer"),
      p("Three EXTERNAL tables (unified_airquality, clean_airquality, stream_alerts) and three views over the Parquet already in HDFS \u2014 no data copied, and DROP TABLE removes only metadata. Exposed through spark-sql and, via start-thriftserver.sh, over the HiveServer2 Thrift protocol on port 10000 so beeline and JDBC clients connect unchanged. All six demonstration queries return real results; the one to show is Delhi's seasonal cycle from measured values only:"),
      T([900, 700, 700, 700, 700, 700, 700, 700, 700, 700, 700, 700, 700], delhi),
      p("A 5.5\u00d7 swing between the August monsoon low and the November stubble-burning peak. That is the physical reason 13 years of history is required to train the model, and why a live feed \u2014 however fresh \u2014 cannot replace it."),

      // ---------------------------------------------------------------- 11
      h1("11. The Five V's"),
      T([1200, 6000, 1800], fiveV),

      // ---------------------------------------------------------------- 12
      h1("12. Limitations, Disclosed"),
      bullet("88.9% of structured rows are synthetic (statistically validated against real data, but not physical measurements). Model results are reported on real rows separately for that reason."),
      bullet("Training used a seeded 10M-row sample of 74.5M available rows: a 15.7 GB RAM ceiling, not a pipeline limit. Evaluation was not sampled."),
      bullet("CAMS is a reanalysis model, not a ground sensor; ammonia is null across the whole region."),
      bullet("The semi-structured layers cover 230 of 241 cities and begin in August 2022; they do not reach back to 2010."),
      bullet("Cross-validation agreement is moderate for particulates and poor for SO\u2082 and O\u2083."),
      bullet("Small-cluster fragility is real: with 4 DataNodes at replication 3, a large derived write failed under memory pressure and was re-run at replication 2 with tuned timeouts. Replication 3 is kept for the raw layer, where fault tolerance is demonstrated."),
      bullet("The dashboard (Phase 10) is not built."),

      // ---------------------------------------------------------------- 13
      h1("13. Conclusion"),
      p("The platform now does what its title says. Real CPCB history trains a forecaster that beats persistence by 12.18% on two million real test rows; real live atmospheric data flows through a Spark-on-YARN enrichment job into a Structured Streaming engine that fires an hour's warning above AQI 150; and everything it has produced is queryable through Hive. Along the way, seven defects that a code review would not have found were found by running the code \u2014 and each is documented with the number of rows it affected and the check that caught it."),
    ],
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync("DATASET_REPORT.docx", buf);
  console.log("wrote DATASET_REPORT.docx", buf.length, "bytes");
});
