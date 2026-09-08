# -*- coding: utf-8 -*-
"""SIH26002 submission deck: exactly 6 slides, on the official template, with
every slide's SIH-given pointer kept verbatim as the visible structure.

Rules this file exists to satisfy (from the template's own "Important
Instructions" slide):
  1. Six slides max, including the title slide.
  2. Points/diagrams/pictures, not paragraphs.
  3. Precise, easy to understand.
  4. The template's own idea-detail pointers are not changed or dropped -
     they are kept as the labelled structure and answered under, not
     replaced with a free-form narrative.
  5. The instructions slide itself is not part of the submission.

Usage: python build_final.py <template.pptx> <out.pptx> <hero-image-dir>
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
GREY  = RGBColor(0x5F, 0x5F, 0x5F)
FAINT = RGBColor(0x8A, 0x8A, 0x8A)
RULE  = RGBColor(0xBF, 0xBF, 0xBF)
PANEL = RGBColor(0xF0, 0xF0, 0xF0)
BLUE  = RGBColor(0x1F, 0x4E, 0x79)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREEN = RGBColor(0x1B, 0xAF, 0x7A)
AMBER = RGBColor(0xE0, 0xA1, 0x00)
RED   = RGBColor(0xD0, 0x3B, 0x3B)

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
         align=PP_ALIGN.LEFT, spacing=1.12, italic=False, bullet=False):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    p.line_spacing = spacing
    p.space_after = Pt(after)
    prefix = "–  " if bullet else ""
    r = p.add_run(); r.text = prefix + text
    r.font.size = Pt(size); r.font.bold = bold; r.font.italic = italic
    r.font.name = F; r.font.color.rgb = color
    return p


def runs(tf, parts, size=11, first=False, after=0, spacing=1.12, bullet=False):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.line_spacing = spacing
    p.space_after = Pt(after)
    if bullet:
        r = p.add_run(); r.text = "–  "
        r.font.size = Pt(size); r.font.name = F; r.font.color.rgb = parts[0][2]
    for text, bold, color in parts:
        r = p.add_run(); r.text = text
        r.font.size = Pt(size); r.font.bold = bold
        r.font.name = F; r.font.color.rgb = color
    return p


def rect(slide, x, y, w, h, fill=None, border=None, width=0.75,
         shape=MSO_SHAPE.RECTANGLE):
    sh = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
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


def dbox(slide, x, y, w, h, title, sub=None, fill=WHITE, border=RULE,
         title_size=10.5, sub_size=8.5, title_color=INK):
    rect(slide, x, y, w, h, fill, border)
    tf = tf_at(slide, x + 0.07, y, w - 0.14, h, anchor=MSO_ANCHOR.MIDDLE)
    line(tf, title, title_size, bold=True, color=title_color, first=True,
         align=PP_ALIGN.CENTER, spacing=1.0, after=1 if sub else 0)
    if sub:
        line(tf, sub, sub_size, color=GREY, align=PP_ALIGN.CENTER, spacing=1.0)
    return tf


def arrow_down(slide, cx, y, h=0.16, w=0.13, color=FAINT):
    sh = slide.shapes.add_shape(MSO_SHAPE.DOWN_ARROW, Inches(cx - w / 2),
                                Inches(y), Inches(w), Inches(h))
    sh.fill.solid(); sh.fill.fore_color.rgb = color
    sh.line.fill.background(); sh.shadow.inherit = False
    sh.text_frame.text = ""
    return sh


def arrow_right(slide, x, cy, w=0.20, h=0.11, color=FAINT):
    sh = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x),
                                Inches(cy - h / 2), Inches(w), Inches(h))
    sh.fill.solid(); sh.fill.fore_color.rgb = color
    sh.line.fill.background(); sh.shadow.inherit = False
    sh.text_frame.text = ""
    return sh


def tag(slide, x, y, text, fill=INK, color=WHITE, size=9.5, w=0.34, h=0.30):
    """A small square index tag, e.g. '01' - the deck's one repeated motif."""
    rect(slide, x, y, w, h, fill, None)
    tf = tf_at(slide, x, y, w, h, anchor=MSO_ANCHOR.MIDDLE)
    line(tf, text, size, bold=True, color=color, first=True, align=PP_ALIGN.CENTER,
         spacing=1.0)


def pointer_head(slide, x, y, w, index, text):
    """The SIH-given pointer, kept verbatim, as a labelled sub-heading."""
    tag(slide, x, y, "%02d" % index)
    tf = tf_at(slide, x + 0.46, y - 0.02, w - 0.46, 0.34, anchor=MSO_ANCHOR.MIDDLE)
    line(tf, text, 12, bold=True, color=INK, first=True, spacing=1.0)


def table(slide, x, y, w, rows, widths, row_h=0.30, head_h=0.30, size=10,
          head_size=9.5, aligns=None, head_fill=PANEL):
    n_rows, n_cols = len(rows), len(rows[0])
    shape = slide.shapes.add_table(n_rows, n_cols, Inches(x), Inches(y),
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
            cell.margin_left = Inches(0.08); cell.margin_right = Inches(0.08)
            cell.margin_top = Inches(0.02); cell.margin_bottom = Inches(0.02)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            cell.fill.fore_color.rgb = head_fill if r == 0 else WHITE
            tfr = cell.text_frame
            tfr.word_wrap = True
            p = tfr.paragraphs[0]
            p.line_spacing = 1.05
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


def picture(slide, path, x, y, w=None, h=None):
    return slide.shapes.add_picture(str(path), Inches(x), Inches(y),
                                    Inches(w) if w else None,
                                    Inches(h) if h else None)


prs = Presentation(SRC)


def set_title(slide, text, size=27):
    for sh in slide.shapes:
        if sh.has_text_frame and sh.name.startswith("Title"):
            sh.left, sh.width = Inches(1.95), Inches(8.55)
            sh.top, sh.height = Inches(0.10), Inches(1.05)
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


def strap(slide, text, y=1.16):
    tf = tf_at(slide, 0.55, y, 12.2, 0.26)
    line(tf, text, 11, color=BLUE, first=True)


def drop(slide, *names):
    for sh in list(slide.shapes):
        if sh.name in names:
            sh._element.getparent().remove(sh._element)


# =============================================================================
# Drop the "important instructions" slide - it is not part of the submission,
# and the template itself says to delete it before uploading.
# =============================================================================
xml_slides = prs.slides._sldIdLst
lst = list(xml_slides)
prs.part.drop_rel(lst[6].rId)
xml_slides.remove(lst[6])
S = prs.slides

# =============================================================================
# 1  TITLE PAGE  (template's own fields, unchanged)
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
            runs(tf, [(k + "  ", True, BLUE), (v, False, INK)],
                 size=13, first=(i == 0), after=9)
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
# 2  IDEA TITLE  -  pointers kept verbatim:
#    - Detailed explanation of the proposed solution
#    - How it addresses the problem
#    - Innovation and uniqueness of the solution
# =============================================================================
s = S[1]; drop(s, "TextBox 8")
set_title(s, "Route the North East by Risk, Not by Distance", 25)
strap(s, "Proposed Solution (Idea / Solution / Prototype)")

LX, LW = 0.55, 7.55
y = 1.66
pointer_head(s, LX, y, LW, 1, "Detailed explanation of the proposed solution")
tf = tf_at(s, LX + 0.46, y + 0.38, LW - 0.46, 0.85)
for i, t in enumerate([
        "One platform, two engines — plans multimodal freight routes and "
        "scores village accessibility, on one shared network.",
        "Layers road, rail, waterway and air into one graph; every change "
        "of vehicle is charged real handling cost and time."]):
    line(tf, t, 11.5, color=INK, first=(i == 0), after=8, bullet=True, spacing=1.15)

y = 3.06
pointer_head(s, LX, y, LW, 2, "How it addresses the problem")
tf = tf_at(s, LX + 0.46, y + 0.38, LW - 0.46, 0.85)
for i, t in enumerate([
        "Turns “the monsoon might disrupt this” into a rupee-and-hour "
        "number a shipper can act on before dispatch.",
        "Names exactly which villages are cut off and by how much — so "
        "investment is targeted, not guessed."]):
    line(tf, t, 11.5, color=INK, first=(i == 0), after=8, bullet=True, spacing=1.15)

y = 4.46
pointer_head(s, LX, y, LW, 3, "Innovation and uniqueness of the solution")
tf = tf_at(s, LX + 0.46, y + 0.38, LW - 0.46, 1.10)
for i, t in enumerate([
        "Keeps “this road may close this month” separate from “this trip "
        "will meet it” — a hill route prices as expensive, not impossible.",
        "Landslide and flood are scored as two independent hazards. Built "
        "and validated entirely on free, open data — ₹0 recurring cost."]):
    line(tf, t, 11.5, color=INK, first=(i == 0), after=8, bullet=True, spacing=1.15)

# hero visual: the whole network, risk-coloured, from the running app
RX, RW = 8.30, 4.48
picture(s, HERO / "risk_map_tight.png", RX, 1.62, RW, RW * 1440 / 2016)
rect(s, RX, 1.62, RW, RW * 1440 / 2016, None, RULE, 0.75)
tf = tf_at(s, RX, 1.62 + RW * 1440 / 2016 + 0.06, RW, 0.45)
line(tf, "The whole network, live from the app — 7,181 road segments "
         "coloured by monsoon risk this month.", 9, color=FAINT, first=True,
     spacing=1.1)

rect(s, RX, 5.55, RW, 1.30, PANEL, None)
tf = tf_at(s, RX + 0.20, 5.68, RW - 0.40, 1.02)
line(tf, "At a glance", 10.5, bold=True, first=True, after=4)
for t in ["7,181 segments  ·  25,360 km scored",
          "5,594 settlements ranked by real access",
          "₹0 data cost · 261 tests · 30 UI checks"]:
    line(tf, t, 10, color=GREY, after=3)

# =============================================================================
# 3  TECHNICAL APPROACH  -  pointers kept verbatim:
#    - Technologies to be used
#    - Methodology and process for implementation (flow chart)
# =============================================================================
s = S[2]; drop(s, "TextBox 8")
set_title(s, "TECHNICAL APPROACH", 27)
strap(s, "Technologies, then how they fit together")

y = 1.60
pointer_head(s, 0.55, y, 12.23, 1, "Technologies to be used")
groups = [
    ("Backend", "Python  ·  FastAPI  ·  NetworkX  ·  scikit-learn (optional)"),
    ("Data", "OpenStreetMap  ·  NASA POWER  ·  Copernicus DEM"),
    ("Frontend", "MapLibre GL — vendored, zero build step"),
    ("Testing", "pytest — 261 tests  ·  Playwright — 30 UI checks"),
]
gw, gg = 2.93, 0.13
for i, (head, body) in enumerate(groups):
    x = 0.55 + i * (gw + gg)
    rect(s, x, y + 0.38, gw, 0.72, PANEL, None)
    tf = tf_at(s, x + 0.14, y + 0.46, gw - 0.28, 0.58)
    line(tf, head.upper(), 9, bold=True, color=BLUE, first=True, after=2)
    line(tf, body, 9.5, color=INK, spacing=1.05)

y2 = 2.86
pointer_head(s, 0.55, y2, 12.23, 2,
             "Methodology and process for implementation")
tf = tf_at(s, 12.23 - 3.55 + 0.55, y2 - 0.01, 3.55, 0.30)
line(tf, "(flow chart — working prototype)", 9.5, italic=True, color=FAINT,
     first=True, align=PP_ALIGN.RIGHT)

# horizontal pipeline: open data -> build -> engine -> answers -> serve
py = y2 + 0.52
bw, bh, gap = 2.18, 1.55, 0.22
steps = [
    ("1.  Open data", "OSM roads & places\nNASA rainfall\nCopernicus elevation"),
    ("2.  Build (offline)", "Contract OSM ways into\n7,181 scored segments\n+ 5,594 settlements"),
    ("3.  Engine", "Risk model (landslide +\nflood) · cost model ·\nmode-layered graph"),
    ("4.  Answer", "Plan a route · compare\noptions · risk map ·\nwho is cut off"),
    ("5.  Serve", "One FastAPI process:\nAPI + dashboard,\nno build, no CDN"),
]
for i, (t, sub) in enumerate(steps):
    x = 0.55 + i * (bw + gap)
    rect(s, x, py, bw, bh, WHITE, RULE)
    rect(s, x, py, bw, 0.34, PANEL, None)
    tf = tf_at(s, x, py, bw, 0.34, anchor=MSO_ANCHOR.MIDDLE)
    line(tf, t, 11, bold=True, color=BLUE, first=True, align=PP_ALIGN.CENTER,
         spacing=1.0)
    tf = tf_at(s, x + 0.12, py + 0.44, bw - 0.24, bh - 0.54,
               anchor=MSO_ANCHOR.MIDDLE)
    for j, ln in enumerate(sub.split("\n")):
        line(tf, ln, 9.5, color=GREY, first=(j == 0), align=PP_ALIGN.CENTER,
             spacing=1.15, after=2)
    if i < len(steps) - 1:
        arrow_right(s, x + bw + 0.02, py + bh / 2, w=gap - 0.04)

rect(s, 0.55, py + bh + 0.30, 12.23, 0.56, PANEL, None)
tf = tf_at(s, 0.78, py + bh + 0.43, 11.77, 0.32)
runs(tf, [("Working prototype:  ", True, INK),
          ("all five stages run today against the full 25,360 km network — "
           "the risk map on this deck's cover slide is a screenshot of the "
           "live application, not a mock-up.", False, GREY)], size=10, first=True)

# =============================================================================
# 4  FEASIBILITY AND VIABILITY  -  pointers kept verbatim:
#    - Analysis of the feasibility of the idea
#    - Potential challenges and risks
#    - Strategies for overcoming these challenges
# =============================================================================
s = S[3]; drop(s, "TextBox 8")
set_title(s, "FEASIBILITY AND VIABILITY", 27)
strap(s, "Already built on free data, with the gaps named plainly")

y = 1.60
pointer_head(s, 0.55, y, 12.23, 1, "Analysis of the feasibility of the idea")
stats = [("25,360 km", "network already built, from open data"),
         ("₹0", "recurring cost — every data source is free"),
         ("261 + 30", "automated tests and UI checks, passing")]
sw = (12.23 - 2 * 0.20) / 3
for i, (big, small) in enumerate(stats):
    x = 0.55 + i * (sw + 0.20)
    rect(s, x, y + 0.38, sw, 0.86, PANEL, None)
    tf = tf_at(s, x + 0.16, y + 0.48, sw - 0.32, 0.66)
    line(tf, big, 19, bold=True, color=BLUE, first=True, after=2)
    line(tf, small, 9, color=GREY, spacing=1.05)

y2 = 2.96
pointer_head(s, 0.55, y2, 6.0, 2, "Potential challenges and risks")
pointer_head(s, 6.75, y2, 6.0, 3, "Strategies for overcoming these challenges")
table(s, 0.55, y2 + 0.40, 12.23,
      [["Challenge", "Strategy"],
       ["No live road-closure feed exists anywhere in India",
        "Predict from rainfall + terrain now; collect driver-reported "
        "closures in-app to learn over time"],
       ["OpenStreetMap has population for only 15% of villages",
        "Rank facility siting by settlements reached, not population; "
        "add the Census 2011 directory next"],
       ["Only 35 markets are mapped for 5,594 villages",
        "Load the Agmarknet market list — the single highest-value "
        "data addition identified"],
       ["Free map and elevation APIs rate-limit large downloads",
        "Offline-first pipeline: fetch once, build once, commit the "
        "result — nothing at runtime re-downloads"]],
      [6.00, 6.23], aligns="ll", row_h=0.62, head_h=0.30, size=10)

# =============================================================================
# 5  IMPACT AND BENEFITS  -  pointers kept verbatim:
#    - Potential impact on the target audience
#    - Benefits of the solution (social, economic, environmental, etc.)
# =============================================================================
s = S[4]; drop(s, "TextBox 8")
set_title(s, "IMPACT AND BENEFITS", 27)
strap(s, "Who this changes things for, and how")

y = 1.60
pointer_head(s, 0.55, y, 12.23, 1, "Potential impact on the target audience")
aw = (12.23 - 2 * 0.20) / 3
audiences = [
    ("Farmers & FPOs", "Billbari, Assam: 1.3 days to a market in the "
     "monsoon. Knowing that before harvest changes what to plant, and when "
     "to sell."),
    ("Transporters & 3PLs", "A defensible mode choice per consignment, "
     "backed by real rupees, hours and risk — not a rate card and a guess."),
    ("MDoNER, NEC & State PWDs", "In July, 1,309 of 4,033 major roads are "
     "at severe risk — and on 1,055 of them the cause is flooding, not "
     "landslides. Spend accordingly."),
]
for i, (head, body) in enumerate(audiences):
    x = 0.55 + i * (aw + 0.20)
    rect(s, x, y + 0.38, aw, 1.55, PANEL, None)
    tf = tf_at(s, x + 0.18, y + 0.50, aw - 0.36, 1.35)
    line(tf, head, 11, bold=True, color=INK, first=True, after=5)
    line(tf, body, 9.5, color=GREY, spacing=1.15)

y2 = 3.75
pointer_head(s, 0.55, y2, 12.23, 2,
             "Benefits of the solution (social, economic, environmental)")
benefits = [
    ("Social", "Visibility for the 399 settlements more than 20 km from any "
     "mapped road — invisible to planning until they are measured."),
    ("Economic", "₹5,032 per tonne and 6.2 days separate the best and worst "
     "choice on one lane alone — the cost of choosing badly, made visible."),
    ("Environmental", "Routes shift to rail and waterway where viable: "
     "2.0 days by rail vs 7.6 days by road only, on the same lane."),
]
for i, (head, body) in enumerate(benefits):
    x = 0.55 + i * (aw + 0.20)
    rect(s, x, y2 + 0.38, aw, 1.55, WHITE, RULE)
    tf = tf_at(s, x + 0.18, y2 + 0.50, aw - 0.36, 1.35)
    line(tf, head.upper(), 10, bold=True, color=BLUE, first=True, after=5)
    line(tf, body, 9.5, color=GREY, spacing=1.15)

# =============================================================================
# 6  RESEARCH AND REFERENCES  -  pointer kept verbatim:
#    - Details / Links of the reference and research work
# =============================================================================
s = S[5]; drop(s, "TextBox 8")
set_title(s, "RESEARCH AND REFERENCES", 27)
strap(s, "Details / Links of the reference and research work")

y = 1.62
tf = tf_at(s, 0.55, y, 6.05, 0.26)
line(tf, "Data", 12, bold=True, first=True)
table(s, 0.55, y + 0.32, 6.05,
      [["Source", "Used for"],
       ["OpenStreetMap (ODbL)\noverpass-api.de", "Roads, towns and villages"],
       ["NASA POWER\npower.larc.nasa.gov", "Monthly rainfall for each place"],
       ["Copernicus DEM via Open-Meteo\nopen-meteo.com", "Ground height, which drives the flood model"],
       ["NASA COOLR landslide catalog\nmaps.nccs.nasa.gov", "Past landslides, for training (download pending)"]],
      [2.75, 3.30], aligns="ll", row_h=0.62, head_h=0.30, size=9.5)

tf = tf_at(s, 6.95, y, 5.83, 0.26)
line(tf, "Policy and method", 12, bold=True, first=True)
table(s, 6.95, y + 0.32, 5.83,
      [["Reference", "Why it matters here"],
       ["MDoNER / NEC Regional Plan", "The connectivity priorities this is built against"],
       ["IWAI, National Waterway 2", "Brahmaputra navigability and terminal locations"],
       ["Dijkstra (1959)", "Shortest path — how the plan is found"],
       ["Yen (1971), Management Science 17(11)", "k shortest loopless paths — how alternatives are found"],
       ["Sagarmala and Bharatmala NE corridors", "Planned infrastructure the model can be re-run against"]],
      [2.55, 3.28], aligns="ll", row_h=0.44, head_h=0.30, size=9.5)

rect(s, 0.55, 5.75, 12.23, 0.62, PANEL, None)
tf = tf_at(s, 0.80, 5.90, 11.73, 0.34)
runs(tf, [("Code, tests and the full method notes:  ", False, GREY),
          ("github.com/Jeffrey2600/Logistics_sih", True, INK)],
     size=12, first=True)

# =============================================================================
# Speaker notes - for whoever presents this, in plain words, slide order.
# =============================================================================
NOTES = [
"""Say the geography before the software. The eight North Eastern states reach
the rest of India through one 22 km strip near Siliguri. Highways are mostly
single lane through hills that slide, Assam floods every year, and for four
months the monsoon shuts the roads the other eight months depend on. MDoNER
asked for a platform that plans freight across all of that and shows which
places are cut off. This deck is that platform, already built and running.""",

"""Point at the map on the right first - say "this is a screenshot of the real
application, not a drawing" - then walk the three pointers on the left.

01: one platform answers two questions - the best way to move freight, and
which villages are cut off.

02: it prices the monsoon in rupees and hours instead of a warning label, and
names which villages are cut off rather than leaving it vague.

03: the one line to make sure lands - we separate "this road may close
sometime this month" from "this trip will be stopped." Treating those as the
same number is the standard mistake, and it prices every hill road as
unusable instead of merely expensive.""",

"""Top row: four technology groups, ten seconds each, no need to read every
word - point and move on.

Bottom: the same five-box flow chart, left to right. Open data comes in,
gets built into a scored network offline, an engine turns that into risk and
cost, four features answer real questions, and one process serves all of it.
Say "no build step, no CDN" when you reach box five - that is why the demo
still works if the venue's wifi blocks something.""",

"""Left: three numbers that prove it already exists - 25,360 km built, ₹0
recurring cost, 261 tests passing. Don't linger, just land the three.

Right: this is the slide judges probe hardest, and it is a table on purpose -
every challenge sits directly across from its answer. The strongest pairing
is the first one: India has no live road-closure feed anywhere, so we predict
from rainfall and terrain instead, and the app is built to take driver reports
later and learn from them. Say that one plainly - it is a real gap and
naming it first is stronger than waiting to be asked.""",

"""Three audiences, three numbers. Billbari - 1.3 days to a market in the
monsoon - is the one to read out loud, it is the most human. For a policy
panel, use the MDoNER card instead: 1,309 of 4,033 major roads at severe risk
in July, and on 1,055 of them the cause is flooding, not landslides - so
spending on slope stabilisation would fix the wrong roads on those.

Bottom row: social, economic, environmental, one line each - don't read all
three unless asked, they are there to show completeness.""",

"""Keep this slide short - it is the credibility slide, not the argument.
Everything used here is open and free, so the platform has nothing to
license before it can be deployed. Mention that the landslide catalogue
download is still pending rather than implying it is loaded - if a judge
checks, honesty here is worth more than a clean-looking list. Close by
pointing at the GitHub link: the code and tests are public.""",
]

for i, text in enumerate(NOTES):
    S[i].notes_slide.notes_text_frame.text = text.strip()

prs.save(OUT)
print("wrote", OUT, "with", len(prs.slides._sldIdLst), "slides")
