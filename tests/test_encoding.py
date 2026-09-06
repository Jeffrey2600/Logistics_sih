"""Every data file is UTF-8, on every platform.

Python's open() uses the *locale* encoding by default. On Linux that is UTF-8
and everything works; on Windows it is cp1252, and the first NER place name
carrying a diacritic - "2Rahan Pathār No.2" - crashes the whole API with
UnicodeDecodeError. Reading a committed data file without an explicit encoding
is therefore a bug even when the tests pass on the developer's machine.
"""
import csv
import json
import locale
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DATA_FILES = sorted(
    [*(REPO / "data" / "seed").glob("*.csv"), *(REPO / "data" / "processed").glob("*.csv")]
)


def test_there_are_data_files_to_check():
    assert DATA_FILES, "no committed data files found"


@pytest.mark.parametrize("path", DATA_FILES, ids=lambda p: p.name)
def test_data_files_are_valid_utf8(path):
    path.read_text(encoding="utf-8")


@pytest.mark.parametrize("path", DATA_FILES, ids=lambda p: p.name)
def test_data_files_parse_as_csv_under_utf8(path):
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert rows, f"{path.name} has no rows"


def test_non_ascii_names_survive_a_round_trip(tmp_path):
    """A real NER name from the settlement data, written and read back."""
    from backend.app.core.network import _read_places

    path = tmp_path / "nodes.csv"
    fields = ["id", "name", "state", "lat", "lon", "kind", "population",
              "has_market", "has_coldstore"]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerow({"id": "s1", "name": "2Rahan Pathār No.2", "state": "Assam",
                         "lat": 26.8, "lon": 94.2, "kind": "village",
                         "population": 0, "has_market": 0, "has_coldstore": 0})
    assert _read_places(path)["s1"].name == "2Rahan Pathār No.2"


def test_no_source_file_opens_data_without_an_encoding():
    """Guards the whole class of bug, not just the file that crashed.

    Parsed with ast rather than matched as text: a call spans as many lines as
    it likes, and a fixed lookahead window reports whichever ones are long.
    """
    import ast

    TEXT_CALLS = {"open", "read_text", "write_text"}
    offenders = []

    for source in [*(REPO / "backend").rglob("*.py"),
                   *(REPO / "data" / "ingest").glob("*.py"),
                   *(REPO / "ml").rglob("*.py")]:
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = (node.func.attr if isinstance(node.func, ast.Attribute)
                    else getattr(node.func, "id", None))
            if name not in TEXT_CALLS:
                continue
            # Binary mode carries no encoding, and is not the bug.
            mode = next((a.value for a in node.args
                         if isinstance(a, ast.Constant) and isinstance(a.value, str)), "")
            if "b" in mode:
                continue
            if not any(kw.arg == "encoding" for kw in node.keywords):
                offenders.append(f"{source.relative_to(REPO)}:{node.lineno} {name}()")

    assert not offenders, (
        "these read or write files using the platform's locale encoding, which "
        "is cp1252 on Windows and will crash on any non-ASCII place name:\n  "
        + "\n  ".join(offenders)
    )


def test_the_locale_default_is_not_relied_upon():
    """Documents why the explicit encodings matter: this is not always UTF-8."""
    preferred = locale.getpreferredencoding(False)
    assert isinstance(preferred, str)
