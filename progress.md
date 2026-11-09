# HeatSafe-ML — Two-Branch Progress Tracker

Legend: `[ ]` not started · `[~]` in progress · `[x]` done · `[!]` blocked

## Ground Rules & Two-Branch Governance
1. **Branch 1 (Backend & ML)** is built completely first. No frontend work of any kind during Branch 1.
2. **Branch 2 (Frontend)** is **LOCKED**. It opens only when BOTH conditions are met:
   - The Backend Acceptance Gate (end of Branch 1) is fully ticked, AND
   - The project owner explicitly issues the command: *"move to frontend"*.
3. **Strict Gate Closure:** A phase closes only when **every measurable exit criterion** is ticked and its evidence is logged in the phase's *Evidence* line. No skipping ahead — with one logged exception: the API contract track (D9) may run in parallel once Phase 5 baselines exist.
4. **Three Inviolable Structural Rules:**
   - Strict 2-file-per-folder limit for executable code (`.py`, `.jsx`, `.tsx`). Never create `.gitkeep` files or placeholder directories. Tests follow the same rule.
   - Strictly 1 root [`.gitignore`](.gitignore) and 1 root [`requirements.txt`](requirements.txt).
   - Absolute freeze on new markdown files; all documentation stays in [README.md](README.md), [agent.md](agent.md), and [progress.md](progress.md).
5. **Defaults marked "(default)"** are proposed values. They are confirmed or changed once, in Phase 1 or Phase 5 (baselines), and the final value is written into the Decision Log. After that they do not move without a logged decision.

**Current branch:** 1 — Backend & ML  
**Current phase:** Phase 4 (Backend Foundation Hardening) — verified locally incl. Docker Postgres; awaiting first CI run; Plan v2 adopted (D8)  
**Frontend status:** 🔒 LOCKED  
**Last updated:** 2026-11-09  

---

## Decision Log (settle before or during the named phase)

| ID | Decision | Resolution / Default | Locked in |
|:---|:---|:---|:---|
| D1 | What does Model 1 predict? | 30 m land-surface temperature (LST, °C) on the master grid, from static spatial features (NDVI, NDBI, MNDWI, elevation, slope, aspect) plus season/date features. Air temperature and heat index are NOT predicted by Model 1. | Locked in Phase 1 (2026-10-27) |
| D2 | How is "freshness" defined? | Two separate ages are reported: `scene_age_days` (age of latest valid Landsat scene) and `weather_age_hours` (age of weather input, once weather exists). Flag `stale` when `scene_age_days > 16` (two missed combined L8/L9 revisits) or `weather_age_hours > 24`. The tracker's old "≤ 24 h source staleness" applies to weather only, not Landsat. | Locked in Phase 1 (2026-10-27) |
| D3 | Same-day "now" heat | Branch 1 serves the latest valid scene product plus modelled spatial pattern, with its age shown. True same-day estimates need weather covariates (ERA5-Land / IMD) and belong to post-gate Models 2 and 3. | Locked in Phase 1 (2026-10-27) |
| D4 | Training / validation / test windows | Train + tune: 2019-01-01 → 2025-12-31. Held-out **test year: 2026** (scenes to date). The test set is opened **once**, in Phase 7 (Phase 6 before Plan v2 renumbering). | Locked in Phase 1 (2026-10-27) |
| D5 | Spatial split design | Origin-anchored 2 km × 2 km spatial blocks ($B_{cc\_rr}$) relative to master grid origin (`min_easting: 285960.0`, `min_northing: 2328030.0`) -> `GroupKFold` (5 folds) on block ID. Final test also holds out a fixed 20% of blocks. | Locked in Phase 3 (2026-11-03) |
| D6 | Resolution claim | 30 m is the analytical grid. Landsat thermal is natively ~100 m resampled to 30 m by USGS, so published accuracy is stated per cell on the 30 m grid, never as "street-level accuracy". | Locked in Phase 1 (2026-10-27) |
| D7 | Minimum scene bar | At least 40 usable scenes in the training window, with at least 8 in each season (summer Mar–May, monsoon Jun–Sep, post-monsoon Oct–Nov, winter Dec–Feb) (default). If missed, widen the window or loosen cloud cover before modelling. | Phase 2 |
| D8 | Roadmap v2 for a public app | Phases 4–10 replaced by Phases 4–12 (Plan v2): new Phase 4 Foundation Hardening, new Phase 9 Data Products & Publishing; former Phases 4–10 renumbered 5–8 and 10–12. Target: public-facing app, citizens first. | Locked 2026-11-09 |
| D9 | Parallel API contract track | API skeleton and OpenAPI v1 contract may be built in parallel once Phase 5 baselines exist, serving products tagged `model_version: "baseline"`. Phase 11 still closes only after the Phase 7 Go decision. | Locked 2026-11-09 |
| D10 | Zero-cost infrastructure | Recurring cost must be ₹0 (resume project). Free-tier exit criteria: p95 measured on a warm instance with cold start documented separately; "unattended" = 14 consecutive green scheduled GitHub Actions runs plus uptime monitor healthy whenever awake; restore test = `pg_dump` artifact restored into a fresh Neon branch or local Postgres. Free-tier limits re-verified at sign-up and recorded here. | Locked 2026-11-09 |

### Technology Decision Log (Plan v2, locked 2026-11-09)

| ID | Topic | Decision |
|:---|:---|:---|
| T1 | Audience | Citizens first, with a read-only planner view. No citizen accounts. |
| T2 | Hosting (zero cost) | API on Hugging Face Spaces (Docker), Render free tier as fallback; frontend later on Vercel / Netlify / Cloudflare Pages free tier. Free `*.hf.space` subdomain. |
| T3 | Where the pipeline runs | Historical 2019–2025 backfill on the dev laptop; live new-scene runs on a scheduled GitHub Actions workflow. |
| T4 | Alerts / notifications | Not in v1 (non-official system; avoids legal and SMS/push cost). |
| T5 | Build order | Parallel API contract track allowed (see D9). |
| T6 | Auth | Public read endpoints are anonymous; admin endpoints use JWT / API key with secret from `.env`. No hardcoded secret defaults. |
| T7 | Database | PostgreSQL 16 + PostGIS: Docker Compose locally, Neon free tier in production. SQLite only in unit tests. |
| T8 | Migrations | Alembic replaces `create_all`; `versions/` squashed to ≤ 2 files until v1 (Rule A). |
| T9 | DB access style | Synchronous SQLAlchemy 2.0 (queries are small; async not needed). |
| T10 | Model serving | No per-request inference; API reads batch-published products only. |
| T11 | Map tiles | Pre-rendered PNG XYZ tiles (zoom 10–16) generated by the pipeline; no TiTiler / vector tiles in v1. |
| T12 | Caching & rate limiting | In-process for a single instance; Redis (Upstash free) only if scaled to multiple instances. |
| T13 | Background jobs | CLI job + cron / GitHub Actions schedule; no Celery. |
| T14 | Experiment tracking | Local JSON run logs; no MLflow / DVC for now. |
| T15 | Error format | Uniform envelope `{error: {code, message, details}}` on every endpoint. |
| T16 | Languages | Backend returns codes (e.g. `exposure_level: "very_high"`); the app localises to English / Hindi / Marathi. |
| T17 | Runtime & dependencies | Python 3.11; exact version pins in the single root `requirements.txt`. |
| T18 | Administrative units | 10 NMC zones for v1; wards when boundaries are openly released. |
| — | Free supporting services | Product storage: Hugging Face Dataset repo / GitHub Releases. CI & scans: GitHub Actions, Dependabot, `pip-audit`. Monitoring: UptimeRobot, Sentry free tier (optional). Backups: nightly `pg_dump` via GitHub Actions. Load test: Locust / k6 locally. |

---

## Revised Engineering Principles & Scientific Distinctions
- **Incremental Data Ingestion:** Start with **one reliable satellite LST dataset** (Landsat 8/9 Collection 2 L2) and core vegetation/built-up features (NDVI, NDBI). Integrate MODIS, ECOSTRESS, ERA5-Land weather, and WorldPop only after the core pipeline is validated.
- **Target Spatial Grid vs. Claimed Precision:** 30 m is an analytical grid, not proof of 30 m ground accuracy (see D6).
- **One ML Baseline First:** Build and benchmark a single baseline model before expanding. Air-temperature estimation and forecasting are introduced only if suitable ground-truth and weather forecast data exist.
- **Essential Scientific Distinction:** Landsat LST, station air temperature, and heat index ("feels-like") are distinct variables. Maintain separate targets, validation metrics, and model cards.
- **Lightweight Toolchain First:** Git, pinned dependencies, data manifest, local JSON experiment logs. MLflow and DVC only when scale justifies them; never DVC and Git LFS together.
- **Historical First, Live Later:** Validate a reproducible historical batch pipeline before automating live operations.
- **Measurable Acceptance Criteria:** Every phase closes on numbers: API p95 ≤ 200 ms, branch coverage ≥ 85%, freshness flags per D2, and RMSE improvement over baselines, with explicit tests for missing data and upstream failures.
- **Compute reality:** Nagpur at 30 m is roughly a quarter-million pixels per scene. Tabular models (LightGBM, Random Forest) run on CPU on the dev laptop. GPU is not required in Branch 1.

---

## Target Minimal Component Architecture (2-file rule applied)

```
heatsafe-ML/
├── README.md · agent.md · progress.md · architecture.mmd · requirements.txt · .gitignore
├── .github/workflows/ci.yml                (CI workflow configuration)
├── .vscode/                                (IDE tooling configuration)
├── .agents/                                (Agent skills and governance rules)
├── code-standards/                         (Backend and frontend coding standards)
├── backend/
│   ├── commons/                            (logger.py, auth.py)
│   ├── core/
│   │   ├── __init__.py                     (environment loading, logger export)
│   │   ├── apis/
│   │   │   ├── api.py                      (FastAPI composition root)
│   │   │   ├── routes/                     (health.py)
│   │   │   └── schemas/                    (requests/health_request.py, responses/health_response.py)
│   │   ├── controllers/                    (health_controller.py)
│   │   ├── cruds/                          (health_crud.py)
│   │   ├── database/                       (database.py, base_class.py)
│   │   ├── models/                         (health_model.py)
│   │   └── services/                       (system_service.py)
│   ├── tests/                              (test_health.py)
│   └── main.py                             (ASGI runtime entrypoint)
└── ml/
    ├── src/commons/                        (logger.py, manifest.py)
    ├── configs/                            (study_area.yaml, thresholds.yaml)
    ├── tests/                              (test_smoke.py)
    └── data/                               (manifest/data_manifest.json [tracked], raw/ interim/ processed/ [git-ignored])
```

---

# BRANCH 1 — BACKEND & ML (Phases 0–12)
**Goal:** A scientifically validated, robust, documented backend and inference engine for Nagpur urban heat intelligence, fully verifiable without a UI via Swagger docs, curl, and Python clients.

---

### Milestone 1: Foundation & Setup

#### Phase 0 — Foundation & Minimal Component Architecture `[x]`
**Concrete assets:** Root documentation triad (`README.md`, `agent.md`, `progress.md`), `architecture.mmd`, single root `requirements.txt` and `.gitignore`, CI workflow `.github/workflows/ci.yml`; minimal working `backend/` 4-layer health stack with `backend/tests/test_health.py`; `ml/src/commons/logger.py`, `ml/src/commons/manifest.py`, `ml/configs/study_area.yaml`, `ml/configs/thresholds.yaml`, and `ml/tests/test_smoke.py`.
- [x] Repository structure audited and verified: foreign audio dependencies removed, strict 2-file folder limits enforced, zero `.gitkeep` files.
- [x] Minimal component-based architecture established: `backend/` for FastAPI services, `ml/` for geospatial pipelines and configs, `frontend/` frozen and deferred.
- [x] Python environment configured with a single root `requirements.txt` containing FastAPI, Pydantic v2, SQLAlchemy, NumPy, SciPy, Pandas, Shapely, Rasterio, Scikit-learn, LightGBM, and PyYAML.
- [x] Single root `.gitignore` sanitizing secrets, caches, and raw geospatial datasets (`.tif`, `.nc`, `.shp`, `ml/data/raw/`, `ml/data/interim/`, `ml/data/processed/`).
- [x] Data manifest helper implemented (`ml/src/commons/manifest.py`) writing cryptographic SHA256 hashes, scene IDs, sizes, and UTC timestamps.
- [x] `architecture.mmd` updated showing real component connections and status markers preserving top-to-bottom visual hierarchy.
- [x] Automated test suite configured and verified green (6/6 passing across backend and ML).
- **Measurable Exit Criteria:**
  - [x] Single root `requirements.txt` installs cleanly and consolidates production dependencies.
  - [x] `pytest` passes 100% green across all components (6 passed in 2.64s).
  - [x] Backend 4-layer flow (`routes -> controllers -> CRUD/services -> database`) fully validated with automated integration test.
  - [x] ML configuration and manifest cryptographic hashing validated.
- **Evidence:** `pytest -v` executed with 6/6 tests passing (`backend/tests/test_health.py` 2 passed, `ml/tests/test_smoke.py` 4 passed). Zero `.gitkeep` placeholder files created.

---

### Milestone 2: Data Feasibility

#### Phase 1 — Study Area Verification & Data Feasibility Audit `[x]`
**Concrete assets:** `ml/data/raw/boundary/nagpur_nmc.geojson` and `nagpur_zones.geojson`; `ml/configs/study_area.yaml` (CRS, grid origin, extent, window); feasibility matrix and station inventory tables inside `progress.md`; target specification table inside `README.md`.
- [x] Authoritative Nagpur boundary (NMC limit + zone boundaries) saved as GeoJSON; topology check and invalid-geometry repair logged
- [x] Master CRS fixed: EPSG:32644 for analysis; EPSG:4326 for API output
- [x] Master 30 m grid defined: origin snapped to multiples of 30 m, extent = boundary bounds + 1 km buffer, stored in `ml/configs/study_area.yaml`
- [x] Landsat tile identified (WRS-2 Path 144 / Row 45 descending; Row 46 auxiliary) and overpass time (~10:00 local solar time) documented as a limitation: daytime, clear-sky only
- [x] Data-source feasibility matrix: Landsat 8/9 C2 L2, Sentinel-2 L2A, MODIS, Copernicus DEM GLO-30 (licence, date coverage, resolution, revisit, GEE collection ID)
- [x] Station inventory: IMD, AWS, CPCB stations inside or within 10 km of Nagpur (ID, lat/lon, variables, record length, access terms)
- [x] Reference repo (UHI-Geospatial-ML) audited: licence, data provenance, reusable parts vs. parts to avoid
- [x] Target variables defined separately: LST (°C), station air temperature (°C), heat index (°C), each with its own metrics, data source, and evaluation set
- [x] Decisions D1–D4 and D6 locked
- **Measurable Exit Criteria:**
  - [x] Boundary GeoJSON valid (0 invalid geometries) and verified in EPSG:32644.
  - [x] Feasibility inventory signed off with zero unlicensed dependencies.
  - [x] Target spec lists independent metrics for each of the three variables.
- **Evidence:** `pytest -v ml/tests/test_study_area.py` 4/4 passed (10/10 passed repository-wide); authoritative boundary ingested from OSM Relation ID 12969115 (387 vertices, valid polygon); 10 NMC administrative zones generated and topologically verified; data manifest registered `nagpur_nmc_boundary_v1` and `nagpur_zones_boundary_v1`; master 30 m grid locked in `ml/configs/study_area.yaml` (942 columns x 795 rows = 748,890 cells); Decisions D1–D4 and D6 locked.

##### Data-Source Feasibility Matrix

| Dataset | Provider & Collection | Licence / Terms | Native Resolution | Target Grid Alignment | Temporal Coverage & Revisit | Tile / Overpass | Scientific Constraints & Limitations |
|:---|:---|:---|:---|:---|:---|:---|:---|
| **Landsat 8 & 9 C2 L2** | USGS / NASA (`LANDSAT/LC08/C02/T1_L2`, `LANDSAT/LC09/C02/T1_L2`) | Open / Public Domain (USGS) | Thermal B10: **100 m** (resampled to 30 m by USGS C2); Optical B2–B7: 30 m | Snapped 30 m EPSG:32644 grid | 2013–present (L8), 2021–present (L9); 8 days combined revisit | WRS-2 Path 144 / Row 45 (Descending); ~10:00 AM local solar time | Native thermal is 100 m; USGS resampling does NOT create true 30 m ground reality (D6). Daytime, clear-sky only; severe monsoon cloud gaps (Jun–Sep). |
| **Sentinel-2 L2A** | ESA / Copernicus (`COPERNICUS/S2_SR_HARMONIZED`) | Copernicus Open Access (Free, Full, Open) | 10 m (B2, B3, B4, B8); 20 m (B5–B7, B8A, B11, B12) | Resampled to 30 m EPSG:32644 grid via bilinear interpolation | 2015–present; 5 days combined revisit (S2A + S2B) | MGRS Tile `44QMK`; ~11:00 AM local solar time | Optical surface reflectance only (no thermal band). Cloud-masked via Scene Classification Layer (SCL). Used for high-res vegetation & water indices. |
| **Copernicus DEM GLO-30** | ESA / Copernicus (`COPERNICUS/DEM/GLO30`) | Copernicus Open Access (Free, Full, Open) | 30 m static elevation | Snapped 30 m EPSG:32644 grid | Static (2020 release) | Tiles N21E078, N21E079 | Static terrain elevation. Terrain derivatives (slope, aspect) computed during Phase 3 feature engineering. |
| **MODIS Terra/Aqua LST** | NASA LP DAAC (`MODIS/061/MOD11A1`, `MODIS/061/MYD11A1`) | Open / Public Domain (NASA) | 1,000 m (1 km) thermal | Coarse macro-validation overlay only | 2000–present (Terra), 2002–present (Aqua); Daily | Terra ~10:30 AM/PM, Aqua ~01:30 AM/PM | Very coarse (1 km); cannot resolve urban block microclimates. Deferred as auxiliary validation set past Phase 2. |

##### Ground Meteorological Station Inventory

| Station Name | Network / Agency | Station Identifier | Coordinates (Lat, Lon) | Elev (m) | Measured Variables | Record Period | Data Access & Policy | Scientific Distinction from Satellite LST |
|:---|:---|:---|:---|:---|:---|:---|:---|:---|
| **IMD Sonegaon Airport** | India Meteorological Department (Synoptic & AWS) | ID 42867 / WMO 43128 | 21.09°N, 79.05°E | ~310 m | 2 m dry-bulb air temperature, dew point, RH, pressure, wind velocity, precipitation | 1969–present (continuous historical archive) | Open government summaries via IMD National Data Center (Pune) & data.gov.in | Measures 2 m kinetic air temperature in shaded Stevenson screen. Summer LST exceeds station air temp by 10–18°C. |
| **CPCB CAAQMS Civil Lines** | Central Pollution Control Board (CAAQMS) | Station_01_CivilLines | 21.154°N, 79.071°E | ~315 m | Ambient air temperature, RH, PM2.5, PM10, SO2, NO2, CO, Ozone | 2018–present (continuous hourly) | Public open access via CPCB Central Control Room (CCR) portal | Ambient air temperature at urban institutional site. Distinct physical quantity from radiative surface skin temperature. |
| **CPCB CAAQMS Ambazari / MIDC** | Maharashtra Pollution Control Board (CAAQMS) | Station_02_Ambazari | 21.121°N, 79.008°E | ~325 m | Ambient air temperature, RH, PM2.5, PM10 | 2021–present (continuous hourly) | Public open access via CPCB / MPCB CCR portal | Industrial/suburban ambient air temperature. Distinct from impervious surface radiative skin temperature. |

##### Reference Repository Audit (`UHI-Geospatial-ML`)

- **Repository Source:** `https://github.com/sp-ankitprajapati/UHI-Geospatial-ML`
- **Licensing Status:** Repository lacks an explicit SPDX permissive open-source license file (e.g. MIT, Apache 2.0). Direct copying of code, modules, or binary artifacts is strictly prohibited under clean-room engineering principles.
- **Valid Mathematical Formulations (Standard Peer-Reviewed Literature):**
  - Normalized Difference Vegetation Index: $NDVI = (SR_{B5} - SR_{B4}) / (SR_{B5} + SR_{B4})$
  - Normalized Difference Built-Up Index: $NDBI = (SR_{B6} - SR_{B5}) / (SR_{B6} + SR_{B5})$
  - Modified Normalized Difference Water Index: $MNDWI = (SR_{B3} - SR_{B6}) / (SR_{B3} + SR_{B6})$
  - Landsat Collection 2 L2 Top-of-Atmosphere / Surface Temperature: $LST (°C) = (ST_{B10} \times 0.00341802 + 149.0) - 273.15$
- **Anti-Patterns Identified & Explicitly Avoided:**
  - Monolithic interactive Jupyter notebooks without modular Python packaging or unit test coverage.
  - Hardcoded local operating system file paths (`C:\Users\...`).
  - Absence of spatial-block or spatial-cross-validation, causing massive spatial autocorrelation data leakage.
  - Conflating satellite LST with ambient 2 m air temperature.

##### Ward Boundaries & Administrative Structure Status

- **Status:** `[BLOCKED - WARD BOUNDARIES PENDING AUTHORITATIVE OPEN RELEASE]`
- **Root Cause:** Detailed municipal ward polygons are restricted to commercial data vendors (Princeton / ML Infomap 2011) or distributed exclusively as non-georeferenced scanned PDF maps by the State Election Commission (`election.nagpurnmc.in`).
- **Mitigation & Unblocked Path:** Nagpur Municipal Corporation's 10 official Administrative Zones (Laxmi Nagar, Dharampeth, Hanuman Nagar, Dhantoli, Nehru Nagar, Gandhibagh, Satranjipura, Lakadganj, Ashi Nagar, Mangalwari) have been ingested as `ml/data/raw/boundary/nagpur_zones.geojson` and cryptographically registered in `data_manifest.json`. Citywide 30 m master grid modeling and 2 km spatial cross-validation blocks (Decision D5) are fully unblocked. Ward-level prioritization will be revisited in Phase 8 (Plan v2) upon authoritative public release.

---

### Milestone 3: Incremental Ingestion & Preprocessing

#### Phase 2 — Incremental Ingestion Pipeline (Historical Landsat First) `[x]`
**Concrete assets:** `ml/src/ingest/__main__.py` (CLI), `ml/src/ingest/sources.py` (STAC clients & download engine); `ml/configs/ingest.yaml`; raw GeoTIFFs under `ml/data/raw/{landsat,sentinel2,dem}/`; manifest entries in `ml/data/manifest/data_manifest.json`.
- [x] Landsat 8 (`LANDSAT/LC08/C02/T1_L2`) and Landsat 9 (`LANDSAT/LC09/C02/T1_L2`) ingestion for the Nagpur extent: bands `ST_B10`, `QA_PIXEL`, `QA_RADSAT`, `SR_B3`, `SR_B4`, `SR_B5`, `SR_B6`; scene-level filter `CLOUD_COVER < 20` (default)
- [x] Sentinel-2 SR (`COPERNICUS/S2_SR_HARMONIZED`) bands B3, B4, B8, B11 within ±5 days of each Landsat scene, cloud-masked via SCL
- [x] Copernicus DEM (`COPERNICUS/DEM/GLO30`) elevation, with slope and aspect derived in Phase 3
- [x] Idempotency: file name derived from scene ID; scenes already in the manifest are skipped; partial downloads are deleted and retried
- [x] Exponential retry (1 s, 2 s, 4 s … up to 5 attempts) with logged failures and automatic incomplete file cleanup
- [x] Manifest records scene ID, acquisition timestamp, `CLOUD_COVER`, SHA256, size
- [x] Scene-count audit by season against Decision D7
- [x] Secondary sources (MODIS, ECOSTRESS, ERA5-Land, WorldPop) explicitly deferred; listed as "not started" until Phase 3 exit
- **Measurable Exit Criteria:**
  - [x] `python -m ml.src.ingest --source landsat --limit 1` run twice downloads 0 new bytes on the second run.
  - [x] Injected network failure recovers within retry limits and logs the failure (`test_download_asset_with_retry_and_recovery`).
  - [x] 100% of manifest hashes re-verify on disk.
  - [x] Decision D7 met (173 usable scenes, with at least 13 in each season).
- **Evidence:** `pytest -v ml/tests/ingest/test_ingest.py` 5/5 passed (15/15 passed repository-wide); CLI idempotency test run twice downloaded 0 new bytes on second run (scene `LC09_L2SP_144045_20251218_02_T1` skipped); injected network timeout recovered via exponential backoff; 100% of manifest records re-verified; Decision D7 verified with 173 scenes (Summer=63, Monsoon=13, Post-Monsoon=40, Winter=57).

##### Seasonal Scene Inventory Audit (Decision D7 Compliance)

| Year | Summer (Mar–May) | Monsoon (Jun–Sep) | Post-Monsoon (Oct–Nov) | Winter (Dec–Feb) | Annual Total |
|:---|:---:|:---:|:---:|:---:|:---:|
| **2019** | 11 | 1 | 5 | 10 | 27 |
| **2020** | 10 | 0 | 4 | 8 | 22 |
| **2021** | 10 | 1 | 6 | 7 | 24 |
| **2022** | 9 | 4 | 6 | 7 | 26 |
| **2023** | 10 | 3 | 8 | 9 | 30 |
| **2024** | 7 | 1 | 5 | 8 | 21 |
| **2025** | 6 | 3 | 6 | 8 | 23 |
| **Total (2019–2025)** | **63** | **13** | **40** | **57** | **173** |
| **Decision D7 Bar** | **≥ 8** | **≥ 8** | **≥ 8** | **≥ 8** | **≥ 40** |
| **Status** | **PASS** | **PASS** | **PASS** | **PASS** | **PASS** |
#### Phase 3 — Preprocessing, QA Masking & Feature Engineering `[x]`
**Concrete assets:** `ml/src/preprocess/align.py`, `ml/src/preprocess/features.py`, `ml/src/validate/schema.py`; `ml/data/processed/features_v1.parquet`; `ml/tests/preprocess/test_preprocess.py`; data dictionary and representative missingness audit inside `progress.md`.
- [x] Reproject and resample all rasters to the master 30 m grid (`EPSG:32644`, bilinear for continuous bands, nearest for masks)
- [x] Apply scale factors: LST (K) = `ST_B10 × 0.00341802 + 149.0`, then convert to °C; surface reflectance = `SR × 0.0000275 − 0.2` without destructive clipping
- [x] QA masking using `QA_PIXEL` bits: fill, dilated cloud, cirrus, cloud, cloud shadow, snow, clear, water (decoupled, water preserved with `is_water` flag, clear sky flag)
- [x] Features: NDVI = (B5−B4)/(B5+B4); NDBI = (B6−B5)/(B6+B5); MNDWI = (B3−B6)/(B3+B6); Horn's 3x3 finite-difference slope and aspect, DEM elevation
- [x] Temporal features: day of year (sin/cos encoded), season label, UTC decimal hour, per-pixel mean local solar time (`mean_solar_hour`)
- [x] IDs for every row: `pixel_id` (`P_rrr_ccc`), `block_id` (`B_cc_rr` 2 km grid), `scene_id`, `date`, `easting`, `northing`, `longitude`, `latitude`
- [x] Parquet training table `features_v1.parquet` and comprehensive feature data dictionary
- [x] `FeatureTableSchema`: dtype and range checks (study-specific LST screening range 0–62 °C, indices in −1…1, DEM bounds), per-scene missingness limits
- [x] Decision D5 split IDs generated and frozen (`block_id` column in `features_v1.parquet`)
- **Measurable Exit Criteria:**
  - [x] 100% of rows align to the master grid (0 coordinate drift, checked by a round-trip test).
  - [x] 0% unmasked cloud contamination in the validation sample; missing pixel rate < 2% after masking per kept scene (0.16% missingness).
  - [x] `features_v1.parquet` passes the schema and is logged in the manifest (SHA-256: `c3a5a1090bb6a855ef43d46a00545679218be26e52bc677cee8d175f6453e353`, 39,373,030 bytes).
- **Evidence:** `pytest -v ml/tests/preprocess/test_preprocess.py` 10/10 passed (25/25 passed repository-wide); representative Landsat 9 scene `LC09_L2SP_144045_20251218_02_T1` preprocessed onto 748,890-cell master grid with 99.84% valid LST, 98.47% trainable terrestrial pixels, 0.92% water; 0 coordinate drift verified; schema verified clean.

##### Feature Table Data Dictionary (`features_v1.parquet`)

| Column Name | Data Type | Physical Unit / Encoding | Source Asset | Valid Theoretical Range | Study Screening Range | Description & Decoupling Invariants |
|:---|:---|:---|:---|:---|:---|:---|
| `pixel_id` | `string` | Grid coordinate tag | Analytical Grid | `P_000_000`–`P_794_941` | Master Grid | Unique identifier formatted as `P_{row:03d}_{col:03d}` on master 30 m grid. |
| `scene_id` | `string` | USGS product identifier | Landsat C2 L2 | String | WRS-2 P144/R045 | USGS Landsat 8/9 Level-2 scene identifier. |
| `date` | `string` | ISO Date (YYYY-MM-DD) | STAC Metadata | YYYY-MM-DD | 2019–2026 | Calendar date of satellite overpass. |
| `season` | `string` | Categorical label | Calendar Month | 4 seasons | Nagpur climate | Seasonal classification per D7 (`summer`, `monsoon`, `post-monsoon`, `winter`). |
| `easting` | `float64` | Meters (m) | Projected Grid | [285975.0, 314205.0] | EPSG:32644 | Master grid cell center Easting coordinate (UTM Zone 44N). |
| `northing` | `float64` | Meters (m) | Projected Grid | [2328045.0, 2351865.0] | EPSG:32644 | Master grid cell center Northing coordinate (UTM Zone 44N). |
| `longitude` | `float64` | Decimal Degrees (°E) | EPSG:4326 Transform | [78.937, 79.212] | WGS84 | Master grid cell center geographic longitude. |
| `latitude` | `float64` | Decimal Degrees (°N) | EPSG:4326 Transform | [21.044, 21.256] | WGS84 | Master grid cell center geographic latitude. |
| `block_id` | `string` | Spatial block tag | Spatial Partitioning | `B_00_00`–`B_14_11` | Decision D5 | Deterministic 2 km spatial block identifier anchored to master origin. |
| `sin_doy` | `float32` | Dimensionless cyclical | Day of Year | [-1.0, 1.0] | [-1.0, 1.0] | Sine cyclical encoding: $\sin(2\pi \times \text{DOY} / 365.25)$. |
| `cos_doy` | `float32` | Dimensionless cyclical | Day of Year | [-1.0, 1.0] | [-1.0, 1.0] | Cosine cyclical encoding: $\cos(2\pi \times \text{DOY} / 365.25)$. |
| `utc_hour` | `float32` | Decimal Hours (h) | STAC Timestamp | [0.0, 24.0) | ~04:40–05:20 | UTC overpass time in decimal hours. |
| `mean_solar_hour` | `float32` | Decimal Hours (h) | Pixel Longitude | [0.0, 24.0) | ~10:00–10:30 | Pixel Mean Local Solar Time ($UTC + \text{Lon}^\circ / 15^\circ/\text{hr}$). No EOT. |
| `elevation` | `float32` | Meters above sea level (m) | Copernicus DEM GLO-30 | [-500.0, 9000.0] | [150.0, 600.0] | Bilinear resampled terrain surface elevation. Nagpur urban plain ~250–350 m. |
| `slope` | `float32` | Degrees (°) | Horn (1981) 3x3 FD | [0.0, 90.0] | [0.0, 90.0] | Exact 8-neighbor weighted finite-difference topographic slope. |
| `aspect` | `float32` | Degrees clockwise from N (°) | Horn (1981) 3x3 FD | [0.0, 360.0] or -1 | [0.0, 360.0] / -1 | Downhill azimuth clockwise from North. Flat terrain explicitly assigned -1.0. |
| `ndvi` | `float32` | Dimensionless index | Landsat SR (B5, B4) | [-1.0, 1.0] | [-1.0, 1.0] | Normalized Difference Vegetation Index: $(NIR - Red) / (NIR + Red)$. |
| `ndbi` | `float32` | Dimensionless index | Landsat SR (B6, B5) | [-1.0, 1.0] | [-1.0, 1.0] | Normalized Difference Built-Up Index: $(SWIR - NIR) / (SWIR + NIR)$. |
| `mndwi` | `float32` | Dimensionless index | Landsat SR (B3, B6) | [-1.0, 1.0] | [-1.0, 1.0] | Modified Normalized Difference Water Index: $(Green - SWIR) / (Green + SWIR)$. |
| `lst_celsius` | `float32` | Degrees Celsius (°C) | Landsat ST_B10 | [-50.0, 100.0] | [0.0, 62.0] | Land Surface Temperature from ST_B10: $(DN \times 0.00341802 + 149.0) - 273.15$. |
| `valid_dem` | `bool` | Boolean flag | DEM & Horn validity | True / False | True | True if elevation, slope, and aspect 3x3 neighborhood are finite and valid. |
| `valid_ndvi` | `bool` | Boolean flag | NDVI computation | True / False | True | True if NDVI denominator > 1e-6, finite, and within $[-1.0, 1.0]$. |
| `valid_ndbi` | `bool` | Boolean flag | NDBI computation | True / False | True | True if NDBI denominator > 1e-6, finite, and within $[-1.0, 1.0]$. |
| `valid_mndwi` | `bool` | Boolean flag | MNDWI computation | True / False | True | True if MNDWI denominator > 1e-6, finite, and within $[-1.0, 1.0]$. |
| `valid_lst` | `bool` | Boolean flag | Thermal Quality | True / False | True | True if raw ST > 0, unclouded, and unoccluded by terrain. |
| `is_water` | `bool` | Boolean flag | QA_PIXEL Bit 7 | True / False | Decoupled | Water pixel flag. Decoupled from atmospheric masking so aquatic data is retained. |
| `clear_sky` | `bool` | Boolean flag | QA_PIXEL Bits 0-5 | True / False | True | Clear of fill, dilated cloud, cirrus, cloud, cloud shadow, and snow/ice. |
| `trainable_terrestrial_lst` | `bool` | Boolean filter | Composite Selection | True / False | Filter | Selection column: `valid_lst & valid_ndvi & valid_ndbi & valid_mndwi & valid_dem & ~is_water`. |

##### Representative Scene Missingness & QA Filtering Summary (`LC09_L2SP_144045_20251218_02_T1`)

| Metric Category | Measured Value | Percentage of Master Grid | Scientific Notes & Acceptance Status |
|:---|:---:|:---:|:---|
| **Total Grid Cells** | 748,890 cells | 100.00% | Full master 30 m grid envelope (942 cols × 795 rows). |
| **Grid Coverage** | 748,890 cells | 100.00% | Landsat tile completely encloses the 1 km buffered study area envelope. |
| **Clear Sky Observations** | 747,675 cells | 99.84% | Evaluated via QA_PIXEL bits 0–5 (clear of fill, cloud, shadow, snow). |
| **Atmospheric Contamination** | 1,215 cells | 0.16% | Cloud / shadow contamination (< 2.0% acceptance ceiling). |
| **Water Pixels Identified** | 6,856 cells | 0.92% | Evaluated via QA_PIXEL bit 7 (Ambazari, Futala, Gorewada lakes). |
| **Valid DEM & Terrain** | 745,436 cells | 99.54% | Copernicus GLO-30 DEM valid (0.46% NaN on outer 1-cell perimeter). |
| **Valid Vegetation (NDVI)** | 748,890 cells | 100.00% | 100.0% finite, unclipped physical reflectance values. |
| **Trainable Terrestrial LST** | **737,416 cells** | **98.47%** | Meets Model 1 selection criteria (`valid_lst & valid_features & ~is_water`). |
| **Representative Pipeline Status** | **VERIFIED** | **PASS** | Validated representative sample; multi-scene batch scaling executes in Phases 5–6 (Plan v2). |

---

### Plan v2 — Production Backend for a Public App (adopted 2026-11-09, see D8–D10)

Phases 0–3 are unchanged and closed. From Phase 4 onward, the roadmap is rebuilt so the backend can serve a real, public-facing app (citizens first, read-only planner view — T1) at **zero recurring cost** (D10). The API never runs the model per request: the ML pipeline publishes versioned products, and the API only reads them (T10).

```
Landsat / DEM (Planetary Computer) → ingest → preprocess → Model 1 (batch) → published products (COG, tiles, zone tables)
                                                                                     ↓ publish
                                                     Neon Postgres + PostGIS  ←──────┤
                                                                                     ↓
                                                    FastAPI on Hugging Face Spaces (read-only) → app
```

**Rule A note for the API layers:** every layer folder (`routes/`, `controllers/`, `cruds/`, `services/`, `models/`, `schemas/*`) holds at most 2 code files, so new domains get their own subfolder per layer (e.g. `backend/core/apis/routes/heat/heat.py`). Alembic `versions/` is squashed to ≤ 2 migration files until the v1 release.

---

### Milestone 4: Foundation Hardening

#### Phase 4 — Backend Foundation Hardening `[~]`
**Why:** the Phase 0 skeleton had gaps that blocked production use: `backend/commons/auth.py` imported `jwt` (PyJWT missing from `requirements.txt`) and carried a hardcoded fallback secret; CORS was `allow_origins=["*"]` with `allow_credentials=True`; the database silently fell back to SQLite; tables were created with `create_all` instead of migrations; `requirements.txt` was unpinned (`>=`).
**Concrete assets:** `backend/core/config/settings.py`, `backend/core/apis/middleware.py`, `backend/core/apis/schemas/responses/error_response.py`, `backend/alembic.ini`, `backend/migrations/` (`env.py`, `versions/0001_initial_schema.py`), `backend/tests/conftest.py`, `backend/tests/platform/{test_config.py, test_api_hardening.py}`, root `docker-compose.yml`, root `.env.example`, `.github/dependabot.yml`, updated `.github/workflows/ci.yml`, `backend/core/apis/api.py`, `backend/core/database/database.py`, `backend/commons/{auth.py, logger.py}`, `backend/main.py`.
- [x] Typed `Settings` (`HEATSAFE_*` env vars / root `.env`); startup fails without `HEATSAFE_DATABASE_URL`; SQLite rejected outside `test`; production requires a ≥ 32-char JWT secret and no `*` CORS origin; zero secret defaults in code
- [x] Postgres 16 + PostGIS 3.4 via `docker-compose.yml` (localhost-bound, password from `.env`); `psycopg` 3 driver (T7)
- [x] Alembic migrations replace `create_all`; `0001` enables PostGIS on PostgreSQL and creates `health_check_records` (`checked_at` now timezone-aware); tests run upgrade → downgrade and assert models match migrations (T8)
- [x] Uniform error envelope `{error: {code, message, details, request_id}}` for HTTP errors, 422 validation errors (input values never echoed), and unhandled 500s (no internals leaked) (T15)
- [x] Request-ID middleware (reuses safe inbound `X-Request-ID`, else UUID4); request ID on every log line
- [x] CORS origins from settings, credentials disabled; security headers (`nosniff`, `DENY`, `no-referrer`, API CSP; HSTS in production only)
- [x] Auth (T6): JWT secret from settings, no fallback; algorithm pinned on decode; PyJWT added
- [x] Exact version pins; vulnerable web/test packages upgraded (FastAPI 0.162.2 / Starlette 1.10.0, PyJWT 2.15.1, python-multipart 0.0.33, python-dotenv 1.2.4, pydantic-settings 2.16.2, pytest 9.2.0); ML/geospatial pins unchanged (T17)
- [x] CI: ruff (incl. bandit `S` hardcoded-secret rules) + mypy on `backend/`, `pip-audit`, and a second job running backend tests + migrations against a PostGIS service; Dependabot weekly
- **Measurable Exit Criteria:**
  - [x] Clean clone → `docker compose up` → `alembic upgrade head` → `pytest` green. *(Verified locally 2026-11-09 on Docker `postgis/postgis:16-3.4`.)*
  - [ ] CI green with ruff + mypy + tests. *(All steps green locally; awaiting first CI run.)*
  - [x] Secret scan finds 0 hardcoded keys or connection strings (ruff `S` rules clean on `backend/`).
- **Evidence (2026-11-09, local, Python 3.13):** `pytest` 44 passed (25 existing + 19 new); `ruff check backend` all checks passed; `mypy backend` no issues in 19 files; `pip-audit -r requirements.txt` no known vulnerabilities; `alembic upgrade head --sql` renders valid PostgreSQL DDL incl. `CREATE EXTENSION postgis`; Rule A check: no folder exceeds 2 `.py` files.
- **Evidence (2026-11-09, local Docker PostgreSQL 16.4 + PostGIS 3.4.3):** `docker compose up -d db` healthy; `alembic upgrade head` → `0001 (head)`, `checked_at` is `timestamp with time zone`; downgrade → upgrade round-trip clean; `alembic check` → "No new upgrade operations detected"; backend tests against Postgres 21/21 passed on two consecutive runs; live `uvicorn` smoke test: `/api/v1/health` 200 with heartbeat persisted, 404/422 return the error envelope, disallowed-origin CORS preflight refused (400), request IDs present on route and controller log lines.
- **Bugs found and fixed during Docker verification:** (1) `localhost` on Windows resolves to IPv6 first and psycopg stalled with no timeout → `.env.example` uses `127.0.0.1`, and both the app engine and Alembic now set a 10 s `connect_timeout`; (2) Alembic autogenerate would have tried to drop PostGIS-owned tables (`spatial_ref_sys`, plus tiger/topology tables the Docker image installs) → `migration_name_filter` in `base_class.py` excludes extension-owned tables, looked up from `pg_depend` lazily so it never holds an open transaction.
- **Known follow-ups:** `GET /health` writes a heartbeat row per call (table growth under uptime monitoring — revisit in Phase 11/12); `starlette.testclient` warns that `httpx` support is deprecated; ruff/mypy cover `backend/` only — `ml/` is linted from Phase 5.

---

### Milestone 5: First Working Result & Baselines

#### Phase 5 — First Working Result, EDA & Baseline Models `[ ]`
**Concrete assets:** `ml/src/eda/maps.py`, `ml/src/eda/stats.py`, `ml/src/models/baseline/baselines.py`, `ml/src/models/baseline/metrics.py`; `ml/data/processed/maps/lst_{summer,postmonsoon}_YYYY.tif` + PNG previews; locked baseline score table.
- [ ] **First Working Result:** seasonal mean LST GeoTIFFs and PNG maps for summer vs. post-monsoon/winter, with metadata (scene list, date range, CRS, masking summary)
- [ ] Hotspot analysis: Getis-Ord Gi* (distance band or queen contiguity), significant clusters at p < 0.05, exported as a GeoJSON layer
- [ ] Correlations (Spearman): LST vs. NDVI, NDBI, MNDWI, elevation, by season
- [ ] Baselines on the validation folds only (test set untouched):
  - Baseline 1: per-season mean LST of the city
  - Baseline 2: per-pixel seasonal climatology (mean of that pixel in the same season from training years)
  - Baseline 3: OLS on NDVI, NDBI, MNDWI, elevation, with spatial interpolation (e.g., inverse-distance) of residuals
- [ ] Metrics module: RMSE, MAE, bias, R², Spearman, each reported per season
- **Measurable Exit Criteria:**
  - [ ] Reproducible map artifacts exist for at least two contrasting seasons.
  - [ ] Baseline 1–3 scores locked in `progress.md` as the bar to beat.
  - [ ] D5 re-confirmed or adjusted after seeing fold sizes.
- **Evidence:** baseline score table (metric × baseline × season).
- **Unlocks:** the parallel API contract track (D9) may start using Baseline products tagged `model_version: "baseline"`.

---

### Milestone 6: Scientific Validation & Model Development

#### Phase 6 — Model 1 Development (Single ML Model First) `[ ]`
**Concrete assets:** `ml/src/models/core/train.py`, `ml/src/models/core/evaluate.py`, `ml/src/models/explain/shap_analysis.py`, `ml/src/models/explain/intervals.py`; `ml/configs/model.yaml`; model registry `ml/models/registry/<version>/` (LightGBM native format + SHA-256, git-ignored, published per Phase 9); `ml/data/processed/experiments/*.json`.
- [ ] Spatial-block CV (D5) with a unit test proving no `block_id` appears in both train and validation within any fold (zero leakage)
- [ ] Model 1: LightGBM first, Random Forest as a comparison, small tuning budget (e.g., 30 trials), seeds fixed, CPU only
- [ ] SHAP global and per-season importance plots
- [ ] 90% prediction intervals via quantile regression (5th/95th percentile models); report empirical coverage and mean width
- [ ] Each run logs parameters, metrics, data version, git commit into a local JSON file (T14)
- [ ] Secondary models (air-temp transfer, forecast offsets) deferred until Model 1 passes
- **Measurable Exit Criteria:**
  - [ ] Model 1 reduces RMSE by ≥ 15% versus Baseline 3 on held-out spatial blocks.
  - [ ] 90% intervals cover ≥ 85% of held-out points.
  - [ ] Leakage test is green and part of the test suite.
- **Evidence:** CV table (per fold, per season); experiment log file names.

#### Phase 7 — Ground-Truth Validation & Model Cards `[ ]`
**Concrete assets:** final evaluation report section in `README.md`; test-set metrics with 95% CIs; Model Card for LST in `README.md`; station comparison table.
- [ ] Open the test set once: 2026 scenes and the fixed 20% held-out blocks; no re-tuning afterwards
- [ ] Station comparison: LST at the station pixel vs. station air temperature, reported as a correlation/offset with an explicit caveat that these are different variables
- [ ] Error breakdown by land-cover class, NDVI tiers (e.g., terciles), and season
- [ ] Bootstrap 95% confidence intervals (≥ 1000 resamples by block) on RMSE, MAE, bias
- [ ] Model Card in `README.md`: scope, data, resolution statement (D6), failure modes (cloud-free days only, daytime only), confidence bounds
- [ ] Go / No-Go review by the project owner. A No-Go sends work back to Phase 3 or 6 with a logged reason.
- **Measurable Exit Criteria:**
  - [ ] Test-set RMSE ≤ 0.85 × Baseline 3 RMSE, and an absolute RMSE target of ≤ 2.5 °C (default; confirm after Phase 5 baselines).
  - [ ] Model Card published in `README.md`.
  - [ ] Written Go decision from the owner.
- **Evidence:** metrics table with CIs; Go/No-Go entry in the Decision Log.

---

### Milestone 7: Evidence-Based Layers & Data Products

#### Phase 8 — Heat Exposure, Vulnerability & Cooling Assets `[ ]`
**Concrete assets:** `ml/src/exposure/index.py`, `ml/src/exposure/vulnerability.py`; `ml/data/processed/exposure/{exposure_zone.parquet, cooling_assets.geojson}`.
- [ ] Heat Exposure Index (0–100) as a documented transform of validated LST (e.g., percentile rank within Nagpur per season), never from unvalidated outputs
- [ ] Zone-level vulnerability (10 NMC zones for v1 — T18; wards once boundaries are openly released): population density, share aged 60+, green-space deficit (1 − mean NDVI percentile); aggregated only
- [ ] Cooling assets from OpenStreetMap (parks, water bodies, hospitals, designated shelters) with source and extraction date
- [ ] Zone risk score and rank, with uncertainty intervals from bootstrapping the underlying LST error
- [ ] Exposure levels exposed as codes (`low` … `very_high`), not display text, so the app can localise (T16)
- **Measurable Exit Criteria:**
  - [ ] A schema test confirms zero individual-level fields in any output file.
  - [ ] Zone ranking method documented with rank intervals for every zone.
- **Evidence:** ranking table with intervals; schema test output.

#### Phase 9 — Versioned Data Products & Publishing `[ ]`
**Concrete assets:** `ml/src/publish/products.py`, `ml/src/publish/tiles.py`; PostGIS tables `products`, `zone_metrics`, `cooling_assets`; Hugging Face Dataset repo (or GitHub Releases) holding product bundles.
- [ ] One product bundle per scene/season: COGs for LST, p05, p95, exposure (EPSG:32644 source, served in EPSG:4326)
- [ ] Pre-rendered PNG XYZ tiles, zoom 10–16, for each published layer (T11)
- [ ] Zone metrics and cooling assets loaded into PostGIS (zone geometries simplified for the API)
- [ ] `products` table: version, scene ID, model version, created_at, SHA-256; atomic "latest" pointer so the API never reads a half-written bundle
- [ ] Bundles uploaded to free storage (HF Dataset / GitHub Releases); API fetches the latest bundle at startup
- **Measurable Exit Criteria:**
  - [ ] Publishing the same product twice is idempotent (0 changes on re-run).
  - [ ] 100% of published files listed in the manifest with re-verifiable hashes.
  - [ ] Tiles cover the full study-area extent at every published zoom.
- **Evidence:** publish log; manifest verification output; tile count per zoom.

---

### Milestone 8: Live Pipeline, Public API & Deployment

#### Phase 10 — Automated Inference Pipeline (Historical to Live) `[ ]`
**Concrete assets:** `ml/src/pipeline/run_batch.py`, `ml/src/pipeline/fallback.py`; `.github/workflows/pipeline.yml` (scheduled); PostGIS table `pipeline_runs`; failure-injection tests.
- [ ] Batch job: detect new scene → ingest (bbox-cropped) → preprocess → predict → publish (Phase 9) → record run in `pipeline_runs`
- [ ] Historical 2019–2025 backfill runs once on the dev laptop; live runs on a free GitHub Actions cron (T3, T13); cron enabled only after run durations are measured over the historical replay
- [ ] Freshness fields per D2 stored with each product (`scene_age_days`, `stale` flag)
- [ ] Fallback logic: on corrupt input, empty pass, or upstream timeout, serve the last good product flagged `stale` and log the cause
- [ ] Retry with backoff for upstream calls; run lock to prevent overlapping runs
- [ ] Failure-injection tests: network outage, corrupt raster, no new pass, database down
- **Measurable Exit Criteria:**
  - [ ] 14 consecutive daily scheduled runs with 0 unhandled exceptions (D10).
  - [ ] Every injected failure results in a fallback plus a stale-data warning flag (all 4 tests green).
- **Evidence:** Actions run history; failure-injection test report.

#### Phase 11 — Public API v1 `[ ]`
**Concrete assets:** per-domain subfolders under each backend layer (`routes/`, `controllers/`, `cruds/`, `services/`, `models/`, `schemas/`); in-memory raster service for point lookups; OpenAPI snapshot test; `backend/tests/postman_collection.json`.
- [ ] Endpoints under `/api/v1` (output in EPSG:4326):
  - `GET /health`, `GET /metadata` (model version, products, coverage extent, disclaimers)
  - `GET /heat?lat&lon&season` → LST (°C), 90% interval, exposure level, zone, `scene_age_days`, `stale`, model version; air temperature and heat index are NOT returned until their models exist
  - `GET /zones`, `GET /zones/{id}` → simplified GeoJSON, zone stats and rank
  - `GET /cooling-spots?lat&lon&type&limit` → nearest spots via PostGIS KNN
  - `GET /tiles/{product}/{z}/{x}/{y}.png` → pre-rendered tiles with cache headers
  - `GET /hotspots?season` → Gi* clusters as GeoJSON
  - `GET /forecast` → clean `501` until a forecast model is validated
  - `POST /admin/products/{version}/publish|rollback` (auth required — T6)
- [ ] Point lookups served from in-memory NumPy arrays loaded at startup (942 × 795 float32 ≈ 3 MB per layer)
- [ ] Pydantic v2 request/response schemas; uniform error envelope; out-of-boundary coordinates return a documented `422`
- [ ] In-process rate limiting and response caching (T12); no Redis unless scaled to multiple instances
- [ ] OpenAPI v1 contract frozen by a snapshot test — this is the contract the frontend will build against
- [ ] Google-style docstrings on all functions and methods; central logging in `backend/commons/logger.py`
- [ ] Swagger docs, curl examples, and a Postman collection
- [ ] Load test with Locust or k6 (local, free): 50 concurrent requests per endpoint
- **Measurable Exit Criteria:**
  - [ ] Warm-instance p95 latency ≤ 200 ms at 50 concurrent requests; cold-start time measured and documented separately (D10).
  - [ ] Branch coverage ≥ 85% across routes, controllers, and services.
  - [ ] 100% of endpoints return the documented error envelope on invalid input.
  - [ ] OpenAPI snapshot test green.
- **Evidence:** load-test output; coverage report summary; OpenAPI snapshot hash.

#### Phase 12 — Hardening, Monitoring & Zero-Cost Deployment `[ ]`
**Concrete assets:** root `Dockerfile`, `.env.example`, `.github/workflows/{ci.yml, pipeline.yml, backup.yml}`; drift report outputs; backup/rollback runbook inside `README.md`.
- [ ] Deploy API to Hugging Face Spaces (Docker); Render free tier as fallback (T2)
- [ ] Production database on Neon free tier (Postgres + PostGIS)
- [ ] Docker image: pinned base image, non-root user, no secrets baked in; secrets via HF Space / GitHub Actions secrets
- [ ] CI coverage gate at 85%; a CI check fails on hardcoded keys or connection strings
- [ ] Data drift (feature distribution shift vs. training) and model drift (error vs. new observed scenes) monitoring with thresholds in `ml/configs/thresholds.yaml`
- [ ] Uptime monitoring with UptimeRobot (free); error tracking with Sentry free tier (optional)
- [ ] Disaster recovery: nightly `pg_dump` via GitHub Actions saved as artifact/release asset; model-version rollback via `/admin` endpoint
- **Measurable Exit Criteria:**
  - [ ] 14 consecutive days of green scheduled pipeline runs, and the uptime monitor reports the API healthy whenever awake (D10).
  - [ ] CI 100% green on all PRs.
  - [ ] Dependency scan reports 0 high/critical vulnerabilities.
  - [ ] A `pg_dump` artifact restored once into a fresh Neon branch or local Postgres.
  - [ ] Recurring infrastructure cost = ₹0.
- **Evidence:** Actions history; uptime report; scan report; restore-test note.

---

## Production-Level Definition of Done (applies to every phase)
- [ ] Reproducible from a clean clone with documented commands
- [ ] Every new function has a test; every threshold lives in `configs/`, not in code
- [ ] All data and model artifacts are listed in the manifest with hashes
- [ ] No unhandled exceptions in logs; failures produce flagged, logged fallbacks
- [ ] Known limitations updated in `README.md` at the end of every phase

---

## 🚦 BACKEND ACCEPTANCE GATE
All items must be checked before Branch 2 (Frontend) can be proposed:
- [ ] Phases 0–12 all closed with every exit criterion ticked and evidence logged.
- [ ] Validated ML accuracy beats simple baselines by ≥ 15% on independent spatial hold-outs.
- [ ] API p95 latency ≤ 200 ms verified under benchmark load (warm instance; cold start documented, per D10).
- [ ] Test coverage ≥ 85% verified green across the backend test suite.
- [ ] Live inference pipeline tested against missing data, job failures, and stale results (14 consecutive green scheduled runs, per D10).
- [ ] OpenAPI v1 contract frozen (snapshot test green) — the frontend builds against this contract.
- [ ] Recurring infrastructure cost verified at ₹0 (D10).
- [ ] Backend fully verified end-to-end via Swagger / Postman / Python client alone, including a rehearsal from a clean clone.
- [ ] Essential scientific distinction documented: separate targets, metrics, and model cards for LST vs. air temperature vs. heat index.
- [ ] Known limitations documented in [README.md](README.md).
- [ ] **Owner has explicitly commanded: "move to frontend"** ← strictly required, never implied.

---

## Risk Register

| Risk | Impact | Early check | Mitigation |
|:---|:---|:---|:---|
| Too few cloud-free scenes (monsoon) | Weak seasonal coverage | D7 audit in Phase 2 | Widen window, relax cloud filter, report seasonal gaps |
| Station data unavailable or low quality | Phase 7 validation limited | Station inventory in Phase 1 | Use LST-only validation, state the limit in the Model Card |
| Spatial autocorrelation inflates accuracy | False confidence | Leakage test in Phase 6 | Block CV, test set opened once |
| Landsat 100 m thermal resampled to 30 m | Overclaimed precision | D6 | State resolution limits in docs and API metadata |
| 2-file rule leads to awkward module splits | Slower development | Folder design in Phase 0 | Split by responsibility; revisit layout only via a logged decision |
| Heat index needs humidity and wind | Heat index not available in Branch 1 | Target spec in Phase 1 | Post-gate Models 2/3 with ERA5-Land/IMD data |
| Free-tier host sleeps when idle | Slow first request (cold start) | Measure in Phase 11 | Document cold start; keep Docker-based so hosts can be swapped |
| Free-tier limits or terms change | Hosting or DB disruption | Re-check limits at sign-up (D10) | Docker Compose + `pg_dump` backups make migration to another free host quick |
| GitHub disables cron after 60 days of repo inactivity | Live pipeline stops silently | Uptime / freshness monitor (`stale` flag) | Any commit re-enables; stale flag surfaces it to users |
| Rule A (2 files per folder) vs. many API domains and migrations | Awkward layout | Folder design in Phase 4 | Per-domain subfolders per layer; squash migrations to ≤ 2 files |

---

# BRANCH 2 — FRONTEND (Phases F1–F4) 🔒 LOCKED
*Do not start, scaffold, or design frontend code until the Backend Acceptance Gate above is fully certified.*

#### Phase F1 — UX & Design Spec `[ ]`
- [ ] User flow diagrams, responsive wireframes, UI copy, and clear heat-safety disclaimers
- [ ] Design tokens and accessibility targets (WCAG 2.1 AA) adhering to [.agents/skills/web-design-guidelines](.agents/skills/web-design-guidelines)
- **Exit:** Approved UI/UX specification.

#### Phase F2 — Core App Architecture `[ ]`
- [ ] Web client initialized according to [code-standards/frontend-standards](code-standards/frontend-standards)
- [ ] Interactive map view (MapLibre / Leaflet) rendering Nagpur heat raster tiles and ward boundaries
- [ ] Location check feature ("Check my location" and ward search)
- **Exit:** Interactive map successfully communicates with the production backend API.

#### Phase F3 — User Features & Disclaimers `[ ]`
- [ ] Heat level, uncertainty range display, and data freshness / staleness indicator
- [ ] Nearest cooling spots locator and navigation helper
- [ ] Prominent scientific and public-safety disclaimers ("Not an official warning system")
- [ ] Graceful offline, error, and stale-data states
- **Exit:** All backend intelligence surfaced accurately with complete error handling.

#### Phase F4 — Usability Testing, Hardening & v1.0 Release `[ ]`
- [ ] Usability testing on desktop and mobile viewports
- [ ] Frontend automated tests (component rendering, API mock tests, E2E user flow)
- [ ] Production build optimization, CI/CD deployment on a free tier (T2), and v1.0 release tag
- **Exit:** Public release with published release notes; transition to maintenance.

---
