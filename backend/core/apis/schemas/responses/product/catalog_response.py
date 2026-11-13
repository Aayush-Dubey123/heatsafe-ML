from pydantic import BaseModel, Field


class ZoneSummary(BaseModel):
    """
    Zone figures for one season: exposure, vulnerability, risk, and rank intervals (95% bootstrap).

    Zone polygons are approximate (generated, not an official map) and population comes from a
    modelled 1 km grid; see the Model Card limits.
    """

    zone_id: int
    zone_name: str
    area_km2: float
    season: str
    mean_lst_celsius: float | None
    exposure_index: float | None
    exposure_index_ci_low: float | None
    exposure_index_ci_high: float | None
    exposure_level: str | None
    exposure_rank: int | None
    vulnerability_score: float | None
    risk_score: float | None
    risk_rank: int | None
    risk_rank_low: int | None
    risk_rank_high: int | None
    population: int | None
    population_density_per_km2: float | None
    share_age_60_plus: float | None
    green_deficit: float | None
    assets: dict[str, int] = Field(default_factory=dict, description="Cooling places per category inside the zone.")


class ZoneDetail(BaseModel):
    """
    One zone with its figures for every season.
    """

    zone_id: int
    zone_name: str
    area_km2: float
    seasons: dict[str, ZoneSummary]


class LocalitySummary(BaseModel):
    """
    Mean surface temperature and exposure of one named locality (revenue village).
    """

    locality_id: int
    locality_name: str
    area_km2: float
    in_extended_limit: bool
    layer: str
    mean_lst_celsius: float | None
    exposure_index: float | None
    exposure_level: str | None


class CoolingSpot(BaseModel):
    """
    A public cooling-related place from OpenStreetMap.
    """

    asset_id: str
    category: str
    name: str | None
    latitude: float
    longitude: float
    distance_km: float


class CoolingSpotsResponse(BaseModel):
    """
    Cooling places near a point, nearest first.
    """

    latitude: float
    longitude: float
    radius_km: float
    count: int
    spots: list[CoolingSpot]
    source: str = "OpenStreetMap contributors (ODbL); completeness varies"


class ForecastResponse(BaseModel):
    """
    Placeholder body; the forecast endpoint currently returns 501.
    """

    available: bool = False
