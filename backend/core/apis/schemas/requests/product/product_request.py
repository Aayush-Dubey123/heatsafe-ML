from enum import StrEnum

# Study-area limits (WGS84). Requests outside them are rejected with a documented 422.
MIN_LATITUDE, MAX_LATITUDE = 21.0, 21.3
MIN_LONGITUDE, MAX_LONGITUDE = 78.9, 79.3
MIN_ZOOM, MAX_ZOOM = 10, 16


class Season(StrEnum):
    """
    Seasons used for seasonal composites and exposure layers.
    """
    SUMMER = "summer"
    MONSOON = "monsoon"
    POST_MONSOON = "post-monsoon"
    WINTER = "winter"


class MetricLayer(StrEnum):
    """
    Layers that locality metrics are reported for.
    """
    LATEST_SCENE = "latest_scene"
    SUMMER = "summer"
    MONSOON = "monsoon"
    POST_MONSOON = "post-monsoon"
    WINTER = "winter"


class TileLayer(StrEnum):
    """
    Map tile layers published with each product bundle.
    """
    LATEST_LST = "latest_lst"
    LST_SUMMER = "lst_summer"
    LST_MONSOON = "lst_monsoon"
    LST_POST_MONSOON = "lst_post-monsoon"
    LST_WINTER = "lst_winter"
    EXPOSURE_SUMMER = "exposure_summer"
    EXPOSURE_MONSOON = "exposure_monsoon"
    EXPOSURE_POST_MONSOON = "exposure_post-monsoon"
    EXPOSURE_WINTER = "exposure_winter"


class AssetCategory(StrEnum):
    """
    Cooling-related place categories (OpenStreetMap).
    """
    GREEN_SPACE = "green_space"
    WATER_BODY = "water_body"
    HEALTH_FACILITY = "health_facility"
    PUBLIC_SHELTER = "public_shelter"
    DRINKING_WATER = "drinking_water"
