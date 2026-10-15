"""
Generates docs/HADOOP_SPARK_CHEATSHEET.pdf - a one-page quick-start card for
bringing the Docker Hadoop cluster and Spark client up and down.

Deps:  pip install reportlab
Run :  python build_cheatsheet.py      (writes HADOOP_SPARK_CHEATSHEET.pdf here)

Kept deliberately to ONE page: it is meant to sit next to the keyboard during
a demo/viva, not to be read. If content is added, tighten the styles at the top
rather than letting it spill to page 2.
"""

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (HRFlowable, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

NAVY = colors.HexColor("#1F3864")
ACCENT = colors.HexColor("#2E74B5")
CODE_BG = colors.HexColor("#F2F2F2")
LIGHT = colors.HexColor("#DDEBF7")

styles = getSampleStyleSheet()
title_style = ParagraphStyle("TitleX", parent=styles["Title"], textColor=NAVY, fontSize=18, spaceAfter=1)
subtitle_style = ParagraphStyle("SubtitleX", parent=styles["Normal"], textColor=ACCENT, fontSize=10, spaceAfter=7)
h2 = ParagraphStyle("H2X", parent=styles["Heading2"], textColor=NAVY, fontSize=11.5, spaceBefore=6, spaceAfter=3)
body = ParagraphStyle("BodyX", parent=styles["Normal"], fontSize=8.8, leading=11.5, alignment=TA_LEFT)
note = ParagraphStyle("NoteX", parent=styles["Normal"], fontSize=8, leading=10, textColor=colors.HexColor("#555555"))
code = ParagraphStyle("CodeX", parent=styles["Normal"], fontName="Courier", fontSize=8.6,
                      leading=11, backColor=CODE_BG, borderPadding=(3, 6, 3, 6),
                      leftIndent=2, spaceBefore=1, spaceAfter=4)


def step(num, title_text, cmd_text, note_text=None):
    out = [Paragraph(f"<b>Step {num} — {title_text}</b>", body),
           Paragraph(cmd_text.replace("\n", "<br/>"), code)]
    if note_text:
        out.append(Paragraph(note_text, note))
    return out


story = [
    Paragraph("HADOOP + SPARK — QUICK START", title_style),
    Paragraph("Air Quality Big Data Platform &nbsp;|&nbsp; 23AID302 &nbsp;|&nbsp; Docker cluster cheat sheet",
              subtitle_style),
    HRFlowable(width="100%", thickness=1.2, color=NAVY, spaceAfter=8),
    Paragraph("A. Start Hadoop (HDFS cluster)", h2),
]

for b in step(1, "Open Docker Desktop",
              "Double-click the Docker Desktop icon.\n"
              "Wait ~30-60s until the whale icon in the system tray stops animating."):
    story.append(b)
for b in step(2, "Open a terminal", "PowerShell or Command Prompt"):
    story.append(b)
for b in step(3, "Start the 5 containers",
              "docker start aq-namenode aq-datanode1 aq-datanode2 aq-datanode3 aq-datanode4",
              "You should see all 5 names printed back."):
    story.append(b)
for b in step(4, "Wait for safe mode OFF",
              "docker exec aq-namenode hdfs dfsadmin -safemode get",
              "Re-run every few seconds until it says <b>Safe mode is OFF</b> (usually &lt; 1 min)."):
    story.append(b)
for b in step(5, "Open the dashboard in your browser", "http://localhost:9870",
              "Shows Live Nodes: 4. Utilities &#8594; Browse the file system to see uploaded data."):
    story.append(b)
for b in step(6, "(Optional) Health check from terminal",
              "docker exec aq-namenode hdfs dfsadmin -report",
              "Look for <b>Live datanodes: 4</b>, 0 corrupt / missing / under-replicated blocks."):
    story.append(b)

story.append(Paragraph("B. Start Spark (runs inside the cluster)", h2))
for b in step(7, "Start the Spark client container", "docker start aq-spark"):
    story.append(b)
for b in step(8, "Submit a job",
              "docker exec aq-spark /opt/spark/bin/spark-submit /scripts/01_clean_select.py",
              "Always use the full path <font face='Courier'>/opt/spark/bin/spark-submit</font> — "
              "it is not on the container's PATH."):
    story.append(b)
for b in step(9, "Watch it run", "http://localhost:4050",
              "The Spark UI is only live <b>while a job is running</b>. Between jobs the page will "
              "look empty or refuse to connect — that is normal, not an error."):
    story.append(b)

story.append(Paragraph("C. Stop everything (end of session)", h2))
for b in step(10, "Stop the containers",
              "docker stop aq-spark aq-namenode aq-datanode1 aq-datanode2 aq-datanode3 aq-datanode4",
              "Data is preserved — it lives on bind mounts (D:\\hdfs\\dnN) and the namenode_meta "
              "volume, not inside the containers. Repeat Section A/B next time."):
    story.append(b)

story += [Spacer(1, 3),
          HRFlowable(width="100%", thickness=0.7, color=colors.HexColor("#AAAAAA"), spaceAfter=4),
          Paragraph("Quick Reference", h2)]

data = [
    ["What", "URL / Command"],
    ["Hadoop NameNode dashboard", "http://localhost:9870"],
    ["Spark job UI (only while running)", "http://localhost:4050"],
    ["Check HDFS is healthy", "docker exec aq-namenode hdfs dfsadmin -report"],
    ["List files in HDFS", "docker exec aq-namenode hdfs dfs -ls -R /user/hadoop"],
    ["See what's running", "docker ps"],
]
t = Table(data, colWidths=[62 * mm, 108 * mm])
t.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), NAVY),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTNAME", (0, 1), (0, -1), "Helvetica"),
    ("FONTNAME", (1, 1), (1, -1), "Courier"),
    ("FONTSIZE", (0, 0), (-1, -1), 8.3),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BBBBBB")),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 3),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ("LEFTPADDING", (0, 0), (-1, -1), 6),
]))
story.append(t)

SimpleDocTemplate("HADOOP_SPARK_CHEATSHEET.pdf", pagesize=A4,
                  topMargin=13 * mm, bottomMargin=11 * mm,
                  leftMargin=16 * mm, rightMargin=16 * mm,
                  title="Hadoop + Spark Quick Start").build(story)
print("wrote HADOOP_SPARK_CHEATSHEET.pdf")
