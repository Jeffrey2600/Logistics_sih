# Running it on your own machine

The dashboard is a web page served by a small Python program. Both have to be
on the same machine as the browser you open it in, which is why a link from
anywhere else will not work.

## Windows, from cmd

Open **Command Prompt** (press Start, type `cmd`, Enter) and run:

```
git clone https://github.com/Jeffrey2600/Logistics_sih
cd Logistics_sih
run.bat
```

Then open **http://localhost:8000** in your browser.

Leave the black window open while you use the dashboard - closing it stops the
server. Ctrl+C stops it deliberately.

No `git`? Download the ZIP from the repository's green **Code** button, extract
it, then `cd` into the extracted folder and run `run.bat`.

## macOS and Linux

```
git clone https://github.com/Jeffrey2600/Logistics_sih
cd Logistics_sih
./run.sh
```

## What you should see

The first start takes about half a minute: it builds a graph of 10,572 places
and 11,276 segments before it answers anything. After that it is fast.

The window prints:

```
Network: full OpenStreetMap road network

  Dashboard  http://localhost:8000/
  API docs   http://localhost:8000/docs
```

## When it does not work

**`'git' is not recognized`** — download the ZIP instead, as above.

**`Could not open requirements file: backend\requirements.txt`** — you are in
the wrong folder. The prompt has to end in `Logistics_sih`. If you extracted a
ZIP, the folder often nests: `Logistics_sih-main\Logistics_sih-main`. `dir`
should list `run.bat`, `backend` and `frontend`; if it does not, `cd` one level
deeper and look again.

**`run.ps1 cannot be loaded ... not digitally signed`** — that is PowerShell
refusing an unsigned script. Use `run.bat` from cmd instead, which has no such
restriction. If you would rather stay in PowerShell:
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then `.\run.ps1`.

**`Failed building wheel for pydantic-core`** — pip could not find a ready-made
package for your Python version and tried to compile one, which needs a Rust
compiler you almost certainly do not have. The requirements ask for minimum
versions rather than exact ones so pip can pick a build that matches, so this
usually means a very new Python. Install Python 3.12 or 3.13 from python.org
and run `py -3.12 -m pip install -r backend\requirements.txt`, then
`py -3.12 -m uvicorn backend.app.main:app --port 8000`.

**`Python was not found`** — install it from
<https://www.python.org/downloads/>, and tick **Add python.exe to PATH** on the
first screen of the installer. That tick box is the whole problem when this
happens.

**Port 8000 already in use** — `set PORT=8090` then `run.bat`, and open
<http://localhost:8090> instead.

**The page loads but the map is blank grey** — the base map tiles are being
blocked, usually by an office or campus network. Everything the project itself
draws - roads, risk colours, villages, routes - still works, because the base
map is deliberately only a backdrop. On a normal connection it fills in.

**Nothing at all at localhost:8000** — check the black window is still open and
has not printed an error. If you closed it, the server stopped.

## Running the tests

```
py -m pip install -r requirements-dev.txt
py -m pytest tests -q
```

261 tests, a few seconds. The browser checks need Node and a running server:

```
node tests/browser/check.js
```
