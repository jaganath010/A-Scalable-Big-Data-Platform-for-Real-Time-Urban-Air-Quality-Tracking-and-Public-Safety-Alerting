// ============================================================================
// Generates the FINAL REVIEW deck - 23AID302 Big Data Analytics, Group A14
//
// Built from the 1st-review deck's structure and look (white slides, 0D5F8E
// blue, blue table headers, the original screenshots) plus the final outputs,
// a full GBT section, and an evidence section built from the preserved logs.
//
// Every number here is a measured value from a logged run; the log is named on
// the evidence slides and lives in docs/run_logs/.
//
// Build (from a dir that has node_modules/pptxgenjs):
//   IMG=<dir with the screenshots> node build_final_review_deck.js
// ============================================================================
const pptxgen = require("pptxgenjs");
const path = require("path");
const fs = require("fs");

const IMG = process.env.IMG;
const OUT = process.env.OUT || "Final_Review_Presentation.pptx";
const SKILL = process.env.SKILL_DIR;          // pptx skill dir, for apply_theme.js

const THEME = {
  name: "AirWatch Final Review",
  headFontFace: "Calibri", bodyFontFace: "Calibri",
  colors: { dk1: "1B2430", lt1: "FFFFFF", dk2: "0D3B5E", lt2: "F1F5F8",
            accent1: "0D5F8E", accent2: "0E7C86", accent3: "C9342B", accent4: "D9A400",
            accent5: "1E8E5A", accent6: "7A1B2E", hlink: "0D5F8E", folHlink: "7A1B2E" },
};
const HEX = { ink: "1B2430", navy: "0D3B5E", blue: "0D5F8E", teal: "0E7C86", red: "C9342B",
              amber: "D9A400", green: "1E8E5A", maroon: "7A1B2E", panel: "F1F5F8",
              line: "D9DFE7", muted: "6B7785", ink2: "46525F", grid: "E6EAF0" };

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";                    // 13.33 x 7.5
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "Final Review - Air Quality Big Data Platform";
pres.author = "Group A14";
const C = pres.SchemeColor;

// ---------------------------------------------------------------- layouts
pres.defineSlideMaster({
  title: "TITLE", background: { color: "FFFFFF" },
  objects: [
    { rect: { x: 0, y: 0, w: 7.6, h: 7.5, fill: { color: C.background2 } } },
    { rect: { x: 7.6, y: 0, w: 5.73, h: 7.5, fill: { color: C.text2 } } },
    { placeholder: { options: { name: "title", type: "title", x: 0.7, y: 1.35, w: 6.5, h: 2.5, fontSize: 32, bold: true, color: C.text2, margin: 0, valign: "top", align: "left" }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.7, y: 4.55, w: 6.5, h: 2.3, fontSize: 14, color: C.text1, margin: 0, valign: "top" }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT", background: { color: "FFFFFF" },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.35, w: 12.1, h: 0.85, fontSize: 30, bold: true, color: C.text2, margin: 0, valign: "middle", align: "left" }, text: "" } },
    { text: { text: "23AID302 · Big Data Analytics · Group A14 · Final Review", options: { x: 0.6, y: 7.05, w: 8, h: 0.3, fontSize: 10, color: HEX.muted, margin: 0 } } },
  ],
  slideNumber: { x: 12.1, y: 7.05, w: 0.6, h: 0.3, fontSize: 10, color: HEX.muted, align: "right" },
});
pres.defineSlideMaster({
  title: "SECTION", background: { color: C.text2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.9, y: 2.6, w: 11.5, h: 1.3, fontSize: 42, bold: true, color: C.background1, margin: 0, valign: "middle", align: "left" }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.9, y: 4.0, w: 11.5, h: 1.2, fontSize: 18, color: "CADCEA", margin: 0, valign: "top" }, text: "" } },
  ],
});

// ---------------------------------------------------------------- helpers
const imgFit = (slide, file, x, y, boxW, boxH, iw, ih, name) => {
  const r = Math.min(boxW / iw, boxH / ih);
  const w = iw * r, h = ih * r;
  slide.addImage({ path: path.join(IMG, file), x: x + (boxW - w) / 2, y: y + (boxH - h) / 2, w, h, objectName: name || file,
                   altText: name || file });
};
const addTitle = (s, t) => s.addText(t, { placeholder: "title" });
const bullets = (s, items, x, y, w, h, size = 16, opts = {}) =>
  s.addText(items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1, paraSpaceAfter: 7 } })),
    { x, y, w, h, fontSize: size, color: C.text1, valign: "top", margin: 0, isTextBox: true, ...opts });
const para = (s, text, x, y, w, h, size = 15, opts = {}) =>
  s.addText(text, { x, y, w, h, fontSize: size, color: C.text1, valign: "top", margin: 0, isTextBox: true, ...opts });
const hdrCell = (t, extra = {}) => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: HEX.blue }, valign: "middle", ...extra } });
const table = (s, header, rows, x, y, w, colW, size = 12, rowH = 0.4, opts = {}) => {
  const body = rows.map((r) => r.map((c) => (typeof c === "object" ? c : { text: String(c) })));
  s.addTable([header.map((h) => hdrCell(h)), ...body], {
    x, y, w, colW, fontFace: THEME.bodyFontFace, fontSize: size, color: HEX.ink,
    border: { type: "solid", pt: 0.5, color: HEX.line }, valign: "middle", rowH, margin: [0.04, 0.1, 0.04, 0.1], ...opts,
  });
};
const stat = (s, x, y, w, h, big, label, color = HEX.blue, bigSize = 34) => {
  s.addShape(pres.ShapeType.rect, { x, y, w, h, fill: { color: C.background2 }, line: { color: HEX.line, width: 0.5 }, objectName: "stat " + label });
  s.addText(big, { x: x + 0.12, y: y + 0.08, w: w - 0.24, h: h * 0.55, fontSize: bigSize, bold: true, color, margin: 0, valign: "middle", isTextBox: true, fit: "shrink" });
  s.addText(label, { x: x + 0.12, y: y + h * 0.6, w: w - 0.24, h: h * 0.36, fontSize: 12, color: HEX.ink2, margin: 0, valign: "top", isTextBox: true });
};
const callout = (s, text, x, y, w, h, size = 14, fill = "EAF2F8") => {
  s.addShape(pres.ShapeType.rect, { x, y, w, h, fill: { color: fill }, line: { color: fill, width: 0.5 } });
  s.addText(text, { x: x + 0.18, y: y + 0.08, w: w - 0.36, h: h - 0.16, fontSize: size, color: HEX.ink, margin: 0, valign: "middle", isTextBox: true });
};
const term = (s, text, x, y, w, h, size = 10.5, label) => {
  s.addShape(pres.ShapeType.rect, { x, y, w, h, fill: { color: "0F1720" }, line: { color: "0F1720", width: 0.5 } });
  s.addText(text, { x: x + 0.12, y: y + 0.1, w: w - 0.24, h: h - 0.2, fontFace: "Courier New", fontSize: size, color: "D7E2EA", margin: 0, valign: "top", isTextBox: true });
  if (label) s.addText(label, { x, y: y + h + 0.04, w, h: 0.28, fontSize: 11, italic: true, color: HEX.muted, margin: 0, isTextBox: true });
};
const chartBase = () => ({
  showTitle: false, showLegend: false, catGridLine: { style: "none" }, valGridLine: { color: HEX.grid, size: 0.5 },
  catAxisLabelColor: HEX.ink2, valAxisLabelColor: HEX.ink2, catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt",
  catAxisLabelFontSize: 11, valAxisLabelFontSize: 11, dataLabelFontFace: "+mn-lt", dataLabelFontSize: 11, dataLabelColor: HEX.ink,
  showValue: true,
});
const content = (section, title, notes) => {
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: section });
  addTitle(s, title);
  if (notes) s.addNotes(notes);
  return s;
};

// ============================================================================
// SECTION: Introduction
// ============================================================================
pres.addSection({ title: "Introduction" });

// 1 ---- Title
{
  const s = pres.addSlide({ masterName: "TITLE", sectionTitle: "Introduction" });
  s.addText("A Scalable Big Data Platform for Real-Time Urban Air Quality Tracking and Public Safety Alerting", { placeholder: "title" });
  s.addText([
    { text: "Final Review  |  23AID302 — Big Data Analytics", options: { color: HEX.blue, bold: true, breakLine: true } },
    { text: " ", options: { breakLine: true, fontSize: 8 } },
    { text: "Sangeeth S (CB.AI.U4AID24050)", options: { breakLine: true } },
    { text: "Jaganath R (CB.AI.U4AID24021)", options: { breakLine: true } },
    { text: "Niranjan S (CB.AI.U4AID24035)", options: { breakLine: true } },
    { text: "PL Kowshik (CB.AI.U4AID24036)", options: { breakLine: true } },
    { text: " ", options: { breakLine: true, fontSize: 8 } },
    { text: "Group A14", options: { bold: true } },
  ], { placeholder: "body" });
  const tiles = [["154.6 M", "rows in one queryable table"], ["R² 0.891", "vs 0.859 persistence, real rows"], ["1,130", "live warnings, 91 cities"], ["10 / 10", "phases executed with logs"]];
  tiles.forEach((t, i) => {
    const x = 8.2 + (i % 2) * 2.45, y = 1.9 + Math.floor(i / 2) * 2.2;
    s.addText(t[0], { x, y, w: 2.3, h: 0.9, fontSize: 34, bold: true, color: "FFFFFF", margin: 0, valign: "middle", isTextBox: true, fit: "shrink" });
    s.addText(t[1], { x, y: y + 0.9, w: 2.3, h: 0.7, fontSize: 13, color: "CADCEA", margin: 0, valign: "top", isTextBox: true });
  });
  s.addNotes("Open with the point: we forecast each city's PM2.5 one hour ahead and warn people before it arrives. The four numbers on the right are the whole story — scale, accuracy, live output, and that every phase was actually executed.");
}

// 2 ---- Abstract
{
  const s = content("Introduction", "Abstract", "Abstract updated from the first review: the infrastructure is no longer a plan, it has run end to end. Hit the four bullets in order: storage, compute plus model, streaming, serving.");
  para(s, "Urban air pollution needs low-latency analytics, not overnight batch reports. Published models predict air quality accurately but run on one machine and raise no automated warnings. This project builds the distributed platform they lack — and now runs it end to end.", 0.6, 1.4, 12.1, 1.1, 17);
  bullets(s, [
    "HDFS (4 DataNodes, 3× replication) holds the lakehouse: 154,583,979 rows, 33 GB — structured CSV and semi-structured JSON on one schema",
    "Spark on YARN runs the cleaning, an 86-feature pipeline (93.2 M labelled rows) and a 300-tree GBT forecaster: R² 0.8910 against 0.8587 for persistence on 2.07 M real test rows",
    "Spark Structured Streaming scores live CAMS and weather data every 10 s — 1,130 warnings across 91 cities",
    "Hive serves the results, and a public warning board shows the message residents receive one hour ahead",
  ], 0.6, 2.75, 12.1, 3.9, 16);
}

// 3 ---- Problem
{
  const s = content("Introduction", "Problem statement", "Three gaps between what exists and what a city needs. Each one maps to a layer we built: scale to HDFS and Spark, latency to streaming, automation to the alert engine.");
  para(s, "Three gaps between what exists and what a city actually needs", 0.6, 1.35, 12.1, 0.4, 16, { color: HEX.ink2, italic: true });
  const cards = [
    ["Scale", "Existing air-quality models run on a single machine. A city-wide deployment produces hundreds of millions of readings — more than one machine can hold in memory.", "Our answer: HDFS + Spark on YARN"],
    ["Latency", "Batch analytics report after the fact. A pollution spike is a public-health event happening now; a warning delivered tomorrow has no value.", "Our answer: 10 s Structured Streaming"],
    ["Automation", "Published frameworks stop at prediction. None close the loop by turning a forecast into an actionable public-safety alert.", "Our answer: AQI > 150 alert engine"],
  ];
  cards.forEach((c, i) => {
    const x = 0.6 + i * 4.1;
    s.addShape(pres.ShapeType.rect, { x, y: 2.0, w: 3.9, h: 4.6, fill: { color: C.background2 }, line: { color: HEX.line, width: 0.5 } });
    s.addText(c[0], { x: x + 0.25, y: 2.2, w: 3.4, h: 0.6, fontSize: 24, bold: true, color: C.text2, margin: 0, isTextBox: true });
    s.addText(c[1], { x: x + 0.25, y: 2.95, w: 3.4, h: 2.4, fontSize: 15, color: HEX.ink, margin: 0, valign: "top", isTextBox: true });
    s.addText(c[2], { x: x + 0.25, y: 5.55, w: 3.4, h: 0.8, fontSize: 14, bold: true, color: HEX.blue, margin: 0, valign: "top", isTextBox: true });
  });
}

// 4 ---- Objectives and final status
{
  const s = content("Introduction", "Objectives — and where each one ended up", "This is the first review's objectives table with a new last column. Every objective now has a measured result, not a promise. Read down the last column.");
  const ok = (t) => ({ text: t, options: { color: "1E6B45", bold: true } });
  table(s, ["#", "Objective", "Success criterion", "Final result"], [
    ["1", "Fault-tolerant HDFS cluster", "≥ 2 DataNodes, 3× replication, 0 corrupt blocks", ok("4 DataNodes · fsck HEALTHY · 0 missing / corrupt")],
    ["2", "Distributed compute on the cluster", "Spark running under YARN, not local", ok("Jobs ran as YARN applications on 4 NodeManagers")],
    ["3", "Ingest into distributed storage", "Split into 128 MB blocks", ok("232 raw blocks → 696 replicas; all layers 33 GB")],
    ["4", "Preprocessing in Scala", "Reads HDFS, cleans, writes back to HDFS", ok("146,276,379 rows → 10.0 GB Parquet, 241 partitions")],
    ["5", "Spatial-temporal features", "T+1 target, rolling history, CPCB AQI", ok("93,216,105 labelled rows · 86-dim vector")],
    ["6", "Distributed GBT forecaster", "Must beat the persistence baseline", ok("R² 0.8910 vs 0.8587 · −12.18 % RMSE")],
    ["7", "Streaming speed layer", "Structured Streaming micro-batches", ok("10 s trigger · ≈ 7 s latency per batch")],
    ["8", "Close the loop with alerts", "Warning when predicted AQI > 150", ok("1,130 warnings · 91 cities")],
  ], 0.6, 1.45, 12.1, [0.5, 3.1, 4.0, 4.5], 13, 0.56);
}

// 5 ---- Literature
{
  const s = content("Introduction", "Literature survey", "The base paper proves multi-source fusion improves accuracy. It stays on one machine. We port the fusion idea onto a distributed platform and add streaming and alerting.");
  s.addText([
    { text: "Primary base paper", options: { bold: true, color: HEX.blue, breakLine: true } },
    { text: "“Air Quality Prediction using Multi-Source Remote Sensing Data Integration with Hybrid Deep Learning Framework (MAST-Net)” — Nature, Scientific Reports, December 2025", options: { italic: true } },
  ], { x: 0.6, y: 1.4, w: 12.1, h: 1.1, fontSize: 16, color: HEX.ink, margin: 0, valign: "top", isTextBox: true });
  para(s, "Contribution: fusing several environmental streams — remote sensing, meteorology, ground sensors — improves accuracy over single-source models.", 0.6, 2.6, 12.1, 0.8, 16);
  s.addText("The architectural gap", { x: 0.6, y: 3.6, w: 5.8, h: 0.4, fontSize: 18, bold: true, color: C.text2, margin: 0, isTextBox: true });
  bullets(s, ["Built on a localised, single-machine framework", "No distributed infrastructure for high-volume, multi-city scaling", "No streaming mechanism for immediate warnings"], 0.6, 4.1, 5.8, 2.4, 16);
  s.addText("What this project adds — and now measures", { x: 6.9, y: 3.6, w: 5.8, h: 0.4, fontSize: 18, bold: true, color: C.text2, margin: 0, isTextBox: true });
  bullets(s, ["Data fusion on Hadoop + Spark: CPCB stations, CAMS reanalysis and live weather", "154.6 M rows processed distributed, 10 s streaming", "A closed loop: forecast → AQI → warning message"], 6.9, 4.1, 5.8, 2.4, 16);
}

// 6 ---- Architecture
{
  const s = content("Introduction", "System architecture", "Lambda-style: a batch layer trains the model on history, a speed layer scores live data, both sharing one HDFS lakehouse, and Hive plus the website serve the results. Walk top to bottom.");
  const box = (x, y, w, h, t, fill, color = "FFFFFF", size = 13) => {
    s.addShape(pres.ShapeType.roundRect, { x, y, w, h, fill: { color: fill }, line: { color: fill, width: 0.5 }, rectRadius: 0.06 });
    s.addText(t, { x: x + 0.1, y, w: w - 0.2, h, fontSize: size, color, bold: true, align: "center", valign: "middle", margin: 0, isTextBox: true });
  };
  const arrow = (x1, y1, x2, y2) => s.addShape(pres.ShapeType.line, { x: x1, y: y1, w: x2 - x1, h: y2 - y1, line: { color: HEX.muted, width: 1.5, endArrowType: "triangle" } });
  box(0.6, 1.4, 3.8, 0.8, "CPCB stations 2010–2023\nstructured CSV · 146.3 M rows", HEX.navy);
  box(4.75, 1.4, 3.8, 0.8, "CAMS history 2022-08 →\nsemi-structured JSON · 8.3 M rows", HEX.teal);
  box(8.9, 1.4, 3.8, 0.8, "CAMS + weather, live\nsemi-structured JSON · 230 cities", HEX.teal);
  [2.5, 6.65, 10.8].forEach((x) => arrow(x, 2.2, x, 2.75));
  box(0.6, 2.75, 12.1, 0.75, "HDFS lakehouse — 1 NameNode + 4 DataNodes · 128 MB blocks · 3× replication · Parquet", HEX.blue, "FFFFFF", 15);
  arrow(3.6, 3.5, 3.6, 4.05); arrow(9.7, 3.5, 9.7, 4.05);
  s.addText("BATCH LAYER — trains on history", { x: 0.6, y: 4.05, w: 6.0, h: 0.3, fontSize: 12, bold: true, color: HEX.blue, margin: 0, isTextBox: true });
  box(0.6, 4.4, 1.9, 0.95, "Phase 3\nclean · impute", "DCEBF4", HEX.ink, 12);
  box(2.65, 4.4, 1.9, 0.95, "Phase 4\n86 features", "DCEBF4", HEX.ink, 12);
  box(4.7, 4.4, 1.9, 0.95, "GBT\n300 trees", "DCEBF4", HEX.ink, 12);
  arrow(2.5, 4.87, 2.65, 4.87); arrow(4.55, 4.87, 4.7, 4.87);
  s.addText("SPEED LAYER — scores live data", { x: 6.9, y: 4.05, w: 5.8, h: 0.3, fontSize: 12, bold: true, color: HEX.teal, margin: 0, isTextBox: true });
  box(6.9, 4.4, 1.85, 0.95, "Live\nenrichment", "D9EFF0", HEX.ink, 12);
  box(8.9, 4.4, 1.85, 0.95, "Structured\nStreaming", "D9EFF0", HEX.ink, 12);
  box(10.9, 4.4, 1.8, 0.95, "AQI alert\n> 150", "D9EFF0", HEX.ink, 12);
  arrow(8.75, 4.87, 8.9, 4.87); arrow(10.75, 4.87, 10.9, 4.87);
  arrow(5.65, 5.35, 8.0, 5.75); arrow(11.8, 5.35, 11.8, 5.75);
  box(0.6, 5.8, 12.1, 0.75, "Hive external tables (SQL)  →  public warning board — “Air quality in Jaisalmer is expected to reach AQI 500 by 00:00 …”", HEX.maroon, "FFFFFF", 14);
}

// ============================================================================
// SECTION: Progress at the first review
// ============================================================================
pres.addSection({ title: "Since the first review" });

// 7 ---- First review recap
{
  const s = content("Since the first review", "Where we were at the first review", "A quick recap so the new work lands in context. At the first review the infrastructure and preprocessing were done; the model, streaming, serving and the website were still ahead.");
  stat(s, 0.6, 1.45, 2.9, 1.35, "232", "HDFS blocks, replicated 3×", HEX.blue);
  stat(s, 3.65, 1.45, 2.9, 1.35, "4 + 4", "DataNodes + NodeManagers", HEX.blue);
  stat(s, 0.6, 2.95, 2.9, 1.35, "2.75×", "CSV → Parquet compression", HEX.blue);
  stat(s, 3.65, 2.95, 2.9, 1.35, "28 min", "Scala preprocessing, 146 M rows", HEX.blue);
  para(s, "Done by the first review", 0.6, 4.55, 5.9, 0.35, 16, { bold: true, color: HEX.blue });
  bullets(s, ["HDFS cluster, Spark on YARN activated", "Ten-step Scala cleaning, 10.0 GB Parquet", "Three-tier imputation, every fill flagged"], 0.6, 4.95, 5.9, 1.7, 15);
  imgFit(s, "s7_2.png", 6.9, 1.4, 5.8, 3.2, 1006, 750, "HDFS DataNode screenshot");
  imgFit(s, "s13_2.png", 6.9, 4.8, 5.8, 1.0, 1708, 290, "YARN node list screenshot");
  para(s, "Still ahead: model training · streaming · live data · Hive · the website", 6.9, 5.95, 5.8, 0.7, 15, { bold: true, color: HEX.maroon });
}

// ============================================================================
// SECTION: Final outputs
// ============================================================================
pres.addSection({ title: "Final outputs" });
{
  const s = pres.addSlide({ masterName: "SECTION", sectionTitle: "Final outputs" });
  s.addText("Final outputs", { placeholder: "title" });
  s.addText("Data · Features · The GBT model · Live alerting · Serving · The website", { placeholder: "body" });
  s.addNotes("Everything from here is new since the first review.");
}

// 8 ---- Data: three layers
{
  const s = content("Final outputs", "The data: three layers, three jobs", "The key idea to teach: these are not three copies. Structured trains, semi-structured history validates, live alerts. Each does a job the others cannot. 88.9 percent of the structured rows are synthetic and we disclose that up front.");
  table(s, ["Layer", "Format", "Rows", "Size", "Period", "Its one job"], [
    ["Structured — CPCB", "Flat CSV", "146,276,379", "27.48 GB", "2010 – 2023", "TRAIN the model"],
    ["Semi-structured — CAMS history", "Nested JSON", "8,263,440", "458 MB", "2022-08 → 2026-09", "VALIDATE the data"],
    ["Semi-structured — CAMS live", "Nested JSON", "44,160", "6.7 MB", "rolling window", "ALERT people now"],
  ], 0.6, 1.5, 12.1, [3.0, 1.5, 1.6, 1.2, 2.3, 2.5], 14, 0.62);
  stat(s, 0.6, 4.35, 2.85, 1.2, "154,583,979", "rows in the unified table", HEX.blue, 26);
  stat(s, 3.6, 4.35, 2.85, 1.2, "33 GB", "on disk, all in HDFS", HEX.blue);
  stat(s, 6.6, 4.35, 2.85, 1.2, "241", "cities · 4,077 stations", HEX.blue);
  stat(s, 9.6, 4.35, 3.1, 1.2, "88.9 %", "of structured rows are synthetic", HEX.maroon);
  callout(s, "Why three? Only the structured layer has the label and 13 years of seasonality. Only CAMS is an independent source on the same cities and hours. Only live data can warn anyone now.", 0.6, 5.75, 12.1, 1.0, 15);
}

// 9 ---- Semi-structured + unified
{
  const s = content("Final outputs", "Semi-structured layers and the unified table", "We were asked for 2010 to 2023. We tested it: the source rejects dates before 2013 and returns 100 percent null values until July 2022. Delivering that would look like ten years of data and contain none. So coverage starts in August 2022 and we say why.");
  para(s, "Why CAMS coverage starts in August 2022", 0.6, 1.4, 5.9, 0.4, 17, { bold: true, color: HEX.blue });
  table(s, ["Dates requested", "What the API returned"], [
    ["before 2013-01-01", "rejected: “out of allowed range”"],
    ["2013-01 → 2022-07", "timestamps returned, every value null (0 % fill)"],
    ["2022-08", "89.7 % fill — real data begins"],
    ["2022-09 onward", "≈ 99.8 % fill (ammonia 0 %)"],
  ], 0.6, 1.9, 5.9, [2.1, 3.8], 13, 0.55);
  para(s, "Requesting 2010–2023 would have produced ten years of rows that look like coverage and contain nothing.", 0.6, 4.85, 5.9, 0.8, 14, { italic: true, color: HEX.ink2 });
  para(s, "230 of 241 cities resolved; 11 small localities had no geocode and were excluded rather than given invented coordinates.", 0.6, 5.8, 5.9, 0.9, 14, { color: HEX.ink2 });
  para(s, "One table, one schema", 6.9, 1.4, 5.8, 0.4, 17, { bold: true, color: HEX.blue });
  table(s, ["data_source", "rows", "cities"], [
    ["synthetic", "130,023,448", "241"], ["real", "16,252,931", "241"],
    ["cams_history", "8,263,440", "230"], ["live_api", "44,160", "230"],
    [{ text: "TOTAL", options: { bold: true, fill: { color: "EAF2F8" } } }, { text: "154,583,979", options: { bold: true, fill: { color: "EAF2F8" } } }, { text: "", options: { fill: { color: "EAF2F8" } } }],
  ], 6.9, 1.9, 5.8, [2.4, 2.2, 1.2], 13, 0.55);
  para(s, "Flat CSV and nested JSON are read by their native Spark readers and unioned onto 17 columns in one job — the Variety requirement doing real work. The total was re-counted live on YARN: 154,583,979.", 6.9, 5.35, 5.8, 1.3, 14, { color: HEX.ink2 });
}

// 10 ---- Phase 4
{
  const s = content("Final outputs", "Phase 4 at full scale — 93.2 M labelled rows", "73.5 minutes. Every checkpoint reproduced the project's own runbook to the row. The T+1 rule drops rows without a genuine next hour instead of mislabelling them. A positional lead would have mislabelled 8.69 percent of targets.");
  s.addChart(pres.charts.BAR, [{ name: "rows (millions)", labels: ["Loaded from clean layer", "After dedupe on (station, hour)", "With a valid T+1 label", "Assemblable into a vector"], values: [146.28, 128.66, 93.22, 93.22] }],
    { x: 0.6, y: 1.4, w: 7.6, h: 4.7, barDir: "bar", ...chartBase(), chartColors: [HEX.blue], barGapWidthPct: 45, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0\" M\"", valAxisHidden: true, valGridLine: { style: "none" }, catAxisOrientation: "maxMin" });
  stat(s, 8.6, 1.45, 4.1, 1.15, "73.5 min", "feature job, distributed Spark", HEX.blue);
  stat(s, 8.6, 2.75, 4.1, 1.15, "19.7 GB", "written · 241 city partitions", HEX.blue);
  stat(s, 8.6, 4.05, 4.1, 1.15, "86 dims", "54 numeric + 32 one-hot", HEX.blue);
  para(s, "The label rule: next_ts must equal ts + 3600 s exactly. 12.3 % of rows had no true next hour and were dropped, not guessed.", 8.6, 5.4, 4.1, 1.2, 14, { color: HEX.ink2 });
  para(s, "Rows dropped at each step are visible, not hidden: 146.3 M → 128.7 M → 93.2 M.", 0.6, 6.25, 7.6, 0.5, 13, { italic: true, color: HEX.muted });
}

// ============================================================================
// SECTION: The GBT model
// ============================================================================
pres.addSection({ title: "The GBT model" });
{
  const s = pres.addSlide({ masterName: "SECTION", sectionTitle: "The GBT model" });
  s.addText("The GBT forecaster", { placeholder: "title" });
  s.addText("What it is · how we configured it · why the design choices · what it achieved · what it learned", { placeholder: "body" });
  s.addNotes("A dedicated section because the model is the core of the project. Five slides: concept, configuration, design choices, results, feature importance.");
}

// 11 ---- GBT concept
{
  const s = content("The GBT model", "Gradient Boosted Trees — what it is", "GBT builds one small tree at a time. Each new tree is trained to correct the mistakes the ensemble has made so far. The prediction is the sum of all the trees, each scaled by a small step size. In Spark, each tree's split search is spread across the data partitions, which is why training issued over 1,300 Spark jobs.");
  const box = (x, w, t, fill, color) => {
    s.addShape(pres.ShapeType.roundRect, { x, y: 1.5, w, h: 0.85, fill: { color: fill }, line: { color: fill, width: 0.5 }, rectRadius: 0.06 });
    s.addText(t, { x, y: 1.5, w, h: 0.85, fontSize: 15, bold: true, color, align: "center", valign: "middle", margin: 0, isTextBox: true });
  };
  box(0.6, 2.0, "baseline\nprediction", HEX.navy, "FFFFFF");
  s.addText("+", { x: 2.65, y: 1.5, w: 0.4, h: 0.85, fontSize: 28, bold: true, color: HEX.muted, align: "center", valign: "middle", margin: 0, isTextBox: true });
  box(3.1, 1.7, "η · tree 1", "DCEBF4", HEX.ink);
  s.addText("+", { x: 4.85, y: 1.5, w: 0.4, h: 0.85, fontSize: 28, bold: true, color: HEX.muted, align: "center", valign: "middle", margin: 0, isTextBox: true });
  box(5.3, 1.7, "η · tree 2", "DCEBF4", HEX.ink);
  s.addText("+  …  +", { x: 7.0, y: 1.5, w: 1.0, h: 0.85, fontSize: 22, bold: true, color: HEX.muted, align: "center", valign: "middle", margin: 0, isTextBox: true });
  box(8.05, 1.9, "η · tree 300", "DCEBF4", HEX.ink);
  s.addText("=", { x: 10.0, y: 1.5, w: 0.4, h: 0.85, fontSize: 28, bold: true, color: HEX.muted, align: "center", valign: "middle", margin: 0, isTextBox: true });
  box(10.45, 2.25, "forecast", HEX.maroon, "FFFFFF");
  para(s, "How it learns", 0.6, 2.8, 5.9, 0.4, 18, { bold: true, color: HEX.blue });
  s.addText([
    { text: "Start from a simple baseline prediction.", options: { bullet: { type: "number" }, breakLine: true, paraSpaceAfter: 8 } },
    { text: "Measure the errors left over (the residuals).", options: { bullet: { type: "number" }, breakLine: true, paraSpaceAfter: 8 } },
    { text: "Fit a small tree to those errors — it learns what the ensemble still gets wrong.", options: { bullet: { type: "number" }, breakLine: true, paraSpaceAfter: 8 } },
    { text: "Add it, scaled by a small step size η = 0.08, so no single tree dominates.", options: { bullet: { type: "number" }, breakLine: true, paraSpaceAfter: 8 } },
    { text: "Repeat 300 times.", options: { bullet: { type: "number" } } },
  ], { x: 0.6, y: 3.3, w: 5.9, h: 3.4, fontSize: 15, color: HEX.ink, margin: 0, valign: "top", isTextBox: true });
  para(s, "Why GBT for this problem", 6.9, 2.8, 5.8, 0.4, 18, { bold: true, color: HEX.blue });
  bullets(s, [
    "Captures non-linear interactions — wind × temperature × humidity — that a linear model cannot",
    "Needs no feature scaling; copes with mixed units (µg/m³, °C, flags, one-hot)",
    "Native to Spark MLlib, so training is distributed across the data partitions",
    "Gives feature importance — we can show what it actually uses",
  ], 6.9, 3.3, 5.8, 3.4, 15);
}

// 12 ---- GBT configuration
{
  const s = content("The GBT model", "How we configured and trained it", "Every parameter has a reason. The two cost-driven choices are the 10 million row training sample, which is a 15.7 GB RAM ceiling, and chronological splitting. Evaluation is never sampled.");
  table(s, ["Setting", "Value", "Why"], [
    ["Trees (maxIter)", "300", "Small steps need many rounds; the plan's default of 20 was far too few"],
    ["Tree depth (maxDepth)", "6", "Up to 64 leaves per tree: enough for interactions without memorising"],
    ["Step size (η)", "0.08", "Shrinks each tree's vote so errors are corrected gradually"],
    ["Row subsampling", "0.8", "Each tree sees 80 % of rows, which decorrelates the trees"],
    ["Feature subset", "sqrt  (≈ 9 of 86)", "Each split considers a random handful of features"],
    ["Max bins", "64", "Histogram bins for split search: speed and memory"],
    ["Target", "next-hour PM₂.₅ − current PM₂.₅", "Predict the change, not the level (next slide)"],
    ["Training rows", "10,000,552", "Seeded 13.41 % sample of 74,544,984 — RAM ceiling on a 15.7 GB host"],
    ["Test rows", "18,671,121", "Not sampled: every row of the hold-out window is scored"],
  ], 0.6, 1.3, 12.1, [2.6, 3.1, 6.4], 12, 0.44);
  para(s, "Trained for 5 h 50 m on one host with a 5 GB driver. A checkpoint directory is set — the earlier full-scale attempt had died at 3 h 50 m with a StackOverflow; this run finished clean.", 0.6, 6.2, 12.1, 0.75, 13, { color: HEX.ink2 });
}

// 13 ---- GBT design choices
{
  const s = content("The GBT model", "Two design choices that decided the result", "Choice one: predict the delta. Trees are piecewise constant, so asked for the level they burn capacity re-deriving that it is about the same as now. Predicting the change removes that burden. Choice two: split by time. A random split leaks on a time series because hour T and T plus 1 are about 0.81 correlated. The persistence gate means we can never report a model that does not beat doing nothing.");
  const col = (x, head, lines) => {
    s.addShape(pres.ShapeType.rect, { x, y: 1.4, w: 5.95, h: 3.85, fill: { color: C.background2 }, line: { color: HEX.line, width: 0.5 } });
    s.addText(head, { x: x + 0.25, y: 1.55, w: 5.45, h: 0.5, fontSize: 20, bold: true, color: C.text2, margin: 0, isTextBox: true });
    s.addText(lines, { x: x + 0.25, y: 2.15, w: 5.45, h: 3.0, fontSize: 15, color: HEX.ink, margin: 0, valign: "top", isTextBox: true });
  };
  col(0.6, "Predict the change, not the level", [
    { text: "Trees are piecewise-constant. Asked for the level, they waste capacity re-deriving “about the same as now”.", options: { breakLine: true, paraSpaceAfter: 10 } },
    { text: "Target: level  →  R² 0.9098, 5.6 % better than persistence", options: { breakLine: true, bold: true } },
    { text: "Target: change →  R² 0.9201, 11.3 % better than persistence", options: { breakLine: true, bold: true, color: HEX.green, paraSpaceAfter: 10 } },
    { text: "About twice the gain, same trees and features (measured in the local reproduction).", options: { color: HEX.ink2 } },
  ]);
  col(6.75, "Split by time, never at random", [
    { text: "Consecutive hours correlate ≈ 0.81. A random split puts hour T in train and T+1 in test — the model has effectively seen the answer.", options: { breakLine: true, paraSpaceAfter: 10 } },
    { text: "Train: earlier ≈ 80 % of history", options: { breakLine: true, bold: true } },
    { text: "Test: 2022-07-01 → 2023-03-31, the most recent window", options: { breakLine: true, bold: true, paraSpaceAfter: 10 } },
    { text: "This is what a live system actually faces: predicting a future it has not seen.", options: { color: HEX.ink2 } },
  ]);
  callout(s, "The persistence gate: every run prints the “next hour = this hour” baseline on the SAME test rows and prints *** FAIL *** if the model does not beat it. A model can never be reported without that comparison.", 0.6, 5.5, 12.1, 1.15, 15);
}

// 14 ---- GBT results
{
  const s = content("The GBT model", "Results — the forecaster beats the baseline", "Quote the real-rows figure: synthetic rows are easier to predict, so the blended number would flatter us. RMSE 21.8 against 24.8 is a 12.18 percent reduction. R squared 0.891 means it explains 89 percent of next-hour variance. And the baseline is the honest bar: doing nothing already scores 0.8587.");
  s.addChart(pres.charts.BAR, [{ name: "RMSE µg/m³", labels: ["Persistence\n(next hour = this hour)", "GBT forecaster"], values: [24.831, 21.806] }],
    { x: 0.6, y: 1.4, w: 5.2, h: 4.3, barDir: "col", ...chartBase(), chartColors: [HEX.muted, HEX.blue], barGapWidthPct: 60, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.00", valAxisMinVal: 0, valAxisMaxVal: 30,
      showValAxisTitle: true, valAxisTitle: "RMSE, µg/m³ (lower is better)", valAxisTitleColor: HEX.ink2, valAxisTitleFontSize: 11 });
  para(s, "Real station-hours only, n = 2,074,569", 0.6, 5.75, 5.2, 0.4, 13, { italic: true, color: HEX.muted });
  table(s, ["Real rows (n = 2,074,569)", "R²", "RMSE", "MAE"], [
    ["Persistence baseline", "0.8587", "24.831", "9.937"],
    [{ text: "GBT forecaster", options: { bold: true } }, { text: "0.8910", options: { bold: true, color: "1E6B45" } }, { text: "21.806", options: { bold: true, color: "1E6B45" } }, { text: "8.926", options: { bold: true, color: "1E6B45" } }],
    ["Improvement", "+ 0.0323", "− 12.18 %", "− 1.011"],
  ], 6.2, 1.4, 6.5, [3.0, 1.1, 1.3, 1.1], 14, 0.5);
  table(s, ["All rows (n = 18,671,121)", "R²", "RMSE", "MAE"], [
    ["Persistence baseline", "0.8563", "25.443", "10.357"], ["GBT forecaster", "0.8884", "22.429", "9.353"], ["Improvement", "+ 0.0321", "− 11.85 %", "− 1.004"],
  ], 6.2, 3.85, 6.5, [3.0, 1.1, 1.3, 1.1], 14, 0.5);
  callout(s, "PASS — beats persistence by 0.0323 R² on real rows. Track A (19 cities, 120 trees) managed 5.67 % RMSE reduction; scaling to 241 cities and 300 trees doubled it.", 6.2, 5.95, 6.5, 0.95, 13);
}

// 15 ---- Feature importance
{
  const s = content("The GBT model", "What the model learned to look at", "Importance is measured from the trained model, mapped back to feature names. The current level and the direction of change dominate, which is physically sensible. The interesting row is pm25 was imputed at number six: the model taught itself to distrust readings that were filled in rather than measured.");
  const names = ["pm25  (current level)", "pm25_delta_1h  (rising / falling)", "pm25_surge_ratio  (spike under way)", "pm25_lag_1h  (previous hour)", "pm25_roll_3h  (3-hour trend)", "pm25_was_imputed  (filled, not measured)", "pm25_std_6h  (recent volatility)", "pm25_avg24h  (daily mean)", "aqi_roll_6h  (6-hour AQI trend)", "pm25_roll_6h  (6-hour trend)"];
  const vals = [0.1011, 0.0758, 0.0688, 0.0594, 0.0542, 0.0535, 0.0397, 0.0331, 0.0315, 0.0309];
  s.addChart(pres.charts.BAR, [{ name: "importance", labels: names, values: vals }],
    { x: 0.6, y: 1.4, w: 7.7, h: 5.3, barDir: "bar", ...chartBase(), chartColors: [HEX.blue], barGapWidthPct: 40, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.000", valAxisHidden: true, valGridLine: { style: "none" }, catAxisOrientation: "maxMin", catAxisLabelFontSize: 11 });
  para(s, "Reading the chart", 8.6, 1.45, 4.1, 0.4, 18, { bold: true, color: HEX.blue });
  bullets(s, [
    "Where you are now, and which way you are moving, matter most",
    "Time of day (hour_sin / hour_cos) and weather also contribute further down the 86 inputs",
  ], 8.6, 1.95, 4.1, 1.9, 14);
  callout(s, "pm25_was_imputed is 6th of 86 inputs. The model learned to discount filled-in readings — direct evidence that flagging every imputed value was the right call.", 8.6, 4.0, 4.1, 2.0, 15, "FBEFD0");
  para(s, "“The model does not just use the numbers — it uses whether it can trust them.”", 8.6, 6.15, 4.1, 0.6, 13, { italic: true, color: HEX.ink2 });
}

// ============================================================================
// SECTION: Live alerting
// ============================================================================
pres.addSection({ title: "Live alerting" });

// 16 ---- Streaming
{
  const s = content("Live alerting", "Streaming speed layer — 10-second micro-batches", "Spark Structured Streaming watches an HDFS folder. Every 10 seconds it takes any new file, rebuilds the features, runs the GBT and writes alerts. The hard part is that streaming has no memory, so we keep a 30 hour rolling history table in HDFS and union it with each batch.");
  s.addChart(pres.charts.BAR, [{ name: "latency (s)", labels: ["batch 0", "batch 1", "batch 2", "batch 3", "live batch"], values: [10.75, 7.82, 7.02, 6.89, 23.45] }],
    { x: 0.6, y: 1.4, w: 6.2, h: 4.0, barDir: "col", ...chartBase(), chartColors: [HEX.blue, HEX.blue, HEX.blue, HEX.blue, HEX.teal], barGapWidthPct: 50, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0\" s\"", valAxisMinVal: 0, valAxisMaxVal: 28,
      showValAxisTitle: true, valAxisTitle: "latency per micro-batch, s", valAxisTitleColor: HEX.ink2, valAxisTitleFontSize: 11 });
  para(s, "Batches 0–3: 120-row replay batches. Live batch: 16,560 rows scored in one pass.", 0.6, 5.5, 6.2, 0.7, 13, { italic: true, color: HEX.muted });
  para(s, "How it works", 7.2, 1.4, 5.5, 0.4, 18, { bold: true, color: HEX.blue });
  bullets(s, [
    "File source on HDFS, 10 s trigger, one file per micro-batch",
    "A persisted 30-hour history table per station supplies lag and rolling features — and survives job restarts",
    "The trained GBT loads straight from HDFS; MLlib's on-disk format is language-neutral",
    "Forecast PM₂.₅ → CPCB AQI; written as an alert when AQI > 150",
  ], 7.2, 1.9, 5.5, 3.2, 15);
  callout(s, "Measured: ≈ 7 s latency once the JVM is warm; 16,560 live rows scored with 0 dropped.", 7.2, 5.3, 5.5, 0.95, 14);
}

// 17 ---- Live enrichment
{
  const s = content("Live alerting", "Live enrichment — making the live feed model-ready", "Raw CAMS JSON carries only 28 of the model's 54 numeric features. We found that by comparing the model's requirements to the payload, then closed the gap by joining CAMS, live weather and the city profiles in one Spark job on YARN. Two unit conversions were measured, not assumed.");
  table(s, ["Missing from raw CAMS JSON", "n", "Real source used"], [
    ["Weather: temperature, humidity, wind speed and direction, rain, pressure, solar", "8", "Open-Meteo weather API (same provider, no key)"],
    ["Derived: ventilation, scrub factor, stagnation, temp × humidity, is_raining", "5", "Computed once weather exists"],
    ["traffic_index, is_rush_hour, urbanization_index", "3", "city_profiles.csv — same profiles as the generator"],
    ["*_was_imputed provenance flags", "10", "0 if the API returned a value, 1 if null"],
  ], 0.6, 1.4, 12.1, [6.0, 0.6, 5.5], 13, 0.62);
  stat(s, 0.6, 4.55, 2.9, 1.15, "16,560", "live rows · 230 cities", HEX.teal);
  stat(s, 3.65, 4.55, 2.9, 1.15, "0 nulls", "on model-critical columns", HEX.teal);
  para(s, "Unit conversions, measured", 6.9, 4.5, 5.8, 0.35, 16, { bold: true, color: HEX.blue });
  bullets(s, ["CO: µg/m³ → mg/m³ (÷ 1000); unconverted, structured CO averages 0.95 vs CAMS 566", "Pressure: hPa → mmHg (× 0.750062); output 753.81 matches the structured median 753"], 6.9, 4.9, 5.8, 1.5, 13);
  para(s, "Ran as a YARN application: CAMS window = weather window = 2026-09-04 → 09-06, joined 16,560 rows.", 0.6, 5.9, 5.95, 0.85, 14, { color: HEX.ink2 });
}

// 18 ---- Live alerts
{
  const s = content("Live alerting", "Live output — who is being warned, and why", "91 cities under warning, 1,130 warnings. 82 percent of alerts are ozone-driven: a photochemical smog signal. That matters because a mask does nothing for ozone, the right advice is avoid midday exertion. We only see this because the alert engine records the dominant pollutant per alert.");
  stat(s, 0.6, 1.4, 2.9, 1.2, "91", "cities under warning", HEX.red);
  stat(s, 3.65, 1.4, 2.9, 1.2, "1,130", "warnings issued", HEX.red);
  stat(s, 6.7, 1.4, 3.0, 1.2, "230", "cities monitored", HEX.blue);
  stat(s, 9.85, 1.4, 2.85, 1.2, "AQI 500", "worst: Jaisalmer, dust", HEX.maroon, 28);
  s.addChart(pres.charts.BAR, [{ name: "warnings", labels: ["Moderate", "Poor", "Very Poor", "Severe"], values: [896, 144, 13, 77] }],
    { x: 0.6, y: 2.95, w: 5.9, h: 3.4, barDir: "col", ...chartBase(), chartColors: [HEX.amber, "E8731A", HEX.red, HEX.maroon], barGapWidthPct: 45, dataLabelPosition: "outEnd", valAxisMinVal: 0 });
  para(s, "Severity of warnings (CPCB bands)", 0.6, 6.35, 5.9, 0.35, 13, { italic: true, color: HEX.muted });
  s.addChart(pres.charts.BAR, [{ name: "warnings", labels: ["Ozone (O₃)", "Coarse dust (PM₁₀)", "Fine particles (PM₂.₅)", "SO₂"], values: [922, 139, 67, 2] }],
    { x: 6.9, y: 2.95, w: 5.8, h: 3.4, barDir: "bar", ...chartBase(), chartColors: [HEX.blue, HEX.muted, HEX.muted, HEX.muted], barGapWidthPct: 45, dataLabelPosition: "outEnd", valAxisHidden: true, valGridLine: { style: "none" }, catAxisOrientation: "maxMin" });
  para(s, "Dominant pollutant per warning — 82 % ozone", 6.9, 6.35, 5.8, 0.35, 13, { italic: true, color: HEX.muted });
}

// ============================================================================
// SECTION: Serving
// ============================================================================
pres.addSection({ title: "Serving and the website" });

// 19 ---- Hive
{
  const s = content("Serving and the website", "Hive serving layer", "Three external tables and three views over the Parquet already in HDFS. External means we added SQL over 154 million rows at zero storage cost and a careless drop table removes only metadata. The one to show is Delhi's seasonal cycle: a 5.5 times swing between August and November, which is exactly why 13 years of history is needed.");
  table(s, ["Object", "Over", "Purpose"], [
    ["unified_airquality", "154.6 M rows", "structured + semi-structured, one schema"],
    ["clean_airquality", "146.3 M rows", "Phase 3 output, partitioned by city"],
    ["stream_alerts", "1,130 warnings", "what the alert engine fired"],
    ["3 views (live, alert, compare)", "views", "ready answers for the dashboard"],
  ], 0.6, 1.4, 6.0, [2.3, 1.4, 2.3], 12, 0.62);
  bullets(s, ["EXTERNAL tables: no data copied; DROP removes metadata only", "Exposed over HiveServer2 Thrift (port 10000) for beeline / JDBC", "All six demo queries return real results"], 0.6, 4.9, 6.0, 1.8, 14);
  s.addChart(pres.charts.LINE, [{ name: "PM2.5", labels: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], values: [180.5, 127.9, 88.6, 86.8, 79.5, 66.3, 44.0, 38.8, 47.1, 120.1, 213.6, 199.4] }],
    { x: 6.9, y: 1.4, w: 5.8, h: 4.2, ...chartBase(), chartColors: [HEX.blue], lineSize: 3, lineDataSymbolSize: 8, dataLabelPosition: "t", dataLabelFontSize: 10, valAxisMinVal: 0, valAxisMaxVal: 250,
      showValAxisTitle: true, valAxisTitle: "PM₂.₅ µg/m³", valAxisTitleColor: HEX.ink2, valAxisTitleFontSize: 11 });
  callout(s, "Delhi, measured values only: 5.5× swing between the August monsoon low (38.8) and the November peak (213.6).", 6.9, 5.7, 5.8, 1.0, 14);
}

// 20 ---- Website
{
  const s = content("Serving and the website", "The final output — the public warning board", "This is the deliverable. Not a chart, a message residents could act on. Every number came from a Hive query; the page displays the precomputed results, so it loads instantly and works with the cluster off. The pipeline is live; the page shows the latest completed cycle.");
  imgFit(s, "site_top.png", 0.6, 1.35, 6.9, 5.5, 1440, 1180, "Warning board screenshot");
  para(s, "What a resident sees", 7.8, 1.4, 4.9, 0.4, 18, { bold: true, color: HEX.blue });
  bullets(s, [
    "Headline: 91 cities under warning, worst forecast first",
    "Search for your city, filter by severity",
    "Each card is the actual message: forecast AQI, the hour, the cause, CPCB's health advice, what to do",
    "India map, warnings per hour, cause breakdown",
  ], 7.8, 1.9, 4.9, 3.1, 14);
  para(s, "How it is built", 7.8, 5.0, 4.9, 0.4, 16, { bold: true, color: HEX.blue });
  para(s, "Hive → export job → one JSON → embedded in a single HTML file. No server, no internet, no cluster needed to open it.", 7.8, 5.4, 4.9, 1.3, 14, { color: HEX.ink2 });
}

// ============================================================================
// SECTION: Veracity
// ============================================================================
pres.addSection({ title: "Is the data honest?" });

// 21 ---- Truthfulness
{
  const s = content("Is the data honest?", "How we know the dataset is truthful", "88.9 percent is synthetic, so this is the hardest question. Two independent lines of evidence: five paired statistical tests of every synthetic station against its own real parent, and an independent comparison against CAMS satellite data. The CAMS result is mixed and we publish it as mixed.");
  para(s, "1. Five paired tests — synthetic vs its own real parent", 0.6, 1.35, 6.4, 0.4, 16, { bold: true, color: HEX.blue });
  table(s, ["#", "Test", "The cheat it catches"], [
    ["1", "Persistence R²", "Fake data easier to predict than real"],
    ["2", "Autocorrelation, lags 1–6 h", "Random noise or over-smoothing"],
    ["3", "Quantiles p5–p95", "Drift and inflated variance"],
    ["4", "Missingness rate", "Gaps filled in to look easy"],
    ["5", "Cross-correlation", "Noise that breaks pollutant links"],
  ], 0.6, 1.8, 6.4, [0.5, 2.6, 3.3], 12, 0.5);
  para(s, "The old generator scored 0.856 synthetic vs 0.733 real on test 1 — it would have failed. Ours passes; FAIL is blocking.", 0.6, 4.95, 6.4, 1.0, 14, { color: HEX.ink2 });
  para(s, "2. Independent check — CPCB vs CAMS, 1,152,707 city-hours", 7.3, 1.35, 5.4, 0.4, 16, { bold: true, color: HEX.blue });
  s.addChart(pres.charts.BAR, [{ name: "correlation", labels: ["PM₂.₅", "PM₁₀", "O₃", "NO₂", "SO₂"], values: [0.565, 0.558, 0.361, 0.219, 0.083] }],
    { x: 7.3, y: 1.8, w: 5.4, h: 3.5, barDir: "col", ...chartBase(), chartColors: [HEX.blue, HEX.blue, HEX.amber, HEX.amber, HEX.red], barGapWidthPct: 45, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.000", valAxisMinVal: 0, valAxisMaxVal: 1,
      showValAxisTitle: true, valAxisTitle: "Pearson correlation", valAxisTitleColor: HEX.ink2, valAxisTitleFontSize: 11 });
  callout(s, "Mixed, and reported as mixed: particulates track moderately, SO₂ shows essentially no agreement.", 7.3, 5.4, 5.4, 0.95, 14, "FBEFD0");
  para(s, "A synthetic-vs-CAMS comparison was run and discarded: city-hour averaging cancels the perturbation, so it cannot tell the two apart.", 0.6, 6.05, 6.4, 0.85, 12, { italic: true, color: HEX.muted });
}

// 22 ---- Defects
{
  const s = content("Is the data honest?", "Eleven defects found — and how each was caught", "Four were in the source data, seven in code that had been written but never run. Two of them produced plausible wrong answers with no error at all: 16,560 rows in and zero out, and a Hive table returning correct counts alongside NULL timestamps. The habit that caught them: reconcile output counts against an independently known number.");
  para(s, "In the dataset (4)", 0.6, 1.35, 5.4, 0.35, 16, { bold: true, color: HEX.blue });
  table(s, ["Defect", "Fix"], [
    ["Flags not binary (24,725 distinct values)", "round to 0 / 1"],
    ["T+1 label via lead(): 8.69 % wrong horizon", "require ts + 3600 s"],
    ["Impossible values: humidity 104.999 %", "clamp to range"],
    ["Only 43 % of rows have all 7 pollutants", "3-tier imputation, flagged"],
  ], 0.6, 1.75, 5.4, [3.4, 2.0], 12, 0.62);
  para(s, "In the pipeline (7) — found only by running it", 6.3, 1.35, 6.4, 0.35, 16, { bold: true, color: HEX.blue });
  table(s, ["Defect", "Caught by"], [
    ["Substring join double-counted Mumbai / Noida", "44,544 ≠ 44,160 rows"],
    ["Streaming used ts_unix before it existed", "alerts printed, then a stall"],
    [{ text: "VectorAssembler silently dropped every live row", options: { bold: true } }, "16,560 in, 0 out, no error"],
    ["paths.py built hdfs:////host (4 slashes)", "printed the resolved path"],
    ["HDFS write died: no spare DataNode", "full-scale write failure"],
    ["numpy missing in the Spark image", "training failed at import"],
    [{ text: "Hive table: column that does not exist", options: { bold: true } }, "NULL timestamps, counts fine"],
  ], 6.3, 1.75, 6.4, [3.8, 2.6], 12, 0.5);
  callout(s, "Two of them gave plausible wrong answers with no error. A silent wrong answer is more dangerous than a crash — reconcile every output count against a number you know independently.", 0.6, 5.1, 5.4, 1.6, 13, "F9E3E1");
}

// ============================================================================
// SECTION: Evidence
// ============================================================================
pres.addSection({ title: "Evidence" });
{
  const s = pres.addSlide({ masterName: "SECTION", sectionTitle: "Evidence" });
  s.addText("Evidence of the whole project", { placeholder: "title" });
  s.addText("Every claim traces to a preserved log, a screenshot of the running cluster, or a script that reproduces it", { placeholder: "body" });
  s.addNotes("The next five slides are the proof. First an index mapping each claim to its log, then live screenshots of HDFS and YARN, then verbatim log excerpts.");
}

// 23 ---- Evidence index
{
  const s = content("Evidence", "Evidence index — claim → proof", "All logs are in docs/run_logs. If an examiner asks how we know a number, point to the row and open the file. One honest note: the first enrichment log recorded a failed run with zero rows, so we kept it labelled as such and saved the successful re-run separately.");
  table(s, ["Claim", "Evidence (preserved in docs/run_logs)"], [
    ["154,583,979 rows, one schema", "merge_run.log · spark_on_yarn_demo.log (live recount on YARN)"],
    ["Phase 4 full scale — 93,216,105 labelled rows", "phase4_fullscale.log"],
    ["GBT R² 0.8910 vs 0.8587 persistence", "trackB_train_fullscale.summary.log (raw 13 MB log kept)"],
    ["Spark ran on YARN, read from HDFS", "spark_on_yarn_demo.log · live_enrichment_yarn_success.log · YARN UI"],
    ["HDFS: 4 live DataNodes, 0 corrupt / missing", "NameNode UI + dfsadmin report (screenshots)"],
    ["Streaming: 16,560 scored → 1,130 alerts", "live_stream_scoring.log"],
    ["CPCB vs CAMS cross-validation", "crossval.log · scripts/04_cross_validate_overlap.py"],
    ["230-city CAMS history, 8,263,440 records", "history_fetch.log"],
    ["Hive tables and queries", "hive_create.log · hive_queries.log"],
    ["Every quoted number is reproducible", "scripts/_audit/ — 15 audit scripts"],
  ], 0.6, 1.4, 12.1, [5.1, 7.0], 13, 0.5);
}

// 24 ---- Evidence: HDFS + YARN screenshots
{
  const s = content("Evidence", "Evidence — HDFS and YARN, live", "Screenshots of the running cluster taken for this presentation. Left: the NameNode UI listing the DataNodes. Right: the YARN ResourceManager listing four NodeManagers.");
  imgFit(s, "hdfs_dn_crop.png", 0.6, 1.4, 6.0, 3.9, 1190, 620, "HDFS DataNode screenshot");
  imgFit(s, "yarn_nodes_crop.png", 6.8, 1.4, 5.9, 3.9, 1440, 520, "YARN nodes screenshot");
  para(s, "HDFS — NameNode UI :9870", 0.6, 5.4, 6.0, 0.35, 15, { bold: true, color: HEX.blue });
  bullets(s, ["4 live DataNodes · replication 3 · 128 MB blocks", "0 under-replicated · 0 missing · 0 corrupt blocks"], 0.6, 5.8, 6.0, 1.1, 14);
  para(s, "YARN — ResourceManager UI :8088", 6.8, 5.4, 5.9, 0.35, 15, { bold: true, color: HEX.blue });
  bullets(s, ["1 ResourceManager + 4 NodeManagers, all RUNNING", "Spark jobs run as YARN applications"], 6.8, 5.8, 5.9, 1.1, 14);
}

// 25 ---- Evidence: Spark on YARN job
{
  const s = content("Evidence", "Evidence — a Spark job on YARN, reading HDFS", "Application AirQuality_Review_Demo was scheduled by YARN and read the unified table from HDFS. The recount reproduced 154,583,979 exactly. The container and the executors are visible in the YARN UI.");
  imgFit(s, "yarn_apps.png", 0.6, 1.3, 12.1, 2.0, 2000, 560, "YARN applications screenshot");
  term(s,
`master     : yarn
app id     : application_1792046046524_0001
[2] Rows per data source (distributed count over 154.6M rows):
|semistructured_json|cams_history|8263440  |230   |
|semistructured_json|live_api    |44160    |230   |
|structured_csv     |real        |16252931 |241   |
|structured_csv     |synthetic   |130023448|241   |
TOTAL rows: 154,583,979   (expected 154,583,979 -> True)`,
    0.6, 3.5, 7.2, 2.55, 11);
  para(s, "What this proves", 8.1, 3.45, 4.6, 0.4, 16, { bold: true, color: HEX.blue });
  bullets(s, ["master: yarn — not local mode", "Data read from hdfs://namenode:9000", "Count reconciles to the independently known total", "Source: spark_on_yarn_demo.log"], 8.1, 3.9, 4.6, 2.2, 14);
  para(s, "A second YARN application, the LiveEnrichment job (application_…_0002), ran the same day: 16,560 rows, 230 cities.", 0.6, 6.2, 12.1, 0.6, 13, { italic: true, color: HEX.muted });
}

// 26 ---- Evidence: logs (Phase 4 + training)
{
  const s = content("Evidence", "Evidence — Phase 4 and GBT training logs", "Verbatim from phase4_fullscale.log and trackB_train_fullscale.summary.log. Left is the Phase 4 summary block; right is the persistence baseline and the PHASE 6 evaluation. The big raw log is 13 MB, mostly Spark cache warnings.");
  term(s,
`rows in            : 146,276,379
rows after dedupe  : 128,660,967
rows with T+1 label: 93,216,105
rows assemblable   : 93,216,105
numeric features   : 54
one-hot width      : 32
FEATURE VECTOR DIM : 86
partitioned by     : city
elapsed            : 4411.0 s`, 0.6, 1.4, 5.6, 2.6, 12, "phase4_fullscale.log — Phase 4 at full scale");
  term(s,
`train 10,000,552 rows | test 18,671,121 rows
test window: 2022-07-01 -> 2023-03-31
PERSISTENCE BASELINE  R2=0.8563 RMSE=25.443
trained on 10,000,552 rows, 300 trees
REAL ROWS ONLY (n=2,074,569)
  persistence baseline  0.8587  24.831  9.937
  GBT model             0.8910  21.806  8.926
  RMSE reduction        12.18%
PASS (real rows): beats persistence by 0.0323 R2`, 6.5, 1.4, 6.2, 3.0, 11, "trackB_train_fullscale.summary.log — Phase 6 evaluation");
  callout(s, "The script's own gate printed PASS. It prints *** FAIL *** and refuses the run if the model does not beat persistence on the same test rows.", 0.6, 5.1, 12.1, 0.95, 14);
}

// 27 ---- Evidence: logs (stream, enrichment, hive)
{
  const s = content("Evidence", "Evidence — streaming, enrichment and Hive logs", "Three more verbatim excerpts. Streaming: 16,560 rows in, 16,560 predicted, 1,130 alerts. Enrichment: the two feed windows overlap exactly and there are zero nulls on the model-critical columns. Hive: row counts by source.");
  term(s,
`[batch 0] *** 1130 ALERTS ***
[batch 0] rows in=16,560
  predicted=16,560
  alerts=1,130
  latency=23,452 ms

|Jaisalmer|LIVE_JAISALMER
|500.0|SEVERE|Air quality
warning for Jaisalmer:
forecast AQI 500 (Severe),
driven by pm10.`, 0.6, 1.4, 3.9, 4.0, 10.5, "live_stream_scoring.log");
  term(s,
`cams window    :
  2026-09-04 .. 2026-09-06
weather window :
  2026-09-04 .. 2026-09-06
joined rows    : 16,560
enriched rows  : 16,560
  across 230 cities
  pm25      nulls=0
  temperature_c nulls=0
  pressure  nulls=0
  traffic_index nulls=0`, 4.7, 1.4, 3.9, 4.0, 10.5, "live_enrichment_yarn_success.log");
  term(s,
`--- Q1: rows by source ---
cams_history  8263440  230
live_api        44160  230
real         16252931  241
synthetic   130023448  241

--- Q6: Delhi PM2.5 by month ---
1   1597473   180.5
8   1402020    38.8
11  1553544   213.6`, 8.8, 1.4, 3.9, 4.0, 10.5, "hive_queries.log");
  para(s, "All logs are preserved in docs/run_logs/ — nothing on these slides was typed in by hand.", 0.6, 6.1, 12.1, 0.5, 14, { italic: true, color: HEX.ink2 });
}

// 28 ---- Evidence: first review screenshots
{
  const s = content("Evidence", "Evidence from the first review — still valid", "These are the original screenshots from the first review: the raw dataset in HDFS, the preprocessing run at full scale, and the first Spark-on-YARN activation. They are retained because the infrastructure they prove underpins everything above.");
  imgFit(s, "s8_2.png", 0.6, 1.4, 3.9, 4.5, 1054, 988, "Raw dataset in HDFS");
  imgFit(s, "s10_1.png", 4.7, 1.4, 4.2, 2.9, 804, 455, "Preprocessing at full scale");
  imgFit(s, "s13_1.png", 9.1, 1.4, 3.6, 2.9, 1062, 429, "Spark activation on YARN");
  para(s, "Raw dataset in HDFS: 232 blocks, replicated 3×", 0.6, 6.0, 3.9, 0.7, 13, { color: HEX.ink2 });
  para(s, "Scala preprocessing: 146,276,379 rows in, 146,276,379 out", 4.7, 4.4, 4.2, 0.7, 13, { color: HEX.ink2 });
  para(s, "First Spark job on YARN: ACCEPTED → RUNNING → SUCCEEDED", 9.1, 4.4, 3.6, 0.7, 13, { color: HEX.ink2 });
  callout(s, "Since then the same infrastructure ran Phase 4 (19.7 GB), the 300-tree training, the streaming job and the live enrichment.", 4.7, 5.35, 8.0, 1.0, 14);
}

// ============================================================================
// SECTION: Closing
// ============================================================================
pres.addSection({ title: "Closing" });

// 29 ---- Five V's
{
  const s = content("Closing", "The five V's — each one demonstrated", "Each V has a concrete measured proof, not a claim. Volume and Variety are the data; Velocity is the streaming run; Veracity is the validation and the defect log; Value is the model beating the honest baseline.");
  table(s, ["V", "Evidence", "State"], [
    ["Volume", "154,583,979 rows · 33 GB · 1 NameNode + 4 DataNodes · fsck HEALTHY", { text: "demonstrated", options: { color: "1E6B45", bold: true } }],
    ["Variety", "Flat CSV and nested JSON read by native Spark readers into one schema; Hive spans both", { text: "demonstrated", options: { color: "1E6B45", bold: true } }],
    ["Velocity", "Structured Streaming, 10 s micro-batches, ≈ 7 s latency, 1,130 alerts on live data", { text: "demonstrated", options: { color: "1E6B45", bold: true } }],
    ["Veracity", "5 paired tests, independent CAMS check, 11 defects found and fixed, every fill flagged", { text: "demonstrated", options: { color: "1E6B45", bold: true } }],
    ["Value", "R² 0.8910 vs 0.8587 on 2.07 M real rows — an hour of warning before pollution arrives", { text: "demonstrated", options: { color: "1E6B45", bold: true } }],
  ], 0.6, 1.5, 12.1, [1.5, 8.5, 2.1], 14, 0.82);
}

// 30 ---- Challenges and limitations
{
  const s = content("Closing", "Challenges and limitations", "Everything here was hit, diagnosed and resolved. The honest limitations are at the bottom: 88.9 percent synthetic, a 10 million row training sample because of RAM, and a dashboard showing the latest completed cycle rather than a push feed. Say them before you are asked.");
  table(s, ["Challenge", "Root cause", "Resolution"], [
    ["Spark could not write to HDFS from the host", "NameNode returns container-internal DataNode addresses", "Run Spark inside the cluster network"],
    ["Full-scale write died after computing", "DataNodes unresponsive under memory pressure; no spare node at replication 3", "Driver 7→5 GB, replication 2, replace-datanode policy NEVER, 180 s timeouts"],
    ["YARN executors killed (exit 137)", "4 × 3 GB NodeManagers advertise 12 GB on a 15.7 GB host", "Stopped NodeManagers for Phase 4; YARN proven by enrichment job"],
    ["Shuffle spill filled the C: drive", "Scratch volume lives in the WSL2 disk (peaked 65 GB)", "Guard job killed below 30 GB free; never tripped"],
    ["Live rows silently dropped", "VectorAssembler skip + CAMS ammonia always null", "Fill after flagging provenance"],
    ["Live feeds shared zero hours", "Fetched weeks apart", "Fetch both in one cycle; window report added"],
  ], 0.6, 1.35, 12.1, [3.4, 4.4, 4.3], 12, 0.62);
  callout(s, "Limitations: 88.9 % of structured rows are synthetic (so results are reported on real rows) · trained on a 10 M-row sample of 74.5 M (RAM ceiling; evaluation not sampled) · the page shows the latest completed cycle · 230 of 241 cities · SO₂ agreement with CAMS is poor.", 0.6, 5.65, 12.1, 1.1, 13, "FBEFD0");
}

// 31 ---- Conclusion
{
  const s = content("Closing", "Conclusion and future work", "The platform does what its title says. Close on the shape of the contribution: not just a model, but a measured, reproducible, honest pipeline. Future work is the natural next steps, not gaps in the demonstration.");
  para(s, "What has been demonstrated", 0.6, 1.4, 6.0, 0.4, 20, { bold: true, color: HEX.blue });
  bullets(s, [
    "A fault-tolerant 4-node HDFS lakehouse of 154.6 M rows, verified HEALTHY",
    "Spark on YARN running cleaning, feature engineering and a 300-tree GBT",
    "A forecaster 12.18 % better than the honest baseline on 2.07 M real rows",
    "Live data enriched on YARN and scored in 10 s micro-batches: 1,130 warnings",
    "Hive serving and a public warning board with the message residents receive",
  ], 0.6, 1.9, 6.0, 4.6, 15);
  para(s, "Future work", 6.9, 1.4, 5.8, 0.4, 20, { bold: true, color: HEX.blue });
  bullets(s, [
    "Schedule the daily cycle and push warnings by SMS / app notification",
    "Compare against Random Forest and XGBoost baselines",
    "Neighbour-station features for a GraphX station-network model",
    "Resolve the 11 unmatched localities and add ground-truth SO₂ validation",
    "Move to a larger multi-host cluster so the full 74.5 M rows can train",
  ], 6.9, 1.9, 5.8, 4.6, 15);
}

// 32 ---- Questions
{
  const s = pres.addSlide({ masterName: "SECTION", sectionTitle: "Closing" });
  s.addText("Thank you — questions", { placeholder: "title" });
  s.addText("Warning board: dashboard/AirWatch_India.html · Logs: docs/run_logs/ · Code: scripts/, scala/, hive/, dashboard/", { placeholder: "body" });
  s.addNotes("Likely questions: What is the accuracy? It is regression, so R squared 0.891 and 12.18 percent better than baseline on real rows. Why so much synthetic data? 88.9 percent, disclosed, which is why we report real-rows-only. Is the site live? The pipeline is; the page shows the latest completed cycle. Does it use Hive? Yes, every number comes from a Hive query. How many partitions? 241, by city. API key? None; Open-Meteo is key-less.");
}

// 33 ---- References
{
  const s = content("Closing", "References", "");
  const refs = [
    "[1] Air Quality Prediction using Multi-Source Remote Sensing Data Integration with Hybrid Deep Learning Framework (MAST-Net). Nature, Scientific Reports, December 2025.",
    "[2] Apache Hadoop Documentation, version 3.3.6. The Apache Software Foundation. hadoop.apache.org/docs/r3.3.6/",
    "[3] Apache Spark Documentation, version 3.5.6. The Apache Software Foundation. spark.apache.org/docs/3.5.6/",
    "[4] Central Pollution Control Board (CPCB). National Air Quality Index — Report of the Expert Group, 2014. Government of India.",
    "[5] Zaharia, M. et al. Resilient Distributed Datasets: A Fault-Tolerant Abstraction for In-Memory Cluster Computing. NSDI, 2012.",
    "[6] Shvachko, K., Kuang, H., Radia, S., Chansler, R. The Hadoop Distributed File System. IEEE MSST, 2010.",
    "[7] Friedman, J. H. Greedy Function Approximation: A Gradient Boosting Machine. Annals of Statistics, 29(5), 2001.",
    "[8] Apache Parquet Documentation. The Apache Software Foundation. parquet.apache.org",
    "[9] Copernicus Atmosphere Monitoring Service (CAMS), ECMWF — via Open-Meteo Air Quality API (CC-BY 4.0). open-meteo.com",
    "[10] Apache Hive Documentation. The Apache Software Foundation. hive.apache.org",
  ];
  s.addText(refs.map((t, i) => ({ text: t, options: { breakLine: i < refs.length - 1, paraSpaceAfter: 7 } })),
    { x: 0.6, y: 1.4, w: 12.1, h: 5.4, fontSize: 14, color: HEX.ink, margin: 0, valign: "top", isTextBox: true });
}

// ---------------------------------------------------------------- write
(async () => {
  await pres.writeFile({ fileName: OUT });
  if (SKILL) {
    const { applyTheme } = require(path.join(SKILL, "scripts", "apply_theme.js"));
    await applyTheme(OUT, THEME);
  }
  console.log("wrote", OUT);
})();
