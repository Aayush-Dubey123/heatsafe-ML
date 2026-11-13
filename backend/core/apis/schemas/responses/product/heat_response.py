from typing import Any

from pydantic import BaseModel, Field


class ProductInfo(BaseModel):
    """
    Which published product an answer comes from and how fresh it is (Decision D2).

    Attributes:
        version (str): Bundle version.
        scene_id (str): Landsat scene id.
        scene_date (str): Acquisition date, YYYY-MM-DD.
        scene_age_days (int): Days since acquisition, computed at request time.
        stale (bool): True when the scene is older than the freshness limit (16 days).
        model_version (str): Model 1 version that produced the estimate.
        published_utc (str | None): When the bundle was published.
        observed_fraction (float | None): Share of land cells with a clear observation (rest is model-filled).
    """

    version: str
    scene_id: str
    scene_date: str
    scene_age_days: int
    stale: bool
    model_version: str
    published_utc: str | None = None
    observed_fraction: float | None = None


class LayerInfo(BaseModel):
    """
    One map layer the frontend can display.

    Attributes:
        id (str): Layer id used in tile URLs.
        kind (str): "lst" (surface temperature, deg C) or "exposure" (index 0-100).
        season (str | None): Season for seasonal layers; None for the latest scene.
        tile_url (str): Tile URL template with {z}/{x}/{y}.
        vmin (float): Value mapped to the low end of the colour scale.
        vmax (float): Value mapped to the high end.
        unit (str): Unit label.
    """

    id: str
    kind: str
    season: str | None
    tile_url: str
    vmin: float
    vmax: float
    unit: str


class MetadataResponse(BaseModel):
    """
    Product description for the app: freshness, extent, layers, and honest limits.
    """

    product: ProductInfo
    bounds: list[float] = Field(description="[west, south, east, north] in WGS84 degrees.")
    center: list[float] = Field(description="[longitude, latitude] of the study-area centre.")
    zoom_min: int
    zoom_max: int
    layers: list[LayerInfo]
    seasons: list[str]
    exposure_levels: list[str] = Field(description="Level codes from coolest to hottest; the app localises them.")
    variable: str = Field(default="land_surface_temperature")
    resolution_note: str
    disclaimers: list[str]


class Locator(BaseModel):
    """
    A named area a point falls in.
    """

    id: int
    name: str


class SeasonExposure(BaseModel):
    """
    Seasonal exposure at a point (relative daytime surface heat within the city).
    """

    mean_lst_celsius: float | None
    exposure_index: float | None
    exposure_level: str | None


class HeatResponse(BaseModel):
    """
    Heat answer for one location.

    Attributes:
        lst_celsius (float | None): Model 1 land-surface temperature estimate (not air temperature).
        lst_p05 (float | None): 5th percentile bound of the 90% range.
        lst_p95 (float | None): 95th percentile bound of the 90% range.
        observed (bool): True if the satellite saw this cell clearly in the latest scene; False if model-filled.
        covered (bool): False for open water or cells without an estimate.
    """

    latitude: float
    longitude: float
    covered: bool
    lst_celsius: float | None
    lst_p05: float | None
    lst_p95: float | None
    observed: bool
    locality: Locator | None
    zone: Locator | None
    seasons: dict[str, SeasonExposure]
    product: ProductInfo
    note: str


class GeoJSONFeatureCollection(BaseModel):
    """
    Generic GeoJSON FeatureCollection (WGS84).
    """

    type: str = "FeatureCollection"
    features: list[dict[str, Any]]
    properties: dict[str, Any] | None = None
