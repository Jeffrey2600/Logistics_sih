# -*- coding: utf-8 -*-
"""Fill the official SIH 2026 Idea template with the SIH26002 NER logistics project."""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
import copy, sys

SRC = sys.argv[1]; OUT = sys.argv[2]

INK   = RGBColor(0x10, 0x32, 0x3C)   # deep slate-teal, dominant
BLUE  = RGBColor(0x00, 0x70, 0xC0)   # SIH template blue
TINT  = RGBColor(0xEE, 0xF3, 0xF6)   # card ground
LINE  = RGBColor(0xD2, 0xDD, 0xE2)
MUTE  = RGBColor(0x54, 0x66, 0x6E)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREEN = RGBColor(0x1B, 0xAF, 0x7A)   # the app's validated risk palette
AMBER = RGBColor(0xE0, 0xA1, 0x00)
RED   = RGBColor(0xD0, 0x3B, 0x3B)

BODY = "Calibri"
NUMF = "Cambria"


def txbox(slide, x, y, w, h, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Emu(0)
    tf.margin_top = tf.margin_bottom = Emu(0)
    tf.vertical_anchor = anchor
    return tf


def para(tf, text, size, bold=False, color=INK, font=BODY, space_after=0,
         first=False, align=PP_ALIGN.LEFT, italic=False, line=None):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    if line:
        p.line_spacing = line
    p.space_after = Pt(space_after)
    r = p.add_run(); r.text = text
    f = r.font
    f.size = Pt(size); f.bold = bold; f.italic = italic
    f.name = font; f.color.rgb = color
    return p


def card(slide, x, y, w, h, fill=TINT, border=LINE, radius=0.06, shadow=False):
    sh = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                Inches(x), Inches(y), Inches(w), Inches(h))
    sh.adjustments[0] = radius
    sh.fill.solid(); sh.fill.fore_color.rgb = fill
    if border is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = border; sh.line.width = Pt(0.75)
    sh.shadow.inherit = False
    sh.text_frame.text = ""
    return sh


def badge(slide, cx, cy, d, text, fill, txt_color=WHITE, size=12):
    sh = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(cx), Inches(cy),
                                Inches(d), Inches(d))
    sh.fill.solid(); sh.fill.fore_color.rgb = fill
    sh.line.fill.background()
    sh.shadow.inherit = False
    tf = sh.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = Emu(0)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = text
    r.font.size = Pt(size); r.font.bold = True
    r.font.name = BODY; r.font.color.rgb = txt_color
    return sh


def set_title(slide, text, size=30):
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
            r.font.name = BODY; r.font.color.rgb = INK
            return sh
    raise AssertionError("no title placeholder on slide")


def drop_body(slide):
    """Remove the template's instruction TextBox 8 placeholder text block."""
    for sh in list(slide.shapes):
        if sh.name == "TextBox 8":
            sh._element.getparent().remove(sh._element)
            return True
    return False


def eyebrow(slide, text, y=1.30):
    tf = txbox(slide, 0.55, y, 11.0, 0.30)
    para(tf, text.upper(), 12, bold=True, color=BLUE, first=True)


prs = Presentation(SRC)

# ---- structural work first: drop the instructions slide (7) -----------------
xml_slides = prs.slides._sldIdLst
slides = list(xml_slides)
prs.part.drop_rel(slides[6].rId)
xml_slides.remove(slides[6])

S = prs.slides

# =============================================================================
# SLIDE 1 - title page
# =============================================================================
s1 = S[0]
for sh in s1.shapes:
    if sh.name == "TextBox 9":
        tf = sh.text_frame
        tf.clear()
        tf.word_wrap = True
        rows = [
            ("Problem Statement ID", "SIH26002"),
            ("Problem Statement", "AI-Based Smart Logistics and Accessibility "
                                  "Intelligence Platform for the North Eastern Region"),
            ("Theme", "Smart Automation  ·  MDoNER"),
            ("PS Category", "Software"),
            ("Team ID", "<your team ID>"),
            ("Team Name", "<your registered team name>"),
        ]
        first = True
        for label, value in rows:
            p = tf.paragraphs[0] if first else tf.add_paragraph()
            first = False
            p.space_after = Pt(9)
            r = p.add_run(); r.text = label + " — "
            r.font.size = Pt(13); r.font.bold = True
            r.font.name = BODY; r.font.color.rgb = BLUE
            r2 = p.add_run(); r2.text = value
            r2.font.size = Pt(13); r2.font.bold = False
            r2.font.name = BODY; r2.font.color.rgb = INK
    if sh.name == "Subtitle 3":
        tf = sh.text_frame
        for p in list(tf.paragraphs)[1:]:
            p._element.getparent().remove(p._element)
        p = tf.paragraphs[0]
        for r in list(p.runs):
            r._r.getparent().remove(r._r)
        r = p.add_run(); r.text = "IDEA SUBMISSION"
        r.font.size = Pt(20); r.font.bold = True
        r.font.name = BODY; r.font.color.rgb = INK

# =============================================================================
# SLIDE 2 - idea title / proposed solution
# =============================================================================
s2 = S[1]; drop_body(s2)
set_title(s2, "Route the North East by risk, not by distance", size=27)
eyebrow(s2, "Proposed solution")

cards2 = [
    ("1", BLUE, "One graph, four modes",
     "Road, rail, the NW-2 waterway and air are separate layers joined by "
     "transfer edges that charge real handling cost and terminal dwell. "
     "A flat graph gives transhipment away free — which is why naive "
     "multimodal plans look better on paper than in a yard."),
    ("2", AMBER, "The monsoon, priced per segment",
     "Landslide and flood susceptibility from terrain, elevation and "
     "per-place NASA rainfall, combined as independent hazards and turned "
     "into expected delay hours and rupees on every one of 7,181 segments."),
    ("3", GREEN, "Access, not just routes",
     "5,594 settlements scored on network travel-hours to market, cold chain "
     "and the Siliguri gateway — plus where the next facility would bring "
     "the most places into reach, before anything is built."),
]
cw, gap = 3.87, 0.31
for i, (num, col, head, body) in enumerate(cards2):
    x = 0.55 + i * (cw + gap)
    card(s2, x, 1.78, cw, 2.62)
    badge(s2, x + 0.26, 2.00, 0.40, num, col, size=13)
    tf = txbox(s2, x + 0.26, 2.52, cw - 0.52, 0.34)
    para(tf, head, 14, bold=True, color=INK, first=True)
    tf2 = txbox(s2, x + 0.26, 2.92, cw - 0.52, 1.32)
    para(tf2, body, 11, color=MUTE, first=True, line=1.18)

# uniqueness band
band = card(s2, 0.55, 4.62, 12.23, 2.05, fill=INK, border=None)
tf = txbox(s2, 0.90, 4.86, 7.35, 0.30)
para(tf, "WHY THIS IS DIFFERENT", 12, bold=True, color=RGBColor(0x8F, 0xC5, 0xE8), first=True)
tf = txbox(s2, 0.90, 5.24, 7.35, 1.20)
lines = [
    "Optimises generalised cost — ₹ + time + expected disruption — never distance.",
    "Separates monthly risk from per-trip risk, so a hill route is expensive, not unusable.",
    "Answers the accessibility half MDoNER actually invests against, not only the routing half.",
]
for i, t in enumerate(lines):
    para(tf, "•   " + t, 12, color=WHITE, first=(i == 0), space_after=7, line=1.1)

card(s2, 8.60, 4.86, 4.00, 1.58, fill=RGBColor(0x1B, 0x4A, 0x58), border=None)
tf = txbox(s2, 8.82, 5.02, 3.56, 0.28)
para(tf, "AIZAWL → GUWAHATI, SAME PLAN", 10, bold=True,
     color=RGBColor(0x9F, 0xD2, 0xC4), first=True)
tf = txbox(s2, 8.82, 5.34, 3.56, 0.62)
p = tf.paragraphs[0]
r = p.add_run(); r.text = "64.5 h"
r.font.size = Pt(28); r.font.bold = True; r.font.name = NUMF; r.font.color.rgb = GREEN
r = p.add_run(); r.text = "   →   "
r.font.size = Pt(18); r.font.name = BODY; r.font.color.rgb = WHITE
r = p.add_run(); r.text = "135.3 h"
r.font.size = Pt(28); r.font.bold = True; r.font.name = NUMF; r.font.color.rgb = RED
tf = txbox(s2, 8.82, 6.02, 3.56, 0.30)
para(tf, "January vs July · ₹1,715 → ₹2,102 per tonne", 10.5,
     color=RGBColor(0xC8, 0xD8, 0xDE), first=True)

# =============================================================================
# SLIDE 3 - technical approach
# =============================================================================
s3 = S[2]; drop_body(s3)
set_title(s3, "TECHNICAL APPROACH", size=30)
eyebrow(s3, "From open data to a routing decision")

steps = [
    ("1", "Ingest open data", BLUE,
     "OpenStreetMap via Overpass, scoped to nine state relations · NASA POWER "
     "rainfall climatology · Copernicus DEM elevation. No keys, no licences."),
    ("2", "Build the graph", BLUE,
     "Contract 14,531 OSM ways into 7,181 segments over 6,502 junctions — "
     "25,360 km — then layer it by mode and charge every transhipment."),
    ("3", "Score the hazard", AMBER,
     "Analytic susceptibility from terrain, rainfall, elevation and carriageway "
     "width; an optional gradient-boosted model refines it. Landslide ⊕ flood."),
    ("4", "Optimise", GREEN,
     "Dijkstra on generalised cost for the plan, Yen's k-shortest paths for the "
     "alternatives, per-request weights over cost, time and risk."),
    ("5", "Serve", GREEN,
     "One FastAPI process serves the API and the MapLibre dashboard. No build "
     "step, no CDN, no runtime npm — it demos on a blocked venue network."),
]
y = 1.78
for num, head, col, body in steps:
    badge(s3, 0.55, y + 0.06, 0.42, num, col, size=13)
    tf = txbox(s3, 1.18, y + 0.02, 6.45, 0.28)
    para(tf, head, 13.5, bold=True, color=INK, first=True)
    tf = txbox(s3, 1.18, y + 0.36, 6.45, 0.60)
    para(tf, body, 10.5, color=MUTE, first=True, line=1.14)
    y += 0.98

card(s3, 8.05, 1.78, 4.73, 2.10)
tf = txbox(s3, 8.32, 1.98, 4.19, 0.28)
para(tf, "STACK", 11, bold=True, color=BLUE, first=True)
tf = txbox(s3, 8.32, 2.34, 4.19, 1.62)
for i, t in enumerate([
    "Python 3 · FastAPI · Pydantic",
    "NetworkX — mode-layered graph",
    "scikit-learn — optional risk model",
    "MapLibre GL, vendored locally",
    "Pure static frontend, zero build",
]):
    para(tf, "•  " + t, 11, color=INK, first=(i == 0), space_after=5)

card(s3, 8.05, 4.06, 4.73, 2.54)
tf = txbox(s3, 8.32, 4.28, 4.19, 0.28)
para(tf, "PROVEN, NOT PROMISED", 11, bold=True, color=GREEN, first=True)
tf = txbox(s3, 8.32, 4.66, 4.19, 1.80)
for i, t in enumerate([
    "260 unit tests · 30 browser checks",
    "Runs offline on a fresh clone — network, "
    "rainfall and elevation are committed",
    "/health reports connectivity, so a "
    "fragmented build is visible before anyone trusts it",
]):
    para(tf, "•  " + t, 11, color=INK, first=(i == 0), space_after=6, line=1.12)

# =============================================================================
# SLIDE 4 - feasibility and viability
# =============================================================================
s4 = S[3]; drop_body(s4)
set_title(s4, "FEASIBILITY AND VIABILITY", size=30)
eyebrow(s4, "Built and running today, on free-tier resources")

tiles = [
    ("25,360", "km of road network built from OSM"),
    ("5,594", "settlements scored for accessibility"),
    ("290", "automated tests, unit and browser"),
    ("₹0", "data cost — every source is open"),
]
for i, (big, lab) in enumerate(tiles):
    x = 0.55 + (i % 2) * 2.90
    yy = 1.85 + (i // 2) * 1.62
    card(s4, x, yy, 2.72, 1.44)
    tf = txbox(s4, x + 0.22, yy + 0.20, 2.28, 0.55)
    para(tf, big, 26, bold=True, color=BLUE, font=NUMF, first=True)
    tf = txbox(s4, x + 0.22, yy + 0.80, 2.28, 0.52)
    para(tf, lab, 10.5, color=MUTE, first=True, line=1.12)

tf = txbox(s4, 0.55, 5.20, 5.12, 1.30)
para(tf, "Free tier is not a compromise here.", 12.5, bold=True, color=INK, first=True)
para(tf, "OpenStreetMap, NASA POWER and Copernicus are open and unmetered. "
         "The built network ships inside the repository, so a fresh clone runs "
         "with no API key, no account and no download.",
     11, color=MUTE, space_after=0, line=1.16)

risks = [
    (RED, "No live road-closure feed exists, at any price",
     "State PWD and NHIDCL publish closures as irregular press notes. "
     "So the platform predicts risk from rainfall and terrain, and is designed "
     "to close the loop with driver and operator reports collected in-app."),
    (AMBER, "OSM records population on only 15% of settlements",
     "Ranking by population ranks where contributors filled in a number. "
     "Facility siting therefore ranks by settlements reached and reports "
     "coverage alongside. The Census 2011 village directory is the clean fix."),
    (GREEN, "Overpass and DEM APIs rate-limit hard",
     "Download is an isolated layer with an offline --from-file path. "
     "One teammate fetches once; the built artefacts are committed, so nothing "
     "at runtime depends on a mirror being up."),
]
card(s4, 6.42, 1.85, 6.36, 4.68, fill=TINT)
tf = txbox(s4, 6.74, 2.06, 5.72, 0.28)
para(tf, "CHALLENGES, AND HOW THEY ARE HANDLED", 11, bold=True, color=INK, first=True)
yy = 2.48
for col, head, body in risks:
    badge(s4, 6.74, yy + 0.03, 0.20, "", col)
    tf = txbox(s4, 7.10, yy - 0.02, 5.36, 0.30)
    para(tf, head, 12, bold=True, color=INK, first=True)
    tf = txbox(s4, 7.10, yy + 0.32, 5.36, 0.95)
    para(tf, body, 10.5, color=MUTE, first=True, line=1.15)
    yy += 1.38

# =============================================================================
# SLIDE 5 - impact and benefits
# =============================================================================
s5 = S[4]; drop_body(s5)
set_title(s5, "IMPACT AND BENEFITS", size=30)
eyebrow(s5, "What the platform changes, in numbers it produces today")

stats = [
    ("₹5,032", RED, "per tonne",
     "separates the best and worst way to move freight Kohima → Guwahati in "
     "July. Rail-mixed: 48.3 h at ₹928. Air: 34.2 h at ₹5,954."),
    ("+70.8 h", AMBER, "monsoon penalty",
     "on the same Aizawl → Guwahati plan — 64.5 h in January, 135.3 h in "
     "July. Shippers see it before the truck leaves, not after."),
    ("1,309", BLUE, "segments at severe risk",
     "of the 4,033 major roads in July — and on 1,055 of them it is flood, "
     "not landslide, that dominates. That changes what you build."),
]
cw, gap = 3.87, 0.31
for i, (big, col, small, body) in enumerate(stats):
    x = 0.55 + i * (cw + gap)
    card(s5, x, 1.78, cw, 2.12)
    tf = txbox(s5, x + 0.26, 1.98, cw - 0.52, 0.60)
    para(tf, big, 30, bold=True, color=col, font=NUMF, first=True)
    tf = txbox(s5, x + 0.26, 2.62, cw - 0.52, 0.26)
    para(tf, small.upper(), 10, bold=True, color=MUTE, first=True)
    tf = txbox(s5, x + 0.26, 2.96, cw - 0.52, 0.96)
    para(tf, body, 11, color=INK, first=True, line=1.16)

card(s5, 0.55, 4.12, 12.23, 2.55, fill=TINT)
tf = txbox(s5, 0.88, 4.34, 11.57, 0.28)
para(tf, "WHO BENEFITS", 11, bold=True, color=INK, first=True)
rows = [
    (GREEN, "Farmers and FPOs",
     "Billbari reaches a market in 3.9 h in the dry season and 32.0 h in the "
     "monsoon. Knowing which day it is decides what you plant and when you sell."),
    (BLUE, "Transporters and 3PLs",
     "A defensible mode mix per consignment, with the transhipment cost counted "
     "and the monsoon delay priced, instead of a rate card and a guess."),
    (AMBER, "MDoNER, NEC and state PWDs",
     "Site a cold store where it reaches 155 settlements rather than 79, and "
     "rank corridor spending by the risk that is actually there."),
]
yy = 4.76
for col, head, body in rows:
    badge(s5, 0.88, yy + 0.04, 0.20, "", col)
    tf = txbox(s5, 1.24, yy - 0.01, 2.70, 0.30)
    para(tf, head, 12, bold=True, color=INK, first=True)
    tf = txbox(s5, 4.10, yy - 0.01, 8.35, 0.52)
    para(tf, body, 11, color=MUTE, first=True, line=1.14)
    yy += 0.60

# =============================================================================
# SLIDE 6 - research and references
# =============================================================================
s6 = S[5]; drop_body(s6)
set_title(s6, "RESEARCH AND REFERENCES", size=30)
eyebrow(s6, "Every source is open, free and cited in the repository")

left = [
    ("OpenStreetMap · Overpass API",
     "Road network and 8,092 named settlements. © OSM contributors, ODbL. "
     "overpass-api.de"),
    ("NASA POWER",
     "Monthly rainfall climatology per place, free and key-less. "
     "power.larc.nasa.gov"),
    ("Copernicus DEM · Open-Meteo",
     "Ground elevation for every network node, 8 m to 4,016 m. "
     "open-meteo.com/en/docs/elevation-api"),
    ("NASA COOLR · Global Landslide Catalog",
     "Landslide occurrences for model training. "
     "maps.nccs.nasa.gov/arcgis/apps/MapAndAppGallery"),
]
right = [
    ("MDoNER · NEC Regional Plan",
     "Regional connectivity priorities and investment framing for the NER."),
    ("IWAI · National Waterway 2",
     "Brahmaputra navigability and terminal locations. iwai.nic.in"),
    ("Yen, J. Y. (1971)",
     "Finding the k shortest loopless paths in a network. "
     "Management Science 17(11) — the alternatives algorithm."),
    ("Dijkstra, E. W. (1959)",
     "A note on two problems in connexion with graphs. Numerische Mathematik 1."),
]
for col_i, items in enumerate((left, right)):
    x = 0.55 + col_i * 6.42
    card(s6, x, 1.78, 5.81, 4.05)
    tf = txbox(s6, x + 0.28, 1.98, 5.25, 0.28)
    para(tf, ["DATA SOURCES", "POLICY AND METHOD"][col_i], 11, bold=True,
         color=BLUE, first=True)
    yy = 2.36
    for head, body in items:
        tf = txbox(s6, x + 0.28, yy, 5.25, 0.28)
        para(tf, head, 12, bold=True, color=INK, first=True)
        tf = txbox(s6, x + 0.28, yy + 0.28, 5.25, 0.56)
        para(tf, body, 10.5, color=MUTE, first=True, line=1.13)
        yy += 0.87

card(s6, 0.55, 6.02, 12.23, 0.62, fill=INK, border=None)
tf = txbox(s6, 0.88, 6.18, 11.57, 0.32)
p = tf.paragraphs[0]
r = p.add_run(); r.text = "Working code and full method notes:  "
r.font.size = Pt(12); r.font.name = BODY; r.font.color.rgb = RGBColor(0xC8, 0xD8, 0xDE)
r = p.add_run(); r.text = "github.com/Jeffrey2600/Logistics_sih"
r.font.size = Pt(12); r.font.bold = True; r.font.name = BODY; r.font.color.rgb = WHITE

# =============================================================================
# Speaker notes - written for a presenter meeting the project for the first time
# =============================================================================
NOTES = {
 0: """Open with the geography, not the software.

The eight North Eastern states reach the rest of India through the 22 km
Siliguri Corridor. National highways are single-lane and thread landslide-prone
gorges. Rail gauge conversion is incomplete. The Brahmaputra is a navigable
national waterway that is barely used. For four months a year the monsoon closes
the corridors the other eight months depend on.

MDoNER asked for a platform that plans freight across all of that AND tells them
which places are cut off. We built both halves. Everything you are about to see
is running software, not a mock-up.""",

 1: """The one sentence to land: existing tools optimise distance; the North East
punishes that.

Card 1 - modes are separate graph layers. Moving cargo from a truck to a train
costs handling money and terminal time, so we charge it. Flat graphs give that
away free, which is exactly why paper multimodal plans fall apart in a yard.

Card 2 - every segment carries a monsoon disruption probability from terrain,
elevation and that place's own NASA rainfall. Two hazards, landslide and flood,
combined as independent risks.

Card 3 - the accessibility half. 5,594 settlements scored on travel HOURS to
market and cold chain over the real network, never straight-line distance.

The number at the bottom is the whole pitch: the same Aizawl-Guwahati plan is
64.5 hours in January and 135.3 in July. That is the decision the platform makes
visible before the truck leaves.

If asked what is unique: we optimise generalised cost - rupees plus time plus
expected disruption - and we separate the chance a road is shut sometime in July
from the chance THIS trip meets it. Conflating those makes every hill route look
unusable instead of merely expensive.""",

 2: """Keep this slide brisk - five steps, one line each.

The step worth dwelling on is 2. OpenStreetMap is a drawing, not a graph: one
highway is hundreds of way objects. We keep junctions and endpoints, contract
everything between them, and carry the real traced length. That is how 14,531
ways become 7,181 usable segments.

Step 3: the analytic model is the default and the machine-learned one is
optional. That is deliberate - a district officer can act on 'narrow carriageway,
high rainfall, steep terrain'. They cannot act on 'the gradient booster said
0.62'.

Step 5 answers the demo question before it is asked: no CDN, no build step,
MapLibre is vendored. It runs on a blocked venue network.""",

 3: """This is the slide that separates us from an idea.

Left: it is built. 25,360 km of network, 5,594 settlements, 290 automated tests.
Zero rupees of data cost, because OpenStreetMap, NASA POWER and Copernicus are
open. The built data ships inside the repository, so a fresh clone runs with no
API key and no download.

Right: be straight about the limits - judges reward it.

The honest one is the first. India has no machine-readable road-closure feed.
So we predict from rainfall and terrain, and the platform is designed to close
that loop with driver reports collected in-app.

Second: OSM has population on only 15% of settlements. Ranking sites by
population would rank where volunteers typed a number. On the real network that
actually reversed our cold-store recommendation, so we rank by settlements
reached instead. Census 2011 is the clean fix.""",

 4: """Three numbers, then who they are for.

Rs 5,032 per tonne separates the best and worst way to move the same consignment
Kohima to Guwahati in July. Rail-mixed is 48.3 hours at Rs 928; air is 34.2 hours
at Rs 5,954. Nobody should be picking between those blind.

70.8 hours is what the monsoon adds to the Aizawl-Guwahati plan.

1,309 of 4,033 major roads are at severe risk in July - and on 1,055 the
dominant hazard is flood, not landslide. That distinction changes what you build:
you do not fix a flood problem with slope stabilisation.

The Billbari example is the human one - 3.9 hours to a market in the dry season,
32.0 in the monsoon. That is a farmer's planting decision.

The MDoNER line is the investment case: the platform put a cold store where it
reaches 155 settlements instead of 79.""",

 5: """Every source is open, free and cited in the repository - no licensed data,
no scraped data, nothing that stops this being deployed.

COOLR is listed because the landslide-history feature is wired and waiting on
that download; say so if asked rather than implying it is loaded.

Close on the repository: the code, the tests and the method notes are public. If
the judges want to run it, they can - clone, pip install, one command.""",
}
for i, txt in NOTES.items():
    S[i].notes_slide.notes_text_frame.text = txt.strip()


prs.save(OUT)
print("wrote", OUT, "slides:", len(prs.slides.__iter__.__self__._sldIdLst))
