"""Merging the OSM road graph into the seed network.

OSM ingestion produces roads only, so the merged network must keep the seed's
rail, waterway and air links or the multimodal model collapses into road-only.
"""
import csv

import pytest

from backend.app.core.network import Network, Place, merge_osm


def place(place_id, lat=26.0, lon=92.0, **kw):
    defaults = dict(
        name=place_id, state="Assam", lat=lat, lon=lon, kind="junction",
        population=0, has_market=False, has_coldstore=False,
    )
    defaults.update(kw)
    return Place(id=place_id, **defaults)


def edge(u, v, mode="road", **kw):
    base = {
        "id": f"{u}-{v}-{mode}", "u": u, "v": v, "mode": mode,
        "distance_km": 100.0, "terrain": "plain", "route_ref": "NH-X",
        "lanes": 2, "monsoon_exposure": 0.3, "landslide_events": 0,
    }
    base.update(kw)
    return base


@pytest.fixture
def seed():
    return Network(
        places={
            "GAU": place("GAU", name="Guwahati", population=1116267, has_market=True),
            "SHL": place("SHL", 25.58, 91.89, name="Shillong", has_coldstore=True),
            "DBG": place("DBG", 27.47, 94.91, name="Dibrugarh"),
        },
        edges=[
            edge("GAU", "SHL", "road", route_ref="NH-6"),
            edge("GAU", "DBG", "road", route_ref="NH-15"),
            edge("GAU", "DBG", "rail", route_ref="NFR"),
            edge("GAU", "DBG", "water", route_ref="NW-2"),
            edge("GAU", "SHL", "air", route_ref="AIR"),
        ],
    )


@pytest.fixture
def osm():
    return Network(
        places={
            "GAU": place("GAU"), "SHL": place("SHL", 25.58, 91.89),
            "DBG": place("DBG", 27.47, 94.91), "n123": place("n123", 26.2, 92.1),
        },
        edges=[
            edge("GAU", "n123", "road", distance_km=40.0, route_ref="NH-6"),
            edge("n123", "SHL", "road", distance_km=55.0, route_ref="NH-6"),
            edge("GAU", "DBG", "road", distance_km=440.0, route_ref="NH-15"),
        ],
    )


def test_seed_road_edges_are_replaced_not_duplicated(seed, osm):
    """Two descriptions of one highway would let the optimiser pick whichever
    the assumptions happened to favour."""
    merged = merge_osm(seed, osm)
    roads = [e for e in merged.edges if e["mode"] == "road"]
    assert len(roads) == len(osm.edges)
    assert all(e["distance_km"] != 100.0 for e in roads), "a seed road survived"


def test_non_road_modes_are_kept(seed, osm):
    merged = merge_osm(seed, osm)
    modes = {e["mode"] for e in merged.edges}
    assert modes == {"road", "rail", "water", "air"}


def test_seed_metadata_wins_over_bare_osm_junctions(seed, osm):
    """OSM junctions carry no population, market or cold store."""
    merged = merge_osm(seed, osm)
    assert merged.places["GAU"].population == 1116267
    assert merged.places["GAU"].has_market
    assert merged.places["SHL"].has_coldstore


def test_new_osm_junctions_are_added(seed, osm):
    merged = merge_osm(seed, osm)
    assert "n123" in merged.places
    assert merged.places["n123"].population == 0


def test_a_place_the_road_graph_missed_survives_on_its_rail_link(seed, osm):
    """Lumding is a rail junction with little road presence. If OSM ingestion
    does not anchor it, dropping it would lose a real link - it must be kept,
    reachable by rail, and the network must stay connected."""
    seed.places["LMD"] = place("LMD", 25.75, 93.17, name="Lumding")
    seed.edges.append(edge("GAU", "LMD", "rail", route_ref="NFR"))

    merged = merge_osm(seed, osm)
    assert "LMD" in merged.places
    rail = [e for e in merged.edges if "LMD" in (e["u"], e["v"])]
    assert [e["mode"] for e in rail] == ["rail"]
    assert len(merged.components()) == 1


def test_merged_network_stays_connected(seed, osm):
    merged = merge_osm(seed, osm)
    assert len(merged.components()) == 1


def test_components_detects_fragmentation(seed, osm):
    """A partial OSM build orphans places; that must be visible, not silent."""
    broken = Network(
        places=dict(osm.places),
        edges=[edge("GAU", "n123", "road")],   # SHL and DBG left unreachable
    )
    merged = merge_osm(
        Network(places=seed.places, edges=[e for e in seed.edges if e["mode"] == "road"]),
        broken,
    )
    assert len(merged.components()) > 1


def test_health_reports_the_network_source_and_connectivity(client):
    body = client.get("/health").json()
    assert body["network_source"] in ("seed", "seed+osm")
    assert body["connected"] is True
    assert body["components"] == 1
    assert body["orphaned_places"] == 0


def test_built_osm_csv_matches_the_loader_schema(tmp_path):
    """The ingester's columns and the loader's expectations must not drift."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "data" / "ingest"))
    from fetch_osm import write_csv

    node_fields = ["id", "name", "state", "lat", "lon", "kind", "population",
                   "has_market", "has_coldstore"]
    edge_fields = ["u", "v", "mode", "distance_km", "terrain", "route_ref", "lanes",
                   "highway", "bridge", "tunnel", "surface", "osm_way_id"]

    nodes_path, edges_path = tmp_path / "n.csv", tmp_path / "e.csv"
    write_csv(nodes_path, [{
        "id": "n1", "name": "n1", "state": "", "lat": 26.0, "lon": 92.0,
        "kind": "junction", "population": 0, "has_market": 0, "has_coldstore": 0,
    }], node_fields)
    write_csv(edges_path, [{
        "u": "n1", "v": "n2", "mode": "road", "distance_km": 10.0, "terrain": "plain",
        "route_ref": "NH-1", "lanes": 2, "highway": "trunk", "bridge": 0,
        "tunnel": 0, "surface": "", "osm_way_id": 5,
    }], edge_fields)

    from backend.app.core.network import _read_edges, _read_places

    places = _read_places(nodes_path)
    assert places["n1"].kind == "junction"
    places["n2"] = place("n2")
    edges = _read_edges(edges_path, places, {"monsoon_exposure": 0.45})
    assert edges[0]["monsoon_exposure"] == 0.45, "OSM default not applied"
    assert edges[0]["landslide_events"] == 0
    assert edges[0]["id"] == "n1-n2-road"


# --------------------------------------------------------- settlements -----

def write(path, rows, fields):
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


@pytest.fixture
def settlement_files(tmp_path, monkeypatch):
    """Point the loader at a temporary settlement dataset."""
    from backend.app.core import network as net_mod

    nodes, edges, merges = (tmp_path / "n.csv", tmp_path / "e.csv", tmp_path / "m.csv")
    write(nodes, [{
        "id": "s1", "name": "Nongpoh", "state": "", "lat": 25.9, "lon": 91.88,
        "kind": "village", "population": 12000, "population_known": 1,
        "has_market": 0, "has_coldstore": 0,
    }], ["id", "name", "state", "lat", "lon", "kind", "population",
         "population_known", "has_market", "has_coldstore"])
    write(edges, [{
        "u": "s1", "v": "n123", "mode": "road", "distance_km": 4.2,
        "terrain": "plain", "route_ref": "access", "lanes": 1,
        "highway": "access", "bridge": 0, "tunnel": 0, "surface": "", "osm_way_id": 0,
    }], ["u", "v", "mode", "distance_km", "terrain", "route_ref", "lanes",
         "highway", "bridge", "tunnel", "surface", "osm_way_id"])
    write(merges, [
        {"node_id": "n123", "name": "Umsning", "kind": "village",
         "population": 3000, "population_known": 1},
        {"node_id": "GAU", "name": "Not Guwahati", "kind": "hamlet",
         "population": 12, "population_known": 1},
    ], ["node_id", "name", "kind", "population", "population_known"])

    monkeypatch.setattr(net_mod, "SETTLEMENT_NODES", nodes)
    monkeypatch.setattr(net_mod, "SETTLEMENT_EDGES", edges)
    monkeypatch.setattr(net_mod, "SETTLEMENT_MERGES", merges)
    return nodes


def test_settlements_are_added_with_connectors(seed, osm, settlement_files):
    from backend.app.core.network import merge_osm, merge_settlements

    merged = merge_settlements(merge_osm(seed, osm), set(seed.places))
    assert "s1" in merged.places
    assert merged.places["s1"].population == 12000
    connector = [e for e in merged.edges if e["u"] == "s1"]
    assert connector and connector[0]["route_ref"] == "access"
    assert len(merged.components()) == 1


def test_a_junction_becomes_the_settlement_sitting_on_it(seed, osm, settlement_files):
    from backend.app.core.network import merge_osm, merge_settlements

    merged = merge_settlements(merge_osm(seed, osm), set(seed.places))
    assert merged.places["n123"].name == "Umsning"
    assert merged.places["n123"].kind == "village"
    assert merged.places["n123"].population == 3000


def test_seed_places_are_never_overwritten_by_an_osm_tag(seed, osm, settlement_files):
    """Seed metadata is curated; an OSM population tag is not better evidence."""
    from backend.app.core.network import merge_osm, merge_settlements

    merged = merge_settlements(merge_osm(seed, osm), set(seed.places))
    assert merged.places["GAU"].name == "Guwahati"
    assert merged.places["GAU"].population == 1116267
    assert merged.places["GAU"].has_market


def test_missing_settlement_files_are_a_no_op(seed, osm, tmp_path, monkeypatch):
    from backend.app.core import network as net_mod

    monkeypatch.setattr(net_mod, "SETTLEMENT_NODES", tmp_path / "absent.csv")
    monkeypatch.setattr(net_mod, "SETTLEMENT_EDGES", tmp_path / "absent2.csv")
    base = net_mod.merge_osm(seed, osm)
    assert net_mod.merge_settlements(base, set(seed.places)).places == base.places


def test_a_village_with_untagged_population_still_counts_as_a_settlement(risk_model):
    """OSM tags population on a minority of villages. Testing population > 0
    would throw most real settlements away as if they were junctions."""
    from backend.app.core.network import Network, Place
    from backend.app.services.accessibility import accessibility_index

    places = {
        "GAU": Place(id="GAU", name="Guwahati", state="Assam", lat=26.14, lon=91.73,
                     kind="city", population=1116267, has_market=True, has_coldstore=True),
        "s9": Place(id="s9", name="Untagged village", state="", lat=26.3, lon=91.9,
                    kind="village", population=0, has_market=False, has_coldstore=False),
        "n7": Place(id="n7", name="n7", state="", lat=26.2, lon=91.8,
                    kind="junction", population=0, has_market=False, has_coldstore=False),
    }
    edges = [
        edge("GAU", "n7", "road", distance_km=20.0),
        edge("n7", "s9", "road", distance_km=15.0),
    ]
    result = accessibility_index(Network(places=places, edges=edges), risk_model, month="jul")
    ranked = {r["id"] for r in result["underserved"]}
    assert "s9" in ranked, "an untagged village is still a place people live"
    assert "n7" not in ranked
