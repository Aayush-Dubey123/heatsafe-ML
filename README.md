# HeatSafe-ML 🌡️

### Geospatial Machine Learning for Urban Heat Intelligence in Nagpur, India

HeatSafe-ML is a research and development project exploring how geospatial data, satellite observations, and machine learning can help us understand urban heat exposure across Nagpur, Maharashtra.

The long-term goal is to turn environmental data into clear, evidence-based insights that can support residents, researchers, urban planners, and local communities in identifying heat-exposed areas and evaluating potential mitigation strategies.

> **Project status:** Initial planning and data-source investigation. No model performance or citywide prediction capability is claimed at this stage.

## 🎯 The Problem

Heat exposure can vary significantly within a city. Vegetation, built-up density, surface materials, shade, and access to cooling resources all influence local conditions.

A single citywide temperature reading cannot explain these spatial differences. HeatSafe-ML will investigate where elevated land-surface temperatures occur, how they relate to the urban environment, and where additional evidence may help prioritize heat-mitigation efforts.

## 🧭 Our Approach

1. **Verify the study area** — identify an authoritative Nagpur city boundary and document the geographic coverage used in analysis.
2. **Audit data sources** — evaluate suitable satellite imagery, land-surface temperature products, vegetation and land-cover datasets, weather observations, and appropriately aggregated vulnerability indicators. Record access conditions, licensing, resolution, dates, and limitations.
3. **Prepare geospatial data** — clean and align datasets, check coordinate systems, handle missing values, and document every processing step.
4. **Explore urban heat patterns** — analyze the spatial distribution of land-surface temperature and investigate relationships with vegetation, built-up areas, and land cover.
5. **Build and evaluate baselines** — begin with descriptive and statistical analyses; use machine-learning models only when the available data and validation design support them.
6. **Investigate vulnerability and interventions** — where reliable, privacy-safe data exists, explore how heat exposure intersects with population vulnerability and access to cooling resources.
7. **Communicate findings** — produce reproducible maps, visualizations, and documented limitations to help people interpret the results responsibly.

## 🗺️ Initial Geographic Scope

**Nagpur, Maharashtra, India**

The intended scope is citywide. The exact boundary and spatial resolution will be documented after data-source verification. Analysis will not imply street-level accuracy when the source data only supports coarser spatial conclusions.

## 🧰 Planned Technology Stack

- **Language:** Python
- **Data analysis:** Pandas, NumPy
- **Geospatial processing:** GeoPandas, Rasterio, Shapely
- **Machine learning:** Scikit-learn; other libraries only where justified
- **Visualization:** Matplotlib, Plotly, Folium or a suitable mapping library
- **Development and reproducibility:** Jupyter Notebook, Git, GitHub

The final stack may change based on the datasets, their formats, and the reproducibility requirements.

## 📊 Expected Outputs

- Data-source inventory and data-quality report
- Maps of available land-surface temperature observations
- Vegetation, land-cover, and built-up-area analysis
- Spatial comparisons of heat exposure
- Reproducible geospatial processing workflows
- Evaluated analytical or machine-learning baselines, if the data supports them
- Potential heat-mitigation priority maps with explicit uncertainty and limitations

These are planned outputs, not completed capabilities.

## 🔬 Reference Project

[UHI-Geospatial-ML](https://github.com/sp-ankitprajapati/UHI-Geospatial-ML)

This project is an initial reference for exploring geospatial and machine-learning approaches to urban heat-island analysis. Before reusing code, datasets, or methodology, we will review the repository's license, dependencies, data provenance, and suitability for Nagpur.

## ⚠️ Scientific Integrity and Limitations

- **Land-surface temperature is not the same as air temperature.** Satellite-derived surface temperature does not directly measure the temperature experienced by a person.
- **Exposure is not the same as vulnerability.** Health and social vulnerability require additional reliable evidence and careful interpretation.
- **Spatial resolution matters.** Coarse satellite pixels cannot support precise claims about individual streets or buildings.
- **Validation comes first.** We will document data splits, baselines, uncertainty, and evaluation metrics before making predictive claims.
- **Privacy matters.** Any population-related indicators should be aggregated appropriately and handled in a way that avoids exposing individuals.
- **Public-safety claims require evidence.** HeatSafe-ML is not an official warning system and will not replace public health guidance or government advisories.

## ⚖️ Project Governance & Standalone Coordination

HeatSafe-ML coordinates development, scientific integrity, and roadmap delivery across three standalone foundational documents:

- **Project Rules & Regulations ([README.md](file:///c:/Users/aayus/heatsafe-ML/README.md)):** The authoritative definition of project scope, domain approach, scientific integrity constraints, and public-safety regulations.
- **IDE Development Commands & Agent Operating System ([agent.md](file:///c:/Users/aayus/heatsafe-ML/agent.md)):** Governs IDE commands, developer workflows, 4-layer backend architecture, folder limits, and coding standards ([code-standards/](file:///c:/Users/aayus/heatsafe-ML/code-standards)).
- **Phasewise Execution Tracker ([progress.md](file:///c:/Users/aayus/heatsafe-ML/progress.md)):** Tracks delivery across Phases 0–12, maintaining strictly gated exit criteria from Foundation to Monitoring & Release.

### Inviolable Structural Rules
Throughout development, 3 structural rules are strictly protected and cannot be overturned by agent commands:
1. **Strict 2-File-Per-Folder Limit:** Every parent folder may contain at most 2 child executable code files (`.py`, `.jsx`, `.tsx`).
2. **Single Root `.gitignore` & `requirements.txt`:** Exactly 1 root [`.gitignore`](file:///c:/Users/aayus/heatsafe-ML/.gitignore) and 1 root [`requirements.txt`](file:///c:/Users/aayus/heatsafe-ML/requirements.txt) across the entire codebase.
3. **No Additional Markdown Files:** Absolute freeze on generating new `.md` files; all project documentation, data logs, and decisions reside exclusively within the standalone triad (`README.md`, `agent.md`, `progress.md`).

## 🚀 Roadmap

> For live phase status, checklists, and exit criteria, see [progress.md](file:///c:/Users/aayus/heatsafe-ML/progress.md).
- [ ] Verify the Nagpur study boundary and available geospatial datasets
- [ ] Audit source quality, licensing, dates, and spatial resolution
- [ ] Create a reproducible data-ingestion and preprocessing workflow
- [ ] Generate initial exploratory maps and analysis
- [ ] Establish and evaluate analytical baselines
- [ ] Investigate appropriate vulnerability indicators
- [ ] Document findings, uncertainty, and potential interventions
- [ ] Consider a public-facing dashboard after the underlying analysis is validated

## 🌱 Long-Term Vision

Build a transparent and reproducible foundation for understanding urban heat in Nagpur, helping turn geospatial evidence into practical questions and potential actions for a more heat-resilient city.

---

**Built for research, civic impact, and responsible geospatial machine learning.**
