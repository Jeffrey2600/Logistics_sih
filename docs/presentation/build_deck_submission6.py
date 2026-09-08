# -*- coding: utf-8 -*-
"""SIH26002 submission deck: exactly 6 slides, on the official template.

Rules this file exists to satisfy (from the template's own "Important
Instructions" slide, followed to the letter):
  1. Six slides max, including the title slide.
  2. Points/diagrams/pictures, not paragraphs.
  3. Precise, easy to understand.
  4. The template's own idea-detail pointers are kept exactly as given -
     including their parentheticals - as the visible structure, answered
     under rather than replaced with a free-form narrative.
  5. The instructions slide itself is deleted before submission.

Writing style: plain, first-person-plural, the way a team explains its own
project out loud - short sentences, few em dashes, no marketing rhetoric.

Usage: python build_final_v2.py <template.pptx> <out.pptx> <hero-image-dir>
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
GREY  = RGBColor(0x50, 0x50, 0x50)   # darkened from the first pass - low
                                      # contrast grey was flagged as hard to
                                      # read; this passes AA at small sizes
RULE  = RGBColor(0xBF, 0xBF, 0xBF)   # borders only, never text
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


def line(tf, text, size=12.5, bold=False, color=INK, first=False, after=0,
         align=PP_ALIGN.LEFT, spacing=1.15, italic=False, bullet=False):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    p.line_spacing = spacing
    p.space_after = Pt(after)
    prefix = "-  " if bullet else ""
    r = p.add_run(); r.text = prefix + text
    r.font.size = Pt(size); r.font.bold = bold; r.font.italic = italic
    r.font.name = F; r.font.color.rgb = color
    return p


def runs(tf, parts, size=12, first=False, after=0, spacing=1.15, bullet=False):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.line_spacing = spacing
    p.space_after = Pt(after)
    if bullet:
        r = p.add_run(); r.text = "-  "
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


def arrow_right(slide, x, cy, w=0.20, h=0.11, color=RULE):
    sh = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x),
                                Inches(cy - h / 2), Inches(w), Inches(h))
    sh.fill.solid(); sh.fill.fore_color.rgb = color
    sh.line.fill.background(); sh.shadow.inherit = False
    sh.text_frame.text = ""
    return sh


def tag(slide, x, y, text, fill=INK, color=WHITE, size=11, w=0.40, h=0.36):
    """A small square index tag, e.g. '01' - the deck's one repeated motif."""
    rect(slide, x, y, w, h, fill, None)
    tf = tf_at(slide, x, y, w, h, anchor=MSO_ANCHOR.MIDDLE)
    line(tf, text, size, bold=True, color=color, first=True, align=PP_ALIGN.CENTER,
         spacing=1.0)


def pointer_head(slide, x, y, w, index, text, detail=None):
    """The SIH-given pointer, kept exactly as written, as a labelled heading.

    `detail` is the pointer's own parenthetical (e.g. "(e.g. programming
    languages, frameworks, hardware)") shown as a second, smaller line so the
    full instruction text is on the slide without being crammed onto one line.
    """
    tag(slide, x, y, "%02d" % index)
    tw = w - 0.52
    if detail:
        tf = tf_at(slide, x + 0.52, y - 0.03, tw, 0.55)
        line(tf, text, 13, bold=True, color=INK, first=True, spacing=1.0, after=1)
        line(tf, detail, 10, color=GREY, italic=True, spacing=1.0)
        return 0.60
    tf = tf_at(slide, x + 0.52, y, tw, 0.36, anchor=MSO_ANCHOR.MIDDLE)
    line(tf, text, 13, bold=True, color=INK, first=True, spacing=1.0)
    return 0.40


def table(slide, x, y, w, rows, widths, row_h=0.34, head_h=0.32, size=11,
          head_size=10.5, aligns=None, head_fill=PANEL):
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
            cell.margin_top = Inches(0.03); cell.margin_bottom = Inches(0.03)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            cell.fill.fore_color.rgb = head_fill if r == 0 else WHITE
            tfr = cell.text_frame
            tfr.word_wrap = True
            p = tfr.paragraphs[0]
            p.line_spacing = 1.08
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


def strap(slide, text, y=1.16, size=11.5):
    tf = tf_at(slide, 0.55, y, 12.2, 0.30)
    line(tf, text, size, color=BLUE, first=True, bold=False)


def drop(slide, *names):
    for sh in list(slide.shapes):
        if sh.name in names:
            sh._element.getparent().remove(sh._element)


# =============================================================================
# Drop the "important instructions" slide - the template says to delete it
# before uploading, and it is not part of the submission.
# =============================================================================
xml_slides = prs.slides._sldIdLst
lst = list(xml_slides)
prs.part.drop_rel(lst[6].rId)
xml_slides.remove(lst[6])
S = prs.slides

# =============================================================================
# 1  TITLE PAGE  (template's own fields)
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
# 2  IDEA TITLE
#    Pointers kept exactly as given:
#      - Detailed explanation of the proposed solution
#      - How it addresses the problem
#      - Innovation and uniqueness of the solution
# =============================================================================
s = S[1]; drop(s, "TextBox 8")
set_title(s, "AI-Based Route Planning and Accessibility Mapping for the North East", 22)
strap(s, "Proposed Solution (Describe your Idea/Solution/Prototype)")

LX, LW = 0.55, 7.55
y = 1.64
pointer_head(s, LX, y, LW, 1, "Detailed explanation of the proposed solution")
tf = tf_at(s, LX + 0.52, y + 0.42, LW - 0.52, 0.95)
for i, t in enumerate([
        "We built one web application that does two things: it plans the "
        "best way to move a shipment across the North East, and it shows "
        "which villages are hard to reach.",
        "It treats road, rail, the Brahmaputra waterway and air as one "
        "connected network, so it can suggest part road and part rail when "
        "that works out cheaper or safer."]):
    line(tf, t, 12.5, color=INK, first=(i == 0), after=9, bullet=True, spacing=1.18)

y = 3.16
pointer_head(s, LX, y, LW, 2, "How it addresses the problem")
tf = tf_at(s, LX + 0.52, y + 0.42, LW - 0.52, 0.95)
for i, t in enumerate([
        "Right now people plan routes off a map and guess how bad the "
        "monsoon will be. We turn that guess into a number - extra hours "
        "and rupees - before the truck leaves.",
        "We also rank villages by how many hours they actually need to "
        "reach a market or hospital, so it is clear which ones need help "
        "first."]):
    line(tf, t, 12.5, color=INK, first=(i == 0), after=9, bullet=True, spacing=1.18)

y = 4.68
pointer_head(s, LX, y, LW, 3, "Innovation and uniqueness of the solution")
tf = tf_at(s, LX + 0.52, y + 0.42, LW - 0.52, 1.15)
for i, t in enumerate([
        "Most tools say a road might be blocked this month and stop there. "
        "We also work out the chance a specific trip gets caught in it, so "
        "a hill route shows up as costly, not impossible.",
        "Landslides and floods are scored separately, since they happen on "
        "different terrain in different seasons - and the whole thing runs "
        "on free data, so there is no cost to keep it running."]):
    line(tf, t, 12.5, color=INK, first=(i == 0), after=9, bullet=True, spacing=1.18)

# hero visual: the whole network, risk-coloured, straight from the app
RX, RW = 8.30, 4.48
RH = RW * 1440 / 2016
picture(s, HERO / "risk_map_tight.png", RX, 1.62, RW, RH)
rect(s, RX, 1.62, RW, RH, None, RULE, 0.75)
tf = tf_at(s, RX, 1.62 + RH + 0.07, RW, 0.55)
line(tf, "A real screenshot from our app: all 7,181 road segments we "
         "track, coloured by monsoon risk.", 10.5, color=GREY, first=True,
     spacing=1.15)

rect(s, RX, 5.70, RW, 1.20, PANEL, None)
tf = tf_at(s, RX + 0.20, 5.83, RW - 0.40, 0.98)
line(tf, "A few numbers that sum it up", 11, bold=True, first=True, after=5)
for t in ["7,181 road segments  ·  25,360 km scored",
          "5,594 villages ranked by real access",
          "₹0 data cost  ·  261 tests  ·  30 UI checks"]:
    line(tf, t, 10.5, color=GREY, after=3)

# =============================================================================
# 3  TECHNICAL APPROACH
#    Pointers kept exactly as given:
#      - Technologies to be used (e.g. programming languages, frameworks, hardware)
#      - Methodology and process for implementation (Flow Charts/Images/ working prototype)
# =============================================================================
s = S[2]; drop(s, "TextBox 8")
set_title(s, "TECHNICAL APPROACH", 27)
strap(s, "Technologies used, and how the system works end to end")

y = 1.60
used_h = pointer_head(s, 0.55, y, 12.23, 1,
                      "Technologies to be used",
                      "(e.g. programming languages, frameworks, hardware)")
groups = [
    ("Backend", "Python  ·  FastAPI  ·  NetworkX  ·  scikit-learn (optional)"),
    ("Data", "OpenStreetMap  ·  NASA POWER  ·  Copernicus DEM"),
    ("Frontend", "MapLibre GL - vendored, zero build step"),
    ("Testing", "pytest - 261 tests  ·  Playwright - 30 UI checks"),
]
gy = y + used_h + 0.08
gw, gg = 2.93, 0.13
for i, (head, body) in enumerate(groups):
    x = 0.55 + i * (gw + gg)
    rect(s, x, gy, gw, 0.74, PANEL, None)
    tf = tf_at(s, x + 0.14, gy + 0.08, gw - 0.28, 0.60)
    line(tf, head.upper(), 10, bold=True, color=BLUE, first=True, after=2)
    line(tf, body, 10.5, color=INK, spacing=1.1)

y2 = gy + 0.74 + 0.24
head2_h = pointer_head(s, 0.55, y2, 12.23, 2,
                       "Methodology and process for implementation",
                       "(Flow Charts / Images / working prototype)")

py = y2 + head2_h + 0.10
bw, bh, gap = 2.18, 1.55, 0.22
steps = [
    ("1.  Open data", "OSM roads and places\nNASA rainfall\nCopernicus elevation"),
    ("2.  Build (offline)", "Turn OSM ways into\n7,181 scored segments\nplus 5,594 villages"),
    ("3.  Engine", "Risk model (landslide\nand flood), cost model,\nmode-layered graph"),
    ("4.  Answer", "Plan a route, compare\noptions, show risk,\nshow who is cut off"),
    ("5.  Serve", "One FastAPI process:\napi and dashboard,\nno build, no CDN"),
]
for i, (t, sub) in enumerate(steps):
    x = 0.55 + i * (bw + gap)
    rect(s, x, py, bw, bh, WHITE, RULE)
    rect(s, x, py, bw, 0.36, PANEL, None)
    tf = tf_at(s, x, py, bw, 0.36, anchor=MSO_ANCHOR.MIDDLE)
    line(tf, t, 11.5, bold=True, color=BLUE, first=True, align=PP_ALIGN.CENTER,
         spacing=1.0)
    tf = tf_at(s, x + 0.12, py + 0.46, bw - 0.24, bh - 0.56,
               anchor=MSO_ANCHOR.MIDDLE)
    for j, ln in enumerate(sub.split("\n")):
        line(tf, ln, 10.5, color=GREY, first=(j == 0), align=PP_ALIGN.CENTER,
             spacing=1.2, after=2)
    if i < len(steps) - 1:
        arrow_right(s, x + bw + 0.02, py + bh / 2, w=gap - 0.04)

rect(s, 0.55, py + bh + 0.20, 12.23, 0.56, PANEL, None)
tf = tf_at(s, 0.78, py + bh + 0.33, 11.77, 0.32)
runs(tf, [("This is not a plan.  ", True, INK),
          ("All five stages run today against the real 25,360 km network we "
           "built - the map on the previous slide is a screenshot from it.",
           False, GREY)], size=10.5, first=True)

# =============================================================================
# 4  FEASIBILITY AND VIABILITY
#    Pointers kept exactly as given:
#      - Analysis of the feasibility of the idea
#      - Potential challenges and risks
#      - Strategies for overcoming these challenges
# =============================================================================
s = S[3]; drop(s, "TextBox 8")
set_title(s, "FEASIBILITY AND VIABILITY", 27)
strap(s, "What already works, and what we are upfront about")

y = 1.60
pointer_head(s, 0.55, y, 12.23, 1, "Analysis of the feasibility of the idea")
stats = [("25,360 km", "of road network we already built from open map data"),
         ("₹0", "spent on data - every source we use is free and public"),
         ("261 + 30", "automated tests and browser checks, all passing today")]
sw = (12.23 - 2 * 0.20) / 3
for i, (big, small) in enumerate(stats):
    x = 0.55 + i * (sw + 0.20)
    rect(s, x, y + 0.44, sw, 0.92, PANEL, None)
    tf = tf_at(s, x + 0.16, y + 0.55, sw - 0.32, 0.72)
    line(tf, big, 20, bold=True, color=BLUE, first=True, after=3)
    line(tf, small, 10, color=GREY, spacing=1.1)

y2 = 3.10
pointer_head(s, 0.55, y2, 6.0, 2, "Potential challenges and risks")
pointer_head(s, 6.75, y2, 6.0, 3, "Strategies for overcoming these challenges")
table(s, 0.55, y2 + 0.46, 12.23,
      [["Challenge", "Strategy"],
       ["There is no official, live feed anywhere in India that says when "
        "a road is actually closed",
        "So we predict risk from rainfall and terrain for now, and the app "
        "is being designed to also take reports from drivers directly"],
       ["OpenStreetMap has population numbers for only about 15% of "
        "villages in the region",
        "We rank villages by how many other places they help connect, not "
        "population, and plan to add the Census 2011 directory next"],
       ["Only 35 markets are mapped for all 5,594 villages we track",
        "Loading the Agmarknet market list is the very next thing we plan "
        "to do - it is the single biggest gap right now"],
       ["The free map and elevation services we use limit how much can be "
        "downloaded at once",
        "We download once, build the network offline, and save the result "
        "- so the app itself never depends on those services being up"]],
      [6.00, 6.23], aligns="ll", row_h=0.66, head_h=0.32, size=10.5)

# =============================================================================
# 5  IMPACT AND BENEFITS
#    Pointers kept exactly as given:
#      - Potential impact on the target audience
#      - Benefits of the solution (social, economic, environmental, etc.)
# =============================================================================
s = S[4]; drop(s, "TextBox 8")
set_title(s, "IMPACT AND BENEFITS", 27)
strap(s, "Who this helps, and why it matters")

y = 1.60
pointer_head(s, 0.55, y, 12.23, 1, "Potential impact on the target audience")
aw = (12.23 - 2 * 0.20) / 3
audiences = [
    ("Farmers and FPOs",
     "In Billbari, Assam, reaching a market takes 1.3 days in the "
     "monsoon. Knowing that ahead of time changes what a farmer plants "
     "and when they sell it."),
    ("Transporters and 3PLs",
     "Instead of guessing which route to take, they get a real "
     "comparison of cost, time and risk for every option available."),
    ("MDoNER, NEC and State PWDs",
     "In July, 1,309 of 4,033 major roads are at serious risk, and on "
     "1,055 of them the real problem is flooding, not landslides - so "
     "money goes to the right fix."),
]
for i, (head, body) in enumerate(audiences):
    x = 0.55 + i * (aw + 0.20)
    rect(s, x, y + 0.44, aw, 1.62, PANEL, None)
    tf = tf_at(s, x + 0.18, y + 0.56, aw - 0.36, 1.42)
    line(tf, head, 12, bold=True, color=INK, first=True, after=6)
    line(tf, body, 10.5, color=GREY, spacing=1.18)

y2 = 3.85
pointer_head(s, 0.55, y2, 12.23, 2,
             "Benefits of the solution", "(social, economic, environmental, etc.)")
benefits = [
    ("Social", "399 villages more than 20 km from any mapped road finally "
     "show up in the data, instead of being invisible to planners."),
    ("Economic", "On a single route, the best and worst choice differ by "
     "₹5,032 a tonne and 6.2 days - money currently lost to guesswork."),
    ("Environmental", "Where rail or water transport works out better, the "
     "app recommends it - cutting road-only trips that take nearly four "
     "times as long."),
]
by = y2 + 0.62
for i, (head, body) in enumerate(benefits):
    x = 0.55 + i * (aw + 0.20)
    rect(s, x, by, aw, 1.40, WHITE, RULE)
    tf = tf_at(s, x + 0.18, by + 0.14, aw - 0.36, 1.16)
    line(tf, head.upper(), 10.5, bold=True, color=BLUE, first=True, after=6)
    line(tf, body, 10.5, color=GREY, spacing=1.18)

# =============================================================================
# 6  RESEARCH AND REFERENCES
#    Pointer kept exactly as given:
#      - Details / Links of the reference and research work
# =============================================================================
s = S[5]; drop(s, "TextBox 8")
set_title(s, "RESEARCH AND REFERENCES", 27)
strap(s, "Details / Links of the reference and research work")

y = 1.62
tf = tf_at(s, 0.55, y, 6.05, 0.28)
line(tf, "Data we use", 12.5, bold=True, first=True)
table(s, 0.55, y + 0.34, 6.05,
      [["Source", "Used for"],
       ["OpenStreetMap (ODbL)\noverpass-api.de", "Roads, towns and villages"],
       ["NASA POWER\npower.larc.nasa.gov", "Monthly rainfall for each place"],
       ["Copernicus DEM via Open-Meteo\nopen-meteo.com", "Ground height, which drives the flood model"],
       ["NASA COOLR landslide catalog\nmaps.nccs.nasa.gov", "Past landslides, for training (download pending)"]],
      [2.75, 3.30], aligns="ll", row_h=0.64, head_h=0.32, size=10)

tf = tf_at(s, 6.95, y, 5.83, 0.28)
line(tf, "Policy and method we build on", 12.5, bold=True, first=True)
table(s, 6.95, y + 0.34, 5.83,
      [["Reference", "Why it matters here"],
       ["MDoNER / NEC Regional Plan", "The connectivity priorities we build against"],
       ["IWAI, National Waterway 2", "Brahmaputra navigability and terminal locations"],
       ["Dijkstra (1959)", "Shortest path - how we find the plan"],
       ["Yen (1971), Management Science 17(11)", "k shortest loopless paths - how we find alternatives"],
       ["Sagarmala and Bharatmala NE corridors", "Planned infrastructure we can re-run the model against"]],
      [2.55, 3.28], aligns="ll", row_h=0.46, head_h=0.32, size=10)

rect(s, 0.55, 5.85, 12.23, 0.62, PANEL, None)
tf = tf_at(s, 0.80, 6.00, 11.73, 0.34)
runs(tf, [("Code, tests and full method notes:  ", False, GREY),
          ("github.com/Jeffrey2600/Logistics_sih", True, INK)],
     size=12, first=True)

# =============================================================================
# Speaker notes - plain language, for whoever presents this.
# =============================================================================
NOTES = [
"""Start with the place, not the software. The eight North Eastern states
reach the rest of India through one narrow strip of land near Siliguri.
Highways are mostly single lane through hills that slide, Assam floods every
year, and for four months the monsoon shuts the roads the other eight months
depend on. That is the problem we are solving, and what follows is already
built and running, not a plan.""",

"""Point at the map on the right first and say plainly: this is a screenshot
of our own application, not an illustration. Then walk the three points on
the left in order.

Point one is what we built. Point two is why it matters - we turn a guess
about the monsoon into an actual number before the truck leaves. Point three
is the one thing worth slowing down for: we separate "this road might close
this month" from "this specific trip will be stopped by it." Treating those
as the same thing is the usual mistake, and it makes every hill road look
unusable instead of just more expensive.""",

"""Top: four groups of tools, ten seconds each - point and move on, no need
to read every word out loud.

Bottom: the same idea as a flow chart. Data comes in, we build a scored
network from it offline, an engine turns that into risk and cost, four
features answer real questions, and one process serves all of it. When you
reach box five, mention there is no build step and no CDN - that is why the
demo still works even if the venue's wifi blocks something.""",

"""Left: three numbers that show this already exists - 25,360 km built, zero
rupees spent on data, 261 tests passing. Say them and move on.

Right is the table judges will look at closest. Every challenge sits right
across from what we are doing about it. Lead with the first row: India has
no live road-closure feed anywhere, so we predict from rainfall and terrain
instead, and we are designing the app to learn from driver reports later.
Naming that gap yourself, before anyone asks, is stronger than waiting to be
caught out.""",

"""Three audiences, three examples. Read the Billbari line out loud - it is
the most human one, a farmer knowing it takes 1.3 days to reach a market in
the monsoon changes what they plant. For a policy-focused panel, use the
MDoNER card instead: 1,309 of 4,033 major roads at serious risk in July, and
on 1,055 of them the real cause is flooding, not landslides - so money gets
spent fixing the right problem.

Bottom row is social, economic, environmental, one line each - only read all
three if asked, they are there to show we thought about it.""",

"""Keep this one short. Everything we used is open and free, so there is
nothing to license before this can be deployed anywhere. Be upfront that the
landslide catalogue download is still pending rather than implying it is
already loaded - if someone checks, honesty here counts for more than
looking complete. Close by pointing at the GitHub link: the code and tests
are public.""",
]

for i, text in enumerate(NOTES):
    S[i].notes_slide.notes_text_frame.text = text.strip()

prs.save(OUT)
print("wrote", OUT, "with", len(prs.slides._sldIdLst), "slides")
