# -*- coding: utf-8 -*-
"""SIH26002 submission deck, diagram/flowchart style - matching the visual
language of the reference deck the team supplied (colour-coded pill headers,
box-and-arrow flowcharts, hub-and-spoke benefit diagrams) rather than the
plainer bullet layout used before.

Same 6 slides, same official template, same honesty rules as the earlier
build: every figure is real, pulled from the running engine, never invented.
The instructions slide is dropped, as the template itself says to.

Usage: python build_visual.py <template.pptx> <out.pptx> <hero-image-dir>
"""
import sys
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

SRC, OUT = sys.argv[1], sys.argv[2]
HERO = Path(sys.argv[3])

INK   = RGBColor(0x1A, 0x1A, 0x1A)
GREY  = RGBColor(0x50, 0x50, 0x50)
RULE  = RGBColor(0xBF, 0xBF, 0xBF)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

# The reference deck's own palette, read off its shapes: an orange pill for
# stage headers, green-bordered cards for a flowing process, teal-bordered
# cards for a set of features, a blue hub-and-spoke diagram, and red text for
# section labels. Reused here rather than invented, since matching the
# reference was the point of the request.
ORANGE = RGBColor(0xED, 0x93, 0x2E)
ORANGE_FILL = RGBColor(0xFC, 0xE4, 0xC6)
GREEN  = RGBColor(0x6C, 0xA6, 0x3D)
GREEN_FILL = RGBColor(0xEE, 0xF5, 0xE4)
TEAL   = RGBColor(0x2E, 0x8B, 0x9B)
TEAL_FILL = RGBColor(0xE7, 0xF3, 0xF5)
BLUEBOX = RGBColor(0x2F, 0x6F, 0xB2)
BLUEBOX_FILL = RGBColor(0xE8, 0xF0, 0xFA)
REDTXT = RGBColor(0xC0, 0x00, 0x00)
PANEL  = RGBColor(0xF2, 0xF2, 0xF2)

F = "Calibri"

# ---------------------------------------------------------------- primitives

def tf_at(slide, x, y, w, h, anchor=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = Emu(0)
    tf.vertical_anchor = anchor
    return tf


def line(tf, text, size=11, bold=False, color=INK, first=False, after=0,
         align=PP_ALIGN.LEFT, spacing=1.1, italic=False, bullet=False):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    p.line_spacing = spacing
    p.space_after = Pt(after)
    prefix = "•  " if bullet else ""
    r = p.add_run(); r.text = prefix + text
    r.font.size = Pt(size); r.font.bold = bold; r.font.italic = italic
    r.font.name = F; r.font.color.rgb = color
    return p


def runs(tf, parts, size=11, first=False, after=0, spacing=1.1, bullet=False):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.line_spacing = spacing
    p.space_after = Pt(after)
    if bullet:
        r = p.add_run(); r.text = "•  "
        r.font.size = Pt(size); r.font.name = F; r.font.color.rgb = parts[0][2]
    for text, bold, color in parts:
        r = p.add_run(); r.text = text
        r.font.size = Pt(size); r.font.bold = bold
        r.font.name = F; r.font.color.rgb = color
    return p


def rect(slide, x, y, w, h, fill=None, border=None, width=1.25,
         shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.09):
    sh = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        try: sh.adjustments[0] = radius
        except Exception: pass
    if fill is None:
        sh.fill.background()
    else:
        sh.fill.solid(); sh.fill.fore_color.rgb = fill
    if border is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = border; sh.line.width = Pt(width)
    sh.shadow.inherit = False
    sh.text_frame.text = ""
    return sh


def card(slide, x, y, w, h, title, body=None, border=TEAL, fill=WHITE,
         title_size=11, body_size=9.5, title_color=None):
    rect(slide, x, y, w, h, fill, border, width=1.5)
    tf = tf_at(slide, x + 0.10, y + 0.08, w - 0.20, h - 0.16,
               anchor=MSO_ANCHOR.TOP if body else MSO_ANCHOR.MIDDLE)
    line(tf, title, title_size, bold=True, color=title_color or border,
         first=True, align=PP_ALIGN.CENTER, spacing=1.05,
         after=4 if body else 0)
    if body:
        line(tf, body, body_size, color=GREY, align=PP_ALIGN.CENTER, spacing=1.12)


def pill(slide, x, y, w, h, text, fill=ORANGE, color=WHITE, size=12.5):
    rect(slide, x, y, w, h, fill, None, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.45)
    tf = tf_at(slide, x, y, w, h, anchor=MSO_ANCHOR.MIDDLE)
    line(tf, text, size, bold=True, color=color, first=True, align=PP_ALIGN.CENTER)


def arrow_down(slide, cx, y, h=0.16, w=0.14, color=GREY):
    sh = slide.shapes.add_shape(MSO_SHAPE.DOWN_ARROW, Inches(cx - w / 2),
                                Inches(y), Inches(w), Inches(h))
    sh.fill.solid(); sh.fill.fore_color.rgb = color
    sh.line.fill.background(); sh.shadow.inherit = False
    sh.text_frame.text = ""
    return sh


def arrow_right(slide, x, cy, w=0.20, h=0.12, color=GREY):
    sh = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x),
                                Inches(cy - h / 2), Inches(w), Inches(h))
    sh.fill.solid(); sh.fill.fore_color.rgb = color
    sh.line.fill.background(); sh.shadow.inherit = False
    sh.text_frame.text = ""
    return sh


def bent_arrow(slide, x1, y1, x2, y2, color=GREY):
    """A simple elbow connector, used for the hub-and-spoke diagram."""
    from pptx.enum.shapes import MSO_CONNECTOR
    conn = slide.shapes.add_connector(MSO_CONNECTOR.ELBOW, Inches(x1), Inches(y1),
                                      Inches(x2), Inches(y2))
    conn.line.color.rgb = color
    conn.line.width = Pt(1.5)
    return conn


def picture(slide, path, x, y, w=None, h=None):
    return slide.shapes.add_picture(str(path), Inches(x), Inches(y),
                                    Inches(w) if w else None,
                                    Inches(h) if h else None)


def table(slide, x, y, w, rows, widths, row_h=0.30, head_h=0.28, size=9.5,
          head_size=9.5, aligns=None, head_fill=PANEL):
    n_rows = len(rows)
    shape = slide.shapes.add_table(n_rows, len(widths), Inches(x), Inches(y),
                                   Inches(w), Inches(head_h + row_h * (n_rows - 1)))
    tbl = shape.table
    tbl.first_row = True
    tbl.horz_banding = False
    for i, cw in enumerate(widths):
        tbl.columns[i].width = Inches(cw)
    tbl.rows[0].height = Inches(head_h)
    for r in range(1, n_rows):
        tbl.rows[r].height = Inches(row_h)
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            cell = tbl.cell(r, c)
            cell.margin_left = Inches(0.06); cell.margin_right = Inches(0.06)
            cell.margin_top = Inches(0.02); cell.margin_bottom = Inches(0.02)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            cell.fill.fore_color.rgb = head_fill if r == 0 else WHITE
            tfr = cell.text_frame
            tfr.word_wrap = True
            p = tfr.paragraphs[0]
            p.line_spacing = 1.02
            if aligns:
                p.alignment = {"l": PP_ALIGN.LEFT, "r": PP_ALIGN.RIGHT,
                               "c": PP_ALIGN.CENTER}[aligns[c]]
            txt, bold, color = (val if isinstance(val, tuple)
                                else (val, r == 0, INK))
            run = p.add_run(); run.text = txt
            run.font.size = Pt(head_size if r == 0 else size)
            run.font.bold = bold
            run.font.name = F
            run.font.color.rgb = color
    return tbl


prs = Presentation(SRC)


def set_title(slide, text, size=27):
    for sh in slide.shapes:
        if sh.has_text_frame and sh.name.startswith("Title"):
            sh.left, sh.width = Inches(1.95), Inches(8.55)
            sh.top, sh.height = Inches(0.08), Inches(0.85)
            tf = sh.text_frame
            tf.word_wrap = True
            for p in list(tf.paragraphs)[1:]:
                p._element.getparent().remove(p._element)
            p = tf.paragraphs[0]
            for r in list(p.runs):
                r._r.getparent().remove(r._r)
            r = p.add_run(); r.text = text
            r.font.size = Pt(size); r.font.bold = True
            r.font.name = F; r.font.color.rgb = INK
            return
    raise AssertionError("no title placeholder")


def drop(slide, *names):
    for sh in list(slide.shapes):
        if sh.name in names:
            sh._element.getparent().remove(sh._element)


# =============================================================================
# Drop the instructions slide - the template says to before submitting.
# =============================================================================
xml_slides = prs.slides._sldIdLst
lst = list(xml_slides)
prs.part.drop_rel(lst[6].rId)
xml_slides.remove(lst[6])
S = prs.slides


def clear_body(slide):
    """Remove the template's own placeholder prose, keep title/logo/oval/footer."""
    KEEP = {"Title 1", "Slide Number Placeholder 5", "Footer Placeholder 6"}
    for sh in list(slide.shapes):
        if sh.name in KEEP or sh.shape_type == 13 or "Oval" in sh.name:
            continue
        sh._element.getparent().remove(sh._element)


# =============================================================================
# 1  TITLE
# =============================================================================
s = S[0]
for sh in s.shapes:
    if sh.name == "TextBox 9":
        tf = sh.text_frame; tf.clear(); tf.word_wrap = True
        rows = [("Problem Statement ID", "SIH26002"),
                ("Problem Statement", "AI-Based Smart Logistics and Accessibility "
                                      "Intelligence Platform for the North Eastern Region"),
                ("Theme", "Smart Automation  |  MDoNER"),
                ("PS Category", "Software"),
                ("Team ID", "<your team ID>"),
                ("Team Name", "<your registered team name>")]
        for i, (k, v) in enumerate(rows):
            runs(tf, [(k + "  ", True, BLUEBOX), (v, False, INK)],
                 size=13.5, first=(i == 0), after=10)
    if sh.name == "Subtitle 3":
        tf = sh.text_frame
        for p in list(tf.paragraphs)[1:]:
            p._element.getparent().remove(p._element)
        p = tf.paragraphs[0]
        for r in list(p.runs):
            r._r.getparent().remove(r._r)
        r = p.add_run(); r.text = "IDEA SUBMISSION"
        r.font.size = Pt(20); r.font.bold = True
        r.font.name = F; r.font.color.rgb = INK

# =============================================================================
# 2  PROPOSED SOLUTION
# =============================================================================
s = S[1]; clear_body(s)
set_title(s, "PROPOSED SOLUTION", 30)

# --- Input / Processing / Output pill row -----------------------------------
py0 = 1.05
pw, pg = 3.85, 0.28
labels = ["Input", "AI Processing", "Output"]
for i, lab in enumerate(labels):
    x = 0.55 + i * (pw + pg)
    pill(s, x, py0, pw, 0.34, lab, fill=ORANGE)

by = py0 + 0.44
bh = 1.00
# Input box: open data sources
rect(s, 0.55, by, pw, bh, WHITE, TEAL)
tf = tf_at(s, 0.68, by + 0.08, pw - 0.26, bh - 0.16)
for i, t in enumerate(["OpenStreetMap - roads & villages",
                       "NASA POWER - monthly rainfall",
                       "Copernicus DEM - ground elevation"]):
    line(tf, t, 9.5, color=INK, first=(i == 0), after=4, bullet=True, spacing=1.1)

# Processing box: engine chips
x2 = 0.55 + (pw + pg)
rect(s, x2, by, pw, bh, WHITE, TEAL)
chip_w, chip_g = (pw - 0.20 - 4 * 0.06) / 5, 0.06
chips = ["Terrain", "Rainfall", "Elevation", "Graph\nsearch", "Risk\nscore"]
for i, c in enumerate(chips):
    cx = x2 + 0.10 + i * (chip_w + chip_g)
    rect(s, cx, by + 0.10, chip_w, 0.42, TEAL_FILL, TEAL, width=1.0, radius=0.2)
    tf = tf_at(s, cx, by + 0.10, chip_w, 0.42, anchor=MSO_ANCHOR.MIDDLE)
    for j, ln in enumerate(c.split("\n")):
        line(tf, ln, 7.3, bold=True, color=TEAL, first=(j == 0),
             align=PP_ALIGN.CENTER, spacing=1.0)
tf = tf_at(s, x2 + 0.10, by + 0.58, pw - 0.20, bh - 0.62)
line(tf, "Landslide + flood scored independently, then combined into a "
         "generalised cost: rupees, hours, and risk together.", 9, color=GREY,
     first=True, spacing=1.1)

# Output box: a real screenshot
x3 = 0.55 + 2 * (pw + pg)
rect(s, x3, by, pw, bh, WHITE, TEAL)
RW3, RH3 = 1.55, 1.55 * 1440 / 2016
picture(s, HERO / "risk_map_tight.png", x3 + 0.08, by + 0.06, RW3, RH3)
tf = tf_at(s, x3 + 0.08 + RW3 + 0.10, by + 0.06, pw - RW3 - 0.34, RH3)
for i, t in enumerate(["Best route + alternatives", "Monsoon risk map",
                       "Village accessibility score", "Live shipment tracking"]):
    line(tf, t, 8.7, color=INK, first=(i == 0), after=3, bullet=True, spacing=1.05)
tf = tf_at(s, x3 + 0.08, by + RH3 + 0.10, pw - 0.16, bh - RH3 - 0.16)
line(tf, "Screenshot from the running app.", 8, italic=True, color=GREY, first=True)

# --- Innovation and uniqueness ----------------------------------------------
iy = by + bh + 0.14
pill(s, 0.55, iy, 12.23, 0.30, "INNOVATION AND UNIQUENESS", fill=ORANGE, size=11.5)
cy = iy + 0.40
cw, cg = (12.23 - 4 * 0.12) / 5, 0.12
innov = [
    ("Multimodal Routing", "Road, rail, water, air as one graph; every mode "
     "change charged real cost and time."),
    ("Dual-Hazard Pricing", "Landslide + flood scored separately, priced into "
     "rupees and hours per route."),
    ("Accessibility Score", "5,594 villages ranked by real travel-hours, not "
     "straight-line map distance."),
    ("Live Shipment Tracking", "A marker animates leg by leg, timed to the "
     "plan's own real transit hours."),
    ("Voice + 5 Languages", "Search by voice; use the whole app in Hindi, "
     "Assamese, Bengali or Nepali."),
]
ch = 0.86
for i, (head, body) in enumerate(innov):
    x = 0.55 + i * (cw + cg)
    card(s, x, cy, cw, ch, head, body, border=TEAL, title_size=9.7, body_size=8.0)

# --- How it addresses the problem -------------------------------------------
hy = cy + ch + 0.12
pill(s, 0.55, hy, 12.23, 0.30, "HOW IT ADDRESSES THE PROBLEM", fill=ORANGE, size=11.5)
tf = tf_at(s, 0.68, hy + 0.38, 11.95, 1.55)
addr = [
    ("Manual planning: ", "shippers pick a route off a map and guess the "
     "monsoon - we compute cost, time and risk together, before dispatch."),
    ("Hidden monsoon cost: ", "risk is priced in rupees and hours, not a "
     "vague colour warning."),
    ("Blind villages: ", "5,594 villages are scored for real accessibility, "
     "worst-connected first."),
    ("Multimodal blindness: ", "every transhipment is charged real handling "
     "cost and time, never free."),
    ("Nothing to show: ", "live tracking and a satellite view let a viewer "
     "watch the plan happen, not just read numbers."),
]
for i, (lead, rest) in enumerate(addr):
    runs(tf, [(lead, True, INK), (rest, False, INK)], size=9.3,
         first=(i == 0), after=4, spacing=1.12, bullet=True)

# =============================================================================
# 3  TECHNICAL APPROACH
# =============================================================================
s = S[2]; clear_body(s)
set_title(s, "TECHNICAL APPROACH", 28)

pill(s, 0.55, 1.05, 4.55, 0.30, "METHODOLOGY AND PROCESS", fill=GREEN, size=10.5)

fx, fw = 1.55, 2.55
fy = 1.50
def flow_box(y, title, sub, w=fw, x=fx, h=0.40, fill=GREEN_FILL, border=GREEN):
    rect(s, x, y, w, h, fill, border, width=1.25)
    tf = tf_at(s, x, y, w, h, anchor=MSO_ANCHOR.MIDDLE)
    line(tf, title, 9.3, bold=True, color=INK, first=True, align=PP_ALIGN.CENTER,
         after=0, spacing=1.0)
    if sub:
        line(tf, sub, 7.3, color=GREY, align=PP_ALIGN.CENTER, spacing=1.0)

flow_box(fy, "OPEN DATA", "OSM + NASA + DEM")
arrow_down(s, fx + fw / 2, fy + 0.42)

y = fy + 0.62
flow_box(y, "NETWORK BUILDER", "7,181 segments · 5,594 villages")
arrow_down(s, fx + fw / 2, y + 0.42)

y2 = y + 0.62
flow_box(y2, "RISK + COST ENGINE", "landslide, flood, ₹/t, hours")

# three branches, asymmetric like the reference - only one continues
by3 = y2 + 0.52
bw3, bg3 = 1.30, 0.08
branch_x = [fx - 0.20, fx - 0.20 + (bw3 + bg3), fx - 0.20 + 2 * (bw3 + bg3)]
for bx in branch_x:
    arrow_down(s, bx + bw3 / 2, y2 + 0.40, h=0.12, w=0.10)
branch_labels = [("MODE-LAYERED\nGRAPH", True), ("ACCESSIBILITY\nINDEX", False),
                 ("LIVE\nTRACKER", False)]
for bx, (lab, cont) in zip(branch_x, branch_labels):
    rect(s, bx, by3, bw3, 0.46, GREEN_FILL, GREEN, width=1.0)
    tf = tf_at(s, bx, by3, bw3, 0.46, anchor=MSO_ANCHOR.MIDDLE)
    for j, ln in enumerate(lab.split("\n")):
        line(tf, ln, 7.6, bold=True, color=INK, first=(j == 0),
             align=PP_ALIGN.CENTER, spacing=1.0)

cont_x = branch_x[0]
arrow_down(s, cont_x + bw3 / 2, by3 + 0.48, h=0.12, w=0.10)
y4 = by3 + 0.62
rect(s, cont_x, y4, bw3, 0.46, GREEN_FILL, GREEN, width=1.0)
tf = tf_at(s, cont_x, y4, bw3, 0.46, anchor=MSO_ANCHOR.MIDDLE)
line(tf, "DIJKSTRA +", 7.6, bold=True, color=INK, first=True, align=PP_ALIGN.CENTER, spacing=1.0)
line(tf, "YEN'S ALGORITHM", 7.6, bold=True, color=INK, align=PP_ALIGN.CENTER, spacing=1.0)
arrow_down(s, cont_x + bw3 / 2, y4 + 0.48, h=0.12, w=0.10)
y5 = y4 + 0.62
rect(s, cont_x - 0.35, y5, bw3 + 0.70, 0.42, GREEN, None, width=0)
tf = tf_at(s, cont_x - 0.35, y5, bw3 + 0.70, 0.42, anchor=MSO_ANCHOR.MIDDLE)
line(tf, "DASHBOARD (API + MAP)", 8.3, bold=True, color=WHITE, first=True,
     align=PP_ALIGN.CENTER, spacing=1.0)

# --- right column: Technical Approach / Working Process ---------------------
rx = 5.55
tf = tf_at(s, rx, 1.05, 6.65, 0.26)
line(tf, "Technical Approach", 12, bold=True, color=REDTXT, first=True)
tf = tf_at(s, rx, 1.37, 6.65, 2.05)
tech_bullets = [
    ("Data ingestion: ", "OSM (roads/villages), NASA POWER (rainfall), "
     "Copernicus DEM (elevation) - all free, no key."),
    ("Network builder: ", "contracts raw OSM ways into 7,181 usable segments "
     "over 6,502 junctions."),
    ("Risk engine: ", "terrain + rainfall + elevation combine into landslide "
     "and flood probability, per segment, per month."),
    ("Cost engine: ", "₹/tonne + hours + risk-adjusted delay blended into "
     "one generalised cost."),
    ("Graph engine: ", "NetworkX mode-layered graph; Dijkstra for the plan, "
     "Yen's algorithm for alternatives."),
    ("Frontend: ", "MapLibre GL (vector + satellite), Web Speech API for "
     "voice, in-app translation for 5 languages."),
]
for i, (lead, rest) in enumerate(tech_bullets):
    runs(tf, [(lead, True, INK), (rest, False, INK)], size=9.3,
         first=(i == 0), after=5, spacing=1.14, bullet=True)

tf = tf_at(s, rx, 3.55, 6.65, 0.26)
line(tf, "Working Process", 12, bold=True, color=REDTXT, first=True)
tf = tf_at(s, rx, 3.87, 6.65, 2.10)
process = [
    ("Data collection - ", "pull roads, rainfall and elevation from open "
     "sources."),
    ("Network construction - ", "merge into one mode-layered graph "
     "(road/rail/water/air)."),
    ("Risk scoring - ", "compute landslide + flood probability for every "
     "segment, every month."),
    ("Route optimisation - ", "run Dijkstra + Yen's k-shortest paths for the "
     "best route and alternatives."),
    ("Accessibility scoring - ", "rank 5,594 villages by real travel-hours "
     "to a market, cold store or gateway."),
    ("Live visualisation - ", "animate the chosen plan on the map, mode by "
     "mode, in the viewer's own language."),
]
for i, (lead, rest) in enumerate(process):
    runs(tf, [(lead, True, INK), (rest, False, INK)], size=9.3,
         first=(i == 0), after=5, spacing=1.14, bullet=True)

rect(s, rx, 6.05, 6.65, 0.55, PANEL, None, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
tf = tf_at(s, rx + 0.14, 6.13, 6.37, 0.40)
line(tf, "Working prototype: all five stages run today against the real "
         "25,360 km network - not a plan.", 9, italic=True, color=GREY, first=True,
     spacing=1.1)

# =============================================================================
# 4  FEASIBILITY AND VIABILITY
# =============================================================================
s = S[3]; clear_body(s)
set_title(s, "FEASIBILITY AND VIABILITY", 27)

pill(s, 0.55, 1.05, 6.55, 0.32, "FEASIBILITY AND VIABILITY", fill=ORANGE, size=12)
for i in range(4):
    arrow_down(s, 0.55 + 6.55 * (i + 0.5) / 4, 1.39, h=0.12, w=0.10)

fcw, fcg = (6.55 - 3 * 0.12) / 4, 0.12
feas = [
    ("Technical Feasibility", "NetworkX handles the 7,181-segment multimodal "
     "graph at proven scale; Dijkstra + Yen's run sub-second; MapLibre GL "
     "renders vector + satellite at zero backend cost."),
    ("Financial Feasibility", "Every data source is free and key-less - "
     "₹0 spent on data. Open-source stack throughout: Python, NetworkX, "
     "MapLibre, no paid API."),
    ("Operational Feasibility", "Runs offline after setup; a single process "
     "serves the API and the dashboard. 261 backend tests + 51 browser "
     "checks pass today."),
    ("Data Feasibility", "25,360 km built from OSM, cross-checked against 46 "
     "seed alignments. Honest gap: only ~15% of villages carry a population "
     "figure, so ranking uses reach, not population."),
]
for i, (head, body) in enumerate(feas):
    x = 0.55 + i * (fcw + fcg)
    card(s, x, 1.55, fcw, 1.75, head, body, border=GREEN, fill=GREEN_FILL,
         title_size=9.7, body_size=7.9, title_color=INK)

# --- right: strategies for overcoming challenges -----------------------------
rx4 = 7.45
pill(s, rx4, 1.05, 5.30, 0.32, "STRATEGIES FOR OVERCOMING CHALLENGES",
     fill=BLUEBOX, size=10.5)

groups = [
    ("Data Challenges", [
        ("No live road-closure feed - ", "predict closure risk from rainfall "
         "and terrain today; add driver-reported closures next."),
        ("Sparse market data - ", "35 markets cover 5,594 villages; loading "
         "Agmarknet mandi prices is the next data source."),
        ("Incomplete population data - ", "rank villages by settlements "
         "reached instead of guessing population."),
    ]),
    ("Coverage Challenges", [
        ("Free tile hosts rate-limit - ", "cache tiles for offline use in "
         "poor-connectivity field conditions."),
        ("399 villages unreachable by any mapped road - ", "reported "
         "explicitly in the accessibility tab, never hidden."),
    ]),
    ("Adoption Challenges", [
        ("Language barrier - ", "5 regional languages plus voice search "
         "remove the English-only barrier."),
        ("Trust in a black-box score - ", "every number traces back to a "
         "real terrain or rainfall input shown in the UI."),
    ]),
]
gy = 1.47
for gname, items in groups:
    tf = tf_at(s, rx4 + 0.10, gy, 5.10, 0.24)
    line(tf, gname, 10.5, bold=True, color=BLUEBOX, first=True)
    gy += 0.28
    tf = tf_at(s, rx4 + 0.18, gy, 5.00, 0.20 * len(items) + 0.30)
    for i, (lead, rest) in enumerate(items):
        runs(tf, [(lead, True, INK), (rest, False, GREY)], size=8.6,
             first=(i == 0), after=3, spacing=1.1, bullet=True)
    gy += 0.24 * len(items) + 0.18

# =============================================================================
# 5  IMPACT AND BENEFITS
# =============================================================================
s = S[4]; clear_body(s)
set_title(s, "IMPACT AND BENEFITS", 28)

pill(s, 0.55, 1.05, 6.30, 0.30, "IMPACTS", fill=ORANGE, size=12)
impacts = [
    ("Farmers and FPOs", "Billbari's market access falls from 3.9 days in "
     "the dry season to 1.3 days once monsoon risk is priced in - no "
     "surprise transit cost."),
    ("Transporters and 3PLs", "A defensible mode choice backed by real "
     "cost, time and risk: ₹5,032/tonne and 6.2 days separate the best "
     "from the worst choice on one lane."),
    ("MDoNER, NEC and State PWDs", "1,309 of 4,033 major roads flagged "
     "severe-risk in July; 1,055 of those flood-driven, not landslide - "
     "facility siting ranks sites by settlements reached."),
    ("General Public and Villages", "399 'invisible' villages, 20+ km from "
     "any mapped road, now show up in the data. The whole app works by "
     "voice, in 5 regional languages."),
]
iy5 = 1.45
for i, (head, body) in enumerate(impacts):
    card(s, 0.55, iy5, 6.30, 0.98, head, body, border=TEAL, fill=TEAL_FILL,
         title_size=10.3, body_size=8.4, title_color=INK)
    iy5 += 1.08

# --- right: hub-and-spoke benefits diagram -----------------------------------
pill(s, 7.15, 1.05, 5.60, 0.30, "BENEFITS", fill=ORANGE, size=12)

hub_cx = 7.15 + 5.60 / 2
hub_w, hub_h = 1.85, 0.55
hub_y = 2.55
top_w, top_h = 2.35, 0.42
rect(s, hub_cx - top_w / 2, 1.55, top_w, top_h, BLUEBOX_FILL, BLUEBOX, width=1.25)
tf = tf_at(s, hub_cx - top_w / 2, 1.55, top_w, top_h, anchor=MSO_ANCHOR.MIDDLE)
line(tf, "Smarter Freight Decisions", 8.6, bold=True, color=BLUEBOX, first=True,
     align=PP_ALIGN.CENTER, spacing=1.0)
arrow_down(s, hub_cx, 1.97, h=0.14, w=0.12)

side_w, side_h = 1.55, 0.55
rect(s, 7.30, hub_y + 0.02, side_w, side_h, BLUEBOX_FILL, BLUEBOX, width=1.25)
tf = tf_at(s, 7.30 + 0.06, hub_y + 0.02, side_w - 0.12, side_h, anchor=MSO_ANCHOR.MIDDLE)
line(tf, "Reduced Manual Planning", 8.4, bold=True, color=BLUEBOX, first=True,
     align=PP_ALIGN.CENTER, spacing=1.0)

rect(s, 12.75 - side_w, hub_y + 0.02, side_w, side_h, BLUEBOX_FILL, BLUEBOX, width=1.25)
tf = tf_at(s, 12.75 - side_w + 0.06, hub_y + 0.02, side_w - 0.12, side_h, anchor=MSO_ANCHOR.MIDDLE)
line(tf, "Real Network Data, Not Guesswork", 8.4, bold=True, color=BLUEBOX,
     first=True, align=PP_ALIGN.CENTER, spacing=1.0)

rect(s, hub_cx - hub_w / 2, hub_y, hub_w, hub_h, BLUEBOX, None, width=0)
tf = tf_at(s, hub_cx - hub_w / 2, hub_y, hub_w, hub_h, anchor=MSO_ANCHOR.MIDDLE)
line(tf, "AI Multimodal Logistics Engine", 9.6, bold=True, color=WHITE, first=True,
     align=PP_ALIGN.CENTER, spacing=1.0)

arrow_down(s, hub_cx, hub_y + hub_h + 0.04, h=0.14, w=0.12)
chain_y = hub_y + hub_h + 0.22
chain_w = 1.75
chain = ["Free Open-Data\nReuse", "Real-Time Risk\nPricing", "Faster, Safer\nDelivery"]
chain_g = (5.60 - 3 * chain_w) / 2
for i, c in enumerate(chain):
    cx = 7.15 + i * (chain_w + chain_g)
    rect(s, cx, chain_y, chain_w, 0.62, TEAL_FILL, TEAL, width=1.25)
    tf = tf_at(s, cx, chain_y, chain_w, 0.62, anchor=MSO_ANCHOR.MIDDLE)
    for j, ln in enumerate(c.split("\n")):
        line(tf, ln, 8.6, bold=True, color=TEAL, first=(j == 0),
             align=PP_ALIGN.CENTER, spacing=1.0)
    if i < 2:
        arrow_right(s, cx + chain_w + 0.02, chain_y + 0.31, w=chain_g - 0.04)

rect(s, 7.15, chain_y + 0.62 + 0.20, 5.60, 0.55, PANEL, None,
     shape=MSO_SHAPE.ROUNDED_RECTANGLE)
tf = tf_at(s, 7.15 + 0.14, chain_y + 0.62 + 0.28, 5.32, 0.40)
line(tf, "Every arrow above is a real, running data path in the app today - "
         "not a roadmap.", 8.6, italic=True, color=GREY, first=True, spacing=1.1)

# =============================================================================
# 6  RESEARCH AND REFERENCES
# =============================================================================
s = S[5]; clear_body(s)
set_title(s, "RESEARCH AND REFERENCES", 26)

tf = tf_at(s, 0.55, 1.05, 6.10, 0.28)
line(tf, "Research Basis", 13, bold=True, color=REDTXT, first=True)
tf = tf_at(s, 0.55, 1.42, 6.10, 4.35)
basis = [
    ("Shortest-Path Routing - ", "Dijkstra's algorithm finds the lowest-cost "
     "path on a weighted graph; it is the direct basis of the route "
     "optimiser, in use since 1959."),
    ("Alternative Route Discovery - ", "Yen's algorithm enumerates the k "
     "shortest loopless paths, used here to offer genuinely different "
     "route options, not near-duplicates."),
    ("Terrain-Based Hazard Modelling - ", "landslide susceptibility is "
     "commonly modelled from slope, rainfall and land cover; the same "
     "terrain-first approach is used here in the absence of a historical "
     "closure dataset."),
    ("DEM-Based Flood Susceptibility - ", "elevation derived from the "
     "Copernicus DEM is a standard proxy for flood-prone terrain where "
     "observed flood extent is unavailable."),
]
for i, (lead, rest) in enumerate(basis):
    runs(tf, [(lead, True, INK), (rest, False, INK)], size=9.6,
         first=(i == 0), after=8, spacing=1.16, bullet=True)

tf = tf_at(s, 6.95, 1.05, 6.25, 0.28)
line(tf, "Reference Papers / Sources", 13, bold=True, color=REDTXT, first=True)
tf = tf_at(s, 6.95, 1.42, 6.25, 4.15)
refs = [
    "Dijkstra, E. W. (1959). “A note on two problems in connexion with "
    "graphs.” Numerische Mathematik, 1, 269-271.",
    "Yen, J. Y. (1971). “Finding the k shortest loopless paths in a "
    "network.” Management Science, 17(11), 712-716.",
    "OpenStreetMap Foundation - overpass-api.de",
    "NASA POWER Project - power.larc.nasa.gov",
    "Copernicus DEM via Open-Meteo - open-meteo.com",
    "MDoNER / North Eastern Council Regional Plan",
    "Inland Waterways Authority of India - National Waterway 2",
]
for i, t in enumerate(refs):
    line(tf, t, 9.3, color=INK, first=(i == 0), after=7, spacing=1.14, bullet=True)

rect(s, 0.55, 5.90, 12.23, 0.90, BLUEBOX_FILL, BLUEBOX, width=1.25)
tf = tf_at(s, 0.72, 5.99, 11.90, 0.74)
line(tf, "Research Gap", 10, bold=True, color=BLUEBOX, first=True, after=2)
line(tf, "Existing tools optimise route distance alone, or model a single "
         "hazard in isolation. None combine multimodal freight optimisation, "
         "per-trip hazard pricing and real accessibility scoring in one open, "
         "free platform for the North East. This is the gap our platform "
         "closes.", 9, color=INK, spacing=1.14)

prs.save(OUT)
print("saved", OUT)
