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
**Current phase:** Phase 12 (Hardening & Zero-Cost Deployment) — Phases 0–9 and 11 closed; Phase 10 open only on the 14-day scheduled-run check (set `HEATSAFE_PIPELINE_ENABLED=true`). Backend API v1 contract frozen: frontend may start.  
**Frontend status:** 🔒 LOCKED  
**Last updated:** 2026-11-13  

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
| D11 | Baseline 2 definition under spatial CV | Per-pixel seasonal climatology is undefined for pixels in held-out blocks (they never appear in training under D5). Baseline 2 is therefore the **per-scene city mean of training-fold pixels**; per-pixel climatology is still produced as the Phase 5 seasonal maps. | Locked 2026-11-09 (Phase 5) |
| D12 | Model 1 feature design | Model 1 predicts the LST **anomaly from a scene anchor** (mean LST of the scene's training-fold / observed pixels), adds 150 m and 450 m neighbourhood means of NDVI/NDBI/MNDWI, and may add per-scene IDW residual kriging (chosen by CV). Rationale: Baseline 3 already uses same-scene information through residual interpolation, so a fair comparison needs the model to see the scene level too; at serving time the anchor comes from the observed clear pixels of the latest scene. | Locked 2026-11-09 (Phase 6) |
| D13 | Branch policy | Exactly two long-lived branches: `main` (released) and `development` (all phase work, one commit per phase). Work merges `development` → `main` only on the owner's instruction. CI runs on both. | Locked 2026-11-09 |
| D14 | LST screening range | Upper screening bound raised from 62 °C to **70 °C**. Evidence (2019–2025, 2.44 M sampled pixels): 0.51% exceed 62 °C, max 68.2 °C, concentrated in mid-May/June scenes on low-NDVI, built/bare surfaces (mean NDVI 0.22, NDBI +0.09) — physically plausible peak surface heat, not sensor error. 62 °C had been set from a single winter scene. | Locked 2026-11-09 (Phase 5) |
| D15 | Phase 7 Go / No-Go | **Go.** On 2026-11-10 the owner instructed "resume phase 7 do till 8" before the test was run. All numeric Phase 7 criteria then passed (test RMSE 1.358 °C ≤ 2.068 °C and ≤ 2.5 °C), so the instruction is recorded as the Go. Known gaps accepted with the Go: no station comparison; intervals cover 87% instead of 90%. The owner may revoke this after reviewing the Model Card. | 2026-11-10 (Phase 7) |
| D16 | Named localities | The owner supplied the official NMC intention map (scan dated 2025-06-16). It has no zone layer, so the 10 approximate zones stay for the risk ranking (T18), and its ~50 revenue villages are added as a second, readable layer: **55 named localities** traced automatically from the map's index panel and fitted to the OSM city boundary (IoU 0.87; the difference is mainly the Hudkeshwar–Narsala extension, which OSM lacks and is now included). Positional accuracy ~100 m. "Nagpur and Sitabuldi" and "Takali Sim and Jaitala" could not be separated; seven small localities were grown from seed points. | 2026-11-11 (Phase 9) |
| D17 | API reads the bundle, not PostGIS | The API answers from the published bundle held in memory (rasters, GeoJSON, tables) instead of querying PostGIS: no database round-trip, no spatial index to maintain, the database is optional for reads, and the data and the API can never disagree about which product is current. The database tables (Phase 9) remain as the audit and future-query store. Revisit if the dataset outgrows memory (it is ~36 MB of arrays today). | 2026-11-13 (Phase 11) |
| D18 | Frontend work on `main`; Dependabot removed | 2026-11-13: `development` was fast-forwarded into `main` on the owner's instruction (D13) and both branches now point at the same commit; frontend work continues on `main`. Dependabot was removed because its automatic pull-request branches (6 appeared within minutes, mostly major-version bumps) break the two-branch policy; vulnerabilities are still caught by `pip-audit` in CI and upgrades are done by hand. | 2026-11-13 |

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
| T17 | Runtime & dependencies | Python **3.13** (changed from 3.11 on 2026-11-10: the first CI run failed because pinned `rasterio==1.5.2` has no Python 3.11 build; all local verification had been on 3.13); exact version pins in the single root `requirements.txt`. |
| T18 | Administrative units | 10 NMC zones for v1; wards when boundaries are openly released. |
| — | Free supporting services | Product storage: Hugging Face Dataset repo / GitHub Releases. CI & scans: GitHub Actions, `pip-audit`. Monitoring: UptimeRobot, Sentry free tier (optional). Backups: nightly `pg_dump` via GitHub Actions. Load test: Locust / k6 locally. |

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
  - [x] Decision D7 met (125 Landsat 8/9 scenes, at least 12 in each season; corrected from 173, which included Landsat 7 — see note below).
- **Evidence:** `pytest -v ml/tests/ingest/test_ingest.py` 5/5 passed (15/15 passed repository-wide); CLI idempotency test run twice downloaded 0 new bytes on second run (scene `LC09_L2SP_144045_20251218_02_T1` skipped); injected network timeout recovered via exponential backoff; 100% of manifest records re-verified; Decision D7 verified with 173 scenes (Summer=63, Monsoon=13, Post-Monsoon=40, Winter=57) — later corrected to 125 Landsat 8/9 scenes (Summer=40, Monsoon=12, Post-Monsoon=29, Winter=44); see the correction note below.

##### Seasonal Scene Inventory Audit (Decision D7 Compliance)

| Year | Summer (Mar–May) | Monsoon (Jun–Sep) | Post-Monsoon (Oct–Nov) | Winter (Dec–Feb) | Annual Total |
|:---|:---:|:---:|:---:|:---:|:---:|
| **2019** | 5 | 0 | 2 | 5 | 12 |
| **2020** | 5 | 0 | 2 | 5 | 12 |
| **2021** | 5 | 1 | 3 | 4 | 13 |
| **2022** | 5 | 4 | 5 | 7 | 21 |
| **2023** | 7 | 3 | 6 | 7 | 23 |
| **2024** | 7 | 1 | 5 | 8 | 21 |
| **2025** | 6 | 3 | 6 | 8 | 23 |
| **Total (2019–2025)** | **40** | **12** | **29** | **44** | **125** |
| **Decision D7 Bar** | **≥ 8** | **≥ 8** | **≥ 8** | **≥ 8** | **≥ 40** |
| **Status** | **PASS** | **PASS** | **PASS** | **PASS** | **PASS** |

> **Correction (2026-11-09, Phase 5):** the original audit reported 173 scenes because the STAC search did not filter by satellite and counted 48 Landsat 7 scenes (SLC-off striping, different band names — out of scope). The table above is the Landsat 8/9-only audit after adding `platforms: [landsat-8, landsat-9]` to `ml/configs/ingest.yaml`. D7 is still met.
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

#### Phase 4 — Backend Foundation Hardening `[x]`
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
- [x] CI: ruff (incl. bandit `S` hardcoded-secret rules) + mypy on `backend/`, `pip-audit`, and a second job running backend tests + migrations against a PostGIS service
- **Measurable Exit Criteria:**
  - [x] Clean clone → `docker compose up` → `alembic upgrade head` → `pytest` green. *(Verified locally 2026-11-09 on Docker `postgis/postgis:16-3.4`.)*
  - [x] CI green with ruff + mypy + pip-audit + tests: run 42814984846 on commit `fbc1b8e` (2026-11-10), both jobs passed (SQLite job and PostgreSQL + PostGIS job). The first run (42810508353) failed at dependency install because `rasterio==1.5.2` has no Python 3.11 build; CI moved to Python 3.13 (T17).
  - [x] Secret scan finds 0 hardcoded keys or connection strings (ruff `S` rules clean on `backend/`).
- **Evidence (2026-11-09, local, Python 3.13):** `pytest` 44 passed (25 existing + 19 new); `ruff check backend` all checks passed; `mypy backend` no issues in 19 files; `pip-audit -r requirements.txt` no known vulnerabilities; `alembic upgrade head --sql` renders valid PostgreSQL DDL incl. `CREATE EXTENSION postgis`; Rule A check: no folder exceeds 2 `.py` files.
- **Evidence (2026-11-09, local Docker PostgreSQL 16.4 + PostGIS 3.4.3):** `docker compose up -d db` healthy; `alembic upgrade head` → `0001 (head)`, `checked_at` is `timestamp with time zone`; downgrade → upgrade round-trip clean; `alembic check` → "No new upgrade operations detected"; backend tests against Postgres 21/21 passed on two consecutive runs; live `uvicorn` smoke test: `/api/v1/health` 200 with heartbeat persisted, 404/422 return the error envelope, disallowed-origin CORS preflight refused (400), request IDs present on route and controller log lines.
- **Bugs found and fixed during Docker verification:** (1) `localhost` on Windows resolves to IPv6 first and psycopg stalled with no timeout → `.env.example` uses `127.0.0.1`, and both the app engine and Alembic now set a 10 s `connect_timeout`; (2) Alembic autogenerate would have tried to drop PostGIS-owned tables (`spatial_ref_sys`, plus tiger/topology tables the Docker image installs) → `migration_name_filter` in `base_class.py` excludes extension-owned tables, looked up from `pg_depend` lazily so it never holds an open transaction.
- **Known follow-ups:** `GET /health` writes a heartbeat row per call (table growth under uptime monitoring — revisit in Phase 11/12); `starlette.testclient` warns that `httpx` support is deprecated; ruff/mypy cover `backend/` only — `ml/` is linted from Phase 5.

---

### Milestone 5: First Working Result & Baselines

#### Phase 5 — First Working Result, EDA & Baseline Models `[x]`
**Concrete assets:** `ml/src/dataset/{build.py, splits.py}`, `ml/src/eda/{maps.py, stats.py}`, `ml/src/models/baseline/{baselines.py, metrics.py}`, `ml/configs/splits.yaml` (frozen), Phase 5 settings in `ml/configs/thresholds.yaml`; cropped multi-scene ingestion in `ml/src/ingest/`; tests in `ml/tests/{dataset,eda,models}/`. Artifacts (git-ignored, hashed in the manifest): `ml/data/interim/scenes/*.npz` (122 scene cubes), `ml/data/processed/{training_v2.parquet, scene_index.parquet}`, `ml/data/processed/maps/lst_<season>_2019_2025.{tif,png}` + `hotspots_<season>.geojson`, `ml/data/processed/baselines/baseline_scores.json`, `ml/data/processed/eda/spearman_by_season.json`.
- [x] Multi-scene ingestion: study-area windows read straight from remote COGs (~6.5 MB/scene instead of ~450 MB), collection-level SAS token (fixes HTTP 429), per-scene failure isolation, Landsat 8/9-only filter. 125/125 scenes ingested, 0 failures.
- [x] Dataset build: terrain computed once; per-scene full-grid cubes; 20,000 trainable pixels sampled per scene with stable seeds; 150 m / 450 m neighbourhood index means; frozen split columns. 122/125 scenes usable (3 excluded at < 30% trainable); 2,440,000 rows.
- [x] Refactor verified bit-for-bit: rebuilding `LC09_L2SP_144045_20251218_02_T1` reproduces `features_v1.parquet` exactly.
- [x] **First Working Result:** seasonal mean LST GeoTIFFs + PNG maps for all four seasons with metadata tags (scene list, date range, CRS, masking, resolution caveat).
- [x] Hotspot analysis: Getis-Ord Gi* (300 m distance band) with Benjamini-Hochberg FDR control (q < 0.05), exported as GeoJSON per season.
- [x] Spearman correlations by season (table below).
- [x] Baselines 1–3 on validation folds only (5-fold spatial-block CV, holdout blocks and 2026 untouched). Baseline 2 redefined per D11.
- [x] Metrics module: RMSE, MAE, bias, R², Spearman, overall and per season.
- **Measurable Exit Criteria:**
  - [x] Reproducible map artifacts exist for at least two contrasting seasons (all four produced).
  - [x] Baseline 1–3 scores locked in `progress.md` as the bar to beat (table below).
  - [x] D5 re-confirmed after seeing fold sizes: folds hold 376,804–421,219 rows and 28–29 blocks each, fold mean LST 37.8–38.8 °C; holdout = 36 blocks / 493,105 rows. No change to D5.
- **Evidence (2026-11-09):** ingestion log 125 found / 0 failed; dataset summary 125 indexed / 122 used / 2,440,000 rows; ML test suites `ml/tests/{dataset,eda,models}` green; ruff + mypy clean on the new modules.

##### Locked Baseline Scores (5-fold spatial-block CV, 1,946,895 validation predictions, 122 scenes)

| Baseline | Overall RMSE (°C) | MAE | Bias | R² | Summer RMSE | Monsoon RMSE | Post-monsoon RMSE | Winter RMSE |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| B1 — season city mean | 5.534 | 4.303 | −0.002 | 0.622 | 6.842 | 8.154 | 3.777 | 4.274 |
| B2 — scene city mean (D11) | 2.807 | 2.148 | −0.002 | 0.903 | 3.472 | 3.792 | 2.268 | 2.081 |
| **B3 — OLS + IDW residuals** | **2.351** | **1.726** | **−0.053** | **0.932** | **2.121** | **2.494** | **2.406** | **2.480** |

**Bar to beat (Phase 6):** Model 1 overall CV RMSE ≤ 0.85 × 2.351 = **1.998 °C**.

##### Seasonal Maps & Hotspots (2019–2025, Landsat 8/9 ~10:00 local solar time)

| Season | Scenes | City-wide mean LST | P5–P95 | Inside NMC vs. outside | Gi* hot / cold area (FDR q<0.05) |
|:---|:---:|:---:|:---:|:---:|:---:|
| Summer (Mar–May) | 40 | 46.26 °C | 41.65–50.69 | **−2.53 °C** (city cooler) | 48.6% / 43.4% |
| Monsoon (Jun–Sep) | 10 | 48.23 °C | 43.30–52.58 | −2.22 °C | 46.9% / 44.3% |
| Post-monsoon (Oct–Nov) | 29 | 34.75 °C | 31.26–37.82 | +0.23 °C | 47.5% / 40.0% |
| Winter (Dec–Feb) | 43 | 31.07 °C | 28.18–34.33 | −1.23 °C | 42.8% / 45.1% |

**Findings and caveats:**
- **Daytime surface urban cool island:** in summer the built-up NMC area is 2.5 °C *cooler* than the dry, bare agricultural periphery at the Landsat overpass. This is surface temperature at ~10:00, not air temperature or night-time conditions, and must not be read as "the city is not hot".
- **Monsoon selection bias:** only 10 clear-sky scenes exist and they cluster in early June (pre-onset) and late September, so the monsoon composite is hotter than summer. It does not represent wet-monsoon conditions.
- **Gi* covers large areas:** at 30 m, neighbouring cells are strongly autocorrelated; even with FDR control, ~90% of the grid is significantly hotter or cooler than the city-wide mean. The layer separates relatively hot from relatively cool zones; it does not isolate rare anomalies.
- Lakes (Ambazari, Futala, Gorewada) are the coolest features; open water is excluded from training via the QA water flag.

##### Spearman ρ between LST and drivers (training folds, ≤ 200,000 rows per season)

| Driver | Summer | Monsoon | Post-monsoon | Winter |
|:---|:---:|:---:|:---:|:---:|
| NDVI | −0.377 | −0.504 | −0.214 | −0.307 |
| NDBI | +0.405 | +0.719 | +0.232 | +0.419 |
| MNDWI | −0.076 | −0.216 | +0.111 | −0.170 |
| Elevation | +0.052 | −0.001 | −0.028 | +0.036 |

p-values are < 1e-10 everywhere but are optimistic because pixels are spatially autocorrelated.

---

### Milestone 6: Scientific Validation & Model Development

#### Phase 6 — Model 1 Development (Single ML Model First) `[x]`
**Concrete assets:** `ml/src/models/core/train.py`, `ml/src/models/core/evaluate.py`, `ml/src/models/explain/shap_analysis.py`, `ml/src/models/explain/intervals.py`; `ml/configs/model.yaml`; model registry `ml/models/registry/<version>/` (LightGBM native format + SHA-256, git-ignored, published per Phase 9); `ml/data/processed/experiments/*.json`.
- [x] Spatial-block CV (D5) with a unit test proving no `block_id` appears in both train and validation within any fold (zero leakage)
- [x] Model 1: LightGBM first, Random Forest as a comparison, small tuning budget (e.g., 30 trials), seeds fixed, CPU only
- [x] SHAP global and per-season importance plots
- [x] 90% prediction intervals via quantile regression (5th/95th percentile models); report empirical coverage and mean width
- [x] Each run logs parameters, metrics, data version, git commit into a local JSON file (T14)
- [x] Secondary models (air-temp transfer, forecast offsets) deferred until Model 1 passes
- **Measurable Exit Criteria:**
  - [x] Model 1 reduces RMSE by ≥ 15% versus Baseline 3 on held-out spatial blocks.
  - [x] 90% intervals cover ≥ 85% of held-out points.
  - [x] Leakage test is green and part of the test suite.
- **Evidence (2026-11-09):** run `m1-20261109T150313Z` (commit `260c6c4`, training table SHA-256 `99822146c014298e…`, 1,946,895 CV rows, 122 scenes), log `ml/data/processed/experiments/m1-20261109T150313Z.json`; leakage tests `ml/tests/models/test_model1.py` green (block disjointness asserted in every fold; anchors use training rows only).

##### Model 1 Cross-Validation Results (5-fold spatial blocks, RMSE °C)

| Season | Baseline 3 | Random Forest | Model 1 (LightGBM) | **Model 1 + residual kriging (chosen)** |
|:---|:---:|:---:|:---:|:---:|
| **Overall** | 2.351 | 1.578 | 1.404 | **1.227** |
| Summer | 2.121 | 1.884 | 1.646 | 1.422 |
| Monsoon | 2.494 | 2.318 | 2.132 | 1.670 |
| Post-monsoon | 2.406 | 1.244 | 1.158 | 1.080 |
| Winter | 2.480 | 1.212 | 1.055 | 0.979 |

- **Gate:** RMSE improvement vs. Baseline 3 = **47.8%** (needed ≥ 15%); MAE 0.877 °C, bias −0.005 °C, R² 0.981.
- **90% intervals:** empirical coverage **87.4%** overall (summer 88.4%, monsoon 88.5%, post-monsoon 86.7%, winter 86.8%), mean width 3.55 °C. Meets the ≥ 85% criterion but is ~2.6 points below nominal 90% — to be re-checked on the test set and calibrated if it persists.
- **Tuned parameters (30-trial random search, 3-fold block CV on 400k rows):** num_leaves 255, learning_rate 0.05, min_child_samples 100, feature_fraction 0.8, lambda_l2 5.0.
- **Top SHAP drivers (mean |SHAP|, °C):** sin_doy 0.86, scene_anchor_lst 0.79, ndbi_150m 0.71, ndvi_150m 0.66, ndvi_450m 0.53, mndwi_450m 0.50 — neighbourhood built-up/vegetation context matters more than the pixel's own index.
- **Caveat:** CV scores reuse the folds that guided tuning (slightly optimistic); the unbiased number comes from the one-time Phase 7 test.
- Model files (`point.txt`, `lower.txt`, `upper.txt`, `metadata.json`) are in the git-ignored registry `ml/models/registry/m1-20261109T150313Z/` with hashes in the manifest.

#### Phase 7 — Ground-Truth Validation & Model Cards `[x]`
**Concrete assets:** `ml/src/validation/final_test.py`, `ml/tests/validation/test_final_test.py`; Model Card and final evaluation in `README.md`; artifacts (git-ignored) `ml/data/processed/final_test/{final_test_report.json, final_test_predictions.parquet, test_set_opened.json}`.
- [x] Test set opened **once** on 2026-11-10 (lock file `test_set_opened.json` blocks any re-run); no re-tuning afterwards. Model `m1-20261109T150313Z` unchanged since Phase 6.
- [!] Station comparison **not performed**: IMD station records need a formal data request and CPCB CAAQMS data sits behind a captcha-protected portal, so neither could be retrieved automatically. Validation is LST-only (risk-register mitigation). Can be added later without touching the model.
- [x] Error breakdown by season, NDVI tercile, and land cover (land cover is an NDVI/NDBI proxy — no land-cover map is ingested).
- [x] Block bootstrap 95% confidence intervals (1,000 resamples of the 36 holdout blocks) on RMSE, MAE, bias.
- [x] Model Card in `README.md`.
- [x] Go / No-Go: see D15.
- **Measurable Exit Criteria:**
  - [x] Test-set RMSE ≤ 0.85 × Baseline 3 RMSE and ≤ 2.5 °C: **1.358 °C** vs. limit 0.85 × 2.433 = 2.068 °C.
  - [x] Model Card published in `README.md`.
  - [x] Written Go decision from the owner (D15).
- **Evidence (2026-11-10):** `final_test_report.json`; rehearsal of the scoring code on training rows only before opening; `ml/tests/validation` green.

##### Final Test Results (holdout blocks only; scene context from non-holdout pixels of the same scene)

| Test group | Rows / scenes | Model 1 RMSE [95% CI] | Baseline 3 RMSE [95% CI] | Ratio | MAE | Bias | R² | 90% interval coverage (mean width) |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **2026 scenes × holdout blocks** (new time and new place — primary) | 112,973 / 28 | **1.358** [1.275, 1.440] | 2.433 [2.285, 2.588] | 0.558 | 0.999 | +0.052 | 0.975 | 87.1% (4.26 °C) |
| 2019–2025 scenes × holdout blocks (new place only) | 493,105 / 122 | 1.212 [1.146, 1.280] | 2.494 [2.361, 2.628] | 0.486 | 0.871 | +0.013 | 0.982 | 88.6% (3.67 °C) |

| 2026 breakdown (RMSE °C) | | | | |
|:---|:---:|:---:|:---:|:---:|
| Season | Summer 1.424 | Monsoon 1.681 | Post-monsoon 1.204 | Winter 1.064 |
| Land-cover proxy | Built-up 1.415 | Bare/mixed 1.390 | Vegetation 1.231 | |
| NDVI tercile | Low 1.536 | Mid 1.289 | High 1.230 | |

**Reading the result:** the 2026 score (1.358) is close to the Phase 6 CV estimate (1.227), so CV was only mildly optimistic. Errors are largest in monsoon scenes and on sparsely vegetated / built surfaces. The 90% intervals cover ~87%, i.e. they are slightly too narrow; widen or calibrate before presenting them as exact 90% ranges. **Scope limit:** the test measures filling in unseen *places* within a scene whose other pixels are observed; it does not measure forecasting a day with no satellite scene.

---

### Milestone 7: Evidence-Based Layers & Data Products

#### Phase 8 — Heat Exposure, Vulnerability & Cooling Assets `[x]`
**Concrete assets:** `ml/src/exposure/{index.py, vulnerability.py}`, `ml/tests/exposure/test_exposure.py`, Phase 8 settings in `ml/configs/thresholds.yaml`. Artifacts (git-ignored, hashed in the manifest): `ml/data/processed/exposure/{exposure_index_<season>.tif, exposure_zone.parquet, cooling_assets.geojson, phase8_summary.json}`, cropped WorldPop windows in `ml/data/raw/population/`, raw Overpass response in `ml/data/raw/osm/`.
- [x] Heat Exposure Index (0–100): percentile rank of each pixel's seasonal mean **observed** Landsat LST (2019–2025) among land pixels inside the NMC boundary, per season. Built from observed LST only.
- [x] Zone-level vulnerability for the 10 NMC zones: population density and share aged 60+ (WorldPop 2020, 1 km, CC BY 4.0), green-space deficit (1 − mean NDVI percentile). Aggregated only.
- [x] Cooling assets from OpenStreetMap (Overpass, data timestamp 2026-11-10): 889 places — 582 health facilities, 194 parks/gardens, 55 water bodies, 53 shelters/community centres, 5 drinking-water points — with source and extraction date in the file.
- [x] Zone risk score (50% exposure, 50% vulnerability) and rank with 95% rank intervals from 1,000 scene-level bootstrap resamples per season.
- [x] Exposure levels exposed as codes (`low`, `moderate`, `high`, `very_high`, `extreme`) for localisation (T16).
- **Measurable Exit Criteria:**
  - [x] A schema test confirms zero individual-level fields in any output file (`assert_no_individual_fields` runs on every build; unit-tested).
  - [x] Zone ranking method documented with rank intervals for every zone (table below).
- **Evidence (2026-11-10):** `python -m ml.src.exposure.vulnerability` completed; `ml/tests/exposure` 9/9 passed; full suite 85 passed; ruff + mypy clean.

##### Zone Risk Ranking — Summer (40 scenes, 2019–2025)

| Risk rank [95% interval] | Zone | Risk score | Exposure index [95% CI] | Mean LST (°C) | Vulnerability | Density (people/km²) | Mean NDVI |
|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 [1–2] | Gandhibagh | 60.0 | 37.5 [33.4, 41.7] | 43.64 | 82.6 | 20,778 | 0.253 |
| 2 [1–4] | Satranjipura | 57.9 | 36.3 [28.5, 42.0] | 43.59 | 79.4 | 20,534 | 0.265 |
| 3 [2–4] | Nehru Nagar | 56.0 | 39.7 [32.3, 46.8] | 43.82 | 72.3 | 16,923 | 0.267 |
| 4 [2–4] | Hanuman Nagar | 53.9 | 37.7 [31.9, 44.7] | 43.75 | 70.0 | 19,448 | 0.295 |
| 5 [5–6] | Lakadganj | 48.8 | 55.4 [51.4, 58.7] | 44.76 | 42.2 | 6,613 | 0.300 |
| 6 [5–7] | Laxmi Nagar | 47.9 | 64.7 [62.2, 67.6] | 46.15 | 31.1 | 10,297 | 0.381 |
| 7 [6–7] | Ashi Nagar | 45.9 | 60.9 [55.2, 64.3] | 45.08 | 30.9 | 4,719 | 0.328 |
| 8 [8–9] | Dhantoli | 40.7 | 28.9 [26.0, 32.8] | 43.05 | 52.6 | 21,134 | 0.386 |
| 9 [8–9] | Dharampeth | 39.4 | 57.0 [54.6, 59.5] | 44.81 | 21.8 | 7,228 | 0.399 |
| 10 [10–10] | Mangalwari | 37.2 | 37.5 [34.0, 41.2] | 43.39 | 36.8 | 12,645 | 0.381 |

Risk ranks are stable across seasons (each zone moves by at most two places). Zone exposure levels in summer are only `moderate` or `high` because zone means average out the extremes; pixel-level rasters span the full 0–100 range.

**Method:** vulnerability = equal-weight mean of min–max scaled population density, 60+ share, and green deficit (0–100 across the 10 zones). Risk = 0.5 × exposure index + 0.5 × vulnerability. Rank intervals resample which clear-sky scenes were observed; vulnerability inputs are treated as fixed. Weights are a design choice set in `thresholds.yaml`, not an empirically validated health model.

**Limits (read before using the ranking):**
- **Zone polygons are approximate.** `nagpur_zones.geojson` was generated in Phase 1 by partitioning the NMC boundary (several zones have only 5–7 vertices); it is not a surveyed official zone map. Zone statistics will shift when authoritative boundaries are available.
- **The 60+ share does not differentiate zones.** WorldPop's 1 km age structure applies one district-level proportion everywhere, so every zone gets 10.96%. The component is kept for when better data exists but currently contributes nothing; vulnerability is in effect density plus green deficit.
- **Exposure and vulnerability pull in opposite directions.** The dense old-city zones (Gandhibagh, Satranjipura) rank highest on risk because of density and low greenery, yet their daytime surface is cooler than the outer zones with bare ground (Laxmi Nagar, Ashi Nagar). Exposure is ~10:00 surface temperature, not night-time or air-temperature heat stress.
- Population is a 2020 modelled 1 km grid (2.44 M people inside the zones), coarse relative to zones of 9–39 km².
- OSM completeness is uneven; counts are places mapped by volunteers, and "shelter"/"community centre" are not designated heat shelters.

---

#### Phase 9 — Versioned Data Products & Publishing `[x]`
**Concrete assets:** `ml/src/publish/{products.py, tiles.py}`, `ml/src/sync/storage.py`, `ml/tests/publish/test_publish.py`, `ml/tests/sync/test_storage.py`, `backend/core/models/product_model.py`, Alembic `0002`, `ml/data/raw/boundary/nagpur_localities.geojson`; bundles under git-ignored `ml/data/published/<version>/`.
- [x] One bundle per scene: COGs for the latest-scene Model 1 LST estimate with 5th/95th percentile bounds and an observed/filled mask, plus seasonal mean LST and exposure index (EPSG:32644). Cloudy cells are estimated with long-term mean spectral indices; open water is left empty.
- [x] Pre-rendered PNG XYZ tiles, zoom 10–16, for 9 layers (latest LST, 4 seasonal LST, 4 seasonal exposure): 18,806 tiles.
- [x] Vector layers (EPSG:4326): zones, **55 named localities** (D16), cooling assets, Gi* hotspots; zone and locality metric tables.
- [x] Database tables via Alembic `0002`: `products`, `zones`, `zone_metrics`, `localities`, `locality_metrics`, `cooling_assets`, `pipeline_runs`; loader replaces reference tables and upserts the product in one transaction. Geometries are stored as GeoJSON text; PostGIS geometry columns and spatial indexes are deferred to Phase 11, when the API needs them.
- [x] `products` row with version, scene, model version, timestamp, manifest SHA-256; `latest.json` switched atomically (`os.replace`), bundle built in a staging folder first.
- [x] Bundles and pipeline state uploaded to a free Hugging Face dataset repo (`ayushji23/heatsafe-products`: `latest.json`, `bundles/<version>.tar`, `state/pipeline_state.tar`; keeps the newest 2 bundles). `python -m ml.src.sync.storage restore-bundle` downloads and hash-verifies the latest bundle; the API serves the local copy, which the deployment container restores at start (Phase 12).
- **Measurable Exit Criteria:**
  - [x] Publishing the same product twice is idempotent (second run: "already published and intact; nothing rewritten"; database load tested twice with identical row counts).
  - [x] 100% of published files listed in the bundle manifest with re-verifiable hashes (18,827 files, 278.7 MB).
  - [x] Tiles cover the full study-area extent at every published zoom (per zoom for one layer: {'10': 2, '11': 4, '12': 15, '13': 48, '14': 156, '15': 552, '16': 2153}).
- **Evidence (2026-11-11):** bundle `2026-11-03_LC09_L2SP_144045_20261103_02_T1_m1-20261109T150313Z` (scene 2026-11-03, age 10 days, stale=false); observed fraction 82.6%, remainder model-filled; bundle loaded into local PostgreSQL 16 + PostGIS on 2026-11-13 (10 zones, 40 zone metrics, 55 localities, 275 locality metrics, 889 cooling assets, 1 latest product; also tested on SQLite); `ml/tests/publish` green.
- **Storage evidence (2026-11-13):** uploaded 90.7 MB state + 316.9 MB bundle; a fresh-runner round trip into an empty folder restored the model, terrain, scene index, maps and exposure layers, and the bundle verified against its manifest (18,806 tiles). A test caught that the PNG-skip filter meant for the state archive would also have dropped every map tile from bundles; fixed so only the state archive skips previews.

---

### Milestone 8: Live Pipeline, Public API & Deployment

#### Phase 10 — Automated Inference Pipeline (Historical to Live) `[~]`
**Concrete assets:** `ml/src/pipeline/{run_batch.py, fallback.py}`, `ml/tests/pipeline/test_pipeline.py`, `.github/workflows/pipeline.yml`, table `pipeline_runs`.
- [x] Batch job `run_once`: detect new scenes → ingest (cropped) → preprocess → predict → publish (Phase 9) → load database → upload to free storage → record the run in `pipeline_runs` (an upload failure leaves the product online and fails the run with status `published_upload_failed`).
- [x] Historical 2019–2026 backfill done on the dev laptop (153 scenes).
- [x] Freshness fields per D2 on every product and pointer (`scene_age_days`, `stale` when older than 16 days).
- [x] Fallback: on network failure, corrupt input, no new pass, or an unusable (cloudy) scene the last good product stays published, gets its age refreshed, and records the cause in `last_run_issue`.
- [x] Retry with backoff for catalogue and download calls (ingestion client); file run lock with a 6-hour abandoned-lock timeout.
- [x] Failure-injection tests: network outage, corrupt raster, no new pass, database down — all green.
- [~] Scheduled live runs: `pipeline.yml` (daily 13:00 IST + manual) now restores state and the last bundle from the Hugging Face repo, runs the pipeline, and the run uploads the new bundle and refreshed state. The storage token is configured as a repository secret. **To start the schedule, set the repository variable `HEATSAFE_PIPELINE_ENABLED` to `true`** (a manual "Run workflow" works without it).
- **Measurable Exit Criteria:**
  - [ ] 14 consecutive daily scheduled runs with 0 unhandled exceptions (D10) — cannot start until the schedule is enabled.
  - [x] Every injected failure results in a fallback plus a stale-data warning flag (all 4 tests green).
- **Evidence (2026-11-11):** `ml/tests/pipeline` 9/9 passed; full suite 102 passed; backend tests 21/21 on Docker PostgreSQL; CI green on 31e0f13 (both jobs, run 42969167032).
- **Not yet exercised:** a real end-to-end `run_once` against the live catalogue (the newest available scene is already published, so a live run would report `no_new_scene`).

#### Phase 11 — Public API v1 `[x]`
**Concrete assets:** routes `backend/core/apis/routes/{product/product.py, product/areas.py, tiles/tiles.py}`; controller `backend/core/controllers/product_controller.py`; services `backend/core/services/product/{store.py, lookup.py}`; schemas `backend/core/apis/schemas/{requests,responses}/product/`; tests `backend/tests/api/{test_product_api.py, bundle_factory.py, openapi_v1.json}`.
- [x] Endpoints under `/api/v1` (all read-only, output in EPSG:4326): `GET /metadata`, `/heat?lat&lon`, `/zones`, `/zones/{id}`, `/zones/geojson`, `/localities`, `/localities/geojson`, `/cooling-spots?lat&lon&category&limit&radius_km`, `/hotspots`, `/tiles/{layer}/{z}/{x}/{y}.png`, `/forecast` (clean `501`), `/health`.
- [x] `GET /heat` returns LST (°C) with a 90% range, whether the cell was observed or model-filled, locality and zone, seasonal exposure with level codes, `scene_age_days`, `stale` (computed per request), model version; air temperature and heat index are not returned.
- [x] Point lookups are array reads from the bundle held in memory (about 12 layers, ~36 MB); zones and localities are pre-rasterised so a point maps to its area in O(1). The API never runs the model (T10). See D17.
- [x] Uniform error envelope with stable codes (`outside_study_area`, `no_product_available`, `not_implemented`, `rate_limited`, `validation_error`, `not_found`); coordinates outside Nagpur → 422; no loaded product → 503.
- [x] In-process per-client rate limiting (300/min default, tiles exempt, 429 + `Retry-After`) and `Cache-Control` headers; request-ID and security-header middleware rewritten as plain ASGI.
- [x] OpenAPI contract frozen by a snapshot test (`openapi_v1.json`); this is the contract the frontend builds against. Swagger UI at `/docs`.
- [ ] Postman collection: not created. `/openapi.json` imports into Postman directly.
- **Measurable Exit Criteria:**
  - [x] p95 latency ≤ 200 ms at 50 concurrent requests: measured 2026-11-13 on the real bundle, single uvicorn worker on the dev laptop (the load generator shared the same CPU): metadata 94 ms, zones 100 ms, tiles 115 ms, localities 119 ms, heat 147 ms, cooling-spots 189 ms (1,000 requests each, 0 errors, 340–750 req/s). The first run (before the middleware rewrite) had heat at 236 ms.
  - [x] Branch coverage ≥ 85% across the backend: **94%** (routes 71–84% because their unexpected-error branches are only reachable by fault injection; controllers 99%, services 96–100%).
  - [x] Every endpoint returns the documented error envelope on invalid input (tests cover validation, out-of-area, unknown zone/season/category/layer, missing tile, no product, rate limit).
  - [x] OpenAPI snapshot test green.
- **Evidence (2026-11-13):** `backend/tests/api` 17 tests; backend suite 38 passed on Docker PostgreSQL; full suite 128 passed; ruff + mypy clean; load-test numbers above.
- **Limits:** the load test measures a warm instance (cold start after free-tier sleep is documented in Phase 12); the rate limiter is per process and trusts the first `X-Forwarded-For` entry, which is spoofable — adequate for a public read-only demo, not for abuse prevention.

---

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
