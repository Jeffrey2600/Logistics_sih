"""Ingestion geometry. The network fetchers themselves need the internet;
the maths that attributes a hazard to a road does not, so it is tested here."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "data" / "ingest"))

from common import NER_BBOX, haversine_km, point_to_segment_km  # noqa: E402

# Guwahati and Shillong: ~65 km apart as the crow flies, ~100 km by NH-6.
GAU = (26.1445, 91.7362)
SHL = (25.5788, 91.8933)


def test_haversine_matches_known_separation():
    assert 60 < haversine_km(*GAU, *SHL) < 70


def test_point_on_the_segment_has_zero_distance():
    assert point_to_segment_km(*GAU, *GAU, *SHL) < 0.5


def test_midpoint_of_the_segment_is_on_it():
    mid = ((GAU[0] + SHL[0]) / 2, (GAU[1] + SHL[1]) / 2)
    assert point_to_segment_km(*mid, *GAU, *SHL) < 2.0


def test_perpendicular_offset_is_measured_not_ignored():
    """A slide 20 km to the side of a road must not snap to it."""
    mid_lat = (GAU[0] + SHL[0]) / 2
    offset = (mid_lat, (GAU[1] + SHL[1]) / 2 + 0.25)   # ~25 km east
    distance = point_to_segment_km(*offset, *GAU, *SHL)
    assert 15 < distance < 35


def test_beyond_an_endpoint_clamps_to_that_endpoint():
    """The segment is finite: a point past Shillong is measured from Shillong."""
    beyond = (25.0, 91.8933)
    assert point_to_segment_km(*beyond, *GAU, *SHL) == pytest.approx(
        haversine_km(*beyond, *SHL), rel=0.05
    )


def test_degenerate_segment_falls_back_to_point_distance():
    assert point_to_segment_km(*GAU, *SHL, *SHL) == pytest.approx(
        haversine_km(*GAU, *SHL), rel=0.01
    )


def test_bbox_covers_every_seed_place(network):
    for place in network.places.values():
        assert NER_BBOX["south"] <= place.lat <= NER_BBOX["north"], place.name
        assert NER_BBOX["west"] <= place.lon <= NER_BBOX["east"], place.name
