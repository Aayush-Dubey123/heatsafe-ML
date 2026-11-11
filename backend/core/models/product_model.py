from sqlalchemy import Boolean, Column, Date, DateTime, Float, Integer, String, Text, UniqueConstraint

from backend.core.database.base_class import Base


class Product(Base):
    """
    One published, versioned data bundle (rasters, tiles, vector layers).

    Attributes:
        version (str): Deterministic bundle id (scene date + scene id + model version).
        is_latest (bool): True for the bundle the API currently serves.
        stale (bool): True when the scene is older than the freshness limit (Decision D2).
    """
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(String(128), nullable=False, unique=True, index=True)
    scene_id = Column(String(64), nullable=False)
    scene_date = Column(Date, nullable=False)
    model_version = Column(String(64), nullable=False)
    manifest_sha256 = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    is_latest = Column(Boolean, nullable=False, default=False)
    stale = Column(Boolean, nullable=False, default=False)


class Zone(Base):
    """
    Administrative zone (10 NMC zones; polygons are approximate, see README).
    """
    __tablename__ = "zones"

    zone_id = Column(Integer, primary_key=True, autoincrement=False)
    zone_name = Column(String(64), nullable=False)
    area_km2 = Column(Float, nullable=False)
    geometry_geojson = Column(Text, nullable=False)


class ZoneMetric(Base):
    """
    Exposure, vulnerability, and risk figures for one zone and season of one product.
    """
    __tablename__ = "zone_metrics"
    __table_args__ = (
        UniqueConstraint("product_version", "zone_id", "season", name="uq_zone_metrics_product_zone_season"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_version = Column(String(128), nullable=False, index=True)
    zone_id = Column(Integer, nullable=False)
    season = Column(String(16), nullable=False)
    mean_lst_celsius = Column(Float)
    exposure_index = Column(Float)
    exposure_index_ci_low = Column(Float)
    exposure_index_ci_high = Column(Float)
    exposure_level = Column(String(16))
    vulnerability_score = Column(Float)
    risk_score = Column(Float)
    risk_rank = Column(Integer)
    risk_rank_low = Column(Integer)
    risk_rank_high = Column(Integer)
    population = Column(Integer)
    population_density_per_km2 = Column(Float)
    share_age_60_plus = Column(Float)
    green_deficit = Column(Float)


class Locality(Base):
    """
    Named locality (revenue village) traced from the NMC intention map (~100 m accuracy).
    """
    __tablename__ = "localities"

    locality_id = Column(Integer, primary_key=True, autoincrement=False)
    locality_name = Column(String(64), nullable=False)
    area_km2 = Column(Float, nullable=False)
    in_extended_limit = Column(Boolean, nullable=False, default=False)
    geometry_geojson = Column(Text, nullable=False)


class LocalityMetric(Base):
    """
    Mean surface temperature and exposure for one locality and layer of one product.
    """
    __tablename__ = "locality_metrics"
    __table_args__ = (
        UniqueConstraint("product_version", "locality_id", "layer", name="uq_locality_metrics_product_locality_layer"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_version = Column(String(128), nullable=False, index=True)
    locality_id = Column(Integer, nullable=False)
    layer = Column(String(32), nullable=False)
    mean_lst_celsius = Column(Float)
    exposure_index = Column(Float)
    exposure_level = Column(String(16))


class CoolingAsset(Base):
    """
    Public cooling-related place from OpenStreetMap (park, water body, health facility, shelter).
    """
    __tablename__ = "cooling_assets"

    asset_id = Column(String(48), primary_key=True)
    category = Column(String(32), nullable=False, index=True)
    name = Column(String(256))
    longitude = Column(Float, nullable=False)
    latitude = Column(Float, nullable=False)


class PipelineRun(Base):
    """
    Audit record of one automated pipeline run (Phase 10).
    """
    __tablename__ = "pipeline_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(32), nullable=False, index=True)
    scene_id = Column(String(64))
    product_version = Column(String(128))
    detail = Column(Text)
