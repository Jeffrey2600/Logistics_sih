# -*- coding: utf-8 -*-
"""Build the SIH26002 submission deck on the official SIH 2026 Idea template.

Usage: python build2.py <template.pptx> <out.pptx> <screenshot-dir>

Every figure here is produced by the code in this repository. Nothing is
estimated. See docs/presentation/README.md for how the numbers were taken.
"""
import sys
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

SRC, OUT = sys.argv[1], sys.argv[2]
SHOTS = Path(sys.argv[3])

# A near-monochrome sheet. Colour is reserved for the risk bands, where it
# carries meaning, and one blue for structure.
INK   = RGBColor(0x1A, 0x1A, 0x1A)
GREY  = RGBColor(0x5F, 0x5F, 0x5F)
FAINT = RGBColor(0x8A, 0x8A, 0x8A)
RULE  = RGBColor(0xBF, 0xBF, 0xBF)
PANEL = RGBColor(0xF0, 0xF0, 0xF0)
BAND  = RGBColor(0xE4, 0xE8, 0xEB)
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
         align=PP_ALIGN.LEFT, spacing=1.15, italic=False):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    p.line_spacing = spacing
    p.space_after = Pt(after)
    r = p.add_run(); r.text = text
    r.font.size = Pt(size); r.font.bold = bold; r.font.italic = italic
    r.font.name = F; r.font.color.rgb = color
    return p


def runs(tf, parts, size=11, first=False, after=0, spacing=1.15):
    """One paragraph made of (text, bold, colour) parts."""
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.line_spacing = spacing
    p.space_after = Pt(after)
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
    """A labelled box in a diagram."""
    rect(slide, x, y, w, h, fill, border)
    tf = tf_at(slide, x + 0.07, y, w - 0.14, h, anchor=MSO_ANCHOR.MIDDLE)
    line(tf, title, title_size, bold=True, color=title_color, first=True,
         align=PP_ALIGN.CENTER, spacing=1.0, after=1 if sub else 0)
    if sub:
        line(tf, sub, sub_size, color=GREY, align=PP_ALIGN.CENTER, spacing=1.0)
    return tf


def arrow_down(slide, cx, y, h=0.22, w=0.16, color=FAINT):
    sh = slide.shapes.add_shape(MSO_SHAPE.DOWN_ARROW, Inches(cx - w / 2),
                                Inches(y), Inches(w), Inches(h))
    sh.fill.solid(); sh.fill.fore_color.rgb = color
    sh.line.fill.background(); sh.shadow.inherit = False
    sh.text_frame.text = ""
    return sh


def arrow_right(slide, x, cy, w=0.30, h=0.14, color=FAINT):
    sh = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x),
                                Inches(cy - h / 2), Inches(w), Inches(h))
    sh.fill.solid(); sh.fill.fore_color.rgb = color
    sh.line.fill.background(); sh.shadow.inherit = False
    sh.text_frame.text = ""
    return sh


def table(slide, x, y, w, rows, widths, row_h=0.30, head_h=0.30, size=10,
          head_size=9.5, aligns=None, head_fill=BAND):
    """A plain data table. Header row, hairline rules, no banding."""
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
            cell.margin_left = Inches(0.07); cell.margin_right = Inches(0.07)
            cell.margin_top = Inches(0.02); cell.margin_bottom = Inches(0.02)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            cell.fill.fore_color.rgb = head_fill if r == 0 else WHITE
            tfr = cell.text_frame
            tfr.word_wrap = True
            p = tfr.paragraphs[0]
            p.line_spacing = 1.0
            if aligns:
                p.alignment = {"l": PP_ALIGN.LEFT, "r": PP_ALIGN.RIGHT,
                               "c": PP_ALIGN.CENTER}[aligns[c]]
            txt, bold, color = (val if isinstance(val, tuple)
                                else (val, r == 0, INK if r == 0 else INK))
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


# ---------------------------------------------------------------- slide frame

prs = Presentation(SRC)


def set_title(slide, text, size=28):
    for sh in slide.shapes:
        if sh.has_text_frame and sh.name.startswith("Title"):
            sh.left, sh.width = Inches(1.95), Inches(8.55)
            sh.top, sh.height = Inches(0.12), Inches(1.00)
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


def strap(slide, text, y=1.18):
    tf = tf_at(slide, 0.55, y, 12.2, 0.28)
    line(tf, text, 11.5, color=BLUE, first=True)


def drop(slide, *names):
    for sh in list(slide.shapes):
        if sh.name in names:
            sh._element.getparent().remove(sh._element)


# =============================================================================
# The template ships six content slides and one instructions slide. We keep the
# six it mandates and add annexure slides after them, which is normal practice
# for SIH: the six carry the submission, the annexure carries the evidence.
# =============================================================================
xml_slides = prs.slides._sldIdLst
lst = list(xml_slides)
prs.part.drop_rel(lst[6].rId)          # the "important instructions" slide
xml_slides.remove(lst[6])
S = prs.slides


_LOGO = None


def clone(index_from=5):
    """Copy an existing content slide, so the SIH furniture comes with it.

    Pictures are re-added rather than deep-copied: a copied <p:pic> keeps the
    source slide's r:embed, which points at a relationship the new slide does
    not have, and PowerPoint reports the whole file as corrupt.
    """
    global _LOGO
    from copy import deepcopy
    import tempfile

    src = S[index_from]
    new = prs.slides.add_slide(src.slide_layout)
    for shape in list(new.shapes):
        shape._element.getparent().remove(shape._element)

    for shape in src.shapes:
        if shape.shape_type == 13:                       # the SIH logo
            if _LOGO is None:
                fh = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                fh.write(shape.image.blob); fh.close()
                _LOGO = fh.name
            new.shapes.add_picture(_LOGO, shape.left, shape.top,
                                   shape.width, shape.height)
        elif shape.name in ("Rectangle 9", "Rectangle 10", "Oval 8", "Oval 9",
                            "Oval 10", "Oval 11",
                            "Slide Number Placeholder 5",
                            "Footer Placeholder 6", "Title 1"):
            new.shapes._spTree.append(deepcopy(shape._element))
    return new


# =============================================================================
# 1  Title page
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
# 2  Idea / proposed solution
# =============================================================================
s = S[1]; drop(s, "TextBox 8")
set_title(s, "Plan freight for the North East the way the region actually works", 24)
strap(s, "Proposed solution")

tf = tf_at(s, 0.55, 1.62, 6.55, 0.30)
line(tf, "The problem, plainly", 13, bold=True, first=True)
tf = tf_at(s, 0.55, 1.98, 6.55, 1.55)
line(tf, "The eight North Eastern states reach the rest of India through one "
         "22 km strip of land at Siliguri. Highways run single-lane through "
         "hills that slide. Assam floods every year. The Brahmaputra is a "
         "national waterway that is barely used. For four months the monsoon "
         "closes the roads the other eight months depend on.",
     11, color=GREY, first=True, after=6)
line(tf, "A shipper today picks a route off a map and a rate card. Neither "
         "of them knows any of this.", 11, color=INK, bold=True)

tf = tf_at(s, 0.55, 3.72, 6.55, 0.30)
line(tf, "What we built", 13, bold=True, first=True)
tf = tf_at(s, 0.55, 4.08, 6.55, 1.30)
runs(tf, [("One web application that answers two questions.  ", False, GREY),
          ("First", True, INK),
          (", what is the cheapest sensible way to move this consignment this "
           "month — road, rail, river, air, or a mix — and what does it cost "
           "in rupees and days?  ", False, GREY),
          ("Second", True, INK),
          (", which towns and villages are cut off, how much worse does the "
           "monsoon make it, and where should the next market or cold store "
           "go?", False, GREY)], size=11, first=True)

tf = tf_at(s, 0.55, 5.52, 6.55, 0.30)
line(tf, "Why this is not a map with a route on it", 13, bold=True, first=True)
tf = tf_at(s, 0.55, 5.88, 6.55, 0.80)
line(tf, "We do not pick the shortest road. We score every stretch on what it "
         "costs, how long it takes, and how likely the monsoon is to shut it — "
         "then compare whole journeys, charging for every change of vehicle.",
     11, color=GREY, first=True)

# the same lane, four ways - the argument in one table
tf = tf_at(s, 7.35, 1.62, 5.43, 0.30)
line(tf, "Kohima to Guwahati in July, as the app reports it", 12.5, bold=True,
     first=True)
tf = tf_at(s, 7.35, 1.94, 5.43, 0.26)
line(tf, "One tonne of general cargo. Figures taken from the running system.",
     9.5, color=FAINT, first=True)
table(s, 7.35, 2.28, 5.43,
      [["Way of moving it", "Days", "Cost/tonne", "Delay"],
       ["Road, then rail  (chosen)", "2.0", "₹928", "22.3 h"],
       ["Road, then air", "1.4", "₹5,954", "19.1 h"],
       ["Road only", "7.6", "₹1,661", "5.8 d"],
       ["Cheapest on paper", "2.0", "₹922", "22.3 h"]],
      [2.43, 0.75, 1.20, 1.05], aligns="lrrr", row_h=0.32, head_h=0.30, size=10)

tf = tf_at(s, 7.35, 4.05, 5.43, 1.05)
runs(tf, [("Between the best and the worst choice on this one lane there is ",
           False, GREY),
          ("₹5,032 per tonne and 6.2 days", True, INK),
          (". Road only — the obvious answer — is the worst of the four. "
           "That gap is what the platform is for.", False, GREY)],
     size=11, first=True)

rect(s, 7.35, 5.30, 5.43, 1.38, PANEL, None)
tf = tf_at(s, 7.58, 5.48, 4.97, 1.02)
line(tf, "What is different about it", 11, bold=True, first=True, after=4)
line(tf, "Changing vehicle is charged, not free. Risk is a cost in hours and "
         "rupees, not a warning label. And the chance a road shuts sometime in "
         "July is kept separate from the chance this lorry meets it.",
     10, color=GREY)

# =============================================================================
# 3  Technical approach - the system, drawn
# =============================================================================
s = S[2]; drop(s, "TextBox 8")
set_title(s, "TECHNICAL APPROACH", 28)
strap(s, "How the system is put together")

L, R = 0.55, 12.78
mid = (L + R) / 2
dmid = (1.85 + R) / 2   # the diagram sits right of the band labels

def band_label(y, text):
    tf = tf_at(s, L, y, 1.55, 0.24, anchor=MSO_ANCHOR.MIDDLE)
    line(tf, text, 9, bold=True, color=FAINT, first=True)

# band 1 - open data in
band_label(1.62, "OPEN DATA")
w1, g1 = 3.44, 0.30
for i, (t, sub) in enumerate([
        ("OpenStreetMap", "roads, towns, villages"),
        ("NASA POWER", "monthly rainfall, per place"),
        ("Copernicus DEM", "ground height, per node")]):
    dbox(s, 1.85 + i * (w1 + g1), 1.56, w1, 0.56, t, sub)
arrow_down(s, dmid, 2.20)

# band 2 - build
band_label(2.60, "BUILD  (offline)")
dbox(s, 1.85, 2.48, 5.30, 0.62, "Road network builder",
     "OSM ways contracted to 7,181 segments over 6,502 junctions · 25,360 km")
dbox(s, 7.45, 2.48, 5.33, 0.62, "Settlement builder",
     "5,594 towns and villages joined to their nearest road")
arrow_down(s, dmid, 3.18)

# band 3 - the engine
band_label(3.62, "ENGINE")
rect(s, 1.85, 3.46, 10.93, 1.30, PANEL, None)
for i, (t, sub) in enumerate([
        ("Risk model", "landslide + flood\nper segment, per month"),
        ("Cost model", "₹ per tonne, hours,\nhandling at every transfer"),
        ("Layered graph", "road / rail / water / air\njoined by transfer edges")]):
    dbox(s, 2.03 + i * 3.57, 3.62, 3.39, 0.98, t, sub, WHITE, RULE, 10.5, 8.5)
arrow_down(s, dmid, 4.84)

# band 4 - what it answers
band_label(5.28, "ANSWERS")
w4 = 2.65
for i, (t, sub) in enumerate([
        ("Plan a shipment", "best route + alternatives"),
        ("Compare options", "seven ways, side by side"),
        ("Monsoon risk map", "every road, any month"),
        ("Who is cut off", "hours to market, siting")]):
    dbox(s, 1.85 + i * (w4 + 0.11), 5.12, w4, 0.60, t, sub, WHITE, RULE, 10, 8)
arrow_down(s, dmid, 5.80)

# band 5 - delivery
dbox(s, 1.85, 6.06, 10.93, 0.52,
     "One FastAPI process serves the API and the dashboard",
     "Python · NetworkX · scikit-learn (optional) · MapLibre GL vendored locally · no build step, no CDN, no API key",
     BAND, None, 10.5, 8.5)

tf = tf_at(s, L, 6.66, 12.23, 0.24)
line(tf, "Everything left of the dashboard runs offline. The built network, the "
         "rainfall and the elevation are committed to the repository, so a "
         "fresh clone works with no internet.", 9.5, color=FAINT, first=True)


# =============================================================================
# 4  Feasibility and viability
# =============================================================================
s = S[3]; drop(s, "TextBox 8")
set_title(s, "FEASIBILITY AND VIABILITY", 28)
strap(s, "It is already built, and it runs on nothing but free data")

tf = tf_at(s, 0.55, 1.60, 6.05, 0.28)
line(tf, "What exists today", 12.5, bold=True, first=True)
table(s, 0.55, 1.92, 6.05,
      [["What", "How much", "Where it came from"],
       ["Road network", "25,360 km", "OpenStreetMap"],
       ["Road segments scored", "7,181", "built here"],
       ["Towns and villages", "5,594", "OpenStreetMap"],
       ["Rainfall, per place", "12 months", "NASA POWER"],
       ["Ground elevation", "8 – 4,016 m", "Copernicus DEM"],
       ["Automated tests", "261 + 30", "written here"],
       ["Cost of the data", "₹0", "all of it is open"]],
      [2.30, 1.55, 2.20], aligns="lrl", row_h=0.295, head_h=0.29, size=10)

tf = tf_at(s, 0.55, 4.55, 6.05, 0.95)
runs(tf, [("It runs offline. ", True, INK),
          ("The built network, the rainfall and the elevation are committed to "
           "the repository, so a fresh clone starts with no API key, no account "
           "and no download. Two commands and it is on screen.", False, GREY)],
     size=11, first=True)

rect(s, 0.55, 5.62, 6.05, 1.05, PANEL, None)
tf = tf_at(s, 0.78, 5.80, 5.59, 0.72)
line(tf, "Cost to run it for a year", 10.5, bold=True, first=True, after=3)
line(tf, "₹0 for data. One free-tier web service hosts it. The heaviest "
         "computation is a graph search that finishes in about a second.",
     10, color=GREY)

tf = tf_at(s, 6.95, 1.60, 5.83, 0.28)
line(tf, "What could go wrong, and what we did about it", 12.5, bold=True,
     first=True)

items = [
    ("India has no live road-closure feed.",
     "No state PWD publishes closures in a form software can read. So we "
     "predict from rainfall and terrain instead of observing, and the app is "
     "built to take driver reports later and learn from them."),
    ("Population is missing for most villages.",
     "OpenStreetMap has a population figure for only 15% of them. Ranking by "
     "population would rank where volunteers typed a number — on the real "
     "network that reversed our cold-store answer. So we rank by how many "
     "settlements a site reaches. Census 2011 would fix it properly."),
    ("Only 35 markets are mapped for 5,594 villages.",
     "So the 'hours to a market' figures are pessimistic and many places score "
     "zero. It is the first thing to fix, and Agmarknet has the data."),
    ("The free map and elevation services rate-limit.",
     "Downloading is a separate step with an offline path. One person fetches "
     "once; everyone else builds from the saved file."),
]
y = 1.95
for head, body in items:
    tf = tf_at(s, 6.95, y, 5.83, 0.26)
    line(tf, head, 11, bold=True, first=True)
    tf = tf_at(s, 6.95, y + 0.26, 5.83, 0.90)
    line(tf, body, 10, color=GREY, first=True, spacing=1.12)
    y += 1.22

# =============================================================================
# 5  Impact and benefits
# =============================================================================
s = S[4]; drop(s, "TextBox 8")
set_title(s, "IMPACT AND BENEFITS", 28)
strap(s, "Numbers the running system produced, not estimates")

tf = tf_at(s, 0.55, 1.60, 6.95, 0.28)
line(tf, "One lane, one month: Kohima to Guwahati in July", 12.5, bold=True,
     first=True)
table(s, 0.55, 1.92, 6.95,
      [["How you move it", "Door to door", "Cost per tonne", "Delay expected"],
       [("Road, then rail — recommended", True, INK), ("2.0 d", True, INK),
        ("₹928", True, INK), ("22.3 h", True, INK)],
       ["Cheapest on paper", "2.0 d", "₹922", "22.3 h"],
       ["Road, then air — fastest", "1.4 d", "₹5,954", "19.1 h"],
       ["Road only", "7.6 d", "₹1,661", "5.8 d"]],
      [2.85, 1.30, 1.45, 1.35], aligns="lrrr", row_h=0.32, head_h=0.30, size=10)

tf = tf_at(s, 0.55, 3.65, 6.95, 0.62)
runs(tf, [("Choosing badly on this one lane costs ", False, GREY),
          ("₹5,032 per tonne, or 6.2 days", True, INK),
          (". Road only — the answer most people would give — is the worst of "
           "the four.", False, GREY)], size=11.5, first=True)

tf = tf_at(s, 0.55, 4.45, 6.95, 0.28)
line(tf, "What the monsoon does, on the same plan", 12.5, bold=True, first=True)
table(s, 0.55, 4.77, 6.95,
      [["Aizawl to Guwahati, road and rail", "January", "July", "Change"],
       ["Door to door", "64.5 h", "135.3 h", ("+70.8 h", True, RED)],
       ["Cost per tonne", "₹1,715", "₹2,102", ("+₹387", True, RED)],
       ["Worst stretch, chance of closing", "8%", "48%", ("+40 pts", True, RED)]],
      [3.15, 1.20, 1.20, 1.40], aligns="lrrr", row_h=0.30, head_h=0.30, size=10)

tf = tf_at(s, 8.05, 1.60, 4.73, 0.28)
line(tf, "Who this helps", 12.5, bold=True, first=True)
who = [
    ("Farmers and FPOs",
     "Billbari in Assam is 1.3 days from a market in the monsoon. Knowing that "
     "before harvest changes what you plant and when you sell it."),
    ("Transporters and 3PLs",
     "A defended mode mix per consignment, with handling charged and the "
     "monsoon delay priced, instead of a rate card and a guess."),
    ("MDoNER, NEC and state PWDs",
     "Rank corridor spending by the risk that is actually there. In July, "
     "1,309 of 4,033 major roads are at severe risk — and on 1,055 of them the "
     "problem is flooding, not landslides. You do not fix a flood with slope "
     "netting."),
    ("Disaster management cells",
     "See which places lose their road link first, before the season starts."),
]
y = 1.95
for head, body in who:
    tf = tf_at(s, 8.05, y, 4.73, 0.26)
    line(tf, head, 11, bold=True, first=True)
    tf = tf_at(s, 8.05, y + 0.26, 4.73, 0.92)
    line(tf, body, 10, color=GREY, first=True, spacing=1.12)
    y += 1.24

# =============================================================================
# 6  Research and references
# =============================================================================
s = S[5]; drop(s, "TextBox 8")
set_title(s, "RESEARCH AND REFERENCES", 28)
strap(s, "Everything used here is open, free and cited in the repository")

tf = tf_at(s, 0.55, 1.60, 6.05, 0.28)
line(tf, "Data", 12.5, bold=True, first=True)
table(s, 0.55, 1.92, 6.05,
      [["Source", "Used for"],
       ["OpenStreetMap (ODbL)\noverpass-api.de", "Roads, towns and villages"],
       ["NASA POWER\npower.larc.nasa.gov", "Monthly rainfall for each place"],
       ["Copernicus DEM via Open-Meteo\nopen-meteo.com", "Ground height, which drives the flood model"],
       ["NASA COOLR landslide catalog\nmaps.nccs.nasa.gov", "Past landslides, for training (download pending)"]],
      [2.75, 3.30], aligns="ll", row_h=0.62, head_h=0.30, size=9.5)

tf = tf_at(s, 6.95, 1.60, 5.83, 0.28)
line(tf, "Policy and method", 12.5, bold=True, first=True)
table(s, 6.95, 1.92, 5.83,
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
# ANNEXURE. The six slides above are the submission. These carry the evidence:
# how the risk number is arrived at, and what the running application shows.
# =============================================================================
SHOT_W, SHOT_H = 8.30, 4.93          # 3200x1900 screenshots
NOTE_X, NOTE_W = 9.10, 3.68


def result_slide(title, strapline, shot, notes, footnote=None):
    s = clone()
    set_title(s, title, 26)
    strap(s, strapline)
    picture(s, SHOTS / shot, 0.55, 1.58, SHOT_W, SHOT_H)
    rect(s, 0.55, 1.58, SHOT_W, SHOT_H, None, RULE, 0.75)
    y = 1.58
    for head, body in notes:
        tf = tf_at(s, NOTE_X, y, NOTE_W, 0.26)
        line(tf, head, 11, bold=True, first=True)
        tf = tf_at(s, NOTE_X, y + 0.25, NOTE_W, 0.95)
        line(tf, body, 10, color=GREY, first=True, spacing=1.13)
        y += 1.18
    if footnote:
        tf = tf_at(s, 0.55, 6.60, 12.23, 0.24)
        line(tf, footnote, 9, color=FAINT, first=True)
    return s


# --- A1  how a risk number is built -----------------------------------------
s = clone()
set_title(s, "How one road gets its risk number", 26)
strap(s, "Worked through on a real segment: Nolikata – Ranikor, Meghalaya, in July")

col = [("Terrain", "plain, from how much\nthe road bends"),
       ("Rainfall", "NASA POWER, this\nplace, this month"),
       ("Ground height", "Copernicus DEM,\nmetres above sea"),
       ("Carriageway", "1 lane, from the\nOSM tags")]
for i, (t, sub) in enumerate(col):
    dbox(s, 0.55 + i * 3.13, 1.62, 2.93, 0.72, t, sub, WHITE, RULE, 10.5, 8.5)
    arrow_down(s, 0.55 + i * 3.13 + 1.465, 2.42, 0.20)

rect(s, 0.55, 2.74, 12.23, 1.02, PANEL, None)
dbox(s, 0.90, 2.92, 5.35, 0.66, "Landslide susceptibility",
     "steepness + rainfall + how narrow the road is", WHITE, RULE, 11, 9)
dbox(s, 7.08, 2.92, 5.35, 0.66, "Flood susceptibility",
     "how low and flat the ground is + the season", WHITE, RULE, 11, 9)
tf = tf_at(s, 0.90, 3.58, 5.35, 0.22)
line(tf, "0.2821", 10.5, bold=True, color=AMBER, first=True, align=PP_ALIGN.CENTER)
tf = tf_at(s, 7.08, 3.58, 5.35, 0.22)
line(tf, "0.3981", 10.5, bold=True, color=AMBER, first=True, align=PP_ALIGN.CENTER)
arrow_down(s, mid, 3.84, 0.22)

dbox(s, 3.30, 4.16, 6.73, 0.62,
     "Combine them as two independent hazards",
     "1 − (1 − 0.2821) × (1 − 0.3981)  =  0.5679", BAND, None, 11, 10)
arrow_down(s, mid, 4.86, 0.22)

dbox(s, 0.55, 5.18, 3.90, 0.70, "57% chance of being blocked",
     "at some point in July — this is what the map colours",
     WHITE, RED, 11, 8.5, RED)
dbox(s, 4.75, 5.18, 3.83, 0.70, "11% chance this lorry meets it",
     "a trip crosses in hours, not all month", WHITE, RULE, 11, 8.5)
dbox(s, 8.88, 5.18, 3.90, 0.70, "5.1 hours of expected delay",
     "which is what enters the cost of the route", WHITE, RULE, 11, 8.5)

rect(s, 0.55, 6.06, 12.23, 0.62, PANEL, None)
tf = tf_at(s, 0.80, 6.20, 11.73, 0.36)
runs(tf, [("Why the middle box matters.  ", True, INK),
          ("Treating 'this road is blocked sometime in July' as 'this lorry "
           "will be blocked' prices every hill route as if the closure were "
           "certain. Every mountain road then looks unusable rather than "
           "merely expensive, and the plan flies everything.", False, GREY)],
     size=10.5, first=True)

# --- A2  plan a shipment ----------------------------------------------------
result_slide(
    "Result 1 — Plan a shipment", "Kohima to Guwahati, July, one tonne of general cargo",
    "01-route.png",
    [("You pick five things",
      "Where from, where to, which month, what you are shipping, and what "
      "matters most. Modes can be switched off one by one."),
     ("It answers in four numbers",
      "2.0 days door to door, ₹928 a tonne, 338.1 km travelled, and 22.3 hours "
      "of delay already counted inside the 2.0 days."),
     ("The colour change is the point",
      "Blue is road, purple is rail. Where the line changes colour the cargo "
      "is unloaded and reloaded, and the app charges 6 hours and ₹250 a tonne "
      "for it at Dimapur."),
     ("Below the fold, leg by leg",
      "“Transhipment at Dimapur, road to rail, 6.0 h, ₹250/t.” Then "
      "“Dimapur to Guwahati, rail, NFR, 290 km, 12.3 h, elevated risk.” "
      "Every leg, with its highway number and its risk band.")],
    "Screenshot taken from the running application. The basemap tiles are blocked "
    "on this network, so the map draws our own data on a blank ground — by design.")

# --- A3  the risk map -------------------------------------------------------
result_slide(
    "Result 2 — Monsoon risk, every road", "The whole network in July, coloured by the chance of being blocked",
    "02-risk.png",
    [("4,067 roads over 5 km",
      "Shorter link roads are hidden by the slider, because thousands of "
      "30-metre stubs make the picture unreadable."),
     ("Green, amber, red",
      "Usually open, often disrupted, frequently blocked. Line thickness "
      "repeats the same information, so the map still works for a "
      "colour-blind viewer and in black and white."),
     ("Slide the month",
      "Watch the network deteriorate through June to September and recover. "
      "The hazard box separates landslides from floods, because they hit "
      "different roads."),
     ("The worst list is Meghalaya, and it is flood",
      "Shella and Jasir at 57%. Of all the roads shown, 6,316 are at more "
      "risk from flooding than from landslides.")])

# --- A4  who is cut off -----------------------------------------------------
result_slide(
    "Result 3 — Who is cut off", "5,505 towns and villages scored on travel hours, not map distance",
    "03-access.png",
    [("Scored out of 100",
      "100 is a place with a market, cold storage and the national gateway all "
      "close by. The score blends travel time to each, plus how much worse the "
      "monsoon makes it."),
     ("Hours, never kilometres",
      "The score comes from a search over the real network. A village 20 km "
      "away across a gorge is not 20 km away."),
     ("Namsai is 4.0 days from a market",
      "Changliang in Arunachal is 7.1 days. Billbari in Assam is 1.3 days — "
      "and that is in the monsoon."),
     ("Mostly red, and we say why",
      "Only 35 markets are mapped in the whole region, so the scores are "
      "pessimistic. Loading the Agmarknet market list is the single biggest "
      "improvement left.")])

# --- A5  compare the options ------------------------------------------------
s = clone()
set_title(s, "Result 4 — Compare every option", 26)
strap(s, "The same consignment, seven ways, with the app's own plain-English reading")

# The Analysis tab leaves the map on whatever the previous tab drew, so the
# map adds nothing here. Crop to the panel, which is the actual result, and
# show it big enough to read.
picture(s, SHOTS / "04b-compare-crop.png", 0.55, 1.58, 2.77, 5.07)
rect(s, 0.55, 1.58, 2.77, 5.07, None, RULE, 0.75)

tf = tf_at(s, 0.55, 6.74, 2.77, 0.30)
line(tf, "The Analysis panel, full height", 9, color=FAINT, first=True)

rect(s, 3.62, 5.92, 9.16, 0.75, PANEL, None)
tf = tf_at(s, 3.87, 6.06, 8.66, 0.50)
runs(tf, [("The app writes this itself:  ", True, INK),
          ("“Across all options the spread is ₹5,032 per tonne and 6.2 days "
           "— the cost of choosing badly on this lane.”", False, GREY)],
     size=11.5, first=True)

tf = tf_at(s, 3.62, 1.58, 9.16, 0.26)
line(tf, "Every option, as the app lists it", 11.5, bold=True, first=True)
table(s, 3.62, 1.90, 9.16,
      [["Option", "Route", "Time", "Cost/t"],
       [("Recommended", True, INK), ("road → rail", True, INK),
        ("2.0 d", True, INK), ("₹928", True, INK)],
       ["Lowest freight cost", "road → rail", "2.0 d", "₹922"],
       ["Fastest door to door", "road → air", "1.4 d", "₹5,954"],
       ["Most reliable", "road → rail", "2.0 d", "₹928"],
       ["Road only", "road", "7.6 d", "₹1,661"],
       ["Surface only", "road → rail", "2.0 d", "₹928"],
       ["Rail and waterway", "road → rail", "2.0 d", "₹928"]],
      [3.28, 2.30, 1.68, 1.90], aligns="llrr", row_h=0.33, head_h=0.31, size=10.5)

tf = tf_at(s, 3.62, 4.66, 4.42, 0.26)
line(tf, "Why several options look identical", 11, bold=True, first=True)
tf = tf_at(s, 3.62, 4.94, 4.42, 0.85)
line(tf, "Because on this lane they are. Only 4 of the 7 are genuinely "
         "different journeys, and the app says so rather than padding the "
         "table out to look busy.", 10, color=GREY, first=True)

tf = tf_at(s, 8.36, 4.66, 4.42, 0.26)
line(tf, "Reading the fastest row", 11, bold=True, first=True)
tf = tf_at(s, 8.36, 4.94, 4.42, 0.95)
line(tf, "Air saves 14.1 hours and costs ₹5,026 a tonne more. Worth it only if "
         "the cargo loses more than that while it waits — which is exactly the "
         "judgement a rate card cannot make for you.", 10, color=GREY,
     first=True)

# --- A6  status -------------------------------------------------------------
s = clone()
set_title(s, "What is finished, and what comes next", 26)
strap(s, "Stated plainly, because the gaps are as informative as the features")

tf = tf_at(s, 0.55, 1.60, 6.05, 0.28)
line(tf, "Working now", 12.5, bold=True, first=True)
table(s, 0.55, 1.92, 6.05,
      [["Capability", "State"],
       ["Multimodal route planning", "Working"],
       ["Alternative routes", "Working"],
       ["Dry season vs monsoon comparison", "Working"],
       ["Option comparison, seven scenarios", "Working"],
       ["Risk map, landslide and flood", "Working"],
       ["Accessibility scoring, 5,505 places", "Working"],
       ["Facility siting", "Working"],
       ["Closure simulation (shut a road, re-plan)", "Working"]],
      [4.35, 1.70], aligns="ll", row_h=0.30, head_h=0.29, size=10)

tf = tf_at(s, 6.95, 1.60, 5.83, 0.28)
line(tf, "Next, in the order we would do it", 12.5, bold=True, first=True)
nxt = [
    ("Load the Agmarknet market list",
     "35 mapped markets for 5,594 villages is why most places score zero. "
     "This is the one change that most improves the accessibility answer."),
    ("Join the Census 2011 village directory",
     "Replaces the 15% of population figures OpenStreetMap happens to carry."),
    ("Add observed flood extent (Sentinel-1)",
     "Replaces the single constant that stands in for how much floodplain road "
     "is actually cut in a normal monsoon."),
    ("Collect closure reports in the app",
     "The only way to turn a prediction into something that learns."),
]
y = 1.95
for head, body in nxt:
    tf = tf_at(s, 6.95, y, 5.83, 0.26)
    line(tf, head, 11, bold=True, first=True)
    tf = tf_at(s, 6.95, y + 0.26, 5.83, 0.80)
    line(tf, body, 10, color=GREY, first=True, spacing=1.12)
    y += 1.02

rect(s, 0.55, 5.35, 6.05, 1.32, PANEL, None)
tf = tf_at(s, 0.80, 5.52, 5.55, 1.00)
line(tf, "Not modelled, and worth saying out loud", 11, bold=True, first=True,
     after=4)
line(tf, "Earthquakes. The North East is in Seismic Zone V, India's highest, so "
         "a major quake is the single largest threat to these corridors — and "
         "this platform says nothing about it. Nor about bandhs, blockades or "
         "bridge failures.", 10, color=GREY)

# =============================================================================
# Speaker notes. Written for someone presenting this who did not build it:
# what to say, in the order to say it, in plain words.
# =============================================================================
NOTES = [
"""Start with the place, not the software. Nobody in the room has driven these roads.

Say: the eight North Eastern states are joined to the rest of India by one
strip of land about 22 km wide, near Siliguri. The highways are mostly single
lane and they run through hills that slide. Assam floods every year. And for
four months of the year the monsoon shuts the roads that the other eight months
depend on.

MDoNER asked for a platform that plans freight across all of that and tells
them which places are cut off. We built both halves, and it is running
software - the screenshots later in this deck are from the live app, not
mock-ups.""",

"""One sentence to land here: everyone else finds the shortest road; the North
East punishes that.

Walk the left side first, then let the table do the work.

The table is the whole argument. The same one tonne, Kohima to Guwahati, in
July. Road then rail is 2 days and ₹928. Air is faster but ₹5,954. Road only -
which is what most people would say - is 7.6 days, the worst of the four.

So the gap between a good choice and an obvious choice on this single lane is
₹5,032 a tonne. Multiply that across a season.

If asked what is new: three things. Changing vehicle costs money and time in our
model, not zero. Risk is converted into hours and rupees instead of a warning
colour. And we keep 'this road shuts sometime in July' separate from 'this lorry
will be stopped' - which sounds like a detail and is not, and there is a whole
slide on it later.""",

"""Do not read every box. Point at the shape and give it four sentences.

Top: three free, open data sources. No licences, no keys.

Middle: we turn OpenStreetMap into something a computer can route on.
OpenStreetMap is a drawing, not a road network - one highway is hundreds of
separate pieces - so we join them into 7,181 real segments.

The engine is three parts: what a road costs, how likely it is to be blocked,
and a graph where road, rail, river and air are separate layers joined by
transfer links.

Bottom: one Python process serves both the API and the dashboard. No build step,
nothing downloaded at runtime. Point at that line and say: this is why the demo
will work even if the venue wifi does not.""",

"""This is the slide that separates a working thing from an idea.

Left table: read out two numbers only - 25,360 km of road, and ₹0 for data.
Everything else is on the slide if they want it.

Then say it runs offline: clone it, install, two commands, it is on screen.

Right side is the honest half, and judges reward it. The strongest one is the
first: India has no live road-closure feed. No state publishes closures in a
form software can read. So we predict from rainfall and terrain, and we built
the app so that driver reports can be collected later and used to correct it.

The third one - only 35 markets mapped - is the weakness in our own numbers, and
we say so before anyone asks.""",

"""Numbers first, people second.

Top table: the cost of choosing badly on one lane is ₹5,032 a tonne.

Second table: the monsoon adds 70.8 hours and ₹387 a tonne to the same Aizawl
to Guwahati plan, and the worst stretch on it goes from an 8% chance of closing
to 48%.

Right side, pick the one that suits the panel. For a policy audience, use the
MDoNER line: in July, 1,309 of 4,033 major roads are at severe risk, and on
1,055 of them the problem is flooding, not landslides. You cannot fix a flood
with slope netting - so knowing which is which changes what gets built.

For a general audience use Billbari: 1.3 days to reach a market in the monsoon.
That is a farmer's decision about what to plant.""",

"""Keep this short. The point is that nothing here is bought, scraped or
restricted, so the platform can actually be deployed.

Mention that the landslide catalogue download is still pending rather than
implying it is loaded - if a judge checks, they will find it, and saying it
first is worth more than hiding it.

End on the repository link: the code, the tests and the method notes are
public.""",

"""This is the technical depth slide. Take it slowly, it is worth it.

We take one real road - Nolikata to Ranikor in Meghalaya - and show exactly how
it gets its number.

Four inputs across the top. Two separate models: landslides come from steepness
and rain, floods come from low flat ground and the season. They are different
roads, so they are different models.

Then we combine them the way you combine two independent risks: 0.28 and 0.40
give 0.57, not 0.68.

Now the three boxes at the bottom, and the middle one is the important one.
There is a 57% chance this road is blocked at some point in July. But a lorry
crosses it in a few hours, not all month - so the chance this particular trip
is affected is 11%. That works out to about 5 hours of expected delay, and it is
the 5 hours, not the 57%, that goes into the cost of the route.

Why it matters: if you use 57% as the trip risk, every hill road looks
impassable and the software tells everyone to fly. That is the mistake this
avoids.""",

"""First of four screenshots from the live app.

Five inputs: from, to, when, what you are shipping, and what matters most. Modes
can be switched off - useful for 'what if the rail line is down'.

Four answers: 2 days, ₹928 a tonne, 338 km, and 22.3 hours of expected delay
which is already inside the 2 days.

Point at the map where the line changes from blue to purple. That is Dimapur.
The cargo comes off a lorry and onto a train, and we charge 6 hours and ₹250 a
tonne for doing it. Most tools treat that as free, which is why their
multimodal plans look better than they turn out to be.

If someone asks why the map has no background: the tile server is blocked on
this network. Our own data still draws. That is deliberate - the map is built to
work without internet.""",

"""This is the picture people remember. Give them a moment to look at it.

Every road in the region longer than 5 km, coloured by how likely it is to be
blocked this July. Green usually open, amber often disrupted, red frequently
blocked.

Two things to point out. The thickness of the line repeats the colour, so it
still reads if you are colour-blind or if the deck is printed in black and
white. And the month is a dropdown - you can watch the network fall apart
through June to September and recover in October.

The finding worth stating: the worst roads on the list are in Meghalaya and the
hazard is flood, not landslide. Across the whole network 6,316 roads are at more
risk from water than from slopes.""",

"""This is the half of the problem statement most teams skip, and it is the half
MDoNER spends money on.

5,505 towns and villages, each scored on how many hours it actually takes to
reach a market, cold storage and the national gateway - travelling over the real
network, not measured across a map.

Namsai is 4 days from a market. Changliang is 7.

Be honest about the red. Only 35 markets are mapped in the entire region, so
most places score badly. It is the first thing we would fix and we know exactly
how - the Agmarknet market list. Saying that is stronger than pretending the
map is finished.""",

"""Last screenshot. This is the app arguing with itself, in English.

It has laid out every sensible way to move the consignment and written the
comparison for you: only 4 of the 7 are genuinely different journeys, air saves
14 hours and costs ₹5,026 a tonne more, and across all of them the spread is
₹5,032 a tonne.

That last sentence is generated by the software, not written by us. Read it out.

Then the judgement it leaves to the human: is the cargo losing more than ₹5,026
a tonne while it waits? If it is perishable, yes. If it is cement, no. A rate
card cannot make that call.""",

"""Close on honesty. Left column: eight things that work today.

Right column: what we would do next, in order, and why. The first one - loading
the Agmarknet market list - is the single change that most improves the
accessibility answer, and we know it.

Then the box at the bottom left, and say it out loud rather than waiting to be
asked: we do not model earthquakes. The North East is in Seismic Zone V, India's
highest, so a major quake is the biggest single threat to these corridors and
this platform says nothing about it. That needs a hazard model crossed with
structural survey data, which is a research project, not a data join.

Finish with: everything in this deck came out of the running system, and the
repository is public if you want to check any of it.""",
]

for i, text in enumerate(NOTES):
    S[i].notes_slide.notes_text_frame.text = text.strip()

prs.save(OUT)
print("wrote", OUT, "with", len(prs.slides._sldIdLst), "slides")
