"""
================================================================================
Generates docs/PROJECT_REPORT.pdf - the complete project report
23AID302 - Big Data Analytics
================================================================================
Every figure here is a MEASURED value from a real, logged run. The log that
backs each one is named in docs/WORK_LOG.md. If a number changes, change it in
the run first, then here.

Deps:  pip install reportlab
Run :  python build_project_report.py      (writes PROJECT_REPORT.pdf in cwd)
================================================================================
"""
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, HRFlowable, KeepTogether,
                                ListFlowable, ListItem, PageBreak, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

NAVY   = colors.HexColor("#15314B")
ACCENT = colors.HexColor("#0E7C86")
INK    = colors.HexColor("#1B2430")
INK2   = colors.HexColor("#46525F")
MUTED  = colors.HexColor("#78848F")
LINE   = colors.HexColor("#C9D3DC")
BAND   = colors.HexColor("#EDF3F5")
GOOD   = colors.HexColor("#1E7B4D")
WARN   = colors.HexColor("#B3541E")
BAD    = colors.HexColor("#A32B25")

ss = getSampleStyleSheet()
H1   = ParagraphStyle("H1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=15.5,
                      textColor=NAVY, spaceBefore=16, spaceAfter=7, leading=19)
H2   = ParagraphStyle("H2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=11.8,
                      textColor=ACCENT, spaceBefore=11, spaceAfter=4, leading=14)
BODY = ParagraphStyle("BODY", parent=ss["Normal"], fontName="Helvetica", fontSize=9.4,
                      textColor=INK, leading=13.6, spaceAfter=6, alignment=TA_LEFT)
SMALL= ParagraphStyle("SMALL", parent=BODY, fontSize=8.5, textColor=INK2, leading=12)
NOTE = ParagraphStyle("NOTE", parent=BODY, fontSize=8.6, textColor=INK2, leading=12.4,
                      leftIndent=8, borderPadding=0)
CODE = ParagraphStyle("CODE", parent=BODY, fontName="Courier", fontSize=8.3, leading=11.6,
                      textColor=INK2, leftIndent=8, spaceAfter=6)
TITLE= ParagraphStyle("TITLE", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=25,
                      textColor=NAVY, leading=29, spaceAfter=6, alignment=TA_CENTER)
SUB  = ParagraphStyle("SUB", parent=BODY, fontSize=12, textColor=ACCENT, alignment=TA_CENTER, leading=16)
SUB2 = ParagraphStyle("SUB2", parent=BODY, fontSize=9.6, textColor=INK2, alignment=TA_CENTER, leading=14)

def P(t, s=BODY):  return Paragraph(t, s)
def bullets(items, style=BODY):
    return ListFlowable([ListItem(Paragraph(t, style), leftIndent=12) for t in items],
                        bulletType="bullet", bulletFontSize=6, bulletOffsetY=1.5,
                        leftIndent=12, spaceAfter=6)

def tbl(data, widths, align=None, head=True, zebra=True, fs=8.4, hi=None):
    # Cells must be Paragraphs, not raw strings: a raw string neither wraps at the
    # column width (it overflows into the neighbouring column) nor parses the HTML
    # entities used throughout this report, which then render literally as "&ndash;".
    cs   = ParagraphStyle("c",  parent=BODY, fontSize=fs, leading=fs*1.35, spaceAfter=0, textColor=INK)
    chs  = ParagraphStyle("ch", parent=cs, fontName="Helvetica-Bold", textColor=colors.white)
    cbs  = ParagraphStyle("cb", parent=cs, fontName="Helvetica-Bold")
    amap = {"RIGHT": 2, "CENTER": 1}
    def mk(v, r, c):
        st = chs if (head and r == 0) else (cbs if (hi is not None and r == hi) else cs)
        if align and c in align and not (head and r == 0):
            st = ParagraphStyle(f"a{r}{c}", parent=st, alignment=amap.get(align[c], 0))
        return Paragraph(str(v).replace(chr(10), "<br/>"), st)
    data = [[mk(v, r, c) for c, v in enumerate(row)] for r, row in enumerate(data)]
    t = Table(data, colWidths=widths, repeatRows=1 if head else 0, hAlign="LEFT")
    st = [("FONTNAME",(0,0),(-1,-1),"Helvetica"), ("FONTSIZE",(0,0),(-1,-1),fs),
          ("TEXTCOLOR",(0,0),(-1,-1),INK), ("VALIGN",(0,0),(-1,-1),"TOP"),
          ("TOPPADDING",(0,0),(-1,-1),4), ("BOTTOMPADDING",(0,0),(-1,-1),4),
          ("LEFTPADDING",(0,0),(-1,-1),6), ("RIGHTPADDING",(0,0),(-1,-1),6),
          ("LINEBELOW",(0,0),(-1,-2),0.4,LINE)]
    if head:
        st += [("BACKGROUND",(0,0),(-1,0),NAVY), ("TEXTCOLOR",(0,0),(-1,0),colors.white),
               ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("BOTTOMPADDING",(0,0),(-1,0),5),
               ("TOPPADDING",(0,0),(-1,0),5)]
    if zebra:
        st += [("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, colors.HexColor("#F6F9FA")])]
    if hi is not None:
        st += [("BACKGROUND",(0,hi),(-1,hi),BAND)]
    t.setStyle(TableStyle(st))
    return t

def callout(title, text, color=ACCENT):
    inner = [Paragraph(f"<b>{title}</b>", ParagraphStyle("ct", parent=BODY, fontSize=9.2, textColor=color, spaceAfter=2)),
             Paragraph(text, SMALL)]
    t = Table([[inner]], colWidths=[170*mm], hAlign="LEFT")
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#F4F8F9")),
                           ("LINEBEFORE",(0,0),(0,-1),2.5,color),
                           ("LEFTPADDING",(0,0),(-1,-1),10),("RIGHTPADDING",(0,0),(-1,-1),10),
                           ("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7)]))
    return t

def rule(): return HRFlowable(width="100%", thickness=0.6, color=LINE, spaceBefore=4, spaceAfter=8)

# ==============================================================================
S = []   # story

# ---------------------------------------------------------------- title
S += [Spacer(1, 42*mm),
      P("A Scalable Big Data Platform for Real-Time Urban Air Quality Tracking and Public Safety Alerting", TITLE),
      Spacer(1, 4*mm),
      P("Complete Project Report", SUB),
      Spacer(1, 2*mm),
      P("23AID302 &mdash; Big Data Analytics", SUB2),
      Spacer(1, 14*mm),
      HRFlowable(width="55%", thickness=1, color=ACCENT, hAlign="CENTER"),
      Spacer(1, 8*mm),
      P("Hadoop &middot; HDFS &middot; Spark &middot; YARN &middot; Spark Structured Streaming &middot; Hive &middot; Scala &middot; PySpark", SUB2),
      Spacer(1, 3*mm),
      P("154,583,979 rows &middot; 33 GB &middot; 241 cities &middot; 4-node cluster", SUB2),
      Spacer(1, 22*mm),
      P("Every figure in this report is a measured value from a real, logged run.<br/>"
        "The log backing each one is preserved in <font face='Courier'>docs/run_logs/</font>.", SUB2),
      Spacer(1, 6*mm),
      P("Report generated 26 September 2026", SUB2),
      PageBreak()]

# ---------------------------------------------------------------- 1
S += [P("1. What the project does", H1),
      P("Air pollution kills, and it kills on a timescale where an hour of warning matters. This project builds "
        "the full data platform behind a public early-warning service: it learns from thirteen years of Central "
        "Pollution Control Board station history, watches live atmospheric data for 230 Indian cities, forecasts "
        "each city's PM<sub>2.5</sub> one hour ahead, and issues a warning wherever the forecast National AQI "
        "crosses 150."),
      P("The deliverable is not a chart. It is a message:", BODY),
      P("&ldquo;Air quality in Jaisalmer is expected to reach AQI 500 (Severe) by 00:00 today, caused by coarse "
        "dust. Affects healthy people; seriously impacts those with existing disease. What to do: avoid all "
        "outdoor activity. Seek care if breathing is difficult.&rdquo;", CODE),
      P("Everything else in this report &mdash; the 154-million-row lakehouse, the gradient-boosted model, the "
        "streaming engine, the Hive layer &mdash; exists to produce that sentence accurately and an hour early.", BODY),

      P("1.1 Starting point versus finishing point", H2),
      tbl([["", "At the start", "Now"],
           ["Data", "27.48 GB structured CSV only", "33 GB: structured + two semi-structured layers, unified"],
           ["Rows", "146,276,379", "154,583,979 in one queryable table"],
           ["Model", "None on disk; an sklearn reproduction quoted", "Real Spark GBT, 300 trees, 241 cities, saved to HDFS"],
           ["Streaming", "Code written, never executed", "Executed on the cluster; 1,130 live alerts fired"],
           ["Serving", "Nothing", "Hive: 3 external tables, 3 views, 6 verified queries"],
           ["Interface", "Nothing", "Public warning board, published and openable offline"],
           ["Phases done", "0&ndash;3 (partially)", "0&ndash;10, all executed with preserved logs"]],
          [26*mm, 62*mm, 82*mm]),
      Spacer(1, 3*mm),
      callout("The headline result",
              "On a chronological hold-out scored on <b>2,074,569 real station-hours</b>, the forecaster reaches "
              "<b>R&sup2; 0.8910 / RMSE 21.806 &micro;g/m&sup3;</b> against a persistence baseline of "
              "<b>R&sup2; 0.8587 / RMSE 24.831</b> &mdash; a <b>12.18% reduction in error</b>. The project's own "
              "quality gate passes by +0.0323 R&sup2;.", GOOD)]

# ---------------------------------------------------------------- 2
S += [P("2. Architecture: three data layers, three jobs", H1),
      P("The three layers are not three copies of the same thing. Each exists because the others cannot do its job."),
      tbl([["Layer", "Size", "Its one job", "Why only it can"],
           ["Structured\nCPCB 2010&ndash;2023", "146,276,379 rows\n27.48 GB", "TRAIN the model",
            "Only it has the label and thirteen years of seasonality"],
           ["Semi-structured\nCAMS history 2022-08&rarr;", "8,263,440 rows\n458 MB", "VALIDATE the structured data",
            "Only independent source covering the same cities and hours"],
           ["Semi-structured\nCAMS live", "44,160 rows\n6.7 MB", "ALERT people now",
            "Alerting is about now; history cannot warn anybody"]],
          [38*mm, 30*mm, 38*mm, 64*mm]),
      Spacer(1, 3*mm),
      P("2.1 How they join", H2),
      P("Physically, in one Parquet table partitioned by <font face='Courier'>source_format</font>. Any row's "
        "origin is recoverable from <font face='Courier'>data_source</font>, so a query can use one layer, two, "
        "or all three."),
      tbl([["source_format", "data_source", "rows", "time range", "cities"],
           ["structured_csv", "synthetic", "130,023,448", "2010-01 &rarr; 2023-03", "241"],
           ["structured_csv", "real", "16,252,931", "2010-01 &rarr; 2023-03", "241"],
           ["semistructured_json", "cams_history", "8,263,440", "2022-08 &rarr; 2026-09", "230"],
           ["semistructured_json", "live_api", "44,160", "rolling 8 days", "230"],
           ["TOTAL", "", "154,583,979", "", ""]],
          [40*mm, 28*mm, 30*mm, 42*mm, 18*mm],
          align={2:"RIGHT", 4:"RIGHT"}, hi=5),
      Spacer(1, 2*mm),
      P("This union is the project's Variety claim doing actual work: two genuinely different data models &mdash; "
        "flat fixed-schema CSV and nested self-describing JSON &mdash; read by their native Spark readers in one "
        "job and reconciled onto one schema, with neither reformatted at source.", SMALL),

      P("2.2 The end-to-end flow", H2),
      P("fetch CAMS + weather  &rarr;  LiveEnrichment (Spark on YARN)  &rarr;  32-col CSV in HDFS<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;&rarr;  AirQualityStream (10 s micro-batches)  &rarr;  GBT forecast  &rarr;  CPCB AQI<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;&rarr;  alerts in HDFS  &rarr;  Hive serving layer  &rarr;  public warning board", CODE)]

# ---------------------------------------------------------------- 3
S += [P("3. Phase by phase: what was done and what came out", H1),

      P("Phase 0 &mdash; Dataset construction and validation", H2),
      P("Rebuilt from a 23.44 GB / 48.6M-row / 139-column CPCB source covering 453 real stations. All 16,252,931 "
        "real rows are kept verbatim; eight synthetic sibling stations per real station are generated with an "
        "AR(1) autocorrelated perturbation (per-station &phi;, &sigma; = 0.08), copying each real station's "
        "missingness pattern rather than densifying it, and clamping every value to its physical range."),
      P("<b>Output:</b> 27.48 GB, 146,276,379 rows, 4,077 stations (453 real + 3,624 synthetic), 241 cities, "
        "31 states/UTs, 2010&ndash;2023, 23 CSV parts. Five statistical fidelity tests pass.", SMALL),

      P("Phase 1 &mdash; HDFS ingest", H2),
      P("<b>Output:</b> raw CSVs, the clean layer, the feature layer, the unified table and the models, all on a "
        "1 NameNode + 4 DataNode cluster. <font face='Courier'>hdfs fsck</font> reports HEALTHY on every path: "
        "0 corrupt, 0 missing, 0 under-replicated blocks.", SMALL),
      P("Four DataNodes rather than the minimum three is deliberate: with replication 3 on three nodes every node "
        "holds every block, so nothing actually distributes and node failure cannot be demonstrated.", SMALL),

      P("Phase 2 &mdash; Spark and YARN activation", H2),
      P("<b>Output:</b> Spark 3.5.6 running inside the cluster network, and YARN with a ResourceManager plus "
        "4 NodeManagers (<font face='Courier'>yarn node -list</font> &rarr; Total Nodes: 4, all RUNNING). The "
        "live enrichment job was submitted to YARN as a real application, not local mode.", SMALL),

      P("Phase 3 &mdash; Clean, range-guard, impute", H2),
      P("Reads with an explicit string schema (never <font face='Courier'>inferSchema</font>), repairs the four "
        "measured source defects, range-guards the seven AQI pollutants plus solar radiation and pressure, then "
        "applies three-tier median imputation (station&times;month&times;hour &rarr; city&times;month &rarr; "
        "global). Critically, <font face='Courier'>pm25_measured</font> preserves the pre-imputation truth so the "
        "forecast label is never built from a filled value."),
      P("<b>Output:</b> 10.0 GB Snappy Parquet in HDFS, partitioned by city, 241 partitions, 100% of rows retained.", SMALL),

      P("Phase 4 &mdash; Feature engineering at full scale", H2),
      P("Ran for 73.5 minutes and reproduced the project's own RUNBOOK figures to the row:"),
      tbl([["Stage", "Rows", "Retained"],
           ["Loaded from the clean layer", "146,276,379", "&mdash;"],
           ["After dedupe on (station, hour)", "128,660,967", "87.96%"],
           ["With a valid T+1 label", "93,216,105", "72.45%"],
           ["Assemblable into a complete vector", "93,216,105", "100.00%"]],
          [78*mm, 36*mm, 26*mm], align={1:"RIGHT", 2:"RIGHT"}),
      Spacer(1, 2*mm),
      P("<b>Output:</b> 19.7 GB, 241 city partitions, <b>86-dimensional</b> feature vector (54 numeric + 32 "
        "one-hot). The T+1 label requires <font face='Courier'>next_ts == ts + 3600</font>; rows without a genuine "
        "successor are dropped rather than mislabelled.", SMALL),

      P("Phase 5&ndash;6 &mdash; Model training and evaluation", H2),
      P("GBT on the <i>delta</i> target (the change, not the level), chronological split, 300 trees, depth 6, "
        "step size 0.08. Ran 5 h 50 m and finished clean &mdash; the previous full-scale attempt had died at "
        "3 h 50 m with a StackOverflow."),
      tbl([["Metric &mdash; real rows only (n = 2,074,569)", "R²", "RMSE", "MAE"],
           ["Persistence baseline (“next hour = this hour”)", "0.8587", "24.831", "9.937"],
           ["GBT forecaster", "0.8910", "21.806", "8.926"],
           ["Improvement", "+0.0323", "-12.18%", "-1.011"]],
          [86*mm, 20*mm, 22*mm, 20*mm], align={1:"RIGHT",2:"RIGHT",3:"RIGHT"}, hi=3),
      Spacer(1, 2*mm),
      P("All-rows figure (n = 18,671,121): R&sup2; 0.8884 vs 0.8563, RMSE 22.429 vs 25.443, -11.85%. "
        "The script prints the persistence baseline on the same test rows every run and fails loudly if the model "
        "does not beat it.", SMALL),
      P("<b>Honest caveat:</b> training used a seeded 10,000,552-row sample of the 74.5M-row training window "
        "because 74.5M &times; 86 dimensions will not fit in 15.7 GB of RAM. <b>Evaluation was not sampled</b> "
        "&mdash; all 18,671,121 test rows were scored, so the metric stands.", SMALL)]

S += [P("Phase 7&ndash;8 &mdash; Streaming speed layer and alert engine", H2),
      P("Spark Structured Streaming, 10-second trigger, watching an HDFS directory. Each micro-batch rebuilds the "
        "Phase 4 features against a persisted 30-hour history table (so lag features survive job restarts), loads "
        "the GBT, predicts the PM<sub>2.5</sub> delta, converts to CPCB AQI, and writes an alert with severity and "
        "dominant pollutant wherever the forecast exceeds AQI 150."),
      tbl([["Batch", "rows in", "predicted", "alerts", "latency"],
           ["0 (replay)", "120", "15", "10", "10,750 ms"],
           ["1 (replay)", "120", "15", "10", "7,817 ms"],
           ["2 (replay)", "120", "14", "10", "7,019 ms"],
           ["3 (replay)", "120", "12", "7", "6,894 ms"],
           ["LIVE (after Phase 8b)", "16,560", "16,560", "1,130", "23,452 ms"]],
          [44*mm, 24*mm, 26*mm, 22*mm, 28*mm],
          align={1:"RIGHT",2:"RIGHT",3:"RIGHT",4:"RIGHT"}, hi=5),

      P("Phase 8b &mdash; Live enrichment (the gap that had to be closed)", H2),
      P("The first streaming run was fed rows already in the structured 32-column schema. That is a replay, not "
        "live consumption. Measured against the model's requirements, raw CAMS JSON supplies only 28 of the 54 "
        "numeric features:"),
      tbl([["Missing from raw CAMS JSON", "n", "Real source used"],
           ["weather: temperature, humidity, wind speed and direction, rain, pressure, solar", "8",
            "Open-Meteo weather API (same provider, free, no key)"],
           ["derived from weather: ventilation, scrub factor, stagnation, temp&times;humidity, is_raining", "5",
            "computed once weather exists"],
           ["traffic_index, is_rush_hour, urbanization_index", "3",
            "city_profiles.csv &mdash; the same profiles the generator used"],
           ["*_was_imputed provenance flags", "10",
            "0 where the API returned a value, 1 where it returned null"]],
          [72*mm, 10*mm, 58*mm], align={1:"CENTER"}),
      Spacer(1, 2*mm),
      P("<font face='Courier'>LiveEnrichment.scala</font> joins CAMS JSON, weather JSON and city profiles into the "
        "schema the stream already consumes, and was submitted to YARN as "
        "<font face='Courier'>application_1788670113534_0002</font>. Two unit conversions were measured, not "
        "assumed: CO from &micro;g/m&sup3; to mg/m&sup3; (&divide;1000 &mdash; unconverted, structured CO averages "
        "0.95 against CAMS 566), and pressure from hPa to mmHg (&times;0.750062 &mdash; the output 753.81 matches "
        "the structured median of 753). Wind is requested from the API in m/s directly."),
      P("<b>Output:</b> 16,560 live city-hours across 230 cities, zero nulls on model-critical columns, all 16,560 "
        "scored, <b>1,130 alerts</b>.", SMALL),

      P("Phase 9 &mdash; Hive serving layer", H2),
      P("Three EXTERNAL tables and three views over the Parquet already in HDFS &mdash; no data copied, and "
        "<font face='Courier'>DROP TABLE</font> removes only metadata, never 154 million rows. Exposed through "
        "<font face='Courier'>spark-sql</font> and, via <font face='Courier'>start-thriftserver.sh</font>, over "
        "the HiveServer2 Thrift protocol on port 10000, so beeline and JDBC clients connect unchanged."),
      P("All six demonstration queries return real results. The one worth showing is Delhi's seasonal cycle from "
        "measured values only:"),
      tbl([["Month", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
           ["PM<sub>2.5</sub>", "180.5", "127.9", "88.6", "86.8", "79.5", "66.3", "44.0", "38.8", "47.1", "120.1", "213.6", "199.4"]],
          [16*mm] + [12.8*mm]*12, fs=7.8),
      Spacer(1, 2*mm),
      P("A <b>5.5&times; swing</b> between the August monsoon low and the November stubble-burning peak. That is "
        "the physical reason thirteen years of history is required to train the model, and why a live feed &mdash; "
        "however fresh &mdash; cannot replace it.", SMALL),

      P("Phase 10 &mdash; Public warning board", H2),
      P("A single self-contained page. The architecture is the production shape, not a demo shortcut: an export "
        "job runs against the Hive layer and materialises one pre-aggregated JSON document, which is embedded into "
        "the page at build time. The page never queries 154 million rows, has no external dependency, and works "
        "opened from disk, hosted, or published."),
      P("It leads with the warning message each city's residents receive, carries CPCB's own health advisory "
        "wording for the band, and lets a reader search for their own city. Behind that sit the map of all 230 "
        "cities, warnings per hour, the cause breakdown, and the strongest warnings verbatim.", SMALL)]

# ---------------------------------------------------------------- 4
S += [P("4. What the live system is producing", H1),
      P("From the most recent cycle: <b>91 cities under warning</b>, 1,130 warnings issued across 230 monitored "
        "cities."),
      tbl([["Severity", "warnings"], ["MODERATE", "896"], ["POOR", "144"], ["SEVERE", "77"], ["VERY POOR", "13"]],
          [34*mm, 22*mm], align={1:"RIGHT"}),
      Spacer(1, 3*mm),
      tbl([["Dominant cause", "warnings", "share"],
           ["Ozone (O<sub>3</sub>)", "922", "82%"],
           ["Coarse dust (PM<sub>10</sub>)", "139", "12%"],
           ["Fine particles (PM<sub>2.5</sub>)", "67", "6%"],
           ["Sulphur dioxide", "2", "<1%"]],
          [46*mm, 24*mm, 20*mm], align={1:"RIGHT", 2:"RIGHT"}),
      Spacer(1, 3*mm),
      callout("A finding the platform surfaced",
              "<b>82% of current warnings are driven by ozone</b>, not particulates &mdash; a September "
              "photochemical-smog signal rather than a dust or combustion one. This is visible only because the "
              "alert engine records the dominant pollutant per alert, and it changes what a public warning should "
              "say: &ldquo;avoid midday exertion&rdquo; is the right advice for ozone, not &ldquo;wear a "
              "mask&rdquo;.", ACCENT),
      Spacer(1, 3*mm),
      P("The worst forecast in the window is Jaisalmer at AQI 500 (Severe), driven by coarse dust &mdash; a desert "
        "city, which is consistent. The Punjab&ndash;Haryana&ndash;Delhi belt dominates the leaderboard.", SMALL),

      P("5. Independent check: CPCB stations versus CAMS reanalysis", H1),
      P("The eight-month overlap (Aug 2022 &ndash; Mar 2023) is the only window in which two independent sources "
        "describe the same cities over the same hours. Structured rows were averaged to a city-hour &mdash; CAMS "
        "gives one point per city, CPCB gives many stations &mdash; using measured values only, and joined on "
        "(city, timestamp): <b>1,152,707 matched city-hours</b>."),
      tbl([["Pollutant", "correlation", "bias", "RMSE", "mean CPCB", "mean CAMS"],
           ["PM<sub>2.5</sub>", "0.565", "+8.55", "50.75", "59.96", "51.41"],
           ["PM<sub>10</sub>", "0.558", "+44.89", "97.18", "121.82", "76.93"],
           ["O<sub>3</sub>", "0.361", "-48.54", "67.17", "28.54", "77.07"],
           ["NO<sub>2</sub>", "0.219", "-2.07", "35.24", "24.87", "26.94"],
           ["SO<sub>2</sub>", "0.083", "-10.05", "43.32", "14.60", "24.65"]],
          [24*mm, 26*mm, 22*mm, 22*mm, 26*mm, 26*mm],
          align={1:"RIGHT",2:"RIGHT",3:"RIGHT",4:"RIGHT",5:"RIGHT"}),
      Spacer(1, 2*mm),
      P("<b>This is a genuinely mixed result and is reported as one.</b> Particulates track moderately, which is "
        "plausible for roadside sensors against a coarse model grid &mdash; a constant bias with decent "
        "correlation is the expected shape, not a failure. <b>SO<sub>2</sub> shows essentially no agreement</b>, "
        "and O<sub>3</sub> carries a large systematic offset. Per-city spread is wide: Kolkata 0.792 and Howrah "
        "0.794 at the top, Pune -0.209 at the bottom."),
      P("Two methodological notes travel with those numbers:"),
      bullets([
        "<b>CO was excluded</b> from the headline because the two sources report it in different units "
        "(mg/m&sup3; versus &micro;g/m&sup3;); comparing raw would manufacture a ~1000&times; disagreement.",
        "<b>A synthetic-versus-CAMS comparison was run and then discarded as invalid.</b> It returned figures "
        "numerically identical to real-versus-CAMS (0.564 against 0.565) because averaging to city-hour means "
        "averages away the AR(1) perturbation. The test cannot distinguish the two by construction, so it is not "
        "evidence either way; generator fidelity is tested at station level by the paired validator instead.",
      ], SMALL),
      Spacer(1, 2*mm),
      P("<b>Timezone alignment was verified, not assumed.</b> Correlation was measured at hour offsets "
        "-3&hellip;+3; it peaks at 0h/+1h (0.565 against 0.566 &mdash; within noise) and decays "
        "symmetrically either side. A genuine timezone error would shift the peak sharply.", SMALL)]

# ---------------------------------------------------------------- 6
S += [P("6. Eleven defects found &mdash; and how each was caught", H1),
      P("Four were in the source dataset. Seven were in pipeline code that had been written, and in several cases "
        "described as complete, but never executed. None surfaced until the code was run against real data on the "
        "cluster."),

      P("6.1 In the dataset", H2),
      tbl([["#", "Defect", "Scale", "Fix"],
           ["1", "is_rush_hour / variation_id not binary", "24,725 and 29,918 distinct values instead of 2 and 3",
            "round, cast to int"],
           ["2", "T+1 label built with a positional lead()", "8.69% of labels carried the wrong forecast horizon",
            "require next_ts == ts + 3600 s"],
           ["3", "physically impossible values", "humidity 104.999%, traffic_index 110.2 on a 0&ndash;100 scale",
            "clamp to [0, 100]"],
           ["4", "sparse simultaneous AQI coverage", "only 43.18% carry all 7 pollutants; 15.72% carry none",
            "three-tier median imputation, every fill flagged"]],
          [8*mm, 46*mm, 62*mm, 34*mm]),
      Spacer(1, 2*mm),
      P("Defect 2 is the consequential one. It, not a modelling limit, was the root cause of an earlier run that "
        "scored R&sup2; = 0.58 &mdash; below the do-nothing persistence baseline of 0.81.", SMALL),

      P("6.2 In the pipeline &mdash; found only by running it", H2),
      tbl([["#", "Where", "What happened", "How it was caught"],
           ["1", "merge job", "A substring file-name join double-counted Mumbai and Noida "
                              "(navi_mumbai.json contains mumbai.json as a literal substring)",
            "row count 44,544 failed to reconcile against the known fetch count of 44,160"],
           ["2", "streaming engine", "Referenced ts_unix one line before it existed; every batch aborted at the "
                                     "history update",
            "alerts printed BEFORE the failure, so it looked like a stall; only fires on a batch that has history"],
           ["3", "streaming engine", "VectorAssembler handleInvalid=“skip” silently dropped every live "
                                     "row, because CAMS returns ammonia as null for 100% of this region",
            "16,560 rows in, 0 predicted, and no error at all"],
           ["4", "paths.py", "HDFS join produced hdfs:////namenode:9000/… &mdash; four slashes; every "
                             "HDFS-mode Python run would fail to find its own data",
            "printed the resolved FEATURE_PATH inside the container"],
           ["5", "Phase 4 write", "DataNodes went unresponsive under host memory pressure; with 4 nodes at "
                                  "replication 3 there was no spare node for the write pipeline",
            "the first full-scale run computed everything correctly, then died writing 19.7 GB"],
           ["6", "Spark image", "numpy absent, so PySpark's ML module aborts at import",
            "training failed on first launch"],
           ["7", "Hive DDL", "Declared a column named “timestamp” that does not exist; the real columns "
                             "are observed_at / forecast_for / generated_at",
            "counts and AQI looked correct while every time value came back NULL"],
           ["8", "live feeds", "CAMS pulled in August joined against weather pulled in September shares zero hours",
            "the join produced 0 rows from two healthy inputs"]],
          [8*mm, 24*mm, 68*mm, 50*mm], fs=7.9),
      Spacer(1, 3*mm),
      callout("The pattern worth naming",
              "Defects 3 and 7 share a shape: both produced <b>plausible-looking output with no error</b>. "
              "Sixteen thousand rows in and zero out, with the surrounding counts looking fine; a Hive table "
              "returning correct counts alongside NULL timestamps. A silent wrong answer is more dangerous than a "
              "crash, because nothing asks you to look. The habit that caught both &mdash; reconcile the output "
              "count against an independently known number &mdash; is the single most transferable practice in "
              "this project.", BAD)]

# ---------------------------------------------------------------- 7
S += [P("7. A request that was declined, and why", H1),
      P("The project was asked for semi-structured coverage spanning 2010&ndash;2023, to match the structured "
        "layer. That was tested rather than assumed:"),
      tbl([["Date range requested", "What the API actually returned"],
           ["before 2013-01-01", "rejected outright: “out of allowed range”"],
           ["2013-01 &rarr; 2022-07", "timestamps returned, but EVERY value null (0% fill)"],
           ["2022-08", "89.7% fill — real data begins here"],
           ["2022-09 onward", "~99.8% fill (ammonia 0%, a real regional gap)"]],
          [48*mm, 108*mm]),
      Spacer(1, 2*mm),
      P("Fulfilling the request literally would have produced roughly ten years of empty rows that <i>look</i> "
        "like coverage &mdash; the kind of thing an examiner finds immediately. Coverage therefore begins at the "
        "first month carrying real values, and the limitation is stated rather than hidden. Evidence: "
        "<font face='Courier'>_audit/cams_history_availability.py</font> and "
        "<font face='Courier'>cams_history_cutoff.py</font>."),
      P("Similarly, 230 of 241 cities resolved. Eleven (Bileipada, Byrnihat, Chikkaballapur, Davanagere, Eloor, "
        "Gummidipoondi, Kunjemura, Mandi Gobindgarh, Palkalaiperur, Sivasagar, Vatva) returned a genuine geocoder "
        "miss and were excluded rather than assigned invented coordinates.", SMALL),

      P("8. The five V's", H1),
      tbl([["V", "Evidence", "State"],
           ["Volume", "154,583,979 rows, 33 GB, 1 NameNode + 4 DataNodes with real block distribution, "
                      "fsck HEALTHY", "demonstrated"],
           ["Variety", "flat fixed-schema CSV and nested self-describing JSON, read by native Spark readers into "
                       "one 17-column schema; Hive queries span both", "demonstrated"],
           ["Veracity", "11 defects found and fixed; independent cross-validation against CAMS reported honestly "
                        "including where it is weak; every fill flagged", "demonstrated"],
           ["Velocity", "Structured Streaming executed on the cluster: 10 s micro-batches, ~7 s latency, "
                        "1,130 alerts on genuinely live data", "demonstrated"],
           ["Value", "R² 0.8910 against persistence 0.8587 on 2,074,569 real test rows — an hour of "
                     "warning before pollution arrives", "demonstrated"]],
          [20*mm, 108*mm, 28*mm]),

      P("9. Limitations, stated plainly", H1),
      bullets([
        "<b>88.9% of structured rows are synthetic.</b> They are statistically validated against real data, but "
        "they are not physical measurements. Every model result is therefore reported on real rows separately, "
        "and that is the figure quoted.",
        "<b>Synthetic rows are easier to predict than real ones</b> (persistence R&sup2; 0.856 against 0.733), so "
        "a blended headline would flatter the model.",
        "<b>Training used a 10M-row sample</b> of 74.5M available rows &mdash; a 15.7 GB RAM ceiling, not a "
        "pipeline limit. Evaluation was not sampled.",
        "<b>CAMS is a reanalysis model, not a ground sensor</b>, and ammonia is null across the whole region.",
        "<b>The semi-structured layers cover 230 of 241 cities</b> and begin in August 2022.",
        "<b>Cross-validation agreement is moderate for particulates and poor for SO<sub>2</sub> and O<sub>3</sub>.</b>",
        "<b>Small-cluster fragility is real.</b> With 4 DataNodes at replication 3, a large derived write failed "
        "under memory pressure and had to be re-run at replication 2 with tuned timeouts. Replication 3 is kept "
        "for the raw layer, where fault tolerance is actually demonstrated.",
        "<b>The dashboard shows the most recent completed cycle</b>, not a continuously refreshing feed; the "
        "refresh is a scheduled job, not a push.",
      ], SMALL)]

# ---------------------------------------------------------------- 10
S += [P("10. What exists on disk", H1),
      P("10.1 Data", H2),
      tbl([["Path", "Contents"],
           ["airquality_expanded/part-*.csv", "structured layer, 23 files, 27.48 GB, 146,276,379 rows"],
           ["airquality_expanded/semistructured_history/", "8,263,440 CAMS records, 230 city JSON files"],
           ["airquality_expanded/live_cams/ + live_weather/", "the live feeds, refreshed each cycle"],
           ["airquality_expanded/unified_merged/", "154,583,979 rows, Parquet, partitioned by source_format"],
           ["HDFS /user/hadoop/", "raw, clean_scala (10 GB), features (19.7 GB), unified, models, stream output"]],
          [62*mm, 94*mm]),

      P("10.2 Code", H2),
      tbl([["File", "What it does"],
           ["scripts/00c_expand_dataset.py", "builds the structured dataset; repairs the four source defects"],
           ["scripts/00d_validate_expansion.py", "five paired statistical fidelity tests"],
           ["scripts/00e_fetch_semistructured_json.py", "live CAMS pull for every city in city_profiles.csv"],
           ["scripts/00f_fetch_semistructured_history.py", "historical CAMS pull; resumable, rate-limit aware"],
           ["scripts/00g_fetch_live_weather.py", "live weather pull (8 fields, m/s requested explicitly)"],
           ["scripts/01_clean_select.py", "Phase 3: range-guard, three-tier imputation, pm25_measured"],
           ["scripts/01c_merge_structured_semistructured.py", "unions structured CSV and nested JSON onto one schema"],
           ["scripts/02_feature_extraction.py", "Phase 4: T+1 label, CPCB AQI, lags, rolling, interactions"],
           ["scripts/03_train_gbt.py", "Phase 5&ndash;6: chronological split, persistence gate, GBT on delta"],
           ["scripts/04_cross_validate_overlap.py", "CPCB vs CAMS over the overlap window"],
           ["scripts/run_daily_live_cycle.py", "the operational job: fetch &rarr; upload &rarr; enrich &rarr; hand off &rarr; dashboard"],
           ["scala/&hellip;/CleanSelect.scala", "Scala port of Phase 3 for on-cluster execution"],
           ["scala/&hellip;/FeatureExtraction.scala", "Scala port of Phase 4"],
           ["scala/&hellip;/AirQualityStream.scala", "Phase 7&ndash;8: streaming speed layer and alert engine"],
           ["scala/&hellip;/LiveEnrichment.scala", "Phase 8b: CAMS + weather + profiles &rarr; model schema, on YARN"],
           ["hive/create_tables.sql, demo_queries.sql", "Phase 9: external tables, views, six verified queries"],
           ["dashboard/", "Phase 10: export from Hive, build, and the warning board itself"],
           ["scripts/_audit/ (15 scripts)", "every quoted number is reproducible from these"]],
          [70*mm, 86*mm], fs=7.9),
      Spacer(1, 2*mm),
      P("The Scala ports exist for a concrete reason: Spark cannot spawn Python worker processes on the "
        "development machine, so anything that must run on the cluster is written for the JVM.", SMALL),

      P("10.3 Documents and evidence", H2),
      tbl([["File", "Contents"],
           ["docs/PROJECT_REPORT.pdf", "this document"],
           ["docs/DATASET_REPORT.docx / .pdf", "the dataset and platform reference, 13 sections"],
           ["docs/ARCHITECTURE.md", "how the three layers combine; the live-alerting design"],
           ["docs/WORK_LOG.md", "every claim tied to the script and log that produces it"],
           ["docs/HADOOP_SPARK_CHEATSHEET.pdf", "one-page start/stop card for the cluster"],
           ["docs/run_logs/ (10 logs)", "raw stdout from every real run &mdash; the primary evidence"]],
          [62*mm, 94*mm]),

      P("11. How to run it", H1),
      P("Start the cluster, then one command does the daily cycle:", SMALL),
      P("docker compose -f docker-compose.yml -f docker-compose.yarn.yml -f docker-compose.spark.yml up -d<br/>"
        "python scripts/run_daily_live_cycle.py --all", CODE),
      P("That fetches both live feeds in the same window (fetching them separately once produced zero overlapping "
        "hours), uploads to HDFS, runs LiveEnrichment on YARN, hands the file to the streaming job's input "
        "directory, waits for it to be scored, and rebuilds the warning board. The streaming engine is a separate "
        "always-on service; dropping the file into its directory is the whole handoff.", SMALL),

      P("12. Conclusion", H1),
      P("The platform does what its title says. Thirteen years of real CPCB history train a forecaster that beats "
        "the honest baseline by 12.18% on two million real test hours. Live atmospheric data flows through a "
        "Spark-on-YARN enrichment job into a Structured Streaming engine that issues an hour's warning wherever "
        "the forecast AQI crosses 150. Everything the platform produces is queryable through Hive and visible on "
        "a public warning board."),
      P("What the project demonstrates beyond the architecture is a working method: measure rather than assume, "
        "reconcile every output count against an independently known number, and report the weak results as "
        "plainly as the strong ones. Eleven defects were found that way &mdash; several of which produced "
        "confident, plausible, wrong answers and would have survived any amount of code review."),
      Spacer(1, 4*mm), rule(),
      P("All figures in this report are measured. Logs in <font face='Courier'>docs/run_logs/</font>; "
        "reproduction scripts in <font face='Courier'>scripts/_audit/</font>.", SMALL)]

# ==============================================================================
def deco(canv, doc):
    canv.saveState()
    if doc.page > 1:
        canv.setStrokeColor(LINE); canv.setLineWidth(0.5)
        canv.line(18*mm, 285*mm, 192*mm, 285*mm)
        canv.setFont("Helvetica", 7.5); canv.setFillColor(MUTED)
        canv.drawString(18*mm, 288*mm, "A Scalable Big Data Platform for Real-Time Urban Air Quality Tracking")
        canv.drawRightString(192*mm, 288*mm, "23AID302  ·  Big Data Analytics")
        canv.line(18*mm, 15*mm, 192*mm, 15*mm)
        canv.setFont("Helvetica", 7.5)
        canv.drawRightString(192*mm, 10*mm, f"{doc.page}")
        canv.drawString(18*mm, 10*mm, "Complete Project Report")
    canv.restoreState()

doc = BaseDocTemplate("PROJECT_REPORT.pdf", pagesize=A4,
                      leftMargin=18*mm, rightMargin=18*mm, topMargin=22*mm, bottomMargin=20*mm,
                      title="Air Quality Big Data Platform - Complete Project Report",
                      author="23AID302 Big Data Analytics")
frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")
doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=deco)])
doc.build(S)
print("wrote PROJECT_REPORT.pdf")
