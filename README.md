# Road-Accident Hotspot Analysis — Stavanger, Norway

**Bachelor Project 2026–2027 | Applied Data Science**

**Working research title:** *Identifying and Profiling Road-Accident Hotspots Using Geospatial Analysis and Predictive Modelling: A Case Study of Stavanger, Norway*

## Overview

This repository contains data-collection and exploratory-analysis code supporting a study of road accidents in Stavanger, Norway. The current scripts retrieve official road-accident and traffic-volume data, clean and integrate those datasets, and generate descriptive visualisations. These outputs provide a foundation for subsequent geographic hotspot detection and simple predictive risk profiling; the scripts documented here do **not**, by themselves, constitute a validated hotspot detection or predictive modelling system.

The project uses data from **Statens vegvesen** through the National Road Database (NVDB), Trafikkdata, and manually exported Trine tables. Data availability, access permissions, reporting coverage, and the limitations of individual sources must be considered when interpreting the results.

## Repository structure

```text
project-root/
├── README.md
├── accident_data_collection.py
├── accident_insights.ipynb
├── traffic_volume_analysis.py
├── traffic_volume_analysis.ipynb
├── data/
│   ├── raw/
│   │   ├── nvdb/                    # Cached NVDB downloads
│   │   ├── traffic/                 # Cached hourly traffic data
│   │   └── trafficAccidents/        # Manually exported Trine CSV files
│   └── processed/                   # Cleaned and integrated CSV tables
└── figures/
    ├── accidents/                   # Figures from accident_insights.ipynb
    └── traffic/                     # Figures from traffic analysis
```

> The `data/` and `figures/` directories are generated or populated during execution. The figure images themselves were **not included** among the files supplied for this README; the Markdown references below use the exact filenames found in the plotting code and will render once the generated PNG files are placed in the corresponding folders.

## Scripts and notebooks

### 1. `traffic_volume_analysis.py` — traffic data collection and analysis

Connects to the [Trafikkdata GraphQL API](https://trafikkdata-api.atlas.vegvesen.no/) to retrieve counting stations and hourly traffic volumes for Stavanger (municipality **1103**, Rogaland **11**). It caches downloads, removes hourly observations with insufficient coverage (below 50% by d

efault), creates daily aggregates, and produces eight traffic figures.

**Key outputs:** `data/processed/traffic_stations.csv`, `traffic_hourly_clean.csv`, and `traffic_daily.csv`. Cached source files are stored under `data/raw/traffic/`. Figures are saved under `figures/traffic/`.

**Example:**

```bash
python traffic_volume_analysis.py --start 2023-01-01 --end 2025-12-31
```

The `--end` date is **exclusive**. Other options include `--municipality`, `--max-points` (limit stations for testing), and `--refresh` (ignore cached downloads). Run `python traffic_volume_analysis.py --help` for details. The default date range is approximately the preceding year, not the entire proposed study period.

### 2. `traffic_volume_analysis.ipynb` — interactive traffic exploration

Provides a notebook-based workflow for examining traffic station coverage, hourly and daily traffic patterns, weekday and monthly variations, heavy-vehicle shares, and geographic station locations. It contains configurable study dates and produces the same eight named traffic figure outputs as the Python script. **Running both may overwrite figures with the same filenames.**

The notebook is suitable for exploratory checks, interpretation, and selecting figures for the research report. Its settings are defined inside notebook cells and should be reviewed before execution.

### 3. `accident_data_collection.py` — accident data acquisition and integration

Downloads record-level road-accident information from the [NVDB API](https://nvdbapiles.atlas.vegvesen.no/vegobjekter/api/v4/vegobjekter), including accident objects (type **570**), involved units (**571**), involved persons (**572**), and traffic-volume road segments (**540**). It processes optional manually exported Trine severity tables and associates accidents with nearby traffic counting stations where matching information is available.

**Key outputs in `data/processed/`:**

| File | Contents |
|---|---|
| `accidents_stavanger.csv` | Cleaned accident records and derived features |
| `accident_units_stavanger.csv` | Units involved in recorded accidents |
| `accident_persons_stavanger.csv` | Persons involved in recorded accidents |
| `aadt_segments_stavanger.csv` | Road-segment annual average daily traffic information |
| `accidents_enriched.csv` | Accident records enriched with unit and nearby traffic-station information |
| `trine_severity_long.csv` | Long-format Trine severity data, when exports are available |

**Examples:**

```bash
python accident_data_collection.py
python accident_data_collection.py --refresh
python accident_data_collection.py --trine-only
```

The `--trine-only` option processes available Trine CSV exports without downloading NVDB records. Trine source files belong in `data/raw/trafficAccidents/`.

**Important limitation:** Some individual-level severity fields are restricted or unavailable through anonymous NVDB access. Trine provides aggregated severity information and should not be treated as a substitute for record-level severity labels. An optional `NVDB_TOKEN` environment variable is supported for authorised access; never commit tokens to version control.

### 4. `accident_insights.ipynb` — accident exploratory data analysis

Reads the prepared accident, Trine, and traffic tables to examine temporal trends, casualties, accident types, road and location characteristics, environmental conditions, vulnerable road users, accident density, and descriptive relationships with traffic volume. It saves 14 figures under `figures/accidents/`.

This notebook supports descriptive interpretation and feature selection. Its density visualisation should **not** automatically be described as a statistically validated accident hotspot analysis; any later hotspot claims require an explicit method, parameters, and evaluation.

## Setup and execution

Python 3.10+ is recommended as a practical starting point. Install dependencies in a virtual environment:

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS / Linux:
# source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install numpy pandas requests matplotlib seaborn jupyter ipykernel
```

Run the components from the **project root** in the following order:

```bash
# 1. Retrieve traffic counts and create traffic figures.
python traffic_volume_analysis.py --start 2023-01-01 --end 2025-12-31

# 2. Retrieve accidents, process Trine exports if present,
#    and link accidents with the available traffic-station data.
python accident_data_collection.py

# 3. Open the exploratory notebooks.
jupyter notebook traffic_volume_analysis.ipynb
jupyter notebook accident_insights.ipynb
```

The traffic notebook can be run independently of the traffic script, but its internal dates and settings should be aligned with the intended analysis. The accident notebook expects the relevant processed CSV files to exist. Running it before data collection or without required Trine/traffic inputs can cause missing-file errors.

## Generated figures

The following images are referenced by their **actual output names** in the scripts/notebooks. After running the code in a repository with the indicated `figures/` directories, GitHub will display them inline.

### Traffic-volume visualisations

| Figure | Purpose |
|---|---|
| 01 — Station average daily traffic | Compares traffic volume across counting stations |
| 02 — Hourly profile | Shows variation across hours of the day |
| 03 — Weekday–hour heatmap | Highlights recurring weekly traffic patterns |
| 04 — Daily trend | Tracks daily traffic over the study period |
| 05 — Monthly pattern | Compares seasonal/monthly variation |
| 06 — Weekday distribution | Compares traffic volumes by day of week |
| 07 — Heavy-vehicle share | Compares the proportion of longer/heavy vehicles |
| 08 — Station map | Displays counting-station locations |

![Average daily traffic by station](figures/traffic/01_station_adt.png)
![Hourly traffic profile](figures/traffic/02_hourly_profile.png)
![Weekday and hour traffic heatmap](figures/traffic/03_weekday_hour_heatmap.png)
![Daily traffic trend](figures/traffic/04_daily_trend.png)
![Monthly traffic pattern](figures/traffic/05_monthly_pattern.png)
![Traffic by weekday](figures/traffic/06_weekday_distribution.png)
![Heavy vehicle share](figures/traffic/07_heavy_vehicle_share.png)
![Traffic counting station map](figures/traffic/08_station_map.png)

### Accident visualisations

| Figure | Purpose |
|---|---|
| 00 — Data completeness | Reviews available and missing fields |
| 01 — Annual trend | Shows changes in recorded accident counts by year |
| 02 — Casualties by severity | Describes casualties using available aggregated severity data |
| 03 — Weekday–hour heatmap | Shows when recorded accidents occur |
| 04 — Monthly pattern | Compares accident counts across months |
| 05 — Accident type and codes | Profiles recorded accident types and classifications |
| 06 — Location type | Compares accidents across location categories |
| 07 — Accident density map | Displays geographic concentration of recorded accidents |
| 08 — Top roads | Highlights roads with more recorded accidents |
| 09 — Conditions | Profiles recorded road or environmental conditions |
| 10 — Speed limit and vulnerable road users | Explores speed-limit patterns involving vulnerable users |
| 11 — Vulnerable road-user trend | Examines changes involving vulnerable road users |
| 12 — Accidents versus traffic volume | Explores a descriptive association between accidents and traffic |
| 13 — Severity profile | Summarises available severity information |

![Accident data completeness](figures/accidents/00_data_completeness.png)
![Annual accident trend](figures/accidents/01_annual_trend.png)
![Casualties by severity](figures/accidents/02_casualties_by_severity.png)
![Accidents by weekday and hour](figures/accidents/03_weekday_hour_heatmap.png)
![Monthly accident pattern](figures/accidents/04_monthly_pattern.png)
![Accident types and codes](figures/accidents/05_accident_type_and_codes.png)
![Accident location types](figures/accidents/06_location_type.png)
![Accident density map](figures/accidents/07_accident_density_map.png)
![Roads with more recorded accidents](figures/accidents/08_top_roads.png)
![Accident conditions](figures/accidents/09_conditions.png)
![Speed limit and vulnerable road users](figures/accidents/10_speed_limit_vru.png)
![Vulnerable road-user trend](figures/accidents/11_vru_trend.png)
![Accidents versus traffic volume](figures/accidents/12_accidents_vs_volume.png)
![Accident severity profile](figures/accidents/13_severity_profile.png)

## Methodological cautions

- **Counts are not risk rates:** High accident counts may reflect greater traffic exposure. Compare rates or model exposure where reliable denominators exist.
- **Proximity is not proof of exposure:** The nearest counting station may not measure traffic on the accident's actual road segment. Check station distance, road reference, and temporal coverage before interpretation.
- **Missingness matters:** Excluded low-coverage traffic hours and unavailable accident attributes can affect comparisons.
- **Source coverage differs:** NVDB record-level accidents and aggregated Trine severity summaries are not interchangeable and may cover different populations or time periods.
- **Descriptive versus predictive:** Correlations and density maps do not establish causation or predictive accuracy. Future models need separate validation and clear reporting of limitations.
- **Reproducibility:** Record extraction dates, study period, filtering decisions, API access conditions, and package versions in the final research report.

## Data sources and acknowledgement

- **Statens vegvesen — NVDB API:** https://nvdbapiles.atlas.vegvesen.no/vegobjekter/api/v4/vegobjekter
- **Statens vegvesen — Trafikkdata:** https://dataut.vegvesen.no/en/dataset/trafikkdata
- **Statens vegvesen — Trine:** https://trine.atlas.vegvesen.no/

The scripts identify the Norwegian Licence for Open Government Data (NLOD 2.0) for the public road-data sources. Follow the applicable terms and attribute **Statens vegvesen** in publications and redistributed datasets. Confirm any additional conditions attached to manually exported or restricted data.

## Project status

**Documented here:** data acquisition, cleaning, integration, descriptive visualisation, and exploratory analysis.

**Future research stages:** formal geospatial hotspot detection, comparative risk profiling, a lightweight predictive model, evaluation, and an interactive dashboard. These should be documented separately when implemented and tested.
