# SIH 2026 idea presentation

`SIH26002_NER_Logistics.pptx` — the submission deck, built on the official
SIH 2026 Idea template.

## Structure

Twelve slides. The first six are the ones SIH's template asks for, in its
order:

1. Title
2. Idea / proposed solution
3. Technical approach — the system, drawn
4. Feasibility and viability
5. Impact and benefits
6. Research and references

Slides 7–12 are an annexure: how a risk number is arrived at, then the four
results with screenshots of the running application, then an honest status
slide. **If the submission portal enforces a six-slide limit, delete slides
7–12** — the first six stand on their own, and the annexure is what you show
when the panel asks to see it working.

Every slide carries speaker notes written for someone presenting this who did
not build it. Open the Notes pane in PowerPoint (View → Notes).

## Before submitting

- Slide 1: fill in **Team ID** and **Team Name**
- Slides 2–12: the **"Your Team Name"** oval in the top-left corner

## Where the numbers came from

Every figure is produced by the code in this repository, not estimated:

| Figure | Source |
|---|---|
| Route times, costs, option tables | `plan_route` / `compare_options` with `NER_USE_OSM=1` |
| Risk bands, flood-vs-landslide counts | `load_risk_model().assess()` over the 4,033 major road segments |
| Network and settlement counts | `data/processed/osm_edges.csv`, `settlement_nodes.csv` |
| Worked risk example | `GET /network/segments?month=jul` — segment `s1262014179-n4021626563-road` |

`screenshots/` holds the captures used on the result slides, taken from the
running application.

## Rebuilding it

```bash
pip install python-pptx
python docs/presentation/build_deck.py <official-template.pptx> out.pptx docs/presentation/screenshots
```
