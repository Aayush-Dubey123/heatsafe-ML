# HeatSafe-ML — Two-Branch Progress Tracker

Legend: `[ ]` not started · `[~]` in progress · `[x]` done · `[!]` blocked

## Ground Rules & Two-Branch Governance
1. **Branch 1 (Backend & ML)** is built completely first. No frontend work of any kind during Branch 1.
2. **Branch 2 (Frontend)** is **LOCKED**. It opens only when BOTH conditions are met:
   - The Backend Acceptance Gate (end of Branch 1) is fully ticked, AND
   - The project owner explicitly issues the command: *"move to frontend"*.
3. **Strict Gate Closure:** A phase closes only when **every measurable exit criterion** is ticked and its evidence is logged in the phase's *Evidence* line. No skipping ahead.
4. **Three Inviolable Structural Rules:**
   - Strict 2-file-per-folder limit for executable code (`.py`, `.jsx`, `.tsx`). Never create `.gitkeep` files or placeholder directories. Tests follow the same rule.
   - Strictly 1 root [`.gitignore`](.gitignore) and 1 root [`requirements.txt`](requirements.txt).
   - Absolute freeze on new markdown files; all documentation stays in [README.md](README.md), [agent.md](agent.md), and [progress.md](progress.md).
5. **Defaults marked "(default)"** are proposed values. They are confirmed or changed once, in Phase 1 or Phase 4, and the final value is written into the Decision Log. After that they do not move without a logged decision.

**Current branch:** 1 — Backend & ML  
**Current phase:** Phase 1 (Study Area Verification & Data Feasibility Audit) — Phase 0 Closed  
**Frontend status:** 🔒 LOCKED  
**Last updated:** 2026-10-25  

---

## Decision Log (settle before or during the named phase)

| ID | Decision | Resolution / Default | Locked in |
|:---|:---|:---|:---|
| D1 | What does Model 1 predict? | 30 m land-surface temperature (LST, °C) on the master grid, from static spatial features (NDVI, NDBI, MNDWI, elevation, slope, aspect) plus season/date features. Air temperature and heat index are NOT predicted by Model 1. | Phase 1 |
| D2 | How is "freshness" defined? | Two separate ages are reported: `scene_age_days` (age of latest valid Landsat scene) and `weather_age_hours` (age of weather input, once weather exists). Flag `stale` when `scene_age_days > 16` (two missed combined L8/L9 revisits) or `weather_age_hours > 24`. The tracker's old "≤ 24 h source staleness" applies to weather only, not Landsat. | Phase 1 |
| D3 | Same-day "now" heat | Branch 1 serves the latest valid scene product plus modelled spatial pattern, with its age shown. True same-day estimates need weather covariates (ERA5-Land / IMD) and belong to post-gate Models 2 and 3. | Phase 1 |
| D4 | Training / validation / test windows | Train + tune: 2019-01-01 → 2025-12-31. Held-out **test year: 2026** (scenes to date). The test set is opened **once**, in Phase 6. | Phase 1 |
| D5 | Spatial split design | 2 km × 2 km spatial blocks → `GroupKFold` (5 folds) on block ID, plus leave-ward-out CV. Final test also holds out a fixed 20% of blocks. | Phase 3 |
| D6 | Resolution claim | 30 m is the analytical grid. Landsat thermal is natively ~100 m resampled to 30 m, so published accuracy is stated per cell on the 30 m grid, never as "street-level accuracy". | Phase 1 |
| D7 | Minimum scene bar | At least 40 usable scenes in the training window, with at least 8 in each season (summer Mar–May, monsoon Jun–Sep, post-monsoon Oct–Nov, winter Dec–Feb) (default). If missed, widen the window or loosen cloud cover before modelling. | Phase 2 |

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

# BRANCH 1 — BACKEND & ML (Phases 0–10)
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

#### Phase 1 — Study Area Verification & Data Feasibility Audit `[ ]`
**Concrete assets:** `data/raw/boundary/nagpur_nmc.geojson` and `wards.geojson`; `configs/study_area.yaml` (CRS, grid origin, extent, window); feasibility matrix and station inventory tables inside `progress.md`; target specification table inside `README.md`.
- [ ] Authoritative Nagpur boundary (NMC limit + ward/zone boundaries) saved as GeoJSON; topology check and invalid-geometry repair logged
- [ ] Master CRS fixed: EPSG:32644 for analysis; EPSG:4326 for API output
- [ ] Master 30 m grid defined: origin snapped to multiples of 30 m, extent = boundary bounds + 1 km buffer, stored in `configs/study_area.yaml`
- [ ] Landsat tile identified (expected WRS-2 path 144 / row 45; verify) and overpass time (~10:00 local solar time) documented as a limitation: daytime, clear-sky only
- [ ] Data-source feasibility matrix: Landsat 8/9 C2 L2, Sentinel-2 L2A, MODIS, Copernicus DEM GLO-30 (licence, date coverage, resolution, revisit, GEE collection ID)
- [ ] Station inventory: IMD, AWS, CPCB stations inside or within 10 km of Nagpur (ID, lat/lon, variables, record length, access terms)
- [ ] Reference repo (UHI-Geospatial-ML) audited: licence, data provenance, reusable parts vs. parts to avoid
- [ ] Target variables defined separately: LST (°C), station air temperature (°C), heat index (°C), each with its own metrics, data source, and evaluation set
- [ ] Decisions D1–D4 and D6 locked
- **Measurable Exit Criteria:**
  - [ ] Boundary GeoJSON valid (0 invalid geometries) and verified in EPSG:32644.
  - [ ] Feasibility inventory signed off with zero unlicensed dependencies.
  - [ ] Target spec lists independent metrics for each of the three variables.
- **Evidence:** matrix and inventory tables committed; D1–D4, D6 marked locked.

---

### Milestone 3: Incremental Ingestion & Preprocessing

#### Phase 2 — Incremental Ingestion Pipeline (Historical Landsat First) `[ ]`
**Concrete assets:** `src/ingest/__main__.py` (CLI), `src/ingest/sources.py` (source definitions); `configs/ingest.yaml`; raw GeoTIFFs under `data/raw/{landsat,sentinel2,dem}/`; manifest entries for every file.
- [ ] Landsat 8 (`LANDSAT/LC08/C02/T1_L2`) and Landsat 9 (`LANDSAT/LC09/C02/T1_L2`) ingestion for the Nagpur extent: bands `ST_B10`, `QA_PIXEL`, `QA_RADSAT`, `SR_B3`, `SR_B4`, `SR_B5`, `SR_B6`; scene-level filter `CLOUD_COVER < 20` (default)
- [ ] Sentinel-2 SR (`COPERNICUS/S2_SR_HARMONIZED`) bands B3, B4, B8, B11 within ±5 days of each Landsat scene, cloud-masked via SCL
- [ ] Copernicus DEM (`COPERNICUS/DEM/GLO30`) elevation, with slope and aspect derived in Phase 3
- [ ] Idempotency: file name derived from scene ID; scenes already in the manifest are skipped; partial downloads are deleted and retried
- [ ] Exponential retry (e.g., 1 s, 2 s, 4 s … up to 5 attempts) with logged failures
- [ ] Manifest records scene ID, acquisition timestamp, `CLOUD_COVER`, SHA256, size
- [ ] Scene-count audit by season against D7
- [ ] Secondary sources (MODIS, ECOSTRESS, ERA5-Land, WorldPop) explicitly deferred; listed as "not started" until Phase 3 exit
- **Measurable Exit Criteria:**
  - [ ] `python -m src.ingest --source landsat` run twice downloads 0 new bytes on the second run.
  - [ ] Injected network failure recovers within retry limits and logs the failure.
  - [ ] 100% of manifest hashes re-verify.
  - [ ] D7 met (≥ 40 scenes, ≥ 8 per season) or the window/filter change is logged.
- **Evidence:** scene-count table by season and year; manifest size.

#### Phase 3 — Preprocessing, QA Masking & Feature Engineering `[ ]`
**Concrete assets:** `src/preprocess/align.py`, `src/preprocess/features.py`, `src/validate/schema.py`; `data/interim/` aligned rasters; `data/processed/features_v1.parquet`; data dictionary in `progress.md`.
- [ ] Reproject and resample all rasters to the master 30 m grid (bilinear for continuous bands, nearest for masks)
- [ ] Apply scale factors: LST (K) = `ST_B10 × 0.00341802 + 149.0`, then convert to °C; surface reflectance = `SR × 0.0000275 − 0.2`
- [ ] QA masking using `QA_PIXEL` bits: fill, dilated cloud, cirrus, cloud, cloud shadow, snow, water (water excluded from training)
- [ ] Features: NDVI = (B8−B4)/(B8+B4); NDBI = (B11−B8)/(B11+B8); MNDWI = (B3−B11)/(B3+B11); elevation, slope, aspect
- [ ] Temporal features: day of year (sin/cos encoded), season label, acquisition hour, solar zenith
- [ ] IDs for every row: `pixel_id`, `ward_id`, `block_id` (2 km grid), `scene_id`, `date`
- [ ] Parquet training table `features_v1.parquet` and data dictionary (column, unit, source, range)
- [ ] `pandera` schema: dtype and range checks (LST plausible 0–62 °C, indices in −1…1), per-column missingness limits
- [ ] D5 split IDs generated and frozen (`split.parquet` or a column in the table)
- **Measurable Exit Criteria:**
  - [ ] 100% of rows align to the master grid (0 coordinate drift, checked by a round-trip test).
  - [ ] 0% unmasked cloud contamination in the validation sample; missing pixel rate < 2% after masking per kept scene.
  - [ ] `features_v1.parquet` passes the schema and is logged in the manifest.
- **Evidence:** schema test output; row count per scene and per season.

---

### Milestone 4: First Working Result & Baselines

#### Phase 4 — First Working Result, EDA & Baseline Models `[ ]`
**Concrete assets:** `src/eda/maps.py`, `src/eda/stats.py`, `src/models/baseline/baselines.py`, `src/models/baseline/metrics.py`; `data/processed/maps/lst_{summer,postmonsoon}_YYYY.tif` + PNG previews; locked baseline score table.
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

---

### Milestone 5: Scientific Validation & Model Development

#### Phase 5 — Model Development (Single ML Model First) `[ ]`
**Concrete assets:** `src/models/core/train.py`, `src/models/core/evaluate.py`, `src/models/explain/shap_analysis.py`, `src/models/explain/intervals.py`; `configs/model.yaml`; `data/processed/models/model1_v1.*`; `data/processed/experiments/*.json`.
- [ ] Spatial-block CV (D5) with a unit test proving no `block_id` appears in both train and validation within any fold (zero leakage)
- [ ] Model 1: LightGBM first, Random Forest as a comparison, small tuning budget (e.g., 30 trials), seeds fixed
- [ ] SHAP global and per-season importance plots
- [ ] 90% prediction intervals via quantile regression (5th/95th percentile models); report empirical coverage and mean width
- [ ] Each run logs parameters, metrics, data version, git commit into a local JSON file
- [ ] Secondary models (air-temp transfer, forecast offsets) deferred until Model 1 passes
- **Measurable Exit Criteria:**
  - [ ] Model 1 reduces RMSE by ≥ 15% versus Baseline 3 on held-out spatial blocks.
  - [ ] 90% intervals cover ≥ 85% of held-out points.
  - [ ] Leakage test is green and part of the test suite.
- **Evidence:** CV table (per fold, per season); experiment log file names.

#### Phase 6 — Ground-Truth Validation & Model Cards `[ ]`
**Concrete assets:** final evaluation report section in `README.md`; test-set metrics with 95% CIs; Model Card for LST in `README.md`; station comparison table.
- [ ] Open the test set once: 2026 scenes and the fixed 20% held-out blocks; no re-tuning afterwards
- [ ] Station comparison: LST at the station pixel vs. station air temperature, reported as a correlation/offset with an explicit caveat that these are different variables
- [ ] Error breakdown by land-cover class, NDVI tiers (e.g., terciles), and season
- [ ] Bootstrap 95% confidence intervals (≥ 1000 resamples by block) on RMSE, MAE, bias
- [ ] Model Card in `README.md`: scope, data, resolution statement (D6), failure modes (cloud-free days only, daytime only), confidence bounds
- [ ] Go / No-Go review by the project owner. A No-Go sends work back to Phase 3 or 5 with a logged reason.
- **Measurable Exit Criteria:**
  - [ ] Test-set RMSE ≤ 0.85 × Baseline 3 RMSE, and an absolute RMSE target of ≤ 2.5 °C (default; confirm after Phase 4 baselines).
  - [ ] Model Card published in `README.md`.
  - [ ] Written Go decision from the owner.
- **Evidence:** metrics table with CIs; Go/No-Go entry in the change log.

---

### Milestone 6: Evidence-Based Layers

#### Phase 7 — Heat Exposure & Vulnerability Layer `[ ]`
**Concrete assets:** `src/exposure/index.py`, `src/exposure/vulnerability.py`; `data/processed/exposure/{exposure_ward.parquet, cooling_assets.geojson}`.
- [ ] Heat Exposure Index (0–100) as a documented transform of validated LST (e.g., percentile rank within Nagpur per season), never from unvalidated outputs
- [ ] Ward-level vulnerability from census/open data: population density, share aged 60+, green-space deficit (1 − mean NDVI percentile); aggregated at ward level only
- [ ] Cooling assets: parks, water bodies, hospitals, designated shelters, with source and date
- [ ] Ward risk score and rank, with uncertainty intervals from bootstrapping the underlying LST error
- **Measurable Exit Criteria:**
  - [ ] A schema test confirms zero individual-level fields in any output file.
  - [ ] Ward ranking method documented with rank intervals for every ward.
- **Evidence:** ranking table with intervals; schema test output.

---

### Milestone 7: Production Backend & Hardening

#### Phase 8 — Resilient Inference Pipeline (Historical to Live) `[ ]`
**Concrete assets:** `src/pipeline/run_batch.py`, `src/pipeline/fallback.py`, `src/storage/cog.py`, `src/storage/postgis.py`; COGs in `data/processed/cog/`; PostGIS tables `heat_products`, `ward_metrics`, `cooling_assets`, `pipeline_runs`; failure-injection tests.
- [ ] Batch job: detect new scene, then ingest, preprocess, predict, write COG and database rows, and record the run in `pipeline_runs`
- [ ] Freshness fields per D2 stored with each product (`scene_age_days`, `stale` flag)
- [ ] Fallback logic: on corrupt input, empty pass, or upstream timeout, serve the last good product flagged `stale` and log the cause
- [ ] Retry with backoff for upstream calls; run lock to prevent overlapping runs
- [ ] Failure-injection tests: network outage, corrupt raster, no new pass, database down
- [ ] Scheduler (cron/Task Scheduler) added only after run durations are measured over the historical replay
- **Measurable Exit Criteria:**
  - [ ] Pipeline runs unattended for 7 consecutive days with 0 unhandled exceptions.
  - [ ] Every injected failure results in a fallback plus a stale-data warning flag (all 4 tests green).
- **Evidence:** 7-day run log; failure-injection test report.

#### Phase 9 — Production Backend API `[ ]`
**Concrete assets:** `backend/main.py`, `backend/deps.py`, `backend/core/{routers,controllers,services,repositories}/<domain>/`; OpenAPI at `/docs`; `postman_collection.json` under `tests/`.
- [ ] FastAPI app in four layers. Build order: `/health`, `/metadata`, `/heat`, `/wards` and `/ward/{id}`, `/cooling-spots`, `/tiles/{z}/{x}/{y}`, `/forecast` (clean `501` until a forecast model is validated)
- [ ] `GET /heat?lat&lon` returns LST (°C), 90% interval, `scene_age_days`, `stale` flag, model version; air temperature and heat index are NOT returned until their models exist
- [ ] Pydantic v2 request/response schemas; one uniform error schema; out-of-boundary coordinates return a documented `422`/`404`
- [ ] Rate limiting and response caching
- [ ] Google-style docstrings on all functions and methods; central logging in `backend/commons/logger.py`
- [ ] Swagger docs, curl examples, and a Postman collection
- [ ] Load test: 50 concurrent requests per endpoint, p95 measured and logged
- **Measurable Exit Criteria:**
  - [ ] p95 latency ≤ 200 ms at 50 concurrent requests.
  - [ ] Branch coverage ≥ 85% across routers, controllers, and services.
  - [ ] 100% of endpoints return the documented error schema on invalid input.
- **Evidence:** load-test output; coverage report summary.

#### Phase 10 — Backend Hardening, Monitoring & Deployment `[ ]`
**Concrete assets:** `.github/workflows/ci.yml`, `Dockerfile`, `.env.example`; drift report outputs; the backup/rollback plan inside `README.md`.
- [ ] CI pipeline: lint (ruff), type check (mypy), unit + integration tests, coverage gate at 85%
- [ ] Docker image: pinned base image, non-root user, no secrets baked in
- [ ] Secrets only via `.env`; a CI check fails on hardcoded keys or connection strings
- [ ] Data drift (feature distribution shift vs. training) and model drift (error vs. new observed scenes) monitoring with alert thresholds in `configs/thresholds.yaml`
- [ ] Disaster recovery: database backup schedule, restore test, and rollback of model version
- **Measurable Exit Criteria:**
  - [ ] Staging runs 14+ consecutive days unattended.
  - [ ] CI 100% green on all PRs.
  - [ ] Dependency scan reports 0 high/critical vulnerabilities.
  - [ ] Restore from backup tested once successfully.
- **Evidence:** staging uptime log; scan report; restore-test note.

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
- [ ] Phases 0–10 all closed with every exit criterion ticked and evidence logged.
- [ ] Validated ML accuracy beats simple baselines by ≥ 15% on independent spatial hold-outs.
- [ ] API p95 latency ≤ 200 ms verified under benchmark load.
- [ ] Test coverage ≥ 85% verified green across the backend test suite.
- [ ] Live inference pipeline tested against missing data, job failures, and stale results (14 days unattended on staging).
- [ ] Backend fully verified end-to-end via Swagger / Postman / Python client alone, including a rehearsal from a clean clone.
- [ ] Essential scientific distinction documented: separate targets, metrics, and model cards for LST vs. air temperature vs. heat index.
- [ ] Known limitations documented in [README.md](README.md).
- [ ] **Owner has explicitly commanded: "move to frontend"** ← strictly required, never implied.

---

## Risk Register

| Risk | Impact | Early check | Mitigation |
|:---|:---|:---|:---|
| Too few cloud-free scenes (monsoon) | Weak seasonal coverage | D7 audit in Phase 2 | Widen window, relax cloud filter, report seasonal gaps |
| Station data unavailable or low quality | Phase 6 validation limited | Station inventory in Phase 1 | Use LST-only validation, state the limit in the Model Card |
| Spatial autocorrelation inflates accuracy | False confidence | Leakage test in Phase 5 | Block CV, test set opened once |
| Landsat 100 m thermal resampled to 30 m | Overclaimed precision | D6 | State resolution limits in docs and API metadata |
| 2-file rule leads to awkward module splits | Slower development | Folder design in Phase 0 | Split by responsibility; revisit layout only via a logged decision |
| Heat index needs humidity and wind | Heat index not available in Branch 1 | Target spec in Phase 1 | Post-gate Models 2/3 with ERA5-Land/IMD data |

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
- [ ] Production build optimization, CI/CD deployment, and v1.0 release tag
- **Exit:** Public release with published release notes; transition to maintenance.

---
