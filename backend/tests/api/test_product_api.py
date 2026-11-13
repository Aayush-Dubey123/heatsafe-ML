import json
import os
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from backend.core.apis.api import create_app
from backend.core.config.settings import get_settings
from backend.core.services.product.lookup import EXPOSURE_BREAKS, EXPOSURE_CODES, exposure_level
from backend.tests.api.bundle_factory import build_bundle

BASE = "/api/v1"
SNAPSHOT = Path(__file__).with_name("openapi_v1.json")
REPO_ROOT = Path(__file__).resolve().parents[3]


def make_client(monkeypatch: pytest.MonkeyPatch, root: Path, **env: str) -> TestClient:
    """
    Build an app whose product folder (and optional settings) point at a test location.
    """
    monkeypatch.setenv("HEATSAFE_PUBLISHED_DIR", str(root))
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    return TestClient(create_app())


@pytest.fixture
def served(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    A running app serving a small synthetic bundle; yields (client, facts).
    """
    facts = build_bundle(tmp_path)
    with make_client(monkeypatch, tmp_path) as client:
        yield client, facts
    get_settings.cache_clear()


def error_code(response) -> str:
    """
    Extract the error envelope code from a response.
    """
    return response.json()["error"]["code"]


def test_metadata_describes_product_layers_and_limits(served):
    """
    Metadata reports freshness, the 9 map layers, bounds, level codes, and disclaimers.
    """
    client, facts = served
    data = client.get(f"{BASE}/metadata").json()
    assert data["product"]["scene_date"] == facts["scene_date"]
    assert data["product"]["scene_age_days"] == 3 and data["product"]["stale"] is False
    assert len(data["layers"]) == 9 and data["layers"][0]["tile_url"].endswith("{z}/{x}/{y}.png")
    assert data["exposure_levels"] == ["low", "moderate", "high", "very_high", "extreme"]
    assert any("not an official warning" in d for d in data["disclaimers"]) and "30 m" in data["resolution_note"]
    west, south, east, north = data["bounds"]
    assert west < data["center"][0] < east and south < data["center"][1] < north


def test_old_scene_is_flagged_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    A scene older than 16 days is reported stale with its real age (Decision D2).
    """
    build_bundle(tmp_path, scene_age_days=20)
    with make_client(monkeypatch, tmp_path) as client:
        product = client.get(f"{BASE}/metadata").json()["product"]
    get_settings.cache_clear()
    assert product["scene_age_days"] == 20 and product["stale"] is True


def test_heat_returns_estimate_range_areas_and_seasons(served):
    """
    A point returns LST with a 90% range, its locality and zone, and exposure for every season.
    """
    client, facts = served
    data = client.get(f"{BASE}/heat", params={"lat": facts["lat"], "lon": facts["lon"]}).json()
    assert data["covered"] is True and data["lst_p05"] < data["lst_celsius"] < data["lst_p95"]
    assert data["lst_p95"] - data["lst_p05"] == pytest.approx(3.0, abs=0.02)
    assert data["zone"]["name"] == "Zone East" and data["locality"]["name"] in {"Locality North", "Locality South"}
    assert set(data["seasons"]) == {"summer", "monsoon", "post-monsoon", "winter"}
    assert data["seasons"]["summer"]["exposure_level"] in EXPOSURE_CODES
    west = client.get(f"{BASE}/heat", params={"lat": facts["lat"], "lon": facts["west_lon"]}).json()
    assert west["zone"]["name"] == "Zone West" and west["lst_celsius"] < data["lst_celsius"]
    assert "air temperature" in data["note"]


def test_heat_for_cell_without_estimate_is_not_covered(served):
    """
    Open water (no estimate) returns covered=false with null temperatures instead of an error.
    """
    client, facts = served
    lat, lon = facts["water_lat_lon"]
    data = client.get(f"{BASE}/heat", params={"lat": lat, "lon": lon}).json()
    assert data["covered"] is False and data["lst_celsius"] is None and data["lst_p05"] is None


def test_heat_rejects_out_of_area_and_invalid_coordinates(served):
    """
    Nagpur-wide limits return 422 `validation_error`; inside the limits but off the grid, `outside_study_area`.
    """
    client, _ = served
    far = client.get(f"{BASE}/heat", params={"lat": 19.0, "lon": 79.0})
    assert far.status_code == 422 and error_code(far) == "validation_error"
    assert client.get(f"{BASE}/heat", params={"lat": "abc", "lon": 79.0}).status_code == 422
    assert client.get(f"{BASE}/heat").status_code == 422
    off_grid = client.get(f"{BASE}/heat", params={"lat": 21.29, "lon": 78.91})
    assert off_grid.status_code == 422 and error_code(off_grid) == "outside_study_area"
    assert "Nagpur" in off_grid.json()["error"]["message"]


def test_zones_are_ranked_with_intervals_and_asset_counts(served):
    """
    Zones come back sorted by risk rank with rank intervals and per-category cooling-place counts.
    """
    client, _ = served
    zones = client.get(f"{BASE}/zones", params={"season": "summer"}).json()
    assert [z["zone_name"] for z in zones] == ["Zone East", "Zone West"]
    assert zones[0]["risk_rank"] == 1
    assert zones[0]["risk_rank_low"] <= zones[0]["risk_rank"] <= zones[0]["risk_rank_high"] + 1
    assert zones[1]["assets"] == {"green_space": 2, "water_body": 0}
    assert client.get(f"{BASE}/zones", params={"season": "spring"}).status_code == 422
    assert "Cache-Control" in client.get(f"{BASE}/zones").headers


def test_zone_detail_and_not_found(served):
    """
    One zone returns all four seasons; an unknown zone is a 404 envelope.
    """
    client, _ = served
    detail = client.get(f"{BASE}/zones/1").json()
    assert detail["zone_name"] == "Zone West"
    assert set(detail["seasons"]) == {"summer", "monsoon", "post-monsoon", "winter"}
    missing = client.get(f"{BASE}/zones/99")
    assert missing.status_code == 404 and error_code(missing) == "not_found"


def test_zones_geojson_merges_figures_into_properties(served):
    """
    The choropleth endpoint returns polygons with the season's figures and an honesty note.
    """
    client, _ = served
    data = client.get(f"{BASE}/zones/geojson", params={"season": "winter"}).json()
    assert data["type"] == "FeatureCollection" and len(data["features"]) == 2
    assert data["features"][0]["properties"]["season"] == "winter"
    assert "approximate" in data["properties"]["boundary_quality"]


def test_localities_listing_and_geojson(served):
    """
    Localities are listed for a layer and can be fetched as polygons with figures.
    """
    client, _ = served
    rows = client.get(f"{BASE}/localities", params={"layer": "summer"}).json()
    assert [r["locality_name"] for r in rows] == ["Locality North", "Locality South"]
    assert rows[1]["in_extended_limit"] is True and rows[0]["exposure_level"] == "high"
    latest = client.get(f"{BASE}/localities/geojson").json()
    assert latest["properties"]["layer"] == "latest_scene" and len(latest["features"]) == 2


def test_cooling_spots_nearest_first_with_filters(served):
    """
    Spots are sorted by distance, filtered by category and radius, and limited.
    """
    client, facts = served
    params = {"lat": facts["lat"], "lon": facts["lon"]}
    data = client.get(f"{BASE}/cooling-spots", params={**params, "radius_km": 1}).json()
    assert [s["asset_id"] for s in data["spots"]] == ["osm-node-1", "osm-node-3", "osm-node-2"]
    assert data["spots"][0]["distance_km"] < data["spots"][1]["distance_km"]
    green = client.get(f"{BASE}/cooling-spots", params={**params, "category": "green_space", "radius_km": 20}).json()
    assert [s["asset_id"] for s in green["spots"]] == ["osm-node-1", "osm-node-4"]
    assert client.get(f"{BASE}/cooling-spots", params={**params, "limit": 1}).json()["count"] == 1
    assert client.get(f"{BASE}/cooling-spots", params={**params, "limit": 500}).status_code == 422
    assert client.get(f"{BASE}/cooling-spots", params={**params, "category": "pool"}).status_code == 422


def test_tiles_are_served_with_cache_headers_and_unsafe_input_is_refused(served):
    """
    Existing tiles return PNG bytes with a day-long cache; missing tiles are 404; bad layers are rejected.
    """
    client, _ = served
    tile = client.get(f"{BASE}/tiles/latest_lst/12/100/200.png")
    assert tile.status_code == 200 and tile.headers["content-type"] == "image/png"
    assert "max-age=86400" in tile.headers["cache-control"] and tile.content.startswith(b"\x89PNG")
    assert client.get(f"{BASE}/tiles/latest_lst/12/100/201.png").status_code == 404
    assert client.get(f"{BASE}/tiles/latest_lst/3/0/0.png").status_code == 404
    assert client.get(f"{BASE}/tiles/secret_layer/12/100/200.png").status_code == 422
    assert client.get(f"{BASE}/tiles/..%2F..%2Fmanifest/12/100/200.png").status_code in {404, 422}


def test_hotspots_and_forecast(served):
    """
    Hotspots return a layer for seasons that have one; the forecast is a clean 501.
    """
    client, _ = served
    summer = client.get(f"{BASE}/hotspots", params={"season": "summer"}).json()
    assert summer["features"][0]["properties"]["cluster"] == "hot"
    assert client.get(f"{BASE}/hotspots", params={"season": "winter"}).status_code == 404
    forecast = client.get(f"{BASE}/forecast")
    assert forecast.status_code == 501 and error_code(forecast) == "not_implemented"


def test_every_error_uses_the_envelope_with_request_id(served):
    """
    Errors from the new endpoints all carry code, message, and a matching request id.
    """
    client, _ = served
    for response in (client.get(f"{BASE}/zones/99"), client.get(f"{BASE}/heat"), client.get(f"{BASE}/forecast")):
        body = response.json()["error"]
        assert set(body) >= {"code", "message", "request_id"} and body["request_id"] == response.headers["X-Request-ID"]


def test_no_published_product_answers_503_not_a_crash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    With nothing published, data endpoints return a documented 503 and health still works.
    """
    with make_client(monkeypatch, tmp_path / "empty") as client:
        for path in ("/metadata", "/zones", "/localities", "/hotspots", "/tiles/latest_lst/12/1/1.png",
                     "/heat?lat=21.1&lon=79.0", "/cooling-spots?lat=21.1&lon=79.0"):
            response = client.get(BASE + path)
            assert response.status_code == 503 and error_code(response) == "no_product_available", path
        assert client.get(f"{BASE}/health").status_code == 200
    get_settings.cache_clear()


def test_rate_limit_blocks_bursts_but_not_tiles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    After the per-minute quota, API calls get 429 with Retry-After; map tiles stay exempt.
    """
    build_bundle(tmp_path)
    with make_client(monkeypatch, tmp_path, HEATSAFE_RATE_LIMIT_PER_MINUTE="10") as client:
        statuses = [client.get(f"{BASE}/metadata").status_code for _ in range(12)]
        blocked = client.get(f"{BASE}/metadata")
        tiles = [client.get(f"{BASE}/tiles/latest_lst/12/100/200.png").status_code for _ in range(20)]
    get_settings.cache_clear()
    assert statuses[:10] == [200] * 10 and statuses[10:] == [429, 429]
    assert blocked.status_code == 429 and error_code(blocked) == "rate_limited"
    assert int(blocked.headers["Retry-After"]) >= 1
    assert tiles == [200] * 20


def test_exposure_level_codes_match_the_ml_configuration():
    """
    The API's level cut-offs and codes equal ml/configs/thresholds.yaml, so the maps and answers agree.
    """
    config = yaml.safe_load((REPO_ROOT / "ml" / "configs" / "thresholds.yaml").read_text(encoding="utf-8"))["exposure"]
    assert list(EXPOSURE_BREAKS) == config["level_breaks"] and list(EXPOSURE_CODES) == config["level_codes"]
    assert [exposure_level(v) for v in (0, 24.9, 25, 74.9, 75, 90, 100, None)] == [
        "low", "low", "moderate", "high", "very_high", "extreme", "extreme", None]


def test_openapi_contract_is_frozen(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    The OpenAPI spec equals the committed snapshot; set UPDATE_OPENAPI_SNAPSHOT=1 to change it on purpose.
    """
    with make_client(monkeypatch, tmp_path / "none") as client:
        current = client.get("/openapi.json").json()
    get_settings.cache_clear()
    current["info"]["version"] = "contract"
    if os.environ.get("UPDATE_OPENAPI_SNAPSHOT") == "1":
        SNAPSHOT.write_text(json.dumps(current, indent=1, sort_keys=True), encoding="utf-8")
    frozen = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert current == json.loads(json.dumps(frozen)), "API contract changed: review it, then UPDATE_OPENAPI_SNAPSHOT=1"
