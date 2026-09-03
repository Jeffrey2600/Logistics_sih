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
    body = client.post("/routing/seasonal", json={"origin": "AZL", "destination": "GAU"}).json()
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
