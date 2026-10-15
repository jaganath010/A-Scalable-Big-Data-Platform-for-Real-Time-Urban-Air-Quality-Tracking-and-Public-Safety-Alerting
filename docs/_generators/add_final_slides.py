"""Appends the FINAL-REVIEW slides to the 1st-review deck (original slides untouched).
Same look as the original: blank layout, 0B5F8A top rule, 28 pt bold titles, blue table headers.
Usage: IMG=<screenshot dir> python add_final_slides.py <1st_review.pptx> <out.pptx>
Every number is a measured value from docs/run_logs."""
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


# ======================= 1. Final outputs at a glance =======================
s = new_slide("Final Outputs — Results at a Glance",
              "Everything since the first review. These four numbers are the headline; each is backed by a preserved log shown in the evidence slides.")
stat(s, 0.7, 1.4, 2.85, 1.35, "154,583,979", "rows in one unified table (33 GB)", size=24)
stat(s, 3.75, 1.4, 2.85, 1.35, "R² 0.8910", "GBT vs 0.8587 persistence, real rows")
stat(s, 6.8, 1.4, 2.85, 1.35, "27,543", "warnings, 1–15 Oct 2026, 221 cities", RED)
stat(s, 9.85, 1.4, 2.78, 1.35, "93.2 M", "labelled rows, 86 features")
table(s, ["Layer", "Format", "Rows", "Period", "Its job"], [
    ["Structured — CPCB stations", "Flat CSV", "146,276,379", "2010 – 2023", "TRAIN the model"],
    ["Semi-structured — CAMS history", "Nested JSON", "8,263,440", "2022-08 → 2026-09", "VALIDATE the data"],
    ["Semi-structured — CAMS live", "Nested JSON", "44,160", "rolling window", "ALERT people now"],
], 0.7, 3.1, 11.93, [3.6, 1.7, 1.9, 2.6, 2.13], 13, 0.5)
callout(s, "Honest framing: 88.9 % of the structured rows are synthetic, so every accuracy figure that follows is quoted on real rows only.", 0.7, 5.15, 11.93, 0.8, 14, WARN)
text(s, "Phase 4 (feature engineering) at full scale: 146.3 M → 128.7 M after de-duplication → 93.2 M with a valid T+1 label; 73.5 min, 19.7 GB, 241 city partitions.", 0.7, 6.15, 11.93, 0.7, 14, False, GREY)

# ======================= 2. GBT: how it works =======================
s = new_slide("Gradient Boosted Trees (GBT) — How the Forecaster Works",
              "Each tree corrects the mistakes of the ones before it; the forecast is the sum of all 300 trees, each scaled by a small step size.")
for x, w, t, fill, white in [(0.7, 2.0, "baseline\nprediction", RGBColor(0x0D, 0x3B, 0x5E), True), (3.15, 1.7, "η · tree 1", RGBColor(0xDC, 0xEB, 0xF4), False),
                             (5.3, 1.7, "η · tree 2", RGBColor(0xDC, 0xEB, 0xF4), False), (8.05, 1.9, "η · tree 300", RGBColor(0xDC, 0xEB, 0xF4), False),
                             (10.5, 2.1, "forecast", MAROON, True)]:
    rect(s, x, 1.4, w, 0.85, fill)
    text(s, t.split("\n"), x, 1.4, w, 0.85, 15, True, WHITE if white else INK, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
for x, t in [(2.75, "+"), (4.9, "+"), (7.0, "+ … +"), (10.05, "=")]:
    text(s, t, x, 1.4, 0.9 if len(t) > 1 else 0.4, 0.85, 24, True, MUTED, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
text(s, "How it learns", 0.7, 2.75, 5.8, 0.4, 18, True, BLUE)
bullets(s, ["Start from a simple baseline prediction", "Measure the errors left over (the residuals)", "Fit a small tree to those errors",
            "Add it, scaled by a small step size η = 0.08", "Repeat 300 times — each tree fixes what the others still get wrong"], 0.7, 3.25, 5.8, 3.4, 15, 8)
text(s, "Why GBT for this problem", 7.0, 2.75, 5.6, 0.4, 18, True, BLUE)
bullets(s, ["Captures non-linear interactions (wind × temperature × humidity) that a linear model cannot",
            "No feature scaling needed; copes with mixed units and one-hot flags",
            "Native to Spark MLlib — training is distributed across the data partitions",
            "Gives feature importance, so we can show what it actually uses"], 7.0, 3.25, 5.6, 3.4, 15, 8)

# ======================= 3. GBT: configuration + design choices =======================
s = new_slide("GBT Configuration and Two Design Choices",
              "Two choices decided the result. Predict the change, because trees are piecewise constant. Split by time, because consecutive hours correlate at 0.81 so a random split leaks.")
table(s, ["Setting", "Value", "Why"], [
    ["Trees / depth", "300 / 6", "small steps need many rounds; depth 6 = up to 64 leaves"],
    ["Step size η / row subsample", "0.08 / 0.8", "gradual correction; decorrelates the trees"],
    ["Feature subset / max bins", "sqrt (≈ 9 of 86) / 64", "random handful per split; histogram split search"],
    ["Target", "next-hour PM₂.₅ − current PM₂.₅", "predict the change, then add current back"],
    ["Training rows", "10,000,552", "seeded 13.41 % sample of 74.5 M (RAM ceiling)"],
    ["Test rows", "18,671,121", "not sampled — every row of the hold-out is scored"],
], 0.7, 1.4, 11.93, [3.0, 3.3, 5.63], 12, 0.44)


def col(x, head, lines):
    rect(s, x, 4.9, 5.85, 1.4, PANEL, LINE)
    text(s, head, x + 0.2, 4.97, 5.45, 0.4, 15, True, BLUE)
    text(s, lines, x + 0.2, 5.37, 5.45, 0.9, 12.5)


col(0.7, "Predict the change, not the level", ["Level target: R² 0.9098 (5.6 % better than persistence)", "Change target: R² 0.9201 (11.3 % better) — about double the gain"])
col(6.78, "Split by time, never at random", ["Consecutive hours correlate ≈ 0.81 — a random split leaks the answer", "Test = 2022-07-01 → 2023-03-31, the most recent window"])
callout(s, "Persistence gate: every run prints the “next hour = this hour” baseline on the same test rows and prints *** FAIL *** if the model does not beat it.", 0.7, 6.45, 11.93, 0.6, 12.5)

# ======================= 4. GBT results =======================
s = new_slide("GBT Results — The Forecaster Beats the Baseline",
              "Quote the real-rows figure: synthetic rows are easier, so the blended number would flatter us. RMSE 21.8 vs 24.8 is a 12.18 percent reduction.")
bar(s, ["Persistence (next hour = this hour)", "GBT forecaster"], [24.831, 21.806], 0.7, 1.4, 5.2, 4.3, colors=[MUTED, BLUE], fmt="0.00", maxv=30)
text(s, "RMSE in µg/m³, lower is better — real station-hours, n = 2,074,569", 0.7, 5.75, 5.2, 0.5, 12, False, MUTED, True)
table(s, ["Real rows (n = 2,074,569)", "R²", "RMSE", "MAE"], [
    ["Persistence baseline", "0.8587", "24.831", "9.937"],
    ["GBT forecaster", ("0.8910", GREEN), ("21.806", GREEN), ("8.926", GREEN)],
    ["Improvement", "+ 0.0323", "− 12.18 %", "− 1.011"]], 6.3, 1.4, 6.33, [2.9, 1.1, 1.2, 1.13], 13, 0.5, bold_rows=(1,))
table(s, ["All rows (n = 18,671,121)", "R²", "RMSE", "MAE"], [
    ["Persistence baseline", "0.8563", "25.443", "10.357"],
    ["GBT forecaster", "0.8884", "22.429", "9.353"],
    ["Improvement", "+ 0.0321", "− 11.85 %", "− 1.004"]], 6.3, 3.5, 6.33, [2.9, 1.1, 1.2, 1.13], 13, 0.5)
callout(s, "PASS — beats persistence by 0.0323 R² on real rows. The 19-city / 120-tree pilot gave 5.67 %; scaling to 241 cities and 300 trees doubled it.", 6.3, 5.65, 6.33, 0.95, 13)

# ======================= 5. Feature importance =======================
s = new_slide("What the Model Learned to Look At",
              "pm25_was_imputed ranks 6th of 86: the model taught itself to distrust filled-in readings.")
names = ["pm25  (current level)", "pm25_delta_1h  (rising / falling)", "pm25_surge_ratio  (spike under way)", "pm25_lag_1h  (previous hour)", "pm25_roll_3h  (3-hour trend)",
         "pm25_was_imputed  (filled, not measured)", "pm25_std_6h  (recent volatility)", "pm25_avg24h  (daily mean)", "aqi_roll_6h  (6-hour AQI trend)", "pm25_roll_6h  (6-hour trend)"]
vals = [0.1011, 0.0758, 0.0688, 0.0594, 0.0542, 0.0535, 0.0397, 0.0331, 0.0315, 0.0309]
bar(s, names, vals, 0.7, 1.35, 7.7, 5.4, horizontal=True, fmt="0.000")
text(s, "Reading the chart", 8.8, 1.4, 3.9, 0.4, 18, True, BLUE)
bullets(s, ["Where you are now, and which way you are moving, matter most", "Time of day and weather contribute further down the 86 inputs"], 8.8, 1.9, 3.9, 1.8, 14)
callout(s, "pm25_was_imputed is 6th of 86. The model learned to discount filled-in readings — direct evidence that flagging every imputed value was the right call.", 8.8, 3.9, 3.85, 2.1, 14, WARN)

# ======================= 6. Streaming + live alerts =======================
s = new_slide("Live Alerting — Streaming Speed Layer and Warnings",
              "10-second micro-batches; about 7 seconds latency once warm. The October batch scored 82,800 rows (230 cities x 360 hours, 1-15 Oct 2026) in 58 s and raised 27,543 warnings; ozone drove 44 percent, coarse dust 36 percent.")
bar(s, ["batch 0", "batch 1", "batch 2", "batch 3", "October batch"], [10.75, 7.82, 7.02, 6.89, 57.82], 0.7, 1.35, 5.6, 3.2, colors=[BLUE] * 4 + [TEAL], fmt='0.0" s"', maxv=70)
text(s, "Latency per micro-batch. Batches 0–3: 120-row replay; October batch: 82,800 rows (1–15 Oct).", 0.7, 4.55, 5.6, 0.4, 12, False, MUTED, True)
bar(s, ["Moderate", "Poor", "Very Poor", "Severe"], [14475, 7756, 2673, 2639], 6.8, 1.35, 5.8, 3.2, colors=[AMBER, RGBColor(0xE8, 0x73, 0x1A), RED, MAROON], fmt="0")
text(s, "Warnings by CPCB severity — 27,543 in total (October)", 6.8, 4.55, 5.8, 0.4, 12, False, MUTED, True)
stat(s, 0.7, 5.15, 2.8, 1.35, "221", "cities under warning (of 230)", RED)
stat(s, 3.7, 5.15, 2.8, 1.35, "AQI 500", "Hisar, Bhiwani, Karnal … (dust)", MAROON)
stat(s, 6.8, 5.15, 2.8, 1.35, "44 %", "of warnings ozone-driven; 36 % dust")
stat(s, 9.8, 5.15, 2.83, 1.35, "32", "cities forecast Severe (AQI > 400)")

# ======================= 7. Website =======================
s = new_slide("Final Output — The Public Warning Board",
              "This is the deliverable: a message residents could act on. Every number came from a Hive query; the page is one HTML file that opens with the cluster off.")
pic(s, "site_top.png", 0.7, 1.3, 7.0, 5.6)
text(s, "What a resident sees", 8.1, 1.4, 4.5, 0.4, 18, True, BLUE)
bullets(s, ["Headline: 221 cities under warning for October, worst forecast first", "Search by city, filter by severity",
            "Each card is the actual message: forecast AQI, the hour, the cause, CPCB health advice", "India map, warnings per hour, cause breakdown"], 8.1, 1.9, 4.5, 3.2, 14)
text(s, "How it is built", 8.1, 5.1, 4.5, 0.4, 16, True, BLUE)
text(s, "Hive → export job → one JSON → embedded in a single HTML file. No server and no internet needed to open it.", 8.1, 5.5, 4.5, 1.2, 14, False, GREY)

# ======================= 8. Truthfulness =======================
s = new_slide("How We Know the Dataset Is Truthful",
              "Two independent lines of evidence. The CAMS result is mixed and is reported as mixed.")
text(s, "1. Five paired tests — synthetic vs its own real parent", 0.7, 1.35, 6.2, 0.4, 16, True, BLUE)
table(s, ["#", "Test", "The cheat it catches"], [
    ["1", "Persistence R²", "Fake data easier to predict than real"], ["2", "Autocorrelation, lags 1–6 h", "Random noise or over-smoothing"],
    ["3", "Quantiles p5–p95", "Drift and inflated variance"], ["4", "Missingness rate", "Gaps filled in to look easy"],
    ["5", "Cross-correlation", "Noise that breaks pollutant links"]], 0.7, 1.85, 6.2, [0.5, 2.5, 3.2], 12, 0.48)
text(s, "The first generator scored 0.856 synthetic vs 0.733 real on test 1 — it would have failed. The final one passes; FAIL is blocking.", 0.7, 4.9, 6.2, 1.0, 14, False, GREY)
text(s, "11 defects found by running the pipeline (4 in data, 7 in code); two gave plausible wrong answers with no error — so every output count is reconciled against a known number.", 0.7, 5.8, 6.2, 1.1, 13, False, GREY, True)
text(s, "2. Independent check — CPCB vs CAMS, 1,152,707 city-hours", 7.3, 1.35, 5.4, 0.4, 16, True, BLUE)
bar(s, ["PM₂.₅", "PM₁₀", "O₃", "NO₂", "SO₂"], [0.565, 0.558, 0.361, 0.219, 0.083], 7.3, 1.8, 5.35, 3.6, colors=[BLUE, BLUE, AMBER, AMBER, RED], fmt="0.000", maxv=1)
text(s, "Pearson correlation", 7.3, 5.4, 5.35, 0.3, 12, False, MUTED, True)
callout(s, "Mixed, and reported as mixed: particulates track moderately, SO₂ shows essentially no agreement.", 7.3, 5.85, 5.35, 0.95, 13, WARN)

# ======================= 9. Evidence: cluster =======================
s = new_slide("Evidence — HDFS, YARN and a Spark Job on the Cluster",
              "Live screenshots of the cluster plus the log of a Spark job run under YARN that recounted the unified table to 154,583,979.")
pic(s, "hdfs_dn_crop.png", 0.7, 1.3, 5.9, 2.65)
pic(s, "yarn_nodes_crop.png", 6.8, 1.3, 5.85, 2.65)
text(s, "HDFS NameNode UI — 4 live DataNodes, replication 3, 0 corrupt / missing blocks", 0.7, 4.0, 5.9, 0.5, 12.5, True, BLUE)
text(s, "YARN ResourceManager UI — 1 RM + 4 NodeManagers, all RUNNING", 6.8, 4.0, 5.85, 0.5, 12.5, True, BLUE)
term(s, "master     : yarn\napp id     : application_1792046046524_0001\n|semistructured_json|cams_history|8263440  |230\n|semistructured_json|live_api    |44160    |230\n|structured_csv     |real        |16252931 |241\n|structured_csv     |synthetic   |130023448|241\nTOTAL rows: 154,583,979   (expected 154,583,979 -> True)",
     0.7, 4.55, 7.7, 2.1, 11, "spark_on_yarn_demo.log")
bullets(s, ["master: yarn — not local mode", "Data read from hdfs://namenode:9000", "Count reconciles to the known total", "2nd YARN app: October live enrichment, 82,800 rows"], 8.7, 4.6, 3.95, 2.1, 13)

# ======================= 10. Evidence: logs + index =======================
s = new_slide("Evidence — Training, Streaming and Where Each Claim Is Proved",
              "All logs are preserved in docs/run_logs. If asked how we know a number, open the named file.")
term(s, "train 10,000,552 rows | test 18,671,121 rows\nPERSISTENCE BASELINE  R2=0.8563 RMSE=25.443\ntrained on 10,000,552 rows, 300 trees\nREAL ROWS ONLY (n=2,074,569)\n  persistence baseline  0.8587  24.831  9.937\n  GBT model             0.8910  21.806  8.926\n  RMSE reduction        12.18%\nPASS (real rows): beats persistence by 0.0323 R2",
     0.7, 1.35, 6.3, 2.4, 11, "trackB_train_fullscale.summary.log")
term(s, "[batch 0] no history yet - first run\n[batch 0] *** 27543 ALERTS ***\n[batch 0] rows in=82,800  predicted=82,800\n  alerts=27,543  latency=57,820 ms\n(1-15 Oct 2026, 230 cities, 221 warned)",
     7.2, 1.35, 5.45, 2.4, 11, "october_stream_scoring.log")
table(s, ["Claim", "Evidence in docs/run_logs"], [
    ["154,583,979 rows, one schema", "merge_run.log · spark_on_yarn_demo.log"],
    ["Phase 4: 93,216,105 labelled rows, 86-dim", "phase4_fullscale.log"],
    ["GBT R² 0.8910 vs 0.8587", "trackB_train_fullscale.summary.log"],
    ["October live data: 82,800 rows enriched on YARN, 27,543 warnings", "october_live_cycle.log · october_stream_scoring.log"],
    ["CPCB vs CAMS cross-validation", "crossval.log · 04_cross_validate_overlap.py"],
    ["Hive tables and queries", "hive_create.log · hive_queries.log"]], 0.7, 4.25, 11.95, [5.2, 6.75], 12, 0.4)

# ======================= 11. Semi-structured layers + unified table =======================
s = new_slide("Semi-Structured Layers and the Unified Table",
              "Why CAMS starts in August 2022: the source rejects dates before 2013 and returns 100 percent nulls until July 2022. Delivering 2010-2023 would look like coverage and contain nothing.")
text(s, "Why CAMS coverage starts in August 2022", 0.7, 1.35, 5.9, 0.4, 16, True, BLUE)
table(s, ["Dates requested", "What the API returned"], [
    ["before 2013-01-01", "rejected: out of allowed range"], ["2013-01 → 2022-07", "timestamps, every value null (0 % fill)"],
    ["2022-08", "89.7 % fill — real data begins"], ["2022-09 onward", "≈ 99.8 % fill (ammonia 0 %)"]], 0.7, 1.85, 5.9, [2.1, 3.8], 12.5, 0.5)
text(s, "230 of 241 cities resolved; 11 small localities had no geocode and were excluded rather than given invented coordinates.", 0.7, 4.6, 5.9, 0.9, 13.5, False, GREY)
text(s, "One table, one schema (17 columns)", 7.0, 1.35, 5.6, 0.4, 16, True, BLUE)
table(s, ["data_source", "rows", "cities"], [
    ["synthetic", "130,023,448", "241"], ["real", "16,252,931", "241"], ["cams_history", "8,263,440", "230"], ["live_api", "44,160", "230"],
    ["TOTAL", "154,583,979", ""]], 7.0, 1.85, 5.6, [2.3, 2.1, 1.2], 12.5, 0.5, bold_rows=(4,))
text(s, "Flat CSV and nested JSON are read by their native Spark readers and unioned in one job (Variety). Re-counted live on YARN: 154,583,979.", 7.0, 5.0, 5.6, 1.0, 13.5, False, GREY)
callout(s, "Why three layers? Only the structured layer has the label and 13 years of seasonality; only CAMS is an independent source on the same cities and hours; only live data can warn anyone now.", 0.7, 6.0, 11.93, 0.85, 13.5)

# ======================= 12. Phase 4 =======================
s = new_slide("Phase 4 at Full Scale — 93.2 M Labelled Rows",
              "73.5 minutes. Every checkpoint matched the runbook. The T+1 rule drops rows without a genuine next hour instead of mislabelling them.")
bar(s, ["Loaded from clean layer", "After dedupe (station, hour)", "With a valid T+1 label", "Assemblable into a vector"], [146.28, 128.66, 93.22, 93.22], 0.7, 1.35, 7.7, 4.9, horizontal=True, fmt='0.0" M"')
stat(s, 8.8, 1.45, 3.85, 1.15, "73.5 min", "feature job, distributed Spark")
stat(s, 8.8, 2.75, 3.85, 1.15, "19.7 GB", "written · 241 city partitions")
stat(s, 8.8, 4.05, 3.85, 1.15, "86 dims", "54 numeric + 32 one-hot")
text(s, "Label rule: next_ts must equal ts + 3600 s. 12.3 % of rows had no true next hour and were dropped, not guessed.", 8.8, 5.4, 3.85, 1.2, 13, False, GREY)

# ======================= 13. Live enrichment =======================
s = new_slide("Live Enrichment — Making the Live Feed Model-Ready",
              "Raw CAMS JSON carries only 28 of the model's 54 numeric features; one Spark job on YARN joined CAMS, weather and city profiles to close the gap.")
table(s, ["Missing from raw CAMS JSON", "n", "Real source used"], [
    ["Weather: temperature, humidity, wind, rain, pressure, solar", "8", "Open-Meteo weather API (no key)"],
    ["Derived: ventilation, scrub factor, stagnation, is_raining ...", "5", "Computed once weather exists"],
    ["traffic_index, is_rush_hour, urbanization_index", "3", "city_profiles.csv"],
    ["*_was_imputed provenance flags", "10", "0 if the API returned a value, else 1"]], 0.7, 1.4, 11.93, [6.2, 0.6, 5.13], 13, 0.6)
stat(s, 0.7, 4.85, 2.9, 1.2, "82,800", "live rows · 230 cities · 1–15 Oct", TEAL)
stat(s, 3.8, 4.85, 2.9, 1.2, "0 nulls", "on model-critical columns", TEAL)
text(s, "Unit conversions, measured", 7.1, 4.8, 5.5, 0.4, 16, True, BLUE)
bullets(s, ["CO: µg/m³ → mg/m³ (÷ 1000); unconverted, CPCB avg 0.95 vs CAMS 566", "Pressure: hPa → mmHg (× 0.750062) = 753.81, matches structured median 753"], 7.1, 5.25, 5.55, 1.4, 13)
text(s, "Ran as a YARN application: CAMS window = weather window = 2026-10-01 → 10-15, 82,800 rows joined.", 0.7, 6.3, 6.0, 0.8, 12.5, False, GREY)

# ======================= 14. Hive =======================
s = new_slide("Hive Serving Layer",
              "External tables over the Parquet already in HDFS: SQL over 154 million rows at zero storage cost. Delhi's 5.5x seasonal swing is why 13 years of history is needed.")
table(s, ["Object", "Over", "Purpose"], [
    ["unified_airquality", "154.6 M rows", "structured + semi-structured, one schema"], ["clean_airquality", "146.3 M rows", "Phase 3 output, by city"],
    ["stream_alerts", "27,543 warnings", "October alerts (Sept archived)"], ["3 views", "views", "live / alert / compare answers"]], 0.7, 1.4, 6.0, [2.2, 1.4, 2.4], 12, 0.62)
bullets(s, ["EXTERNAL tables: no data copied; DROP removes metadata only", "HiveServer2 Thrift (port 10000) for beeline / JDBC", "All six demo queries return real results"], 0.7, 4.7, 6.0, 1.8, 13.5)
cd = CategoryChartData()
cd.categories = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
cd.add_series("PM2.5", [180.5, 127.9, 88.6, 86.8, 79.5, 66.3, 44.0, 38.8, 47.1, 120.1, 213.6, 199.4])
ch = s.shapes.add_chart(XL_CHART_TYPE.LINE_MARKERS, Inches(7.0), Inches(1.35), Inches(5.65), Inches(4.2), cd).chart
ch.has_legend = False
ch.has_title = False
ch.font.size = Pt(11)
ch.font.color.rgb = GREY
pl = ch.plots[0]
pl.has_data_labels = True
pl.data_labels.font.size = Pt(10)
pl.data_labels.number_format = "0"
pl.data_labels.number_format_is_linked = False
pl.data_labels.position = XL_LABEL_POSITION.ABOVE
pl.series[0].format.line.color.rgb = BLUE
pl.series[0].format.line.width = Pt(2.5)
ch.value_axis.major_gridlines.format.line.color.rgb = RGBColor(0xE6, 0xEA, 0xF0)
ch.value_axis.minimum_scale = 0
callout(s, "Delhi, measured values only: 5.5× swing, August low 38.8 → November peak 213.6 (µg/m³).", 7.0, 5.7, 5.65, 0.9, 13)

# ======================= 15. Defects =======================
s = new_slide("Eleven Defects Found — and How Each Was Caught",
              "Four in the data, seven in code written but never run. Two gave plausible wrong answers with no error. The habit that caught them: reconcile output counts against an independently known number.")
text(s, "In the dataset (4)", 0.7, 1.35, 5.4, 0.35, 16, True, BLUE)
table(s, ["Defect", "Fix"], [["Flags not binary (24,725 distinct values)", "round to 0 / 1"], ["T+1 label via lead(): 8.69 % wrong horizon", "require ts + 3600 s"],
                             ["Impossible values: humidity 104.999 %", "clamp to range"], ["Only 43 % rows have all 7 pollutants", "3-tier imputation, flagged"]], 0.7, 1.75, 5.5, [3.5, 2.0], 12, 0.6)
text(s, "In the pipeline (7) — found only by running it", 6.5, 1.35, 6.1, 0.35, 16, True, BLUE)
table(s, ["Defect", "Caught by"], [["Substring join double-counted Mumbai / Noida", "44,544 ≠ 44,160 rows"], ["Streaming used ts_unix before it existed", "alerts printed, then a stall"],
                                  ["VectorAssembler dropped every live row", "16,560 in, 0 out, no error"], ["paths.py built hdfs:////host", "printed the resolved path"], ["HDFS write died: no spare DataNode", "full-scale write failure"],
                                  ["numpy missing in the Spark image", "training failed at import"], ["Hive column that does not exist", "NULL timestamps, counts fine"]], 6.5, 1.75, 6.15, [3.7, 2.45], 12, 0.5, bold_rows=(2, 6))
callout(s, "Two gave plausible wrong answers with no error. A silent wrong answer is more dangerous than a crash — reconcile every output count against a known number.", 0.7, 4.75, 5.5, 1.7, 13.5, RGBColor(0xF9, 0xE3, 0xE1))

# ======================= 16. Five V's =======================
s = new_slide("The Five V's — Each One Demonstrated", "Each V has a concrete measured proof, not a claim.")
G = ("demonstrated", GREEN)
table(s, ["V", "Evidence", "State"], [
    ["Volume", "154,583,979 rows · 33 GB · 1 NameNode + 4 DataNodes · fsck HEALTHY", G],
    ["Variety", "Flat CSV and nested JSON read by native Spark readers into one schema; Hive spans both", G],
    ["Velocity", "Structured Streaming, 10 s micro-batches, ≈ 7 s latency on replay; 82,800 live rows scored, 27,543 alerts", G],
    ["Veracity", "5 paired tests, independent CAMS check, 11 defects found and fixed, every fill flagged", G],
    ["Value", "R² 0.8910 vs 0.8587 on 2.07 M real rows — an hour of warning before pollution arrives", G]], 0.7, 1.5, 11.93, [1.5, 8.6, 1.83], 14, 0.85)

# ======================= 17. Challenges =======================
s = new_slide("Challenges and Limitations",
              "Every challenge was hit, diagnosed and resolved. The limitations are stated before being asked.")
table(s, ["Challenge", "Root cause", "Resolution"], [
    ["Spark could not write to HDFS from the host", "NameNode returns container-internal DataNode addresses", "Run Spark inside the cluster network"],
    ["Full-scale write died after computing", "DataNodes unresponsive under memory pressure; no spare node", "Driver 7→5 GB, replication 2, 180 s timeouts"],
    ["YARN executors killed (exit 137)", "4 × 3 GB NodeManagers advertise 12 GB on a 15.7 GB host", "Phase 4 in local mode; YARN proven by enrichment job"],
    ["Shuffle spill filled the C: drive", "Scratch lives in the WSL2 disk (peaked 65 GB)", "Guard job kills below 30 GB free; never tripped"],
    ["Live rows silently dropped", "VectorAssembler skip + CAMS ammonia always null", "Fill after flagging provenance"]], 0.7, 1.35, 11.93, [3.5, 4.4, 4.03], 12, 0.62)
callout(s, "Limitations: 88.9 % of structured rows are synthetic (results reported on real rows) · trained on a 10 M-row sample of 74.5 M (RAM ceiling; evaluation not sampled) · the page is a snapshot of the 1–15 Oct run, scored as one batch with cold-start history · 230 of 241 cities · SO₂ agreement with CAMS is poor.", 0.7, 5.6, 11.93, 1.1, 13, WARN)

# ======================= 18. Conclusion =======================
s = new_slide("Conclusion and Future Work", "The platform does what its title says: a measured, reproducible, honest pipeline.")
text(s, "What has been demonstrated", 0.7, 1.4, 5.9, 0.4, 18, True, GREEN)
bullets(s, ["A fault-tolerant 4-node HDFS lakehouse of 154.6 M rows, verified HEALTHY", "Spark on YARN running cleaning, feature engineering and a 300-tree GBT",
            "A forecaster 12.18 % better than the honest baseline on 2.07 M real rows", "Live data enriched on YARN and scored by the stream: 27,543 October warnings",
            "Hive serving and a public warning board with the message residents receive"], 0.7, 1.9, 5.9, 4.6, 14.5, 8)
text(s, "Future work", 7.0, 1.4, 5.6, 0.4, 18, True, BLUE)
bullets(s, ["Connect a paid SMS gateway and schedule the dispatcher daily (Telegram / e-mail already built)", "Compare against Random Forest and XGBoost baselines", "Neighbour-station features for a GraphX station-network model",
            "Resolve the 11 unmatched localities; add ground-truth SO₂ validation", "Larger multi-host cluster so the full 74.5 M rows can train"], 7.0, 1.9, 5.6, 4.6, 14.5, 8)

# ======================= 19. Alert delivery =======================
s = new_slide("Alerting the Public — From Forecast to Message",
              "The last hop of the pipeline: stream_alerts becomes a resident-facing message and is dispatched. Run here as a dry run; real delivery needs a Telegram bot token or SMTP login, supplied as environment variables.")
text(s, "Pipeline: forecast AQI > 150  →  worst warning per city  →  message + CPCB health advice  →  channels", 0.7, 1.35, 11.93, 0.4, 15, True, BLUE)
term(s, "AIR QUALITY WARNING - Hisar\nExpected by 12 Oct, 08:00: AQI 500 (Severe), mainly coarse\ndust (PM10).\nAvoid all outdoor activity. Seek care if breathing is\ndifficult. Keep windows closed.\nSource: AirWatch India forecast, CPCB National AQI.",
     0.7, 1.9, 6.4, 2.6, 12, "alert_dispatch_demo.log — message built from a real stream_alerts row")
table(s, ["Channel", "Enabled by", "Status"], [
    ["Outbox log + console", "always on", ("working", GREEN)], ["Telegram push (phone)", "bot token + chat id", "ready — needs token"],
    ["E-mail", "SMTP login", "ready — needs login"], ["SMS", "paid gateway (Twilio / MSG91)", "next step"]], 7.4, 1.9, 5.25, [1.9, 1.9, 1.45], 11.5, 0.55)
bullets(s, ["Subscribers pick a city; each person receives only their own city's warnings", "Run as a dry run unless credentials are set — it never claims a phone was reached when it was not", "Code: scripts/send_alerts.py (not yet scheduled; it is a standalone step after the daily live cycle)"], 0.7, 4.85, 11.93, 1.8, 14)

# ---------------------- keep only the important first-review slides, order everything ----------------------
lst = prs.slides._sldIdLst
els = list(lst)
orig, new = els[:n_orig], els[n_orig:]
keep_orig = [0, 2, 3, 5, 6, 7, 9, 11, 12]          # title, problem, objectives, method, cluster, raw data, preprocess run, quality, spark on YARN
order_new = [0, 10, 11, 12, 1, 2, 3, 4, 5, 18, 13, 6, 7, 14, 8, 9, 15, 16, 17]
final = [orig[i] for i in keep_orig] + [new[i] for i in order_new] + [orig[18]]   # orig[18] = References
for el in els:
    lst.remove(el)
for el in orig:
    if el not in final:
        prs.part.drop_rel(el.rId)
for el in final:
    lst.append(el)
for sh in prs.slides[0].shapes:
    if sh.has_text_frame:
        for p in sh.text_frame.paragraphs:
            for r in p.runs:
                r.text = r.text.replace("First Review", "Final Review")
prs.save(OUT)
print("saved", OUT, len(prs.slides), "slides")
