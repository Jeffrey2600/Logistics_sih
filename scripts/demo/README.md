# Static demo build

Bakes a snapshot of the API's answers into one self-contained HTML file, so the
dashboard can be handed to someone as a link with no server behind it. Useful
for showing the project on a phone, or anywhere a laptop and a terminal are not
available.

It is a snapshot, and the page says so on itself: months and lanes that were not
baked report that plainly rather than inventing an answer.

## Rebuilding it

With the app running (`./run.sh`) on port 8000:

```bash
bash scripts/demo/fetch_snapshot.sh /tmp/nerdemo
python3 scripts/demo/build_static_demo.py /tmp/nerdemo frontend /tmp/nerdemo/ner-logistics.html
```

The output is authored as artifact content - no `<!doctype>`, `<html>`, `<head>`
or `<body>` wrapper - because the Artifact host supplies those. Opening it as a
plain file works too; browsers tolerate the missing wrapper.

## What it contains, and what it leaves out

| | |
|---|---|
| Months | July and January |
| Lanes | eight origins into Guwahati, default cargo and priority |
| Roads | those over 5 km (4,067 of 11,276), to keep the page near 9 MB |
| Villages | all 5,609 scored settlements |
| Left out | live routing for arbitrary lanes, the sub-5 km link roads |

Everything that is pure client-side work - the place search, voice input, the
language switch, the tab layout - behaves exactly as it does against the live
server, because it is the same `frontend/app.js` with only the network layer
swapped.

Two limits are worth knowing before showing it to anyone:

- The satellite base map fetches tiles from Esri, which an Artifact's content
  security policy blocks. The switch is present and reports itself unreachable
  rather than failing silently. It works in the real application.
- Speech recognition may be unavailable inside an embedded frame. The button
  hides itself where the API is missing, and says why where permission is
  refused.
