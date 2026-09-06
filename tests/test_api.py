"""HTTP contract: status codes and response shape."""


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["places"] > 0 and body["segments"] > 0


def test_list_places_and_filter(client):
    assert client.get("/network/places").json()["count"] > 0
    body = client.get("/network/places?state=Mizoram").json()
    assert body["count"] == 4
    assert {p["state"] for p in body["places"]} == {"Mizoram"}


def test_segments_carry_geometry_and_risk(client):
    body = client.get("/network/segments?month=jul").json()
    assert body["count"] > 0
    first = body["segments"][0]
    assert len(first["geometry"]) == 2
    assert 0.0 <= first["risk"]["probability"] <= 1.0
    # Sorted worst-first so the map can draw the hotspots on top.
    probabilities = [s["risk"]["probability"] for s in body["segments"]]
    assert probabilities == sorted(probabilities, reverse=True)


def test_segment_mode_filter(client):
    body = client.get("/network/segments?mode=water").json()
    assert {s["mode"] for s in body["segments"]} == {"water"}


def test_plan_endpoint(client):
    response = client.post("/routing/plan", json={"origin": "IMP", "destination": "GAU", "month": "jul"})
    assert response.status_code == 200
    body = response.json()
    assert body["recommended"]["legs"]
    assert body["recommended"]["summary"]["objective_score"] > 0


def test_plan_rejects_unknown_place(client):
    response = client.post("/routing/plan", json={"origin": "ZZZ", "destination": "GAU"})
    assert response.status_code == 422


def test_plan_rejects_invalid_month(client):
    response = client.post("/routing/plan", json={"origin": "IMP", "destination": "GAU", "month": "smarch"})
    assert response.status_code == 422


def test_isolation_returns_422_not_500(client):
    response = client.post(
        "/routing/plan",
        json={"origin": "GTK", "destination": "GAU", "blocked_edge_ids": ["SLG-GTK-road"]},
    )
    assert response.status_code == 422
    assert "isolated" in response.json()["detail"]


def test_seasonal_endpoint(client):
    body = client.post("/routing/seasonal", json={
        "origin": "AZL", "destination": "GAU", "modes": ["road", "rail", "water"],
    }).json()
    assert body["delta"]["hours"] > 0


def test_accessibility_index_endpoint(client):
    body = client.get("/accessibility/index?month=jul").json()
    assert len(body["underserved"]) == 10


def test_facility_impact_endpoint(client):
    response = client.post(
        "/accessibility/facility-impact",
        json={"candidate_ids": ["KHM", "TWG"], "facility_type": "coldstore", "threshold_hours": 10},
    )
    assert response.status_code == 200
    assert len(response.json()["ranked_sites"]) == 2


def test_facility_impact_validates_candidate_list(client):
    assert client.post("/accessibility/facility-impact", json={"candidate_ids": []}).status_code == 422


def test_segment_labels_are_readable(client):
    """Two thirds of an OSM network's nodes are unnamed junctions, so a label
    built from node ids would be the common case and would say nothing."""
    body = client.get("/network/segments?month=jul").json()
    for segment in body["segments"][:200]:
        assert segment["label"]
        assert "n1" not in segment["label"] or not segment["label"].startswith("n")


def test_segment_label_forms():
    from backend.app.api.routes.network import segment_label

    assert segment_label("Guwahati", "Nagaon", "NH-27") == "Guwahati – Nagaon"
    assert segment_label("Shillong", "n123", "NH-6") == "NH-6 near Shillong"
    assert segment_label("n1", "Shillong", "NH-6") == "NH-6 near Shillong"
    # An OSM highway class is not a road name.
    assert segment_label("Shillong", "n123", "primary") == "Road near Shillong"
    assert segment_label("n1", "n2", "trunk") == "Road"


def test_landslide_history_counts_only_the_rows_returned(client):
    """The seed rail alignments carry history while the OSM roads do not, so a
    plain any() over every edge answers yes and hides the gap."""
    body = client.get("/network/segments?month=jul&mode=road").json()
    history = body["landslide_history"]
    assert history["total"] == body["count"]
    assert 0 <= history["segments"] <= history["total"]


def test_places_can_exclude_junctions(client):
    everything = client.get("/network/places").json()["count"]
    settlements = client.get("/network/places?settlements_only=true").json()
    assert settlements["count"] <= everything
    assert all(p["kind"] != "junction" for p in settlements["places"])


def test_risk_bands_are_the_three_validated_ones(client):
    body = client.get("/network/segments?month=jul").json()
    bands = {s["risk"]["band"] for s in body["segments"]}
    assert bands <= {"low", "elevated", "severe"}


def test_the_frontend_palette_covers_every_band_the_api_returns(client):
    """A band the page's palette does not know reaches MapLibre as undefined,
    which it paints black - a colour absent from the legend that reads as a
    fourth severity. This is the check that would have caught it."""
    import re
    from pathlib import Path

    app_js = (Path(__file__).resolve().parents[1] / "frontend" / "app.js").read_text(
        encoding="utf-8"
    )
    match = re.search(r"const RISK_COLOUR = \{([^}]*)\}", app_js)
    assert match, "RISK_COLOUR not found in frontend/app.js"
    palette = set(re.findall(r"(\w+):", match.group(1)))

    served = {s["risk"]["band"] for s in client.get("/network/segments?month=jul").json()["segments"]}
    assert served <= palette, (
        f"the API returns bands the dashboard cannot colour: {sorted(served - palette)}"
    )
