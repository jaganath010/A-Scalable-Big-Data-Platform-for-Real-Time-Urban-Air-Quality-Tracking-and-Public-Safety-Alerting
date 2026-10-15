// PROJECT STUDY GUIDE - plain-English explanation of every part of the project (generator)
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
const OUT = process.env.OUT || "Study_Guide.docx";
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

// ============================ STUDY GUIDE CONTENT ============================
const GREEN = "1B7A3D", AMBER = "8A6A00", RED = "C9342B";
// shaded call-out box: kind = "say" (blue), "why" (green), "analogy" (amber), "warn" (red)
function box(kind, title, text) {
  const col = { say: BLUE, why: GREEN, analogy: AMBER, warn: RED }[kind];
  const fill = { say: "EAF2F8", why: "E9F5EC", analogy: "FBF3D9", warn: "FBE6E4" }[kind];
  const b = (c) => ({ style: BorderStyle.SINGLE, size: 4, color: c });
  const kids = [new Paragraph({ spacing: { after: 40 }, children: [new TextRun({ text: title, bold: true, font: "Calibri", size: 20, color: col })] })];
  (Array.isArray(text) ? text : [text]).forEach((t) => kids.push(new Paragraph({ spacing: { after: 40, line: 270 }, children: [run(t, { size: 21 })] })));
  return [new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [W], rows: [new TableRow({ children: [new TableCell({
    width: { size: W, type: WidthType.DXA }, margins: { top: 90, bottom: 90, left: 160, right: 140 }, shading: { fill, type: ShadingType.CLEAR, color: "auto" },
    borders: { top: b(fill), bottom: b(fill), right: b(fill), left: { style: BorderStyle.SINGLE, size: 24, color: col } }, children: kids })] })] }),
    new Paragraph({ spacing: { after: 120 }, children: [] })];
}
const Pl = (t) => P(t, { p: { alignment: AlignmentType.LEFT } });
const T = (header, rows, widths, o) => table(header, rows, widths, { size: 18, ...(o || {}) });
const body = [];

// ---------------- cover ----------------
body.push(
  new Paragraph({ spacing: { before: 1500, after: 200 }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: "PROJECT STUDY GUIDE", font: "Calibri", size: 30, bold: true, color: BLUE })] }),
  new Paragraph({ spacing: { after: 300 }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Everything explained in simple English — every tool, every term, and why we used it", font: "Calibri", size: 24, color: GREY })] }),
  new Paragraph({ spacing: { before: 300, after: 300 }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: "A Scalable Big Data Platform for Real-Time Urban Air Quality Tracking and Public Safety Alerting", font: "Calibri", size: 40, bold: true })] }),
  new Paragraph({ spacing: { after: 200 }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: "23AID302 Big Data Analytics · Group A14", font: "Calibri", size: 26, bold: true, color: BLUE })] }),
  ...table(["Team member", "Register number"], [["Sangeeth S", "CB.AI.U4AID24050"], ["Jaganath R", "CB.AI.U4AID24021"], ["Niranjan S", "CB.AI.U4AID24035"], ["PL Kowshik", "CB.AI.U4AID24036"]], [4500, 4526], { size: 22 }),
  new Paragraph({ spacing: { before: 100, after: 60 }, children: [bold("Faculty: "), run("Sreeja B P")] }),
  new Paragraph({ spacing: { after: 60 }, children: [bold("GitHub: "), link(GH, GH)] }),
  new Paragraph({ spacing: { after: 60 }, children: [bold("Website: "), link(WS, WS)] }));

// ---------------- how to use ----------------
body.push(H1("How to use this guide"),
  P("This guide is written so that someone who has never seen the project can understand it, and so that you can explain it to your teammates and answer questions in the presentation. Nothing here is new work: every number is the same one used in the slides and in the full report."),
  T(["If you have…", "Read"], [
    ["30 minutes", "Part A (the big picture) and Part G (the slide-by-slide script and the numbers cheat-sheet)"],
    ["2 hours", "Parts A to E in order, then the questions in Part G"],
    ["The night before", "Part G: the script, the 34 questions and answers, and the numbers cheat-sheet. Use the glossary (Part H) when a word is unfamiliar"],
  ], [2400, 6626]),
  H2("The four boxes you will see"),
  ...box("say", "SAY IT SIMPLY", "A sentence you can say out loud, in plain words."),
  ...box("analogy", "ANALOGY", "A real-life comparison to make the idea stick."),
  ...box("why", "WHY WE USED IT", "The reason we chose this tool or method, and what else we could have used."),
  ...box("warn", "BE CAREFUL", "A point where it is easy to say something wrong. Say the honest version."),
  H2("The five numbers to remember"),
  T(["Number", "What it is"], [
    ["154.6 million rows / 33 GB", "The size of the data (why we need big data tools)"],
    ["R² 0.8910 vs 0.8587", "Our model's accuracy against the “do nothing” baseline"],
    ["12.18 %", "How much smaller our error is than the baseline"],
    ["10 seconds", "How often the streaming job scores new data"],
    ["27,543 warnings, 221 cities", "What the October 2026 live run produced"],
  ], [3000, 6026], { boldRows: [1] }));

// ================= PART A =================
body.push(H1("Part A — The Big Picture"), H2("A1. The project in one minute"),
  P("Air pollution hurts people, and one hour of warning is enough to change what they do: stay indoors, wear a mask, avoid exercise. So we built a system that looks at the air-quality numbers of Indian cities, predicts what each city's pollution (PM₂.₅) will be one hour from now, turns that into the official Air Quality Index (AQI), and sends a warning when the AQI is going above 150."),
  ...box("say", "SAY IT SIMPLY", "“We built a weather forecast for air pollution. It predicts each city's PM2.5 one hour ahead and warns people before the air gets bad. It runs on a cluster of computers because the data is far too big for one.”"),
  ...box("analogy", "ANALOGY", "Think of a rain forecast app. The app does not just show today's rain; it tells you “rain in 1 hour, take an umbrella”. Our project does that for pollution. The difference is that our “weather data” is 154 million rows, so we needed a team of computers (a cluster) instead of one laptop."),
  H2("A2. Why this is a big data problem"),
  P("Three things made a normal program impossible:"),
  B([bold("The data is huge. "), run("154,583,979 rows and 33 GB. The laptop has 15.7 GB of memory, so the data cannot even be loaded at once. We split it into pieces and process the pieces on several machines at the same time.")]),
  B([bold("The data keeps arriving. "), run("A warning is useless if it arrives tomorrow. The live data must be processed every 10 seconds.")]),
  B([bold("The data comes in different shapes and cannot be fully trusted. "), run("Some is flat tables (CSV), some is nested JSON, and most of the training data is synthetic (computer-generated), so we had to prove it is realistic.")]),
  H2("A3. The whole pipeline in six steps"),
  ...fig(img("architecture.png"), "The system architecture. Read it left to right: sources, ingest, storage, processing, serve and alert", 600),
  T(["Step", "What happens", "Tool"], [
    ["1. Collect", "Download station data, satellite-model data (CAMS) and weather; fetch live data from free APIs", "Python scripts"],
    ["2. Store", "Put everything in a distributed file system that splits files into blocks and keeps 3 copies", "HDFS"],
    ["3. Clean", "Fix errors, fill gaps (and mark every filled value), convert to a fast format", "Spark (Scala) + Parquet"],
    ["4. Learn", "Build 86 clues per row and train a model that predicts next-hour PM2.5", "Spark (Scala) + PySpark MLlib"],
    ["5. Score live", "Every 10 seconds, take new data, use the model, compute the AQI, raise alerts", "Spark Structured Streaming"],
    ["6. Serve and alert", "Store results in Hive, show them on a website, send the messages", "Hive, HTML page, Telegram"],
  ], [1500, 5226, 2300]),
  H2("A4. One reading's journey (follow the data)"),
  P("To understand the system, follow one number from the outside world to a phone."),
  N("At 14:00 the satellite-model service (CAMS, through Open-Meteo) says Hisar's PM₂.₅ is 197 µg/m³. A Python script downloads it as JSON for all 230 cities.", "j"),
  N("The script uploads the JSON to HDFS. The weather for the same hours is downloaded and uploaded too.", "j"),
  N("A Scala job (LiveEnrichment) joins air quality + weather + city profile (traffic, urbanisation) and writes a single CSV with 32 columns, every missing value flagged.", "j"),
  N("The CSV is dropped into a folder. The streaming job (AirQualityStream) notices the new file within 10 seconds.", "j"),
  N("It adds the last 30 hours of that station's history, calculates the clues (previous hour, 3-hour average, change in the last hour, …), and gives them to the trained GBT model.", "j"),
  N("The model returns the predicted change; add it to the current value to get next hour's PM₂.₅. The job converts it to an AQI using the official government table.", "j"),
  N("If the AQI is above 150, a row goes into the alerts table with the severity and the main pollutant.", "j"),
  N("The dispatcher picks the worst alert for Hisar in the next six hours, checks that nobody was already warned, and sends the message: “Air quality warning – Hisar. Expected AQI 463 (Severe), mainly coarse dust. Avoid all outdoor activity…”", "j"),
  N("The same results go to Hive and onto the public website.", "j"),
  H2("A5. The five V's of big data, with our numbers"),
  P("“The five V's” are the standard way to explain why a problem needs big-data tools. Be ready to state each one with a number from our project."),
  T(["V", "Meaning", "Our proof"], [
    ["Volume", "The amount of data", "154,583,979 rows, 33 GB, 241 cities, 4,077 stations. HDFS cuts files into 128 MB blocks and keeps 3 copies"],
    ["Variety", "Different shapes of data", "Structured flat CSV (CPCB) + semi-structured nested JSON (CAMS) + live API, all on one 17-column schema"],
    ["Velocity", "Speed of arrival and processing", "Live feed scored every 10 seconds, about 7 seconds latency per batch"],
    ["Veracity", "Can we trust it?", "88.9 % of structured rows are synthetic, so we ran 5 paired tests, an independent CAMS check, fixed 11 defects, and flagged every filled value"],
    ["Value", "Is it useful?", "12.18 % lower error than the baseline; 27,543 warnings in October, delivered an hour ahead with health advice"],
  ], [1200, 2300, 5526], { boldRows: [3] }),
  ...box("warn", "BE CAREFUL", "Veracity is the V that examiners ask about, because 88.9 % of our structured rows are synthetic. Do not hide it. Say it first, then say how we validated it and that all accuracy numbers are on the real rows only."));

// ================= PART B =================
body.push(H1("Part B — The Data"), H2("B1. Where the data comes from"),
  T(["Name", "What it is", "Format", "Our use"], [
    ["CPCB", "Central Pollution Control Board — India's government body that measures air quality at ground stations", "Flat CSV, 146.3 M rows, 2010–2023", "Training data (has the 13-year history and seasons)"],
    ["CAMS", "Copernicus Atmosphere Monitoring Service — a European satellite + computer-model product that estimates pollution everywhere", "Nested JSON via the Open-Meteo API", "History to validate the data; live feed for alerts"],
    ["Open-Meteo", "A free website/API that serves CAMS air quality and weather; no API key needed (CC-BY 4.0 licence)", "JSON over HTTP", "How we download CAMS and weather"],
    ["city_profiles.csv", "Traffic index, urbanisation index and climate for each city", "CSV", "Context features for the model"],
  ], [1500, 3400, 1900, 2226]),
  H2("B2. Structured vs semi-structured data"),
  P("This is a favourite question because our teacher asked us to combine both."),
  T(["", "Structured (CPCB CSV)", "Semi-structured (CAMS JSON)"], [
    ["Shape", "Flat table: every row has the same fixed columns", "Nested: values inside objects inside lists; each file describes itself with field names"],
    ["Example", "Hisar,2026-10-15 14:00,pm25=197.4,pm10=410", "{ “hourly”: { “time”: […], “pm2_5”: […], “pm10”: […] } }"],
    ["Schema", "Fixed in advance", "Read when you open it (schema-on-read)"],
    ["Spark reader", "spark.read.csv", "spark.read.json"],
  ], [1400, 3600, 4026]),
  ...box("say", "SAY IT SIMPLY", "“Structured data is an Excel sheet. Semi-structured data is a JSON message where each record carries its own field names. Spark reads both and we union them onto one table.”"),
  H2("B3. The pollutants and the AQI"),
  P("The seven pollutants used by India's National Air Quality Index are:"),
  T(["Short name", "Name", "Where it comes from / why it matters"], [
    ["PM₂.₅", "Fine particles (smaller than 2.5 micrometres)", "Smoke, vehicles; goes deep into lungs. Our forecast target"],
    ["PM₁₀", "Coarse dust (smaller than 10 micrometres)", "Dust, construction, crop burning; mask helps"],
    ["NO₂", "Nitrogen dioxide", "Traffic fumes"],
    ["SO₂", "Sulphur dioxide", "Industry, coal burning"],
    ["CO", "Carbon monoxide", "Incomplete combustion"],
    ["O₃", "Ozone", "Formed by sunlight on fumes; peaks in the afternoon; a mask does not help"],
    ["NH₃", "Ammonia", "Agriculture and waste"],
  ], [1400, 3000, 4626]),
  P("Concentrations are measured in µg/m³ (micrograms per cubic metre of air). The AQI turns each pollutant into a score from 0 to 500; the overall AQI is the highest score among the pollutants, and the pollutant that gives the highest score is the “dominant pollutant” (the cause we show in the warning)."),
  T(["AQI", "Category", "Meaning"], [
    ["0–50", "Good", "Minimal impact"], ["51–100", "Satisfactory", "Minor discomfort to sensitive people"], ["101–200", "Moderate", "Discomfort to people with lung or heart disease, children, older adults"],
    ["201–300", "Poor", "Discomfort to most people on prolonged exposure"], ["301–400", "Very Poor", "Respiratory illness on prolonged exposure"], ["401–500", "Severe", "Affects healthy people; serious for those with disease"],
  ], [1400, 2000, 5626]),
  P("How the score is calculated: each pollutant has breakpoints. For PM₂.₅ a 24-hour average of 0–30 µg/m³ maps to AQI 0–50, 30–60 maps to 51–100, 60–90 to 101–200, 90–120 to 201–300, 120–250 to 301–400 and 250–500 to 401–500, interpolating in a straight line inside each band. Averages are 24 hours for PM, NO₂, SO₂ and NH₃ and 8 hours for CO and O₃, because the AQI is defined on averages, not single readings."),
  ...box("say", "SAY IT SIMPLY", "“AQI is a 0–500 score. We predict PM2.5, convert it with the government's table, and raise an alert when the forecast AQI is above 150.”"),
  H2("B4. Synthetic data — the honest part"),
  P("The real CPCB data we could obtain was 16,252,931 station-hours. To get to 146 million rows (thirteen years, 241 cities, 4,077 stations) the dataset was expanded with synthetic rows: 130,023,448 of the 146,276,379 structured rows (88.9 %). Synthetic data is only acceptable if it behaves like the real thing. If it were easier to predict than real data, our accuracy would be fake."),
  P("So every synthetic station is compared with its own real parent station by five tests, and a failure stops the run:"),
  T(["#", "Test", "In plain words"], [
    ["1", "Persistence R²", "Is “next hour = this hour” just as accurate on the synthetic data as on the real data? (The first generator scored 0.856 vs 0.733 and was rejected.)"],
    ["2", "Autocorrelation, lags 1–6 hours", "Does today's value depend on the last few hours the same way?"],
    ["3", "Quantiles (p5 to p95)", "Do the low, middle and high values have the same spread?"],
    ["4", "Missingness rate", "Does it have the same share of missing values (not artificially complete)?"],
    ["5", "Cross-correlation", "Do pollutants move together the same way (e.g. PM2.5 and PM10)?"],
  ], [500, 3000, 5526]),
  P("A separate, independent check compares CPCB with CAMS on 1,152,707 matching city-hours: particulates agree moderately (PM₂.₅ correlation 0.565), SO₂ hardly at all (0.083). We report this as mixed."),
  ...box("warn", "BE CAREFUL", "Never say “the dataset is real”. Say: “The dataset is mostly synthetic expansion of real data, validated by five tests, and we report accuracy on the real rows only.”"),
  H2("B5. The CAMS coverage finding (a good story to tell)"),
  P("We were asked for semi-structured data for 2010–2023. Before building it, we tested the API. It rejects dates before 2013, and from 2013 to July 2022 it returns timestamps with every value empty. Real data starts in August 2022. Delivering 2010–2023 would have looked like ten years of data and contained nothing, so we start in August 2022 and explain why. This shows we check data before trusting it."),
  H2("B6. Cleaning and imputation (Phase 3)"),
  P("Raw data has errors and gaps. The Scala job CleanSelect fixes them in ten steps:"),
  N("Use an explicit 32-column schema (do not let Spark guess types).", "c"), N("Convert text to numbers; bad values become null.", "c"), N("Parse timestamps; drop rows whose time cannot be read.", "c"),
  N("Repair yes/no flags to strict 0 or 1 (they had 24,725 different values).", "c"), N("Clamp impossible values (humidity 104.999 % becomes 100).", "c"), N("Null out readings outside plausible sensor limits.", "c"),
  N("Fill gaps with the median in three tiers: same station, month and hour; else same city and month; else the global median.", "c"), N("Add a flag column for every filled value (pm25_was_imputed = 1).", "c"),
  N("Keep pm25_measured: the original value before filling, so the model is never trained to predict a number we invented.", "c"), N("Save as Parquet (compressed, columnar), one folder per city.", "c"),
  ...box("why", "WHY WE USED IT", "Imputation means filling missing values. We used medians because they are not distorted by extreme pollution spikes. We flag every filled value so measured and estimated data are never confused — and the model itself ranked the pm25_was_imputed flag 6th of 86 features, which proves it learned to trust filled values less."));

// ================= PART C =================
body.push(H1("Part C — The Technology: What, Why, and How"),
  P("For each tool: what it is, an analogy, why we used it, and what it does in our project."),
  H2("C1. Hadoop HDFS — the shared hard disk"),
  P("HDFS (Hadoop Distributed File System) stores very large files across many machines. It cuts each file into blocks (ours are 128 MB), spreads the blocks over several machines and keeps several copies of each block, so the data survives a machine failing."),
  T(["Term", "Meaning", "Our setting"], [
    ["NameNode", "The “index”: knows which blocks make up which file and where each block lives. Stores no data itself", "1"],
    ["DataNode", "A worker machine that stores the blocks", "4"],
    ["Block", "A chunk of a file", "128 MB; the raw 27.5 GB data = 232 blocks"],
    ["Replication factor", "How many copies of each block", "3 (derived layers 2) → 232 blocks × 3 = 696 copies, 82.4 GB on disk"],
    ["fsck", "File-system check: reports missing, corrupt or under-replicated blocks", "Result: HEALTHY, 0 missing, 0 corrupt"],
  ], [1800, 4600, 2626]),
  ...box("analogy", "ANALOGY", "A library with four branches. The librarian (NameNode) has the catalogue. Every book is split into chapters (blocks) and three branches each keep a copy of each chapter. If one branch burns down, nothing is lost and the missing copies are re-made from the others."),
  ...box("why", "WHY WE USED IT", "One machine could not hold or read 33 GB quickly, and a single disk failing would lose everything. HDFS gives capacity, parallel reading (232 blocks = 232 parallel tasks) and fault tolerance. Why four DataNodes? With three nodes and replication 3, every node must hold every block, so nothing is actually spread and a failed node has nowhere to re-copy to. Four is the smallest cluster that behaves like a real distributed one."),
  H2("C2. YARN — the manager that hands out computers"),
  P("YARN (Yet Another Resource Negotiator) decides which application gets how much memory and CPU on which machine."),
  B([bold("ResourceManager (1): "), run("the boss. Receives requests and decides who gets resources.")]),
  B([bold("NodeManager (4): "), run("one per machine. Starts and watches containers (small bundles of CPU and memory). Ours have 3 GB and 2 vcores each.")]),
  B([bold("Container: "), run("the box in which one piece of a Spark job runs.")]),
  ...box("analogy", "ANALOGY", "YARN is the manager of a shared office. Teams (Spark jobs) ask for desks (containers); the manager gives desks on whichever floor (machine) has space."),
  ...box("why", "WHY WE USED IT", "It is the standard way to run Spark on a Hadoop cluster and lets several jobs share the cluster. We proved Spark runs on YARN with a recount job (154,583,979 rows) and the live enrichment job. For the heavy feature job we ran Spark in local mode because four 3 GB NodeManagers advertise 12 GB on a 15.7 GB laptop and YARN killed executors (exit code 137 = out of memory)."),
  H2("C3. Apache Spark — the engine"),
  P("Spark processes big data in parallel across the cluster, keeping data in memory where it can. Version 3.5.6."),
  T(["Term", "Meaning"], [
    ["Driver", "The program's brain: builds the plan and gives tasks to executors"],
    ["Executor", "A worker process that runs tasks on a piece of the data"],
    ["RDD", "Resilient Distributed Dataset: Spark's basic, low-level distributed collection. We do not write RDDs by hand; Spark uses them internally"],
    ["DataFrame", "A distributed table with named columns. What we use. Spark can optimise it (Catalyst optimizer)"],
    ["Transformation", "A step that describes a change (filter, join, withColumn). Lazy: nothing runs yet"],
    ["Action", "A step that actually triggers work (count, write)"],
    ["DAG", "Directed Acyclic Graph: the chain of steps Spark builds before running"],
    ["Stage / task", "Spark cuts the DAG into stages; each stage has one task per partition"],
    ["Shuffle", "Moving data between machines (needed for groupBy, join, window). The expensive part, and where stages are cut"],
    ["Partition", "One slice of the data processed by one task"],
    ["Cache / persist", "Keep a DataFrame in memory because it is used more than once; unpersist frees it"],
    ["Broadcast join", "Send a small table to every machine so the big table need not be shuffled"],
    ["Window function", "A calculation over an ordered group of rows, e.g. each station's last 24 hours"],
  ], [2000, 7026]),
  ...box("analogy", "ANALOGY", "Spark is a kitchen with many cooks. The recipe (DAG) is written first (lazy). The big pile of vegetables (data) is split into trays (partitions); each cook (executor) works a tray. Passing vegetables between cooks (shuffle) is slow, so a good recipe does it rarely."),
  ...box("why", "WHY WE USED IT", "It is the course's main tool, handles batch, streaming and machine learning in one engine, and is much faster than Hadoop MapReduce because it keeps data in memory. Alternatives: MapReduce (slower, disk-based), Flink (streaming specialist), Dask/pandas (single machine)."),
  H3("How our feature job looks inside Spark (the DAG)"),
  P("Six steps: (1) read Parquet — 232 parallel tasks; (2) remove duplicates — shuffle by station and hour; (3) add rolling history features — window shuffle; (4) add the next-hour label; (5) pack 86 numbers per row into a vector; (6) write one folder per city — shuffle by city. Rows go 146.3 M → 128.7 M → 93.2 M in 73.5 minutes."),
  H3("Partitioning and caching choices (be ready to explain)"),
  T(["Choice", "Why"], [
    ["128 MB HDFS blocks → 232 input tasks", "Parallel reading"],
    ["partitionBy(city) → 241 folders", "A query for one city reads one folder. Partitioning by year and month made 5,237 tiny files, so we rejected it (the small-files problem: HDFS wastes a block and time on each tiny file)"],
    ["Shuffle partitions 16 to 400, tuned per job", "Too few = huge tasks and out-of-memory; too many = overhead"],
    ["cache() on the cleaning table, training data and stream predictions", "Each is used several times; unpersist() afterwards"],
    ["Broadcast the median tables", "Two shuffle joins become map-side joins"],
    ["Checkpoint directory for GBT", "Cuts the long chain of steps; an earlier run died with a StackOverflow after 3 h 50 m"],
  ], [3800, 5226]),
  H2("C4. Scala and PySpark — two languages, two jobs"),
  T(["", "Scala", "PySpark (Python)"], [
    ["What it is", "A JVM language; Spark itself is written in Scala", "Python interface to Spark"],
    ["Our use", "CleanSelect, FeatureExtraction, LiveEnrichment, AirQualityStream (1,536 lines)", "GBT training and evaluation, data fetchers, merge, validation, alert dispatch"],
    ["Why", "Native speed for cluster jobs and the latency-critical stream; the course requires it", "MLlib code is short and readable; data scripts are simpler in Python"],
  ], [1600, 3700, 3726]),
  B([bold("sbt: "), run("Scala's build tool. “sbt package” compiles our code into a jar file.")]),
  B([bold("spark-submit: "), run("the command that sends a jar or Python file to Spark/YARN to run.")]),
  B([bold("Scala 2.12.18: "), run("not our choice. It is the exact Scala version Spark 3.5.6 was built with. A newer Scala compiles but crashes at run time (NoSuchMethodError).")]),
  H2("C5. Parquet, Snappy and partitioned folders"),
  P("Parquet is a columnar file format: it stores each column together. Queries that need three columns read only those three, and similar values compress well. Snappy is a fast compression codec. Our CSV of 27.5 GB became 10.0 GB of Parquet (2.75 times smaller), and it keeps the column types."),
  ...box("why", "WHY WE USED IT", "CSV is simple but slow and big. Parquet is the standard format for Spark and Hive: smaller, faster and typed."),
  H2("C6. Hive — SQL on top of the lake"),
  P("Hive lets you run SQL on files in HDFS. Our tables are external: Hive only stores the description (metadata); the data stays as Parquet in HDFS. We defined three tables (unified_airquality, clean_airquality, stream_alerts) and three views, exposed through HiveServer2 so tools can connect."),
  ...box("why", "WHY WE USED IT", "It gives SQL over 154 million rows at zero extra storage, and dropping an external table never deletes the data. The dashboard's numbers (alerts by city, the Delhi seasonal curve) come from Hive queries."),
  H2("C7. Docker and Docker Compose"),
  P("Docker runs software in isolated containers. Docker Compose starts many containers together from one file. Our cluster is 11 containers: 1 NameNode, 4 DataNodes, 1 ResourceManager, 4 NodeManagers and 1 Spark client, all on one laptop."),
  ...box("why", "WHY WE USED IT", "We have one machine, not a data centre. Containers let one laptop act like a cluster, and anyone can recreate it with one command."),
  ...box("warn", "BE CAREFUL", "Our cluster is real Hadoop and Spark software, but all nodes share one laptop. Say “a four-node cluster simulated in containers on one host”. Do not claim it is four physical servers."),
  H2("C8. Spark Structured Streaming — live scoring"),
  P("Structured Streaming treats a stream of new data as a table that keeps growing and processes it in small batches (micro-batches)."),
  T(["Term", "Meaning in our project"], [
    ["Micro-batch", "Process the data that arrived since the last batch, then wait for the next"],
    ["Trigger", "How often to run a batch: every 10 seconds"],
    ["File source", "The stream watches an HDFS folder; each new CSV file is a new input (maxFilesPerTrigger = 1)"],
    ["foreachBatch", "Lets us run our own code on each batch: features, model, AQI, alerts"],
    ["Checkpoint", "Remembers which files are already processed so a restart does not repeat work"],
    ["History table", "A table on HDFS with each station's last 30 hours. Every batch is unioned with it, because a single batch cannot see the previous 24 hours needed for the features. It survives restarts"],
    ["Latency", "Time to process a batch: about 7 seconds after warm-up (the first batch is slower)"],
  ], [2000, 7026]),
  ...box("why", "WHY WE USED IT", "It is the course's streaming engine and uses the same DataFrame code as batch. We kept the history in an HDFS table rather than in memory so the job can restart without losing state."),
  H2("C9. Lambda architecture"),
  P("Lambda architecture has two layers over the same data: a batch layer (slow, learns from all history; ours trains the model) and a speed layer (fast, handles new data; ours scores live data). Both use the same model and the same HDFS lake. Our slide shows the batch layer on top and the speed layer below."));

// ================= PART D =================
body.push(H1("Part D — The Machine Learning"), H2("D1. What exactly do we predict?"),
  P("For every station and hour we predict the PM₂.₅ of the next hour (this is the “T+1 label”, T = now). It is a regression problem: predicting a number, not a category. The label is only defined if the next record is exactly one hour later (next time = this time + 3600 seconds). 12.3 % of rows have no genuine next hour and are dropped rather than guessed. (An earlier method used the next row, which would have given 8.69 % of labels the wrong time distance.)"),
  H2("D2. The clues we give the model (features)"),
  P("A feature is a clue. We have 86 numbers per row: 54 numeric clues plus 32 columns of one-hot encoding."),
  T(["Group", "Examples", "Why it helps"], [
    ["Now", "pm25, pm10, no2, so2, co, o3, nh3", "Current state of the air"],
    ["Recent past (lags)", "pm25_lag_1h (value an hour ago)", "Pollution changes slowly"],
    ["Rolling averages", "pm25_roll_3h, roll_6h, avg24h, std_6h", "Smooths noise; std shows volatility"],
    ["Change", "pm25_delta_1h (change in last hour), pm25_surge_ratio", "Is it rising or falling, and how fast?"],
    ["AQI features", "sub-indices, AQI rolling 6 h", "The official scale"],
    ["Weather", "temperature, humidity, wind, pressure, rain, solar", "Wind clears pollution; calm, cold air traps it"],
    ["Time", "hour_sin, hour_cos, is_rush_hour", "Daily cycle; sin/cos make 23:00 and 00:00 neighbours"],
    ["City context", "traffic_index, urbanization_index, climate (one-hot)", "Different cities behave differently"],
    ["Provenance flags", "pm25_was_imputed, etc.", "Tell the model which values are estimated"],
  ], [1700, 3500, 3826]),
  ...box("analogy", "ANALOGY", "A doctor predicting tomorrow's temperature of a patient looks at today's temperature (now), yesterday's (lag), the average of the last 3 days (rolling), and whether it is climbing (delta). Our features are exactly that, for air."),
  P("Rolling windows use the value of the timestamp, not the row position (rangeBetween). If an hour is missing, the window is simply shorter instead of silently reaching back further in time. We call this gap-safe."),
  H2("D3. Getting the features ready (the ML pipeline)"),
  T(["Stage", "What it does"], [
    ["StringIndexer", "Turns text categories (e.g. climate type, city) into numbers 0, 1, 2…"],
    ["OneHotEncoder", "Turns those numbers into a 0/1 column per category, so the model does not think “2 is bigger than 1” (this gives the 32 one-hot columns)"],
    ["VectorAssembler", "Packs all 86 numbers into the single “features” vector column that MLlib needs"],
    ["Pipeline", "Chains the above and is saved to HDFS so the streaming job applies exactly the same steps"],
  ], [2200, 6826]),
  H2("D4. The model: Gradient Boosted Trees (GBT)"),
  P("A decision tree asks yes/no questions (“is PM2.5 above 100? is wind below 3?”) and ends at a number. One small tree is weak. Boosting builds many small trees one after another; each new tree is trained to fix the mistakes the earlier trees still make. The final forecast is the sum of all trees, each scaled by a small step."),
  ...box("analogy", "ANALOGY", "Golf. The first shot gets you near the hole. The second shot is aimed at the remaining distance. The third fixes what is left. Each shot is small and corrects the previous error. 300 small corrections reach the hole very precisely."),
  T(["Setting", "Value", "Meaning and why"], [
    ["maxIter", "300", "Number of trees. Small steps need many rounds; the plan's default of 20 was far too few"],
    ["maxDepth", "6", "Each tree asks up to 6 questions in a row (up to 64 leaves). Deep enough for interactions, shallow enough not to memorise"],
    ["stepSize (learning rate)", "0.08", "How much each tree's answer is trusted; small = gradual correction"],
    ["subsamplingRate", "0.8", "Each tree sees a random 80 % of rows; makes trees different and reduces overfitting"],
    ["featureSubsetStrategy", "sqrt", "Each split considers only about 9 of the 86 features (square root); again adds variety"],
    ["maxBins", "64", "Continuous values are grouped into 64 buckets to find splits faster and with less memory"],
    ["seed", "42", "Makes the run repeatable"],
  ], [2300, 1000, 5726]),
  ...box("why", "WHY WE USED IT", "GBT captures non-linear interactions (wind together with humidity and temperature) that a straight-line model cannot, needs no feature scaling, handles mixed units and 0/1 flags, is built into Spark MLlib so training spreads over the cluster, and gives feature importance. Alternatives: linear regression (too simple), Random Forest (parallel trees; listed as future work), XGBoost (a different library), deep learning (more data and tuning needed)."),
  H2("D5. Two design choices that decided the result"),
  H3("1. Predict the change, not the level (the delta target)"),
  P("Trees give piecewise-constant answers. If asked for the level, they waste effort re-learning “it is about the same as now”. So we predict the change PM₂.₅(t+1) − PM₂.₅(t) and add the current value back. In a controlled test the level target was 5.6 % better than the baseline and the delta target 11.3 % better: about double."),
  H3("2. Split by time, never at random"),
  P("Consecutive hours are very similar (correlation about 0.81). With a random split, hour 10:00 could be in training and 11:00 in the test set, so the model has effectively seen the answer. We train on the earlier history and test on the most recent window (2022-07-01 to 2023-03-31), which is what a live system really faces: a future it has not seen."),
  H3("3. The persistence baseline and the gate"),
  P("The simplest forecast is “next hour = this hour”. It is surprisingly good because pollution changes slowly (R² 0.8587). Our model must beat it. Every run prints the baseline on the same test rows and prints *** FAIL *** if the model does not win, so we can never report a model without that comparison."),
  H2("D6. The metrics, explained with our numbers"),
  T(["Metric", "Meaning", "Baseline", "Our GBT"], [
    ["R² (R-squared)", "Share of the variation in next-hour PM2.5 that the model explains. 1.0 = perfect, 0 = no better than the average", "0.8587", "0.8910"],
    ["RMSE", "Typical size of the error in µg/m³; punishes big misses more", "24.831", "21.806"],
    ["MAE", "Average absolute error in µg/m³; easier to read", "9.937", "8.926"],
  ], [1600, 4300, 1500, 1626]),
  P("So our typical error fell from 24.8 to 21.8 µg/m³, which is 12.18 % less. All of these are on the 2,074,569 real test rows. On all 18,671,121 test rows (including synthetic) the numbers are R² 0.8884 vs 0.8563."),
  ...box("warn", "BE CAREFUL", "“Accuracy” is not the right word for a regression model. Say “R² of 0.891” or “12 % lower error than the baseline”. And always say “on real rows”."),
  H2("D7. What we trained on, and how we tuned"),
  B("Trained on a seeded 10,000,552-row sample of the 74.5 M training rows (the laptop RAM limit); tested on all 18,671,121 test rows (not sampled). Training took 5 h 50 m."),
  B("Tuning was done by experiments, not a blind grid search: trees 20 → 120 → 300, and level versus delta target. A pilot on 19 cities with 120 trees gave a 5.67 % error reduction; the full model on 241 cities with 300 trees gave 12.18 %."),
  B("Feature importance: pm25 (current level), pm25_delta_1h (rising or falling) and pm25_surge_ratio matter most — sensible. pm25_was_imputed ranks 6th of 86."),
  ...box("warn", "BE CAREFUL", "Do not say we did hyper-parameter grid search. Say we tuned by controlled experiments, and that training used a sample because of memory."));

// ================= PART E =================
body.push(H1("Part E — Live Data, Alerts and the Website"), H2("E1. Live enrichment"),
  P("The raw live CAMS JSON has only 28 of the model's 54 numeric clues. The LiveEnrichment job (Scala, on YARN) builds the rest: weather from Open-Meteo, derived values (ventilation, stagnation, …), city traffic and urbanisation, and provenance flags. Two unit conversions were measured, not assumed: CO from µg/m³ to mg/m³ (divide by 1000; unconverted CO would be about 566 vs 0.95), and pressure from hPa to mmHg (multiply by 0.750062). The October run joined 82,800 rows (230 cities × 360 hours) with no nulls in the key columns."),
  H2("E2. The alert engine"),
  B("The forecast PM₂.₅ → AQI by the official breakpoints → category and dominant pollutant."),
  B("If the forecast AQI is above 150, a row is written to the alerts table with a severity (Moderate, Poor, Very Poor, Severe) and the message."),
  B("The alert message includes the CPCB health advice for that category and what to do."),
  H2("E3. Sending the alerts without spamming (de-duplication)"),
  P("If a city stays polluted for 10 hours we must not send 10 messages. The dispatcher (send_alerts.py) looks at the next six hours for each city and messages a city only if:"),
  B("it was not under warning before (new warning), or"), B("the severity got worse (Poor → Severe), or"), B("six hours passed and it is still under warning (a reminder)."),
  P("When a city leaves warning, its state is cleared, so a later episode alerts again. We replayed the real October forecast: at 20:00 two cities were messaged; at 21:00 those two were suppressed while two others were messaged; the next morning no city was under warning."),
  H2("E4. The hourly loop"),
  P("run_hourly_cycle.py has two speeds. Scoring (fetch, enrich, stream, rebuild the website) every 6 hours, because CAMS refreshes only a few times a day. Dispatch every hour from the already-scored forecast: as the clock moves, a new forecast hour becomes “next”, so an alert can fire without refetching. Only forecast hours newer than the last scored hour are given to the stream (a watermark), so nothing is scored twice."),
  H2("E5. Telegram, e-mail, SMS — what is real"),
  ...box("warn", "BE CAREFUL", "The Telegram and e-mail delivery code is built and tested as a dry run (it builds the messages and logs them) but we did not send a live message because no bot token was configured. SMS needs a paid gateway. Say exactly that. The website's “Alert me” button and WhatsApp share button work without any account."),
  H2("E6. The website"),
  P("A Hive export job writes one JSON file; a build script embeds it in a single HTML page. The page opens without a server or internet. Each card shows the warning message residents would receive, with search, a severity filter, an India map, a warnings-per-hour chart and a cause breakdown. It is also served by GitHub Pages from docs/index.html."),
  ...box("say", "SAY IT SIMPLY", "“The website shows the same warning a resident would receive. It is a snapshot of the 1–15 October run, because the pipeline output is exported to a static page.”"),
  H2("E7. The October 2026 result"),
  P("82,800 live rows were scored in one batch (58 s, cold start) and produced 27,543 warnings across 221 of 230 cities. 32 cities were forecast Severe (AQI above 400). The worst were Hisar, Bhiwani, Fatehabad, Kaithal, Karnal and Patiala in Haryana and Punjab (AQI 500, dust). The causes were 44 % ozone and 36 % coarse dust, which need different advice: avoid midday exercise for ozone, wear a mask for dust."));

// ================= PART F =================
body.push(H1("Part F — Quality, Problems and Honesty"), H2("F1. The eleven defects and what each taught us"),
  T(["Defect", "Lesson"], [
    ["Flags had 24,725 different values instead of 0/1", "Never assume a flag column is clean"],
    ["Next-row label was the wrong hour 8.69 % of the time", "Define the label by exact time, not row position"],
    ["Humidity 104.999 %", "Clamp to physical limits"],
    ["Only 43 % of rows had all seven pollutants", "Impute, and flag every fill"],
    ["Substring join double-counted Mumbai and Noida (44,544 rows instead of 44,160)", "Reconcile row counts; use exact-name joins"],
    ["Streaming used a timestamp column before it existed", "Run the code end to end"],
    ["VectorAssembler silently dropped every live row (16,560 in, 0 out, no error)", "A silent wrong answer is worse than a crash; check output counts"],
    ["Path built as hdfs:////host (4 slashes)", "Print resolved paths"],
    ["HDFS write died: no spare DataNode", "Memory and replication settings matter on a small cluster"],
    ["numpy missing in the Spark image", "Check dependencies in the container"],
    ["Hive table had a column that does not exist: NULL timestamps with correct counts", "Counts can look right while data is wrong"],
  ], [5200, 3826]),
  ...box("say", "SAY IT SIMPLY", "“We found 11 defects by actually running the pipeline. Two of them produced wrong answers with no error message, so we reconcile every output count against a number we know independently.”"),
  H2("F2. Limitations — say them before you are asked"),
  B("88.9 % of the structured rows are synthetic; accuracy is quoted on real rows only."),
  B("The model trained on a 10 M-row sample of 74.5 M because of single-laptop memory; the evaluation is not sampled."),
  B("CAMS is a model product, not a sensor feed, and updates only a few times a day. SO₂ agreement with CPCB is poor (0.083). Real-time CPCB data needs an API key."),
  B("The cluster is four containers on one laptop. The October result is a snapshot scored as one batch with a cold start. 230 of 241 cities have live coverage."),
  B("Telegram and e-mail were not sent live; SMS needs a paid gateway."),
  H2("F3. Future work"),
  B("Schedule the hourly loop on an always-on server and connect an SMS gateway."), B("Compare with Random Forest and XGBoost."), B("Add neighbouring-station features (a graph of stations, GraphX)."),
  B("Use a multi-machine cluster to train on all 74.5 M rows and a real-time CPCB feed."));

// ================= PART G =================
body.push(H1("Part G — Presentation Help"), H2("G1. Slide-by-slide script (15 minutes)"),
  P("The final deck has the ten slides your faculty asked for, then an evidence appendix. Aim for about 1.5 minutes per slide."),
  T(["Slide", "What to say (in your own words)"], [
    ["1. Title", "Introduce the team and the one-line goal: forecast each city's PM2.5 one hour ahead and warn people before it arrives."],
    ["2. Problem, objectives, why big data", "Three gaps: scale, latency, automation. Then the numbers: 154.6 M rows and 33 GB vs a 15.7 GB laptop; a 10-second requirement; two data shapes; synthetic data to validate."],
    ["3. Dataset and five V's", "Three layers with three jobs: CPCB trains, CAMS history validates, live data alerts. Walk through the five V cards. Say 88.9 % synthetic and that results are on real rows."],
    ["4. Architecture", "Left to right: sources → Python fetchers → HDFS → Spark on YARN (batch layer on top, speed layer below) → outputs. Point at the red arrow: the trained model is loaded from HDFS by the stream."],
    ["5. Spark workflow", "Six steps of the feature job. Orange steps move data between machines (shuffle). Then partitioning (128 MB blocks, 241 city folders) and caching (reused tables)."],
    ["6. Scala implementation", "Four Scala jobs, 1,536 lines; sbt builds a jar; spark-submit runs it. Show the three snippets: gap-safe window, broadcast imputation, streaming foreachBatch."],
    ["7. ML pipeline", "StringIndexer, OneHot, VectorAssembler → 86 features → chronological split → GBT 300 trees on the delta target. Explain the tuning experiments honestly."],
    ["8. Results", "R² 0.8910 vs 0.8587, error 12.18 % lower, on real rows. Then the October business result. Switch to the website demo here."],
    ["9. Challenges and conclusion", "Two real challenges and the fix; limitations before questions; conclusion; future work."],
    ["10. References and GitHub", "References, then the GitHub link; the report and slides are uploaded."],
  ], [2300, 6726]),
  H2("G2. A 5-minute demo plan"),
  N("Show the architecture slide, then say “the cluster is running”.", "d"), N("Open the HDFS page (localhost:9870): 4 live DataNodes. Open YARN (localhost:8088): 4 NodeManagers.", "d"),
  N("Run demo\\start_demo.ps1: a Spark job on YARN counts 154,583,979 rows read from HDFS; show the application in the YARN page.", "d"), N("Open dashboard/AirWatch_India.html: 221 cities under warning; search a city; click the Alert me button.", "d"),
  N("Show the alert message in docs/run_logs/hourly_dedupe_demo.log if asked about the de-duplication.", "d"),
  ...box("warn", "BE CAREFUL", "Start Docker and the cluster well before the demo (it takes a few minutes). If the cluster does not start, show the screenshots in the appendix and the website, which works without Docker."),
  H2("G3. Likely questions and answers"));
const QA = [
  ["Why do you need big data tools for this?", "154.6 M rows and 33 GB do not fit in the 15.7 GB memory of one machine, the live data needs scoring every 10 seconds, and the data comes in two shapes (CSV and JSON)."],
  ["What is HDFS and why 4 DataNodes?", "A distributed file system: files are cut into 128 MB blocks with 3 copies. With 3 nodes and replication 3 every node holds every block so nothing distributes; 4 is the smallest real cluster."],
  ["What is the NameNode?", "The catalogue: it knows which blocks belong to which file and where they are. It stores no data."],
  ["What is YARN?", "The resource manager. The ResourceManager decides who gets memory and CPU; NodeManagers run the containers on each machine."],
  ["What is the difference between RDD and DataFrame?", "An RDD is the low-level distributed collection; a DataFrame is a table with named columns that Spark can optimise. We use DataFrames; Spark uses RDDs internally."],
  ["What is a DAG?", "The chain of steps Spark builds before running. It is cut into stages wherever data must move between machines (a shuffle)."],
  ["What is a shuffle and why is it expensive?", "Moving data between machines for operations like groupBy, join and window. It needs network and disk, so we reduce it (broadcast joins, fewer wide steps)."],
  ["How did you partition the data?", "HDFS blocks of 128 MB give 232 input tasks; on disk we use partitionBy(city) = 241 folders; shuffle partitions 16 to 400 depending on the job."],
  ["What did you cache and why?", "The cleaning table, the training and test sets, and the stream predictions, because each is used several times. We unpersist afterwards."],
  ["Why Scala and not only Python?", "Spark is written in Scala; it is the native, faster option for cluster jobs and the streaming job, and the course requires it. We use PySpark where the MLlib code is simpler."],
  ["Why Scala 2.12?", "It is the version Spark 3.5.6 is built with. A newer Scala compiles but fails at run time."],
  ["What is Parquet?", "A compressed columnar file format. It made 27.5 GB of CSV into 10.0 GB and keeps types."],
  ["What is Hive and what is an external table?", "SQL over files in HDFS. An external table stores only metadata; the data stays in HDFS and dropping the table does not delete it."],
  ["Structured vs semi-structured data?", "Structured is a fixed flat table (CPCB CSV). Semi-structured is nested self-describing JSON (CAMS). Spark reads both and we union them on one schema."],
  ["How do you know the synthetic data is realistic?", "Five paired tests against the real parent (persistence R², autocorrelation, quantiles, missingness, cross-correlation) with a blocking FAIL, plus an independent CPCB-vs-CAMS check. And we report accuracy on real rows only."],
  ["Why is the model accuracy only 0.89?", "R² of 0.89 means it explains 89 % of the variation. More importantly the “do nothing” baseline already scores 0.8587; we cut the error by 12.18 % on top of that, which is what makes the warning an hour earlier useful."],
  ["Why GBT?", "It captures non-linear interactions, needs no scaling, handles mixed units and flags, is native to MLlib and gives feature importance."],
  ["Explain how GBT works.", "Many small trees built one after another; each tree is trained to correct the remaining errors of the previous ones; the prediction is the sum of all trees scaled by a small step (0.08)."],
  ["What are the main hyperparameters?", "300 trees, depth 6, step size 0.08, subsampling 0.8, sqrt features per split, 64 bins."],
  ["Why predict the delta?", "Trees are piecewise-constant, so predicting the change instead of the level removes the effort of re-learning the current value: 11.3 % vs 5.6 % improvement in a controlled test."],
  ["Why not a random train/test split?", "Consecutive hours are about 0.81 correlated, so a random split lets the model see the answer. We train on the past and test on the most recent period."],
  ["What is the persistence baseline?", "Predict that next hour equals this hour. Our run fails automatically if the model does not beat it."],
  ["What do R², RMSE and MAE mean?", "R² is the share of variation explained; RMSE is the typical error size (punishes big misses); MAE is the average absolute error. All in µg/m³ except R²."],
  ["Which features are most important?", "Current PM2.5, the last-hour change and the surge ratio. The imputed-value flag is 6th of 86, showing the model learned to trust filled values less."],
  ["How does streaming work here?", "Structured Streaming watches an HDFS folder, takes each new file as a micro-batch every 10 seconds, unions it with the last 30 hours of history, builds features, applies the GBT, converts to AQI and writes alerts."],
  ["Why keep a history table?", "One micro-batch cannot see a station's previous 24 hours, which the features need. The table is stored on HDFS so the job can restart without losing state."],
  ["What is a checkpoint?", "It records which input files were processed so a restarted stream does not repeat them."],
  ["How is the AQI computed?", "Each pollutant's average is mapped to a 0–500 score with the CPCB breakpoints; the AQI is the highest score and that pollutant is the dominant one."],
  ["What is your alert rule?", "A warning when the forecast AQI is above 150, one hour ahead, with CPCB advice for the category."],
  ["How do you avoid sending too many alerts?", "De-duplication: message only for a new warning, a worse severity, or after a 6-hour cooldown; clear the state when the city recovers."],
  ["Did you really send SMS or Telegram messages?", "The code is built and tested as a dry run; we did not send live messages because no bot token was set, and SMS needs a paid gateway. The website's Alert me notification and WhatsApp share work now."],
  ["Is it real time?", "The streaming job scores in 10-second micro-batches with about 7 seconds latency. The data source (CAMS) refreshes a few times a day, so the end-to-end freshness is limited by the source."],
  ["What was the hardest problem?", "Silent errors: VectorAssembler dropped every live row with no error (16,560 in, 0 out), and Hive returned right counts with NULL timestamps. We fixed it by reconciling counts against known numbers."],
  ["What would you do next?", "Run the hourly loop on an always-on server with an SMS gateway, compare Random Forest and XGBoost, add neighbour-station features and train on all 74.5 M rows on a bigger cluster."],
];
QA.forEach(([q, a], i) => { body.push(new Paragraph({ spacing: { before: 100, after: 30 }, keepNext: true, children: [run(`Q${i + 1}. ${q}`, { bold: true, color: BLUE })] }), new Paragraph({ spacing: { after: 60, line: 270 }, children: [run(a)] })); });
body.push(H2("G4. Numbers cheat-sheet"),
  T(["Topic", "Number"], [
    ["Dataset", "154,583,979 rows · 33 GB · 241 cities · 4,077 stations · structured 146,276,379 (27.5 GB) · CAMS history 8,263,440 · 88.9 % synthetic (130,023,448) · real 16,252,931"],
    ["Cluster", "1 NameNode + 4 DataNodes · 128 MB blocks · 3× replication · 232 blocks · 696 replicas · 1 ResourceManager + 4 NodeManagers (3 GB, 2 vcores) · 11 containers"],
    ["Cleaning", "146,276,379 rows · 10 steps · 28 min · 27.5 GB → 10.0 GB (2.75×) · 241 city partitions · 32 → 44 columns"],
    ["Features", "146.3 M → 128.7 M → 93.2 M rows · 73.5 min · 19.7 GB · 54 numeric + 32 one-hot = 86 features"],
    ["Model", "GBT 300 trees, depth 6, step 0.08 · trained on 10,000,552 rows · tested on 18,671,121 · 5 h 50 m"],
    ["Accuracy (real rows)", "R² 0.8910 vs 0.8587 · RMSE 21.806 vs 24.831 (− 12.18 %) · MAE 8.926 vs 9.937 · n = 2,074,569"],
    ["Accuracy (all rows)", "R² 0.8884 vs 0.8563 · RMSE 22.429 vs 25.443 (− 11.85 %)"],
    ["Experiments", "Pilot 19 cities 120 trees: 5.67 % · level target 5.6 % · delta target 11.3 % · full 12.18 %"],
    ["Streaming", "10 s trigger · ≈ 7 s latency · 30 h history · October batch 82,800 rows in 57.8 s"],
    ["October 2026", "82,800 rows (230 cities × 360 h) · 27,543 warnings · 221 cities · 32 Severe · ozone 44 % · dust 36 %"],
    ["Validation", "5 paired tests · CPCB vs CAMS 1,152,707 city-hours · PM2.5 r = 0.565 · SO₂ r = 0.083 · 11 defects"],
    ["Delhi seasonal", "Aug 38.8 → Nov 213.6 µg/m³ (5.5×)"],
    ["Code", "1,536 lines of Scala in 4 jobs · Scala 2.12.18 · Spark 3.5.6 · Hadoop 3.3.6"],
  ], [2200, 6826], { boldRows: [5] }),
  H2("G5. Things not to say"),
  T(["Do not say", "Say instead"], [
    ["“The dataset is real”", "“Mostly synthetic expansion of real data, validated by five tests; accuracy is on real rows.”"],
    ["“The accuracy is 89 %”", "“R² is 0.891 — 12 % lower error than the baseline.”"],
    ["“We tuned with grid search”", "“We tuned by controlled experiments.”"],
    ["“We have a four-server cluster”", "“A four-node cluster in Docker containers on one host.”"],
    ["“We sent SMS to people”", "“The Telegram and e-mail delivery is built and dry-run tested; SMS needs a paid gateway.”"],
    ["“It is fully real time”", "“The stream scores every 10 seconds; the CAMS source refreshes a few times a day.”"],
    ["“The website updates itself”", "“The page is a snapshot of the 1–15 October run.”"],
  ], [3800, 5226]));

// ================= PART H =================
body.push(H1("Part H — Glossary A to Z"),
  P("Every term used in the project, in plain words, with where it appears."));
const G = [
  ["Action (Spark)", "A step that triggers real work, e.g. count or write", "Spark workflow"],
  ["AQI", "Air Quality Index: 0–500 score from the pollutant concentrations", "Alert rule"],
  ["Autocorrelation", "How much a value depends on its own past values", "Veracity test 2"],
  ["Batch layer", "Slow layer that learns from all history", "Lambda architecture"],
  ["Block (HDFS)", "A 128 MB chunk of a file", "HDFS"],
  ["Boosting", "Building models one after another, each fixing the previous errors", "GBT"],
  ["Broadcast join", "Send a small table to every machine to avoid a shuffle", "CleanSelect"],
  ["Cache / persist", "Keep a table in memory for reuse", "Spark workflow"],
  ["CAMS", "Copernicus Atmosphere Monitoring Service (satellite + model data)", "Semi-structured layer"],
  ["Catalyst", "Spark's optimiser for DataFrame queries", "Spark"],
  ["Checkpoint", "Saved progress so a restart does not repeat work", "Streaming, GBT"],
  ["Chronological split", "Train on the past, test on the newest period", "Training"],
  ["Cluster", "A group of machines working together", "Whole project"],
  ["Container", "An isolated package running one piece of software (Docker) or one task (YARN)", "Docker, YARN"],
  ["CPCB", "Central Pollution Control Board, India", "Structured data"],
  ["DAG", "Directed acyclic graph: Spark's chain of steps", "Spark workflow"],
  ["DataFrame", "A distributed table with named columns", "All Spark code"],
  ["DataNode", "HDFS machine that stores blocks", "HDFS"],
  ["De-duplication (alerts)", "Not sending the same warning repeatedly", "Dispatcher"],
  ["Delta target", "Predicting the change instead of the level", "Model"],
  ["Docker Compose", "Starts several containers from one file", "Cluster"],
  ["Dominant pollutant", "The pollutant giving the highest AQI sub-index", "Alert message"],
  ["Driver / executor", "Spark's coordinator / its workers", "Spark"],
  ["Enrichment", "Adding missing columns (weather, city context) to the live data", "LiveEnrichment"],
  ["External table", "A Hive table that points to data without owning it", "Hive"],
  ["Feature", "A clue given to the model", "Model"],
  ["Feature importance", "How much each feature helped the model", "Results"],
  ["foreachBatch", "Runs your code on every streaming micro-batch", "Streaming"],
  ["fsck", "HDFS health check", "Evidence"],
  ["GBT", "Gradient Boosted Trees", "Model"],
  ["HDFS", "Hadoop Distributed File System", "Storage"],
  ["Hive / HiveServer2", "SQL on HDFS files / the service that accepts connections", "Serving"],
  ["Hyperparameter", "A setting chosen before training (trees, depth…)", "Model"],
  ["Imputation", "Filling missing values", "Cleaning"],
  ["Lag feature", "The value some hours ago", "Features"],
  ["Lambda architecture", "A batch layer plus a speed layer over the same data", "Architecture"],
  ["Latency", "Time taken to process a batch", "Streaming"],
  ["Lazy evaluation", "Spark plans first and runs only when an action is called", "Spark"],
  ["MAE", "Mean absolute error", "Metrics"],
  ["Micro-batch", "A small batch processed every few seconds", "Streaming"],
  ["MLlib", "Spark's machine-learning library", "Model"],
  ["NameNode", "HDFS catalogue machine", "HDFS"],
  ["NodeManager / ResourceManager", "YARN's per-machine worker / central boss", "YARN"],
  ["One-hot encoding", "One 0/1 column per category", "Pipeline"],
  ["Open-Meteo", "Free API for CAMS air quality and weather", "Live data"],
  ["Parquet", "Compressed columnar file format", "Storage"],
  ["Partition", "One slice of data processed by one task; also a folder per city on disk", "Spark, HDFS"],
  ["Persistence baseline", "Predict next hour = this hour", "Evaluation"],
  ["PM2.5 / PM10", "Fine / coarse particles", "Pollutants"],
  ["Provenance flag", "A column recording that a value was estimated", "Cleaning"],
  ["PySpark", "Python interface to Spark", "Training"],
  ["R²", "Share of variation explained", "Metrics"],
  ["RDD", "Spark's low-level distributed collection", "Spark"],
  ["Replication factor", "Number of copies of each block", "HDFS"],
  ["RMSE", "Root mean squared error", "Metrics"],
  ["Rolling average", "Average over the last N hours", "Features"],
  ["Scala / sbt", "JVM language / its build tool", "Scala jobs"],
  ["Schema-on-read", "The structure is discovered when the file is read", "JSON"],
  ["Semi-structured data", "Nested, self-describing data like JSON", "CAMS"],
  ["Shuffle", "Moving data between machines", "Spark"],
  ["Snappy", "Fast compression codec", "Parquet"],
  ["Spark", "Distributed processing engine", "Everything"],
  ["spark-submit", "Command to run a Spark job", "Running jobs"],
  ["Speed layer", "Fast layer that handles new data", "Streaming"],
  ["Stage / task", "A group of steps between shuffles / one unit of work on a partition", "Spark"],
  ["Structured Streaming", "Spark's engine for continuous data", "Speed layer"],
  ["Synthetic data", "Computer-generated data that mimics real data", "Dataset"],
  ["T+1 label", "The value one hour after now; what we predict", "Model"],
  ["Trigger", "How often a streaming batch runs", "Streaming"],
  ["Veracity", "How trustworthy the data is", "Five V's"],
  ["VectorAssembler", "Packs columns into one features vector", "Pipeline"],
  ["Window function", "Calculation over an ordered group of rows", "Features"],
  ["YARN", "Hadoop's resource manager", "Cluster"],
];
body.push(...T(["Term", "Simple meaning", "Where in the project"], G, [2400, 4900, 1726], { size: 17 }));

// ================= appendix =================
body.push(H1("Appendix — Where Everything Is"),
  T(["What", "Where"], [
    ["Full project report", "docs/PROJECT_REPORT.pdf / .docx"], ["Final presentation", "presentation/Final_Project_Presentation.pptx"],
    ["Scala jobs", "scala/streaming/src/main/scala/ (CleanSelect, FeatureExtraction, LiveEnrichment, AirQualityStream)"],
    ["GBT training", "scripts/03_train_gbt.py"], ["Alert dispatch and hourly loop", "scripts/send_alerts.py, scripts/run_hourly_cycle.py, docs/ALERTING.md"],
    ["Hive tables", "hive/create_tables.sql, hive/demo_queries.sql"], ["Cluster", "hadoop/docker-compose*.yml"],
    ["Website", "dashboard/AirWatch_India.html (and docs/index.html for GitHub Pages)"], ["Evidence logs", "docs/run_logs/"],
    ["Demo", "demo/start_demo.ps1"], ["Commands in order", "RUNBOOK.md"], ["GitHub", GH],
  ], [2800, 6226]));

const doc = new Document({
  creator: "Group A14", title: "Project Study Guide - Air Quality Big Data Platform",
  styles: {
    default: { document: { run: { font: "Calibri", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 36, bold: true, font: "Calibri", color: BLUE }, paragraph: { spacing: { before: 240, after: 200 }, outlineLevel: 0, keepNext: true } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 28, bold: true, font: "Calibri", color: "0D3B5E" }, paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1, keepNext: true } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 24, bold: true, font: "Calibri" }, paragraph: { spacing: { before: 160, after: 80 }, outlineLevel: 2, keepNext: true } },
    ],
  },
  numbering: { config: [
    { reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] },
    ...["num", "j", "c", "d"].map((r) => ({ reference: r, levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] })),
  ] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1300, right: 1440, bottom: 1300, left: 1440 } } },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: LINE, space: 4 } },
      children: [new TextRun({ text: "Project Study Guide · 23AID302 Big Data Analytics · Group A14", font: "Calibri", size: 17, color: GREY })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: ["Page ", PageNumber.CURRENT, " of ", PageNumber.TOTAL_PAGES], font: "Calibri", size: 18, color: GREY })] })] }) },
    children: body.flat(Infinity),
  }],
});
Packer.toBuffer(doc).then((b) => { fs.writeFileSync(OUT, b); console.log("wrote", OUT, (b.length / 1024).toFixed(0) + " KB"); });
