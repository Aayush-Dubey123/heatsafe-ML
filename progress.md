# HeatSafe-ML — Two-Branch Progress Tracker

Legend: `[ ]` not started · `[~]` in progress · `[x]` done · `[!]` blocked

## Ground rules
1. **Branch 1 (Backend & ML)** is built completely first. No frontend work of any kind during Branch 1.
2. **Branch 2 (Frontend)** is **LOCKED**. It opens only when BOTH are true:
   - the Backend Acceptance Gate (end of Branch 1) is fully ticked, AND
   - the project owner explicitly says "move to frontend".
3. A phase closes only when every exit criterion is ticked. No skipping ahead.
4. Extra feature branches (alerts, mobile app, other cities, etc.) start only after BOTH branches are complete.

**Current branch:** 1 — Backend & ML
**Current phase:** Phase 0
**Frontend status:** 🔒 LOCKED
**Last updated:** 2026-10-23

---
# BRANCH 1 — BACKEND & ML  (Phases 0–10)
Goal: a validated, automated, documented API that returns accurate heat results for any point in Nagpur, usable without any UI (Swagger docs, curl/Postman, Python client).
---

## Phase 0 — Foundation & Setup  `[ ]`
- [ ] GitHub repo, branching rules (main / dev / feature), issue board
- [ ] Folder structure: `data/raw|interim|processed`, `notebooks/`, `src/`, `configs/`, `tests/`, `docs/`
- [ ] Python env (conda/uv) + pinned `requirements.txt`
- [ ] Git LFS / DVC for data versioning
- [ ] MLflow (or W&B) experiment tracking
- [ ] Google Earth Engine account (non-commercial) authenticated
- [ ] Data sources logged, decisions tracked, and limitations documented (in README.md / progress.md — no new .md files)
- **Exit:** fresh clone → one command builds env → sample notebook runs

## Phase 1 — Study Area & Data Audit  `[ ]`
- [ ] Authoritative Nagpur boundary (NMC limit + ward polygons) saved as GeoJSON, CRS documented
- [ ] Master CRS fixed (EPSG:32644) for analysis; EPSG:4326 for API output
- [ ] Data-source inventory: source, resolution, dates, license, access, limitations
- [ ] Ground-truth sources identified (IMD station, AWS, CPCB, other)
- [ ] Review UHI-Geospatial-ML repo: license, provenance, reusability
- [ ] Define target variables (LST, air temp, heat index) and output grid (e.g. 30 m)
- **Exit:** signed-off data inventory + target definition doc

## Phase 2 — Data Ingestion Pipeline  `[ ]`
- [ ] Landsat 8/9 Collection 2 L2 LST + cloud mask (2015–present)
- [ ] MODIS LST (daily, 1 km)
- [ ] ECOSTRESS LST (where available)
- [ ] Sentinel-2 indices (NDVI, NDBI, NDWI, MNDWI, albedo)
- [ ] Land cover: ESA WorldCover / Dynamic World
- [ ] Terrain: Copernicus DEM (elevation, slope, aspect)
- [ ] OSM: roads, buildings, parks, water, hospitals
- [ ] Building footprints (Open Buildings / Microsoft)
- [ ] Weather: ERA5-Land hourly, IMD gridded, station observations
- [ ] Population: WorldPop grid + Census ward data (aggregated only)
- [ ] All pulls scripted, idempotent, logged
- **Exit:** `make ingest` reproduces all raw data; provenance logged

## Phase 3 — Preprocessing & Feature Engineering  `[ ]`
- [ ] Reproject / resample everything to master grid
- [ ] Quality filters (cloud %, QA bands, outliers)
- [ ] Seasonal composites + per-scene dataset
- [ ] Spatial features: built-up fraction, building density, distance to water/green/road, buffers (100/300/500 m)
- [ ] Temporal features: day-of-year, hour, lagged weather
- [ ] Final training table (Parquet) + data dictionary
- [ ] Data-quality report (coverage, missingness, per-year counts)
- **Exit:** versioned dataset v1 + passing data-validation tests (pandera / Great Expectations)

## Phase 4 — Exploratory Analysis & Baselines  `[ ]`
- [ ] LST maps by season and year
- [ ] Correlations: LST vs NDVI / NDBI / land cover / building density
- [ ] Hotspot analysis (Getis-Ord Gi*, ward-level stats)
- [ ] Trivial baselines: mean, persistence, linear regression
- [ ] Metrics defined: RMSE, MAE, bias, R², Spearman rank
- **Exit:** EDA report + baseline scores locked as the bar to beat

## Phase 5 — Model Development  `[ ]`
- [ ] Spatial validation scheme (block / leave-ward-out CV) — no random splits
- [ ] Model A: LST downscaling (coarse → 30 m) with Random Forest / LightGBM
- [ ] Model B: air-temperature / heat-index estimation using station ground truth
- [ ] Model C: short-term forecast (24–72 h) = weather forecast + spatial offsets
- [ ] Hyperparameter tuning, feature selection, SHAP analysis
- [ ] Uncertainty estimates (quantile regression / conformal prediction)
- [ ] Model registry with versions
- **Exit:** models beat baselines on held-out spatial + temporal test sets

## Phase 6 — Validation & Ground Truth  `[ ]`
- [ ] Independent hold-out: unseen year + unseen wards
- [ ] Comparison against IMD / AWS observations
- [ ] Error breakdown by season, land cover, time of day
- [ ] (Optional) field validation with low-cost sensors
- [ ] Model card: intended use, metrics, failure modes
- **Exit:** published accuracy numbers with confidence intervals; go / no-go decision

## Phase 7 — Exposure & Vulnerability Layer  `[ ]`
- [ ] Heat Exposure Index (0–100) from validated outputs
- [ ] Vulnerability indicators (aggregated: density, age structure, green access)
- [ ] Cooling-resources dataset (parks, water bodies, hospitals, shelters)
- [ ] Ward-level risk ranking with uncertainty
- **Exit:** reviewed, privacy-safe layers with documented methodology

## Phase 8 — Live Inference Pipeline  `[ ]`
- [ ] Scheduled fetch (forecast + latest satellite)
- [ ] Inference job → gridded heat output + heat index
- [ ] Storage: PostGIS + Cloud-Optimized GeoTIFF
- [ ] Failure handling, fallbacks, stale-data flags
- **Exit:** pipeline runs unattended for 7 days with no manual fixes

## Phase 9 — Backend API  `[ ]`
- [ ] `GET /heat?lat&lon` (current heat, feels-like, uncertainty range)
- [ ] `GET /forecast?lat&lon`
- [ ] `GET /ward/{id}` and `GET /wards` (exposure + vulnerability)
- [ ] `GET /cooling-spots?lat&lon&radius`
- [ ] `GET /tiles/{z}/{x}/{y}` (map tiles, ready for any future client)
- [ ] `GET /health` and `GET /metadata` (data freshness, model version)
- [ ] Input validation, caching, rate limiting, error schema
- [ ] OpenAPI / Swagger docs + example requests
- [ ] Python client + Postman collection for testing without a UI
- **Exit:** every endpoint returns correct, documented responses

## Phase 10 — Backend Hardening, Deployment & Monitoring  `[ ]`
- [ ] Unit, integration, data-validation and model-regression tests
- [ ] CI/CD (GitHub Actions), Docker images
- [ ] Deploy API, DB and scheduler; secrets management, backups
- [ ] Security review (auth for admin routes, dependency scan)
- [ ] Data-drift and model-drift monitoring, alerts
- [ ] Retraining schedule defined
- [ ] Docs: README, methodology, data dictionary, API guide, model card
- **Exit:** staging → production with rollback plan; docs complete

---
## 🚦 BACKEND ACCEPTANCE GATE
All must be ticked before Branch 2 can even be proposed:
- [ ] Phase 0–10 all closed
- [ ] Validated accuracy published and accepted by owner
- [ ] API p95 latency target met; test suite green
- [ ] Live pipeline stable for 14+ days unattended
- [ ] Backend usable end-to-end via Swagger / Postman / Python client alone
- [ ] Known limitations documented in [README.md](file:///c:/Users/aayus/heatsafe-ML/README.md)
- [ ] **Owner has explicitly said: "move to frontend"**   ← required, not implied
---

# BRANCH 2 — FRONTEND  (Phases F1–F4)   🔒 LOCKED
Do not start, scaffold or design anything here until the gate above is fully ticked.

## Phase F1 — UX & Design Spec  `[ ]`
- [ ] User flows, wireframes, copy (incl. heat-safety disclaimers)
- [ ] Design system, accessibility targets, language support decision
- **Exit:** approved design spec

## Phase F2 — Core App  `[ ]`
- [ ] Next.js app wired to the backend API
- [ ] Map view (MapLibre/Leaflet) with heat layer and ward layer
- [ ] "Check my location" + search by area/ward
- **Exit:** map and location check work against production API

## Phase F3 — User Features  `[ ]`
- [ ] Heat level, feels-like, uncertainty range, data-freshness label
- [ ] Nearest cooling spots, forecast view
- [ ] Error / offline / stale-data states
- [ ] "Not an official warning system" disclaimer shown clearly
- **Exit:** all backend features surfaced correctly

## Phase F4 — Testing, Deploy & v1.0 Release  `[ ]`
- [ ] Usability testing with real users, mobile responsiveness, accessibility audit
- [ ] E2E tests, CI/CD, deploy
- [ ] Public v1.0 release + changelog
- **Exit:** foundation complete → extra feature branches may begin

---

## Change Log
| Date | Phase | Note |
|------|-------|------|
| 2026-10-23 | — | Tracker created |
| 2026-10-23 | — | Restructured into Backend (Branch 1) and Frontend (Branch 2, locked) |