"""
Automated Unit and Integration Test Suite for Preprocessing, QA Masking,
Horn Terrain Derivatives, Spatial Partitioning, and Schema Validation.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from rasterio.transform import Affine

from ml.src.preprocess.align import (
    load_master_grid_spec,
    decode_landsat_qa_pixel,
    decode_landsat_qa_radsat,
    scale_landsat_lst,
    scale_surface_reflectance,
)
from ml.src.preprocess.features import (
    compute_spectral_indices,
    compute_horn_terrain_derivatives,
    assign_deterministic_spatial_blocks,
    compute_pixel_mean_local_solar_time,
)
from ml.src.validate.schema import FeatureTableSchema, audit_scene_missingness


def test_master_grid_spec_and_affine():
    """Verify master grid origin snapping, dimensions, CRS, and affine transform."""
    spec = load_master_grid_spec()

    assert spec["crs"] == "EPSG:32644"
    assert spec["ncols"] == 942
    assert spec["nrows"] == 795
    assert spec["total_cells"] == 748890
    assert spec["cell_size"] == 30.0

    assert spec["min_easting"] == 285960.0
    assert spec["max_easting"] == 314220.0
    assert spec["min_northing"] == 2328030.0
    assert spec["max_northing"] == 2351880.0

    # Assert affine transform matches (cell_size, 0, min_e, 0, -cell_size, max_n)
    expected_transform = Affine(30.0, 0.0, 285960.0, 0.0, -30.0, 2351880.0)
    assert spec["transform"] == expected_transform

    # Assert coordinates snap strictly to 30 m multiples
    assert spec["min_easting"] % 30.0 == 0.0
    assert spec["max_easting"] % 30.0 == 0.0
    assert spec["min_northing"] % 30.0 == 0.0
    assert spec["max_northing"] % 30.0 == 0.0


def test_qa_pixel_bit_decoding_explicit_masks():
    """Test synthetic bitfield decoding; verify decoupling of atmospheric contamination and water."""
    # Test values with individual bits set:
    # Bit 0 (1): Fill
    # Bit 1 (2): Dilated cloud
    # Bit 2 (4): Cirrus
    # Bit 3 (8): Cloud
    # Bit 4 (16): Cloud Shadow
    # Bit 5 (32): Snow
    # Bit 6 (64): Clear
    # Bit 7 (128): Water
    raw_qa = np.array([0, 1, 2, 4, 8, 16, 32, 64, 128, 128 | 64], dtype=np.uint16)
    masks = decode_landsat_qa_pixel(raw_qa)

    assert bool(masks["fill_mask"][1]) is True
    assert bool(masks["dilated_cloud_mask"][2]) is True
    assert bool(masks["cirrus_mask"][3]) is True
    assert bool(masks["cloud_mask"][4]) is True
    assert bool(masks["cloud_shadow_mask"][5]) is True
    assert bool(masks["snow_mask"][6]) is True
    assert bool(masks["clear_mask"][7]) is True
    assert bool(masks["water_mask"][8]) is True

    # Decoupling check: Water bit (index 8) MUST NOT trigger atmospheric contamination mask
    assert bool(masks["water_mask"][8]) is True
    assert bool(masks["atmospheric_contamination_mask"][8]) is False

    # Snow bit (index 6) MUST trigger atmospheric contamination mask
    assert bool(masks["snow_mask"][6]) is True
    assert bool(masks["atmospheric_contamination_mask"][6]) is True

    # Combined clear water (index 9: water + clear)
    assert bool(masks["water_mask"][9]) is True
    assert bool(masks["clear_mask"][9]) is True
    assert bool(masks["atmospheric_contamination_mask"][9]) is False


def test_qa_radsat_usgs_specification_and_thermal_separation():
    """Verify USGS Landsat Collection 2 QA_RADSAT bitmask assignments and thermal decoupling."""
    # Bit 0: Band 1 (1)
    # Bit 1: Band 2 (2)
    # Bit 2: Band 3 Green (4)
    # Bit 3: Band 4 Red (8)
    # Bit 4: Band 5 NIR (16)
    # Bit 5: Band 6 SWIR-1 (32)
    # Bit 6: Band 7 SWIR-2 (64)
    # Bit 8: Band 9 (256)
    # Bit 11: Terrain Occlusion (2048)
    raw_radsat = np.array([0, 1, 4, 8, 16, 32, 64, 256, 2048], dtype=np.uint16)
    masks = decode_landsat_qa_radsat(raw_radsat)

    assert bool(masks["band1_sat_mask"][1]) is True
    assert bool(masks["band3_sat_mask"][2]) is True
    assert bool(masks["band4_sat_mask"][3]) is True
    assert bool(masks["band5_sat_mask"][4]) is True
    assert bool(masks["band6_sat_mask"][5]) is True
    assert bool(masks["band7_sat_mask"][6]) is True
    assert bool(masks["band9_sat_mask"][7]) is True
    assert bool(masks["terrain_occlusion_mask"][8]) is True

    # Decoupling check: Optical band saturation does not imply terrain occlusion
    assert bool(masks["any_optical_sat_mask"][2]) is True
    assert bool(masks["terrain_occlusion_mask"][2]) is False


def test_lst_scaling_and_fill_masking():
    """Verify LST Kelvin -> Celsius scaling and strict invalid/fill masking prior to scaling."""
    # USGS formula: LST_K = DN * 0.00341802 + 149.0; LST_C = LST_K - 273.15
    raw_st = np.array([0, 44000, 45000, 46000], dtype=np.uint16)
    fill_mask = np.array([False, False, True, False], dtype=bool)
    terrain_occlusion = np.array([False, False, False, True], dtype=bool)

    scaled_lst, valid_mask = scale_landsat_lst(
        raw_st=raw_st,
        fill_mask=fill_mask,
        terrain_occlusion_mask=terrain_occlusion,
    )

    # Pixel 0 is raw DN 0 (fill) -> invalid and NaN
    assert not valid_mask[0]
    assert np.isnan(scaled_lst[0])

    # Pixel 1 is valid raw DN 44000
    expected_kelvin = 44000 * 0.00341802 + 149.0
    expected_celsius = expected_kelvin - 273.15
    assert valid_mask[1]
    assert np.isclose(scaled_lst[1], expected_celsius, atol=1e-4)

    # Pixel 2 is masked by fill -> invalid and NaN
    assert not valid_mask[2]
    assert np.isnan(scaled_lst[2])

    # Pixel 3 is masked by terrain occlusion -> invalid and NaN
    assert not valid_mask[3]
    assert np.isnan(scaled_lst[3])


def test_reflectance_scaling_no_clipping():
    """Verify Surface Reflectance scaling preserves unclamped values with independent validity flags."""
    # USGS formula: SR = DN * 0.0000275 - 0.2
    # Case A: DN 15000 -> 15000 * 0.0000275 - 0.2 = 0.2125 (valid)
    # Case B: DN 50000 -> 50000 * 0.0000275 - 0.2 = 1.175 (unclamped > 1.0, validity False)
    # Case C: DN 2000  -> 2000 * 0.0000275 - 0.2 = -0.145 (unclamped < 0.0, validity False)
    raw_sr = np.array([15000, 50000, 2000], dtype=np.uint16)
    fill_mask = np.array([False, False, False], dtype=bool)
    band_sat_mask = np.array([False, True, False], dtype=bool)

    scaled_sr, valid_mask = scale_surface_reflectance(
        raw_sr=raw_sr,
        fill_mask=fill_mask,
        band_sat_mask=band_sat_mask,
    )

    # Assert no clipping to [0, 1] occurred
    assert np.isclose(scaled_sr[0], 0.2125, atol=1e-4)
    assert np.isclose(scaled_sr[1], 1.175, atol=1e-4)
    assert np.isclose(scaled_sr[2], -0.145, atol=1e-4)

    # Assert validity flags capture boundaries and saturation
    assert bool(valid_mask[0]) is True
    assert bool(valid_mask[1]) is False  # Out of bounds (>1.0) and saturated
    assert bool(valid_mask[2]) is False  # Out of bounds (<0.0)


def test_horn_terrain_derivatives_known_geometry():
    """Test Horn's 3x3 algorithm on synthetic planes with known slope and aspect."""
    cell_size = 30.0
    nrows, ncols = 11, 11
    r, c = np.indices((nrows, ncols))

    # 1. Plane dipping East at 45 degrees: z = 1000 - 30 * col
    dem_east = (1000.0 - c * cell_size).astype(np.float32)
    terrain_east = compute_horn_terrain_derivatives(dem_east, cell_size=cell_size)
    slope_e, valid_slope_e = terrain_east["slope"]
    aspect_e, valid_aspect_e = terrain_east["aspect"]

    # Check interior cell (5, 5)
    assert np.isclose(slope_e[5, 5], 45.0, atol=0.01)
    assert np.isclose(aspect_e[5, 5], 90.0, atol=0.01)
    assert bool(valid_slope_e[5, 5]) is True
    assert bool(valid_aspect_e[5, 5]) is True

    # 2. Plane dipping South at 45 degrees: z = 1000 - 30 * row
    dem_south = (1000.0 - r * cell_size).astype(np.float32)
    terrain_south = compute_horn_terrain_derivatives(dem_south, cell_size=cell_size)
    slope_s, _ = terrain_south["slope"]
    aspect_s, _ = terrain_south["aspect"]

    assert np.isclose(slope_s[5, 5], 45.0, atol=0.01)
    assert np.isclose(aspect_s[5, 5], 180.0, atol=0.01)

    # 3. Perimeter border handling: outer boundary must be NaN and invalid
    assert np.isnan(slope_e[0, 0])
    assert bool(valid_slope_e[0, 0]) is False
    assert np.isnan(aspect_e[0, 0])
    assert bool(valid_aspect_e[0, 0]) is False

    # 4. NoData propagation: an interior NaN must make center cell slope/aspect NaN
    dem_with_nan = dem_east.copy()
    dem_with_nan[4, 4] = np.nan
    terrain_nan = compute_horn_terrain_derivatives(dem_with_nan, cell_size=cell_size)
    slope_nan, valid_slope_nan = terrain_nan["slope"]
    # Cell (5, 5) has (4, 4) in its 3x3 neighborhood, so it must be NaN
    assert np.isnan(slope_nan[5, 5])
    assert bool(valid_slope_nan[5, 5]) is False


def test_deterministic_spatial_blocks():
    """Verify origin-anchored 2 km spatial block assignment (Decision D5)."""
    origin_e = 285960.0
    origin_n = 2328030.0

    eastings = np.array([
        origin_e,
        origin_e + 1000.0,
        origin_e + 2000.0,  # Boundary point -> snaps to col 1
        origin_e + 3999.0,
        314205.0,           # Near grid max
    ])
    northings = np.array([
        origin_n,
        origin_n + 1000.0,
        origin_n + 2000.0,  # Boundary point -> snaps to row 1
        origin_n + 3999.0,
        2351865.0,          # Near grid max
    ])

    block_ids = assign_deterministic_spatial_blocks(
        easting=eastings,
        northing=northings,
        origin_easting=origin_e,
        origin_northing=origin_n,
        block_size=2000.0,
    )

    assert block_ids[0] == "B_00_00"
    assert block_ids[1] == "B_00_00"
    assert block_ids[2] == "B_01_01"
    assert block_ids[3] == "B_01_01"
    assert block_ids[4] == "B_14_11"


def test_pixel_mean_local_solar_time_computation():
    """Verify pixel Mean Local Solar Time calculation, seasonal DOY encoding, and documentation."""
    # Nagpur longitude range ~78.95E to 79.20E
    # UTC overpass ~05:08:52 UTC
    utc_str = "2025-12-18T05:08:52.167187Z"
    lons = np.array([78.95, 79.0882, 79.20])

    res = compute_pixel_mean_local_solar_time(utc_str, lons)

    # UTC decimal ~ 5.1478 h
    assert np.isclose(res["utc_decimal"], 5.1478, atol=1e-3)
    # IST = UTC + 5:30 = 10.6478 h
    assert np.isclose(res["ist_decimal"], 10.6478, atol=1e-3)

    # MLST = UTC + lon / 15
    expected_mlst = (res["utc_decimal"] + lons / 15.0) % 24.0
    assert np.allclose(res["mean_solar_time_hours"], expected_mlst, atol=1e-4)

    # Verify Season & Date
    assert res["season"] == "winter"
    assert res["date"] == "2025-12-18"

    # DOY cyclical encoding
    assert -1.0 <= res["sin_doy"] <= 1.0
    assert -1.0 <= res["cos_doy"] <= 1.0


def test_independent_feature_validity_masks():
    """Verify independent feature validity preservation: invalid LST does not destroy valid NDVI/DEM."""
    green = np.array([0.1, 0.1])
    red = np.array([0.1, 0.1])
    nir = np.array([0.4, 0.4])
    swir = np.array([0.2, 0.2])

    indices = compute_spectral_indices(green, red, nir, swir)
    ndvi, valid_ndvi = indices["ndvi"]
    ndbi, valid_ndbi = indices["ndbi"]
    mndwi, valid_mndwi = indices["mndwi"]

    # Both pixels have valid vegetation and built-up indices
    assert np.all(valid_ndvi)
    assert np.all(valid_ndbi)

    # Pixel 0 has valid LST, Pixel 1 has cloudy LST (invalid)
    valid_lst = np.array([True, False])
    valid_dem = np.array([True, True])
    is_water = np.array([False, False])

    trainable_terrestrial_lst = (
        valid_lst & valid_ndvi & valid_ndbi & valid_mndwi & valid_dem & (~is_water)
    )

    # Pixel 0 is trainable, Pixel 1 is excluded from LST training
    assert trainable_terrestrial_lst[0] is np.True_ or trainable_terrestrial_lst[0] == True
    assert trainable_terrestrial_lst[1] is np.False_ or trainable_terrestrial_lst[1] == False

    # But Pixel 1 NDVI and DEM remain completely intact and valid!
    assert valid_ndvi[1] is np.True_ or valid_ndvi[1] == True
    assert valid_dem[1] is np.True_ or valid_dem[1] == True


def test_feature_table_schema_and_missingness():
    """Verify schema validation passes on valid data, catches screening breaches, and computes audit."""
    n = 100
    valid_df = pd.DataFrame({
        "pixel_id": [f"P_{i:03d}" for i in range(n)],
        "scene_id": ["LC09_TEST"] * n,
        "date": ["2025-12-18"] * n,
        "season": ["winter"] * n,
        "easting": np.linspace(286000.0, 314000.0, n),
        "northing": np.linspace(2329000.0, 2351000.0, n),
        "longitude": np.linspace(78.96, 79.19, n),
        "latitude": np.linspace(21.06, 21.24, n),
        "block_id": ["B_00_00"] * n,
        "sin_doy": np.zeros(n, dtype=np.float32),
        "cos_doy": np.ones(n, dtype=np.float32),
        "utc_hour": np.full(n, 5.15, dtype=np.float32),
        "mean_solar_hour": np.full(n, 10.42, dtype=np.float32),
        "elevation": np.full(n, 310.0, dtype=np.float32),
        "slope": np.full(n, 4.5, dtype=np.float32),
        "aspect": np.full(n, 90.0, dtype=np.float32),
        "ndvi": np.full(n, 0.45, dtype=np.float32),
        "ndbi": np.full(n, -0.12, dtype=np.float32),
        "mndwi": np.full(n, -0.28, dtype=np.float32),
        "lst_celsius": np.full(n, 28.5, dtype=np.float32),
        "valid_dem": np.ones(n, dtype=bool),
        "valid_ndvi": np.ones(n, dtype=bool),
        "valid_ndbi": np.ones(n, dtype=bool),
        "valid_mndwi": np.ones(n, dtype=bool),
        "valid_lst": np.ones(n, dtype=bool),
        "is_water": np.zeros(n, dtype=bool),
        "clear_sky": np.ones(n, dtype=bool),
        "trainable_terrestrial_lst": np.ones(n, dtype=bool),
    })

    # Assert schema passes on valid data
    is_valid, errors = FeatureTableSchema.validate(valid_df, raise_errors=False)
    assert is_valid is True
    assert len(errors) == 0

    # Test study screening violation: LST > 70.0 C (Decision D14)
    bad_df = valid_df.copy()
    bad_df.loc[0, "lst_celsius"] = 72.0  # Exceeds 70.0 C
    is_bad_valid, bad_errors = FeatureTableSchema.validate(bad_df, raise_errors=False)
    assert is_bad_valid is False
    assert any("screening range" in err for err in bad_errors)

    # Test missingness audit
    audit = audit_scene_missingness(valid_df, "LC09_TEST", total_grid_cells=100)
    assert audit["grid_coverage_pct"] == 100.0
    assert audit["valid_lst_pct"] == 100.0
    assert audit["missing_lst_pct"] == 0.0
    assert audit["water_cells_pct"] == 0.0
