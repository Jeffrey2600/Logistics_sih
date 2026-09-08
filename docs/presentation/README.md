# SIH 2026 idea presentation

`SIH26002_NER_Logistics.pptx` — the submission deck, built on the official
SIH 2026 Idea template. Six slides, as the template asks for.

Before submitting, fill in on slide 1:

- **Team ID** and **Team Name** — exactly as registered on the SIH portal
- The **"Your Team Name"** oval in the top-left corner of slides 2–6

Every slide carries speaker notes written for a presenter meeting the project
for the first time. Open the Notes pane in PowerPoint (View → Notes) to read them.

Every figure in the deck is produced by the code in this repository, not
estimated. The routing and risk numbers come from the engine with
`NER_USE_OSM=1`; the network and settlement counts come from
`data/processed/`.

## Rebuilding it

`build_deck.py` regenerates the deck from the official template, so edits
survive a template change:

```bash
pip install python-pptx
python docs/presentation/build_deck.py <official-template.pptx> out.pptx
```
