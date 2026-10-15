"""FINAL REVIEW deck in the faculty 10-slide structure. Usage: IMG=<dir> python build_final_10slides.py <1st_review.pptx> <out.pptx>"""
import os, sys
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
from PIL import Image

SRC, OUT = sys.argv[1], sys.argv[2]
IMG = os.environ["IMG"]
BLUE, INK, PANEL = RGBColor(0x0B, 0x5F, 0x8A), RGBColor(0x1A, 0x1A, 0x1A), RGBColor(0xF1, 0xF5, 0xF8)
GREEN, RED, MUTED, GREY = RGBColor(0x1B, 0x7A, 0x3D), RGBColor(0xC9, 0x34, 0x2B), RGBColor(0x6B, 0x77, 0x85), RGBColor(0x5A, 0x66, 0x73)
AMBER, MAROON, TEAL = RGBColor(0xD9, 0xA4, 0x00), RGBColor(0x7A, 0x1B, 0x2E), RGBColor(0x0E, 0x7C, 0x86)
WHITE, LINE, WARN = RGBColor(255, 255, 255), RGBColor(0xD9, 0xDF, 0xE7), RGBColor(0xFB, 0xEF, 0xD0)

prs = Presentation(SRC)
blank = prs.slide_layouts[6]
n_orig = len(prs.slides)

# start from the 1st-review deck's theme, drop its slides (the final deck follows the faculty's 10-slide structure)
_lst = prs.slides._sldIdLst
for _el in list(_lst):
    prs.part.drop_rel(_el.rId)
    _lst.remove(_el)



def rect(s, x, y, w, h, fill, line=None):
    r = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    r.fill.solid()
    r.fill.fore_color.rgb = fill
    if line:
        r.line.color.rgb = line
        r.line.width = Pt(0.5)
    else:
        r.line.fill.background()
    r.shadow.inherit = False
    return r


def text(s, t, x, y, w, h, size=15, bold=False, color=INK, italic=False, align=None, anchor=MSO_ANCHOR.TOP, font=None):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    lines = t if isinstance(t, list) else [t]
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        if align:
            p.alignment = align
        r = p.add_run()
        r.text = ln
        f = r.font
        f.size = Pt(size)
        f.bold = bold
        f.italic = italic
        f.color.rgb = color
        if font:
            f.name = font
    return tb


def bullets(s, items, x, y, w, h, size=15, gap=6):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(gap)
        r = p.add_run()
        r.text = "•  " + it
        r.font.size = Pt(size)
        r.font.color.rgb = INK
    return tb


def new_slide(title, notes=None):
    s = prs.slides.add_slide(blank)
    for ph in list(s.placeholders):
        ph._element.getparent().remove(ph._element)
    rect(s, 0, 0, 13.333, 0.09, BLUE)
    text(s, title, 0.6, 0.32, 12.13, 0.75, 28, True)
    if notes:
        s.notes_slide.notes_text_frame.text = notes
    return s


def table(s, header, rows, x, y, w, colw, size=12, rowh=0.4, bold_rows=()):
    gs = s.shapes.add_table(len(rows) + 1, len(header), Inches(x), Inches(y), Inches(w), Inches(rowh * (len(rows) + 1)))
    t = gs.table
    tblPr = gs._element.graphic.graphicData.tbl.tblPr
    tblPr.set("bandRow", "0")
    tblPr.set("firstRow", "0")
    for i, cw in enumerate(colw):
        t.columns[i].width = Inches(cw)
    for r in range(len(rows) + 1):
        t.rows[r].height = Inches(rowh)
    for c, h in enumerate(header):
        cell = t.cell(0, c)
        cell.fill.solid()
        cell.fill.fore_color.rgb = BLUE
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        r = cell.text_frame.paragraphs[0].add_run()
        r.text = h
        r.font.size = Pt(size)
        r.font.bold = True
        r.font.color.rgb = WHITE
    for ri, row in enumerate(rows, 1):
        for c, v in enumerate(row):
            cell = t.cell(ri, c)
            cell.fill.solid()
            cell.fill.fore_color.rgb = WHITE if ri % 2 else RGBColor(0xF7, 0xF9, 0xFB)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            color = INK
            if isinstance(v, tuple):
                v, color = v
            r = cell.text_frame.paragraphs[0].add_run()
            r.text = str(v)
            r.font.size = Pt(size)
            r.font.color.rgb = color
            r.font.bold = (ri - 1) in bold_rows
    return t


def stat(s, x, y, w, h, big, label, color=BLUE, size=30):
    rect(s, x, y, w, h, PANEL, LINE)
    text(s, big, x + 0.12, y + 0.08, w - 0.24, h * 0.55, size, True, color, anchor=MSO_ANCHOR.MIDDLE)
    text(s, label, x + 0.12, y + h * 0.62, w - 0.24, h * 0.36, 12, False, GREY)


def callout(s, t, x, y, w, h, size=14, fill=RGBColor(0xEA, 0xF2, 0xF8)):
    rect(s, x, y, w, h, fill)
    text(s, t, x + 0.18, y + 0.06, w - 0.36, h - 0.12, size, anchor=MSO_ANCHOR.MIDDLE)


def term(s, t, x, y, w, h, size=10.5, label=None):
    rect(s, x, y, w, h, RGBColor(0x0F, 0x17, 0x20))
    text(s, t.split("\n"), x + 0.12, y + 0.1, w - 0.24, h - 0.2, size, False, RGBColor(0xD7, 0xE2, 0xEA), font="Courier New")
    if label:
        text(s, label, x, y + h + 0.04, w, 0.28, 11, False, MUTED, True)


def pic(s, f, x, y, bw, bh):
    iw, ih = Image.open(os.path.join(IMG, f)).size
    r = min(bw / iw, bh / ih)
    w, h = iw * r, ih * r
    s.shapes.add_picture(os.path.join(IMG, f), Inches(x + (bw - w) / 2), Inches(y + (bh - h) / 2), Inches(w), Inches(h))


def bar(s, cats, vals, x, y, w, h, horizontal=False, colors=None, fmt="0.0", size=11, maxv=None):
    cd = CategoryChartData()
    cd.categories = cats
    cd.add_series("v", vals)
    t = XL_CHART_TYPE.BAR_CLUSTERED if horizontal else XL_CHART_TYPE.COLUMN_CLUSTERED
    ch = s.shapes.add_chart(t, Inches(x), Inches(y), Inches(w), Inches(h), cd).chart
    ch.has_legend = False
    ch.has_title = False
    ch.font.size = Pt(size)
    ch.font.color.rgb = GREY
    pl = ch.plots[0]
    pl.has_data_labels = True
    pl.gap_width = 50
    dl = pl.data_labels
    dl.number_format = fmt
    dl.number_format_is_linked = False
    dl.font.size = Pt(size)
    dl.font.color.rgb = INK
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    va = ch.value_axis
    va.has_major_gridlines = not horizontal
    if va.has_major_gridlines:
        va.major_gridlines.format.line.color.rgb = RGBColor(0xE6, 0xEA, 0xF0)
    va.format.line.fill.background()
    va.minimum_scale = 0
    if maxv:
        va.maximum_scale = maxv
    if horizontal:
        va.visible = False
        ch.category_axis.reverse_order = True
    ch.category_axis.format.line.color.rgb = RGBColor(0xC8, 0xCF, 0xD8)
    ser = pl.series[0]
    ser.format.fill.solid()
    ser.format.fill.fore_color.rgb = BLUE
    if colors:
        for i, c in enumerate(colors):
            pt = ser.points[i]
            pt.format.fill.solid()
            pt.format.fill.fore_color.rgb = c
    return ch


NOTES_TOTAL = "15 min talk: ~1.5 min per slide"
NAVY, TEALC = RGBColor(0x0D, 0x3B, 0x5E), RGBColor(0x0E, 0x7C, 0x86)
SIZE = Pt


def region(s, x, y, w, h, head, color=BLUE):
    """Panel with a coloured heading strip."""
    rect(s, x, y, w, h, PANEL, LINE)
    rect(s, x, y, w, 0.42, color)
    text(s, head, x + 0.15, y, w - 0.3, 0.42, 14, True, WHITE, anchor=MSO_ANCHOR.MIDDLE)


def code(s, x, y, w, h, title, body, size=9.5):
    rect(s, x, y, w, h, RGBColor(0x0F, 0x17, 0x20))
    text(s, title, x + 0.12, y + 0.05, w - 0.24, 0.25, 10, True, RGBColor(0x7F, 0xC8, 0xF8))
    text(s, body.split("\n"), x + 0.12, y + 0.32, w - 0.24, h - 0.36, size, False, RGBColor(0xD7, 0xE2, 0xEA), font="Courier New")


GH_URL = "https://github.com/jaganath010/A-Scalable-Big-Data-Platform-for-Real-Time-Urban-Air-Quality-Tracking-and-Public-Safety-Alerting"
WS_URL = "https://jaganath010.github.io/A-Scalable-Big-Data-Platform-for-Real-Time-Urban-Air-Quality-Tracking-and-Public-Safety-Alerting/"


def link(tb, url):
    for p in tb.text_frame.paragraphs:
        for r in p.runs:
            r.hyperlink.address = url
            r.font.underline = True
            r.font.color.rgb = BLUE


# ============================ SLIDE 1 - title ============================
s = prs.slides.add_slide(blank)
for ph in list(s.placeholders):
    ph._element.getparent().remove(ph._element)
rect(s, 0, 0, 13.333, 7.5, RGBColor(0xF2, 0xF5, 0xF7))
rect(s, 0, 0, 13.333, 0.16, BLUE)
text(s, "A Scalable Big Data Platform for Real-Time Urban Air Quality Tracking and Public Safety Alerting", 0.9, 1.1, 11.5, 1.9, 34, True)
text(s, "Final Project Review  |  23AID302 — Big Data Analytics  |  Group A14", 0.9, 3.15, 11.5, 0.4, 16, True, BLUE)
table(s, ["Team member", "Register number"], [
    ["Sangeeth S", "CB.AI.U4AID24050"], ["Jaganath R", "CB.AI.U4AID24021"],
    ["Niranjan S", "CB.AI.U4AID24035"], ["PL Kowshik", "CB.AI.U4AID24036"]], 0.9, 3.85, 6.2, [3.2, 3.0], 13, 0.42)
text(s, "Faculty:", 7.6, 3.9, 1.3, 0.4, 14, True)
text(s, "Sreeja B P", 8.7, 3.9, 4.2, 0.4, 14, True, INK)
text(s, "Stack:  Hadoop HDFS · YARN · Spark 3.5 · Scala 2.12 · PySpark MLlib · Structured Streaming · Hive", 7.6, 4.5, 5.2, 1.0, 13, False, GREY)
s.notes_slide.notes_text_frame.text = ("(1 min) Introduce the team and the one-line goal: forecast each city's PM2.5 one hour ahead on a distributed platform and warn people before it arrives. "
                                      "Fill in the faculty name on this slide before presenting.")

# ============================ SLIDE 2 - problem / objectives / why big data ============================
s = new_slide("Problem Statement, Objectives and Why Big Data",
              "(1.5 min) Three gaps: scale, latency, automation. Then the objectives and the numbers that make this a big-data problem: 154.6 M rows and 33 GB on a host with 15.7 GB RAM; a 10-second streaming requirement; two data models.")
region(s, 0.6, 1.25, 4.0, 5.6, "Problem")
bullets(s, ["Air-quality models run on one machine — they cannot hold a city-wide, multi-year history in memory",
            "Batch reports arrive after the fact; a pollution spike is a health event happening now",
            "Published frameworks stop at prediction — none turn a forecast into a public warning"], 0.8, 1.8, 3.65, 4.9, 16, 14)
region(s, 4.75, 1.25, 4.0, 5.6, "Objectives")
bullets(s, ["Fault-tolerant HDFS lakehouse (4 DataNodes, 3× replication)",
            "Distributed cleaning and feature engineering in Scala on Spark/YARN",
            "Gradient-boosted forecaster that must beat the persistence baseline",
            "Structured Streaming speed layer, 10 s micro-batches",
            "Alert engine: warn when forecast AQI > 150, one hour ahead",
            "Serve results through Hive and a public warning board"], 4.95, 1.8, 3.65, 4.9, 15, 11)
region(s, 8.9, 1.25, 3.85, 5.6, "Why big data is needed", RGBColor(0x0D, 0x3B, 0x5E))
stat(s, 9.05, 1.8, 1.7, 1.15, "154.6 M", "rows", BLUE, 22)
stat(s, 10.9, 1.8, 1.7, 1.15, "33 GB", "on disk", BLUE, 22)
bullets(s, ["Volume: 33 GB vs 15.7 GB RAM on the host — only partitioned, distributed processing fits",
            "Velocity: live feed scored every 10 s",
            "Variety: flat CSV and nested JSON on one schema",
            "Veracity: 88.9 % synthetic rows must be validated, not trusted"], 9.05, 3.1, 3.55, 3.7, 14, 10)

# ============================ SLIDE 3 - dataset + the five V's ============================
s = new_slide("Dataset \u2014 Source, Size and the Five V's",
              "(1.5 min) Three data layers with three jobs: structured CPCB trains, semi-structured CAMS history validates, live data alerts. Then the five V's with one measured fact each. Be upfront that 88.9 percent of structured rows are synthetic and that accuracy is quoted on real rows.")
table(s, ["Layer", "Source", "Format", "Rows", "Size", "Period"], [
    ["Structured", "CPCB stations (+ validated synthetic expansion)", "Flat CSV", "146,276,379", "27.5 GB", "2010 \u2013 2023"],
    ["Semi-structured", "CAMS reanalysis via Open-Meteo (history)", "Nested JSON", "8,263,440", "458 MB", "2022-08 \u2192 2026-09"],
    ["Semi-structured", "CAMS + weather, live (keyless API, CC-BY 4.0)", "Nested JSON", "82,800 per refresh", "\u2248 20 MB", "1\u201315 Oct 2026"],
], 0.6, 1.25, 12.15, [1.7, 4.6, 1.5, 1.7, 1.1, 1.55], 12, 0.45)
text(s, "Unified table: 154,583,979 rows \u00b7 33 GB \u00b7 241 cities / 4,077 stations \u00b7 one 17-column schema", 0.6, 3.05, 12.15, 0.3, 12.5, True, BLUE)
vs = [("V", "Volume", "154.6 M rows, 33 GB", "Far more than the 15.7 GB RAM of one machine; HDFS splits it into 128 MB blocks, 3\u00d7 copies", NAVY),
      ("V", "Variety", "CSV + nested JSON + live API", "Flat structured tables and nested semi-structured JSON, read by native Spark readers into one schema", TEALC),
      ("V", "Velocity", "10 s micro-batches", "Live feed scored by Structured Streaming, \u2248 7 s latency; hourly alert loop", RGBColor(0xC2, 0x5E, 0x00)),
      ("V", "Veracity", "88.9 % synthetic, validated", "5 paired tests, independent CPCB-vs-CAMS check, 11 defects fixed, every filled value flagged", MAROON),
      ("V", "Value", "R\u00b2 0.8910 vs 0.8587", "12.18 % lower error; 27,543 warnings in Oct, delivered one hour ahead with health advice", GREEN)]
for i, (_, name, big, desc, colr) in enumerate(vs):
    x = 0.6 + i * 2.45
    rect(s, x, 3.45, 2.3, 2.3, PANEL, LINE)
    rect(s, x, 3.45, 2.3, 0.45, colr)
    text(s, name, x + 0.12, 3.45, 2.1, 0.45, 15, True, WHITE, anchor=MSO_ANCHOR.MIDDLE)
    text(s, big, x + 0.12, 3.97, 2.08, 0.5, 13, True, colr)
    text(s, desc, x + 0.12, 4.5, 2.08, 1.2, 10.5, False, INK)
text(s, "Key attributes", 0.6, 5.9, 3, 0.3, 12.5, True, BLUE)
text(s, "Identity / time: station_id, city, state, hourly timestamp \u00b7 Pollutants: pm25, pm10, no2, so2, co, o3, nh3 (\u2192 CPCB AQI, T+1 label) \u00b7 Weather: temperature, humidity, wind, pressure, rain, solar \u00b7 Context: traffic_index, urbanization_index, climate_type \u00b7 Provenance: data_source, *_was_imputed \u00b7 Model input: 54 numeric + 32 one-hot = 86 features", 0.6, 6.2, 12.15, 0.8, 11, False, GREY)

# ============================ SLIDE 4 - architecture ============================
s = new_slide("System Architecture",
              "(1.5 min) Left to right: sources are fetched by Python scripts and land in HDFS; Spark on YARN runs the batch layer (Scala cleaning and features, PySpark GBT training) and the speed layer (live enrichment and the streaming scorer); the trained model is loaded by the stream; the alert engine feeds Hive, the warning board and Telegram.")

NAVY, TEALC = RGBColor(0x0D, 0x3B, 0x5E), RGBColor(0x0E, 0x7C, 0x86)
LIGHT, LIGHT_T = RGBColor(0xDC, 0xEB, 0xF4), RGBColor(0xD9, 0xEF, 0xF0)
ORANGE = RGBColor(0xE8, 0x73, 0x1A)


def box(x, y, w, h, t, fill, color=WHITE, size=11, bold=True, line=None):
    rect(s, x, y, w, h, fill, line)
    text(s, t.split("\n"), x + 0.05, y, w - 0.1, h, size, bold, color, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)


def arrow(x1, y1, x2, y2, color=MUTED, width=2.0, dash=False):
    from lxml import etree
    c = s.shapes.add_connector(1, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = color
    c.line.width = Pt(width)
    ln = c.line._get_or_add_ln()
    if dash:
        d = etree.SubElement(ln, "{http://schemas.openxmlformats.org/drawingml/2006/main}prstDash")
        d.set("val", "dash")
    tail = etree.SubElement(ln, "{http://schemas.openxmlformats.org/drawingml/2006/main}tailEnd")
    tail.set("type", "triangle")


def colhead(x, w, t):
    text(s, t, x, 1.12, w, 0.28, 10.5, True, MUTED, align=PP_ALIGN.CENTER)
    rect(s, x, 1.4, w, 0.03, LINE)


# column headers
colhead(0.45, 2.4, "1  DATA SOURCES")
colhead(3.1, 1.6, "2  INGEST")
colhead(4.95, 1.9, "3  STORAGE")
colhead(7.1, 4.15, "4  PROCESSING")
colhead(11.5, 1.4, "5  SERVE / ALERT")

# 1 sources
for i, (t, f) in enumerate([("CPCB stations CSV\n2010–2023 · 146.3 M rows", NAVY), ("CAMS history JSON\n2022–26 · 8.3 M rows", TEALC),
                            ("CAMS + weather APIs\nlive · 230 cities (keyless)", TEALC), ("city_profiles.csv\ntraffic, urbanization", NAVY)]):
    box(0.45, 1.6 + i * 1.05, 2.4, 0.9, t, f, size=10.5)
# 2 ingest
rect(s, 3.1, 1.6, 1.6, 3.9, PANEL, LINE)
text(s, ["Python fetchers", "", "00e / 00f / 00g", "HTTP, no API key", "", "run_daily_live_cycle", "run_hourly_cycle", "", "upload to HDFS"], 3.15, 1.7, 1.5, 3.7, 10.5, False, INK, align=PP_ALIGN.CENTER)
for i in range(4):
    arrow(2.85, 2.05 + i * 1.05, 3.1, 2.05 + i * 1.05)
# 3 storage
rect(s, 4.95, 1.6, 1.9, 3.9, BLUE)
text(s, "HDFS lakehouse", 5.0, 1.65, 1.8, 0.35, 13, True, WHITE, align=PP_ALIGN.CENTER)
for j, t in enumerate(["raw (CSV / JSON)", "clean (Parquet, by city)", "features (86-dim)", "unified table", "stream: input · history", "models: GBT + pipeline"]):
    box(5.05, 2.1 + j * 0.5, 1.7, 0.4, t, RGBColor(0x2A, 0x7F, 0xAE), WHITE, 9.5, False)
text(s, "1 NN + 4 DN\n128 MB · 3×", 5.0, 5.1, 1.8, 0.4, 9.5, False, RGBColor(0xDC, 0xEB, 0xF4), align=PP_ALIGN.CENTER)
arrow(4.7, 3.55, 4.95, 3.55)
# 4 processing
rect(s, 7.1, 1.6, 4.15, 3.9, RGBColor(0xE9, 0xF1, 0xF6), BLUE)
text(s, "Apache Spark 3.5.6 on YARN  (1 RM + 4 NM)", 7.2, 1.65, 3.95, 0.3, 11, True, BLUE)
text(s, "BATCH LAYER — trains on 13 years of history", 7.2, 2.05, 3.95, 0.25, 9.5, True, MUTED)
box(7.25, 2.35, 1.15, 0.85, "CleanSelect\n(Scala)\nclean + impute", LIGHT, INK, 9.5)
box(8.65, 2.35, 1.15, 0.85, "Feature-\nExtraction\n(Scala) 86 feat.", LIGHT, INK, 9.5)
box(10.05, 2.35, 1.1, 0.85, "GBT training\n(PySpark MLlib)\n300 trees", MAROON, WHITE, 9.5)
arrow(8.4, 2.78, 8.65, 2.78)
arrow(9.8, 2.78, 10.05, 2.78)
rect(s, 7.25, 3.55, 3.9, 0.02, LINE)
text(s, "SPEED LAYER — scores live data every 10 s", 7.2, 3.62, 3.95, 0.25, 9.5, True, MUTED)
box(7.25, 3.95, 1.5, 0.95, "LiveEnrichment\n(Scala)\nCAMS+weather+profile", LIGHT_T, INK, 9.5)
box(9.1, 3.95, 2.05, 0.95, "AirQualityStream (Scala)\nforeachBatch: features → GBT\n→ AQI → alerts", TEALC, WHITE, 9.5)
arrow(8.75, 4.42, 9.1, 4.42)
arrow(10.6, 3.2, 10.6, 3.95, MAROON, 2.2)
text(s, "model", 10.7, 3.4, 0.5, 0.25, 9, True, MAROON)
text(s, "state: 30 h history + checkpoint (HDFS)", 7.25, 5.0, 3.9, 0.3, 9, False, GREY, True)
# storage <-> processing
arrow(6.85, 2.5, 7.1, 2.5)
arrow(7.1, 2.9, 6.85, 2.9)
arrow(6.85, 4.2, 7.1, 4.2)
arrow(7.1, 4.6, 6.85, 4.6)
# 5 outputs
box(11.5, 1.6, 1.4, 0.8, "Hive\nexternal tables", NAVY, WHITE, 10)
box(11.5, 2.75, 1.4, 0.8, "Warning board\n(HTML / Pages)", NAVY, WHITE, 10)
box(11.5, 3.9, 1.4, 0.8, "Alert engine\nAQI > 150", MAROON, WHITE, 10)
box(11.5, 5.05, 1.4, 0.45, "Telegram", TEALC, WHITE, 10)
arrow(11.25, 2.0, 11.5, 2.0)
arrow(11.25, 4.3, 11.5, 4.3)
arrow(12.2, 2.4, 12.2, 2.75)
arrow(12.2, 4.7, 12.2, 5.05)
# bottom strip
for i, t in enumerate(["Docker Compose · 11 containers", "HDFS 128 MB blocks · 3× replication", "Parquet (snappy), partitioned by city",
                       "Scala 2.12.18 = Spark 3.5.6 build", "Lambda: batch + speed over one lakehouse"]):
    box(0.45 + i * 2.5, 5.85, 2.4, 0.5, t, PANEL, INK, 10, False, LINE)
text(s, "Blue = storage · light = Scala jobs · maroon = ML model / alert logic · teal = live path. Arrows show data flow; the model is read from HDFS by the streaming job.", 0.45, 6.55, 12.4, 0.5, 10.5, False, MUTED, True)

# ============================ SLIDE 5 - Spark workflow (simple) ============================
s = new_slide("Spark Workflow \u2014 How the Data Flows",
              "(1.5 min) Keep it simple. The job is a chain of six steps; Spark builds this chain as a DAG and splits it into stages wherever data must move between machines (a shuffle, shown in orange). Partitioning decides how the data is cut up; caching keeps a table in memory when it is reused.")
text(s, "The feature-engineering job as a chain of steps (Spark builds this DAG)", 0.6, 1.2, 12.1, 0.35, 15, True, BLUE)
steps = [("1  Read", "Parquet from HDFS\n232 parallel tasks", False), ("2  Remove\nduplicates", "one row per\nstation + hour", True), ("3  Add history", "rolling averages,\nlag, trend", True),
         ("4  Add the label", "next-hour PM\u2082.\u2085\n(only if exactly 1 h later)", False), ("5  Pack features", "86 numbers\nper row", False), ("6  Write", "one folder\nper city (241)", True)]
for i, (a, b, wide) in enumerate(steps):
    x = 0.6 + i * 2.05
    rect(s, x, 1.65, 1.85, 1.5, RGBColor(0xFB, 0xE3, 0xC8) if wide else RGBColor(0xDC, 0xEB, 0xF4), LINE)
    text(s, a.split("\n"), x + 0.05, 1.7, 1.75, 0.6, 13, True, INK, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    text(s, b.split("\n"), x + 0.05, 2.35, 1.75, 0.7, 11, False, GREY, align=PP_ALIGN.CENTER)
    if i < 5:
        text(s, "\u2192", x + 1.85, 1.65, 0.2, 1.5, 16, True, MUTED, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
text(s, "Orange = shuffle (data moves between machines, a new stage). Blue = runs inside one stage.  Measured: 146.3 M \u2192 128.7 M \u2192 93.2 M rows in 73.5 min.", 0.6, 3.25, 12.1, 0.3, 11.5, False, MUTED, True)
cards = [("DataFrames, not RDDs", BLUE, ["We work with DataFrames (tables); Spark turns them into RDDs inside.", "Window functions give every station its own history.", "Small lookup tables are broadcast to all machines \u2014 no shuffle needed."]),
         ("Partitioning \u2014 how data is cut", TEALC, ["HDFS stores 128 MB blocks \u2192 232 tasks read in parallel.", "Results are saved one folder per city (241), so one city reads one folder.", "Shuffle partitions tuned per job (from 16 up to 400)."]),
         ("Caching \u2014 what we keep in memory", MAROON, ["cache() keeps a table in memory when it is used more than once.", "We cache: the cleaning table, the training data, the stream predictions.", "unpersist() frees the memory when we are done."])]
for i, (h, colr, items) in enumerate(cards):
    x = 0.6 + i * 4.1
    rect(s, x, 3.75, 3.95, 3.15, PANEL, LINE)
    rect(s, x, 3.75, 3.95, 0.5, colr)
    text(s, h, x + 0.15, 3.75, 3.7, 0.5, 14, True, WHITE, anchor=MSO_ANCHOR.MIDDLE)
    bullets(s, items, x + 0.18, 4.4, 3.6, 2.5, 13, 8)

# ============================ SLIDE 6 - Scala implementation ============================
s = new_slide("Scala Implementation — Project Structure and Key Code",
              "(1.5 min) 1,536 lines of Scala across four jobs. Scala 2.12.18 is pinned because Spark 3.5.6 is built against it. Show the three snippets: the gap-safe rolling window, the broadcast imputation join, and the streaming skeleton with foreachBatch.")
region(s, 0.6, 1.25, 4.2, 5.6, "Project structure")
term(s, "scala/streaming/\n  build.sbt   Scala 2.12.18\n              Spark 3.5.6 (provided)\n  src/main/scala/\n    CleanSelect.scala        344\n      10-step clean, 3-tier\n      impute, write by city\n    FeatureExtraction.scala  377\n      86 features, T+1 label\n    LiveEnrichment.scala     324\n      CAMS+weather+profiles\n    AirQualityStream.scala   491\n      streaming + alert engine\n\nsbt package -> jar\nspark-submit --class <Job>\n  --master yarn\n\nscripts/03_train_gbt.py\n  PySpark MLlib GBT", 0.7, 1.75, 4.0, 5.0, 10)
code(s, 5.0, 1.25, 7.75, 1.95, "FeatureExtraction.scala — dedupe + gap-safe rolling window",
     'val dedupW = Window.partitionBy("station_id","variation_bucket","ts_unix")\n                   .orderBy(col("pm25").desc_nulls_last)\ndf = df.withColumn("_rn", row_number().over(dedupW)).filter(col("_rn")===1)\n\ndef hoursBack(n: Int) = Window.partitionBy("station_id","variation_bucket")\n  .orderBy("ts_unix").rangeBetween(-(n-1).toLong * Hour, 0L)  // value-based:\ndf = df.withColumn(s"${p}_avg${h}h", avg(col(p)).over(hoursBack(h)))  // gap-safe')
code(s, 5.0, 3.3, 7.75, 1.7, "CleanSelect.scala — broadcast joins for the 3-tier median imputation",
     'val t1 = df.groupBy("station_id","month","hour").agg(med(c).as(s"${c}__t1"))\nval t2 = df.groupBy("city","month").agg(med(c).as(s"${c}__t2"))\ndf = df.join(broadcast(t1), Seq("station_id","month","hour"), "left")\n       .join(broadcast(t2), Seq("city","month"), "left")\ndf = df.withColumn(c, coalesce(col(c), col(s"${c}__t1"), col(s"${c}__t2"), lit(t3(c))))')
code(s, 5.0, 5.1, 7.75, 1.75, "AirQualityStream.scala — Structured Streaming speed layer",
     'val raw = spark.readStream.schema(InputSchema).option("header","true")\n  .option("maxFilesPerTrigger","1").csv(StreamInput)        // HDFS file source\nraw.writeStream.option("checkpointLocation", CheckpointDir)\n  .foreachBatch { (batch: DataFrame, id: Long) =>\n     // union with 30 h history -> features -> GBT -> AQI -> alerts.write.partitionBy("city")\n  }.trigger(Trigger.ProcessingTime("10 seconds")).start()')

# ============================ SLIDE 7 - ML pipeline ============================
s = new_slide("Spark ML Pipeline — Features, Algorithm, Tuning",
              "(1.5 min) Pipeline from indexers to the GBT. We tuned by controlled experiments: tree count 20 to 120 to 300, and level target versus delta target, plus a chronological split. Persistence is the baseline and a built-in gate fails the run if the model does not beat it.")
flow = [("Features\n(Parquet)", NAVY), ("StringIndexer\n+ OneHot", BLUE), ("VectorAssembler\n54 + 32 = 86", BLUE), ("Chronological\nsplit (not random)", BLUE), ("GBTRegressor\n300 trees", MAROON), ("Model on HDFS\n→ stream", TEALC)]
for i, (t, f) in enumerate(flow):
    box(0.6 + i * 2.05, 1.3, 1.85, 0.95, t, f, WHITE, 12)
    if i < 5:
        text(s, "→", 0.6 + i * 2.05 + 1.85, 1.3, 0.2, 0.95, 16, True, MUTED, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
region(s, 0.6, 2.5, 4.1, 4.35, "Features (86)")
bullets(s, ["Current: pm25, pm10, no2, so2, co, o3, nh3", "History: lag_1h, rolling 3/6/24 h means, std_6h, delta_1h, surge_ratio", "CPCB AQI sub-indices, AQI rolling",
            "Weather: temperature, humidity, wind, pressure, rain, solar", "Time: hour_sin / hour_cos, rush hour", "Context: traffic, urbanization, climate (one-hot)", "Provenance: *_was_imputed flags"], 0.75, 3.0, 3.85, 3.85, 11.5, 4)
region(s, 4.85, 2.5, 3.9, 4.35, "Algorithm — GBTRegressor")
table(s, ["Parameter", "Value"], [["maxIter", "300"], ["maxDepth", "6"], ["stepSize η", "0.08"], ["subsamplingRate", "0.8"], ["featureSubset", "sqrt"], ["maxBins", "64"], ["Target", "PM₂.₅(t+1) − PM₂.₅(t)"]], 5.0, 3.0, 3.6, [1.8, 1.8], 11.5, 0.38)
text(s, "Trained on 10 M rows (seeded sample; RAM ceiling), tested on all 18.7 M hold-out rows.", 5.0, 6.15, 3.6, 0.65, 10.5, False, GREY, True)
region(s, 8.9, 2.5, 3.85, 4.35, "Tuning — controlled experiments")
table(s, ["Experiment", "RMSE gain vs persistence"], [["20 trees (plan default)", "too few"], ["19 cities, 120 trees", "5.67 %"], ["Level target (local repro)", "5.6 %"], ["Delta target (local repro)", "11.3 %"], ["241 cities, 300 trees", "12.18 %"]], 9.0, 3.0, 3.65, [2.0, 1.65], 11, 0.42)
text(s, "Split by time, never at random: consecutive hours correlate ≈ 0.81 → a random split leaks the answer.", 9.0, 5.75, 3.65, 1.0, 10.5, False, GREY, True)

# ============================ SLIDE 8 - results ============================
s = new_slide("Results — Metrics, Model Comparison, Business Insight",
              "(2 min) Real-rows figure first: R-squared 0.8910 vs 0.8587, RMSE down 12.18 percent. Then the business result from the October live run: 27,543 warnings, 221 of 230 cities, a dust belt in Haryana and Punjab. Switch to the website demo here.")
bar(s, ["Persistence\nbaseline", "GBT\nforecaster"], [24.831, 21.806], 0.6, 1.25, 3.7, 3.3, colors=[MUTED, BLUE], fmt="0.00", maxv=30, size=11)
text(s, "RMSE µg/m³ (lower is better), real rows n = 2,074,569", 0.6, 4.55, 3.7, 0.5, 11, False, MUTED, True)
table(s, ["Metric table", "Persistence", "GBT", "Gain"], [
    ["R² (real rows)", "0.8587", ("0.8910", GREEN), "+ 0.0323"], ["RMSE (real)", "24.831", ("21.806", GREEN), "− 12.18 %"], ["MAE (real)", "9.937", ("8.926", GREEN), "− 1.011"],
    ["R² (all 18.7 M)", "0.8563", "0.8884", "+ 0.0321"], ["RMSE (all)", "25.443", "22.429", "− 11.85 %"]], 4.5, 1.25, 4.3, [1.5, 1.0, 0.8, 1.0], 11, 0.42)
table(s, ["Model comparison", "RMSE gain"], [["Persistence (next hr = this hr)", "baseline"], ["GBT pilot (19 cities, 120 trees)", "5.67 %"], ["GBT, level target (local)", "5.6 %"], ["GBT, delta target (local)", "11.3 %"], [("GBT full (241 cities, 300 trees)", GREEN), ("12.18 %", GREEN)]], 4.5, 3.9, 4.3, [2.9, 1.4], 11, 0.37)
text(s, "Top features: pm25, pm25_delta_1h, pm25_surge_ratio — and pm25_was_imputed ranks 6th of 86: the model learned to distrust filled-in values.", 4.5, 6.3, 4.3, 0.7, 9.5, False, GREY, True)
region(s, 9.0, 1.25, 3.75, 5.65, "Business insight — Oct 2026 live run", MAROON)
stat(s, 9.15, 1.8, 1.7, 1.0, "27,543", "warnings", RED, 20)
stat(s, 10.9, 1.8, 1.7, 1.0, "221/230", "cities warned", RED, 20)
bullets(s, ["32 cities forecast Severe (AQI > 400); worst: Hisar, Bhiwani, Fatehabad — the Haryana–Punjab dust belt",
            "Cause mix: ozone 44 %, coarse dust 36 % → different advice: avoid midday exertion vs wear a mask",
            "A warning reaches residents one hour ahead, with CPCB health advice",
            "Delhi PM₂.₅ swings 5.5× (Aug 38.8 → Nov 213.6) — why 13 years of history matters"], 9.15, 2.95, 3.5, 3.95, 11.5, 6)

# ============================ SLIDE 9 - challenges / conclusion ============================
s = new_slide("Challenges, Limitations, Conclusion and Future Work",
              "(1.5 min) Name two real challenges and how they were solved, state the limitations before being asked, then conclude and point to the next steps.")
region(s, 0.6, 1.25, 6.0, 2.75, "Challenges (found by running, then fixed)")
bullets(s, ["Spark could not write to HDFS from the host → run Spark inside the cluster network",
            "Full-scale write died: DataNodes starved → driver 7→5 GB, replication 2, timeouts",
            "YARN executors OOM-killed (exit 137) on a 15.7 GB host → Phase 4 local mode; YARN proven by enrichment job",
            "11 defects found (2 silent wrong answers) → reconcile every count"], 0.75, 1.75, 5.75, 2.25, 12.5, 5)
region(s, 6.75, 1.25, 6.0, 2.75, "Limitations", RGBColor(0x8A, 0x6A, 0x00))
bullets(s, ["88.9 % of structured rows synthetic — results quoted on real rows only",
            "Trained on a 10 M-row sample of 74.5 M (RAM); evaluation not sampled",
            "CAMS is a model product, not a sensor feed; SO₂ agreement with CAMS is poor (0.083)",
            "October page is a snapshot; SMS needs a paid gateway; 230 of 241 cities"], 6.9, 1.75, 5.75, 2.25, 12.5, 5)
region(s, 0.6, 4.15, 6.0, 2.7, "Conclusion", GREEN)
bullets(s, ["A fault-tolerant 4-node HDFS + YARN + Spark platform processing 154.6 M rows", "GBT forecaster 12.18 % better than the honest baseline on real rows",
            "Live data scored in the stream and turned into 27,543 warnings with health advice", "Hive serving, public warning board, de-duplicated Telegram alert loop"], 0.75, 4.65, 5.75, 2.2, 14, 8)
region(s, 6.75, 4.15, 6.0, 2.7, "Future work")
bullets(s, ["Hourly scheduler + SMS gateway; push via Telegram bot at scale", "Random Forest / XGBoost comparison", "Neighbour-station features (GraphX station network)", "Multi-host cluster to train on all 74.5 M rows; real-time CPCB feed with an API key"], 6.9, 4.65, 5.75, 2.2, 14, 8)

# ============================ SLIDE 10 - references + GitHub ============================
s = new_slide("References and GitHub",
              "(0.5 min) References, then the repository link. Upload the PPT and the report to the repository before submission.")
refs = ["[1] Air Quality Prediction using Multi-Source Remote Sensing Data Integration with Hybrid Deep Learning Framework (MAST-Net). Nature, Scientific Reports, Dec 2025.",
        "[2] Apache Hadoop 3.3.6 Documentation. hadoop.apache.org/docs/r3.3.6/",
        "[3] Apache Spark 3.5.6 Documentation (SQL, MLlib, Structured Streaming). spark.apache.org/docs/3.5.6/",
        "[4] Central Pollution Control Board. National Air Quality Index — Report of the Expert Group, 2014.",
        "[5] Zaharia, M. et al. Resilient Distributed Datasets. NSDI, 2012.",
        "[6] Shvachko, K. et al. The Hadoop Distributed File System. IEEE MSST, 2010.",
        "[7] Friedman, J. H. Greedy Function Approximation: A Gradient Boosting Machine. Annals of Statistics 29(5), 2001.",
        "[8] Copernicus Atmosphere Monitoring Service (CAMS), via Open-Meteo Air Quality API (CC-BY 4.0). open-meteo.com",
        "[9] Apache Hive and Apache Parquet Documentation. hive.apache.org, parquet.apache.org"]
bullets_free = None
tb = text(s, refs, 0.6, 1.25, 12.15, 3.6, 13.5, False, INK)
for p in tb.text_frame.paragraphs:
    p.space_after = Pt(8)
rect(s, 0.6, 5.0, 12.15, 1.95, PANEL, LINE)
text(s, "GitHub repository", 0.8, 5.08, 4, 0.35, 14, True, BLUE)
link(text(s, "https://github.com/jaganath010/A-Scalable-Big-Data-Platform-for-Real-Time-Urban-Air-Quality-Tracking-and-Public-Safety-Alerting", 0.8, 5.43, 11.7, 0.35, 12.5, True, INK), GH_URL)
text(s, "Website (warning board, GitHub Pages)", 0.8, 5.85, 6, 0.35, 14, True, BLUE)
link(text(s, "https://jaganath010.github.io/A-Scalable-Big-Data-Platform-for-Real-Time-Urban-Air-Quality-Tracking-and-Public-Safety-Alerting/", 0.8, 6.2, 11.7, 0.35, 12.5, True, INK), WS_URL)
text(s, "Uploaded: this PPT (presentation/) + PROJECT_REPORT.pdf (docs/), code (scala/, scripts/, hive/, dashboard/), run logs (docs/run_logs/)", 0.8, 6.58, 11.7, 0.3, 10.5, False, GREY)

# ============================================================================
# APPENDIX - EVIDENCE (after the 10 required slides; every item is a real screenshot or a verbatim log excerpt)
# ============================================================================
def cap(s, t, x, y, w, h=0.4, size=11):
    text(s, t, x, y, w, h, size, True, BLUE)


# ---- A1 HDFS ----
s = new_slide("Appendix — Evidence: HDFS Cluster",
              "Screenshots from the running cluster. dfsadmin shows 4 live DataNodes; fsck reports HEALTHY with 232 blocks at replication 3.0 and no missing or corrupt blocks; the NameNode UI and du show the data layers.")
pic(s, "s7_1.png", 0.6, 1.3, 7.3, 1.9)
cap(s, "dfsadmin -report: Live datanodes (4), 4 DataNodes each holding ≈ 24–28 GB", 0.6, 3.2, 7.3)
pic(s, "hdfs_dn_crop.png", 0.6, 3.65, 3.6, 2.2)
cap(s, "NameNode UI — DataNodes in service", 0.6, 5.85, 3.6)
pic(s, "s11_2.png", 4.3, 3.9, 3.6, 0.5)
text(s, "hdfs dfs -du -h: raw 27.5 GB → 82.4 GB on disk (3×); clean_scala 10.0 GB → 20.0 GB (2×)", 4.3, 4.5, 3.6, 0.9, 11, False, GREY)
pic(s, "s8_1.png", 8.1, 1.3, 4.65, 4.9)
cap(s, "hdfs fsck /lakehouse/raw: HEALTHY — 232 blocks, replication 3.0, 0 missing / corrupt", 8.1, 6.25, 4.65, 0.6, 10.5)

# ---- A2 YARN + Spark ----
s = new_slide("Appendix — Evidence: YARN and Spark on the Cluster",
              "YARN lists four NodeManagers; the applications list shows the Spark job we submitted; the terminal shows master yarn and the reconciled total of 154,583,979 rows.")
pic(s, "yarn_nodes_crop.png", 0.6, 1.3, 5.9, 2.6)
cap(s, "YARN ResourceManager — 4 NodeManagers, RUNNING", 0.6, 3.9, 5.9)
pic(s, "yarn_apps.png", 6.7, 1.3, 6.05, 1.75)
cap(s, "Applications: AirQuality_Review_Demo → FINISHED / SUCCEEDED", 6.7, 3.05, 6.05)
pic(s, "s13_1.png", 6.7, 3.5, 6.05, 2.4)
cap(s, "First Spark job on YARN: Spark 3.5.6 / Scala 2.12.18, state ACCEPTED → RUNNING → SUCCEEDED", 6.7, 5.95, 6.05, 0.6, 10.5)
term(s, "master     : yarn\napp id     : application_1792046046524_0001\n|semistructured_json|cams_history|8263440  |230\n|semistructured_json|live_api    |44160    |230\n|structured_csv     |real        |16252931 |241\n|structured_csv     |synthetic   |130023448|241\nTOTAL rows: 154,583,979   (expected 154,583,979 -> True)",
     0.6, 4.4, 5.9, 2.0, 10, "spark_on_yarn_demo.log — distributed count over the unified table")

# ---- A3 Scala processing ----
s = new_slide("Appendix — Evidence: Scala Processing and Feature Engineering",
              "Left: the Scala source in the editor. Middle: the CleanSelect run at full scale. Right: the processed layer in HDFS partitioned by city (241 directories). Bottom: the Phase 4 feature job summary.")
pic(s, "s9_1.png", 0.6, 1.3, 4.0, 4.0)
cap(s, "CleanSelect.scala (source)", 0.6, 5.3, 4.0)
pic(s, "s10_1.png", 4.8, 1.3, 4.3, 2.3)
cap(s, "CleanSelect at full scale: 146,276,379 rows in → out", 4.8, 3.6, 4.3)
pic(s, "s11_1.png", 9.3, 1.3, 3.45, 3.2)
cap(s, "HDFS clean_scala: city=… partitions (241)", 9.3, 4.5, 3.45)
term(s, "rows in            : 146,276,379\nrows after dedupe  : 128,660,967\nrows with T+1 label: 93,216,105\nrows assemblable   : 93,216,105\nnumeric features   : 54    one-hot width : 32\nFEATURE VECTOR DIM : 86    partitioned by: city\nelapsed            : 4411.0 s (73.5 min)",
     4.8, 4.05, 4.3, 2.2, 9.5, "phase4_fullscale.log")
callout(s, "Preprocessing: 32 → 44 columns, 10 steps, 3-tier imputation, every fill flagged; Phase 4 output 19.7 GB in 241 city partitions.", 9.3, 5.05, 3.45, 1.2, 11)

# ---- A4 model + validation ----
s = new_slide("Appendix — Evidence: Model Training and Data Validation",
              "Left: the verbatim evaluation block of the 300-tree training log; the script's own gate printed PASS. Right: the independent CPCB-versus-CAMS cross-validation on 1.15 M matched city-hours, reported as mixed.")
term(s, "train 10,000,552 rows | test 18,671,121 rows\ntest window: 2022-07-01 -> 2023-03-31\nPERSISTENCE BASELINE  R2=0.8563 RMSE=25.443\ntrained on 10,000,552 rows, 300 trees\nREAL ROWS ONLY (n=2,074,569)\n  persistence baseline  0.8587  24.831  9.937\n  GBT model             0.8910  21.806  8.926\n  RMSE reduction        12.18%\nPASS (real rows): beats persistence by 0.0323 R2",
     0.6, 1.3, 6.3, 2.9, 11, "trackB_train_fullscale.summary.log — PHASE 6 evaluation (5 h 50 m on one host)")
text(s, "Persistence gate: the script prints *** FAIL *** if the model does not beat “next hour = this hour” on the same rows.", 0.6, 4.75, 6.3, 0.7, 12, False, GREY)
text(s, "Cross-validation: CPCB vs CAMS, 1,152,707 city-hours (Pearson r)", 7.2, 1.3, 5.5, 0.35, 13, True, BLUE)
bar(s, ["PM₂.₅", "PM₁₀", "O₃", "NO₂", "SO₂"], [0.565, 0.558, 0.361, 0.219, 0.083], 7.2, 1.7, 5.55, 2.8, colors=[BLUE, BLUE, AMBER, AMBER, RED], fmt="0.000", maxv=1)
stat(s, 0.6, 5.5, 3.0, 1.3, "5 / 5", "paired synthetic-vs-real tests pass (blocking)", GREEN)
stat(s, 3.8, 5.5, 3.0, 1.3, "11", "defects found by running, all fixed", BLUE)
stat(s, 7.0, 5.5, 2.9, 1.3, "6th / 86", "pm25_was_imputed importance", BLUE)
callout(s, "SO₂ agreement is essentially none (0.083) — published as a limitation, not hidden.", 10.05, 5.5, 2.7, 1.3, 11, WARN)

# ---- A5 live + alerting ----
s = new_slide("Appendix — Evidence: October Live Run, Alerts and Website",
              "October 1–15: 82,800 live rows enriched on YARN with no nulls on key columns, scored in the stream (27,543 alerts, 221 cities), served in Hive, shown on the board, and dispatched with de-duplication on a replay of the forecast.")
term(s, "cams window    : 2026-10-01 .. 2026-10-15 23:00\nweather window : 2026-10-01 .. 2026-10-15 23:00\njoined rows    : 82,800\nenriched rows  : 82,800 across 230 cities\n  pm25 nulls=0   temperature_c nulls=0\n  pressure nulls=0   traffic_index nulls=0",
     0.6, 1.3, 4.1, 1.85, 9.5, "october_live_cycle.log (LiveEnrichment on YARN)")
term(s, "[batch 0] no history yet - first run\n[batch 0] *** 27543 ALERTS ***\n[batch 0] rows in=82,800  predicted=82,800\n  alerts=27,543  latency=57,820 ms\nHive stream_alerts: 27543 rows, 221 cities,\n  2026-10-01 .. 2026-10-16 00:00",
     0.6, 3.5, 4.1, 1.85, 9.5, "october_stream_scoring.log + Hive count")
term(s, "clock 20:00  108 cities warned -> 2 sent\n  Hisar new warning (AQI 463 Severe)\n  Fatehabad new warning (AQI 418)\nclock 21:00   93 warned -> 2 sent, 2 suppressed\n  (already sent 1.0 h ago)\nclock 02:00   0 under warning, 0 sent",
     0.6, 5.7, 4.1, 1.25, 9, "hourly_dedupe_demo.log — dry-run replay")
pic(s, "site_top.png", 4.9, 1.3, 5.2, 5.5)
text(s, "Public warning board (AirWatch_India.html): 221 cities, worst forecast first; search, severity filter, WhatsApp share, “Alert me” notification.", 10.3, 1.4, 2.45, 2.6, 11.5, False, GREY)
callout(s, "Telegram delivery is built and dry-run tested; a live message needs the bot token.", 10.3, 4.4, 2.45, 1.5, 11, WARN)

# ---- A6 claim -> proof index ----
s = new_slide("Appendix — Claim to Evidence Index",
              "If asked how we know a number, open the named file. All logs are preserved in docs/run_logs; screenshots are in this appendix.")
table(s, ["Claim", "Where the proof is"], [
    ["154,583,979 rows, one schema", "spark_on_yarn_demo.log, merge_run.log (A2)"],
    ["4 DataNodes, replication 3, HEALTHY", "dfsadmin + fsck screenshots (A1)"],
    ["Spark job ran on YARN, read HDFS", "YARN UI screenshots + spark_on_yarn_demo.log (A2)"],
    ["146,276,379 rows cleaned, 241 city partitions", "CleanSelect run + HDFS browse (A3)"],
    ["93,216,105 labelled rows, 86 features", "phase4_fullscale.log (A3)"],
    ["R² 0.8910 vs 0.8587, RMSE − 12.18 %", "trackB_train_fullscale.summary.log (A4)"],
    ["CPCB vs CAMS cross-validation", "crossval.log, scripts/04_cross_validate_overlap.py (A4)"],
    ["Oct 2026: 82,800 rows → 27,543 alerts", "october_live_cycle.log, october_stream_scoring.log (A5)"],
    ["De-duplicated alert dispatch", "hourly_dedupe_demo.log, scripts/send_alerts.py (A5)"],
    ["Hive tables and Delhi seasonality", "hive_create.log, hive_queries.log"],
    ["Every number reproducible", "scripts/_audit/ (15 scripts), docs/WORK_LOG.md, PROJECT_REPORT.pdf"]], 0.6, 1.3, 12.15, [5.0, 7.15], 12.5, 0.46)

prs.save(OUT)
print("saved", OUT, len(prs.slides), "slides")
