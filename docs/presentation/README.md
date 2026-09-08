# SIH 2026 idea presentation

Two decks, both built on the official SIH 2026 Idea template.

## `SIH26002_NER_Logistics_Submission6.pptx` — submit this one

Exactly **6 slides**, matching the template's own "Important Instructions"
slide to the letter:

- 6 slides including the title (the instructions slide itself is deleted,
  as the template says to)
- Points and diagrams, not paragraphs
- Every content slide keeps the template's own idea-detail pointers
  **verbatim**, as a numbered sub-heading (e.g. "Detailed explanation of the
  proposed solution") — content is filled in under each one, nothing is
  reworded or dropped
- Slide 3 (Technical Approach) includes an actual flow diagram, not a
  screenshot
- Slide 2 carries one real screenshot of the running app (the network-wide
  risk map) as its supporting picture

**Before submitting:** fill in Team ID and Team Name on slide 1, and the
"Your Team Name" oval on slides 2–6. The instructions slide also says to
**save as PDF before uploading** — PowerPoint or Google Slides: File → Save
As / Download → PDF.

## `SIH26002_NER_Logistics_Extended.pptx` — for practice and deep-dive questions

12 slides: the same 6, followed by an annexure — a worked risk calculation
and four screenshots of the running app with real values, for rehearsing
answers to judges' follow-up questions. **Not** for the portal upload.

## Where the numbers came from

Every figure is produced by the code in this repository, not estimated:

| Figure | Source |
|---|---|
| Route times, costs, option tables | `plan_route` / `compare_options` with `NER_USE_OSM=1` |
| Risk bands, flood-vs-landslide counts | `load_risk_model().assess()` over the 4,033 major road segments |
| Network and settlement counts | `data/processed/osm_edges.csv`, `settlement_nodes.csv` |
| Worked risk example | `GET /network/segments?month=jul` — segment `s1262014179-n4021626563-road` |
| Facility siting (Haflong vs Kohima) | `accessibility.facility_impact` over the full network |

`screenshots/` holds the captures used in both decks, taken from the running
application.

## Rebuilding either deck

```bash
pip install python-pptx
python docs/presentation/build_deck_submission6.py <template.pptx> out.pptx docs/presentation/screenshots
python docs/presentation/build_deck_extended.py    <template.pptx> out.pptx docs/presentation/screenshots
```
