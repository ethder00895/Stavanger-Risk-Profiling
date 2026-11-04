"""
accident_data_collection.py
===========================

Collects every traffic accident record available for Stavanger municipality
(kommune 1103) from official Statens vegvesen open data, merges it with the
Trine severity tables and links each accident to the nearest Trafikkdata
counting station, producing ML-ready tables for the bachelor project.

Data sources
------------
1. NVDB API Les v4 (record level, one row per accident, no API key)
     https://nvdbapiles.atlas.vegvesen.no/vegobjekter/api/v4/vegobjekter
     570 Trafikkulykke            : time, place, conditions, road design, AADT
     571 Ulykkesinvolvert enhet   : vehicles / units involved
     572 Ulykkesinvolvert person  : road-user type
     540 Trafikkmengde            : AADT road segments (exposure)
2. Trine (aggregated tables exported manually, severity breakdowns)
     https://trine.atlas.vegvesen.no  ->  data/raw/trafficAccidents/*.csv
3. Trafikkdata (already collected by traffic_volume_analysis.py)
     data/processed/traffic_stations.csv, data/processed/traffic_daily.csv

License : NLOD 2.0 - cite "Statens vegvesen" in the report.

Why two accident sources
------------------------
Trine only exports pivot tables (max. a few dimensions per download) and the
open NVDB API does not publish injury severity. NVDB therefore supplies the
record-level data for modelling, and Trine supplies severity profiles per
dimension for descriptive profiling and validation.

Outputs (data/processed/)
-------------------------
    accidents_stavanger.csv          one row per accident, cleaned + features
    accident_units_stavanger.csv     one row per involved unit
    accident_persons_stavanger.csv   one row per involved person
    accidents_enriched.csv           accidents + unit mix + nearest station volume
    aadt_segments_stavanger.csv      AADT road segments with length (exposure)
    trine_severity_long.csv          all Trine exports stacked in long format
    nvdb_severity_summary.csv        NVDB severity and location-accuracy totals

Severity from NVDB
------------------
Record-level severity (Alvorlighetsgrad) and casualty counts are withheld
from anonymous API access. The grouped statistics endpoint
    /vegobjekter/{type}/statistikk/gruppert/egenskap
does return aggregated counts per property value for the municipality or
for any polygon, which is used here for the severity summary. When a bearer
token with extended rights is available, set NVDB_TOKEN before running and
it is sent with every request.

Usage
-----
    pip install requests pandas numpy
    python accident_data_collection.py                 # full run, uses cache
    python accident_data_collection.py --refresh       # re-download NVDB data
    python accident_data_collection.py --trine-only    # only parse Trine files
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Iterator

import numpy as np
import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
NVDB_URL = "https://nvdbapiles.atlas.vegvesen.no/vegobjekter/api/v4/vegobjekter"
NVDB_HEADERS = {
    "Accept": "application/json",
    "X-Client": "BachelorsProject2026-Stavanger",  # Required by NVDB API v4
}
# Optional bearer token (bearerAuth in the NVDB OpenAPI spec) for restricted fields
if os.environ.get("NVDB_TOKEN"):
    NVDB_HEADERS["Authorization"] = f"Bearer {os.environ['NVDB_TOKEN']}"

# Grouped statistics: accident property types and their enum labels
SEVERITY_PROPERTY_ID = 5074        # Alvorlighetsgrad
ACCURACY_PROPERTY_ID = 5120        # Stedfestingens nøyaktighet
SEVERITY_LABELS = {
    6427: "Fatal accident",
    6428: "Very serious injury accident",
    6429: "Serious injury accident",
    6430: "Slight injury accident",
    6431: "Accident without injury",
    11664: "Unknown severity",
}
ACCURACY_LABELS = {
    6688: "Accurate",
    6689: "Approximate",
    6690: "Inaccurate",
}
MUNICIPALITY_STAVANGER = 1103
SRID_WGS84 = 4326
PAGE_SIZE = 1000
REQUEST_PAUSE_S = 0.2
MAX_RETRIES = 4

# NVDB object types collected for this study
NVDB_TYPES = {
    570: "accidents",
    571: "accident_units",
    572: "accident_persons",
    540: "aadt_segments",
}

# Accident-to-station linking
MAX_STATION_DISTANCE_M = 1500.0
EARTH_RADIUS_M = 6_371_008.8

PROJECT_ROOT = Path(__file__).resolve().parent
RAW_NVDB_DIR = PROJECT_ROOT / "data" / "raw" / "nvdb"
RAW_TRINE_DIR = PROJECT_ROOT / "data" / "raw" / "trafficAccidents"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

# Trine severity headers -> (severity level, counting unit)
TRINE_MEASURES = {
    "Drept": ("killed", "persons"),
    "Hardt skadd": ("serious", "persons"),
    "Meget alvorlig skadd": ("very_serious", "persons"),
    "Alvorlig skadd": ("serious", "persons"),
    "Lettere skadd": ("light", "persons"),
    "Dødsulykke": ("killed", "accidents"),
    "Ulykke med hardt skadde": ("serious", "accidents"),
    "Ulykke med meget alvorlig skadde": ("very_serious", "accidents"),
    "Ulykke med alvorlig skadde": ("serious", "accidents"),
    "Ulykke med lettere skadde": ("light", "accidents"),
}
TRINE_TOTAL_COLUMNS = {"Sum", "Totalt", "Total"}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("accident_data_collection")


# ---------------------------------------------------------------------------
# 1. NVDB download
# ---------------------------------------------------------------------------
def _get_with_retry(session: requests.Session, url: str, params: dict[str, Any]) -> dict:
    """GET a JSON payload with exponential back-off on transient failures."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(url, params=params, headers=NVDB_HEADERS, timeout=90)
            if response.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"HTTP {response.status_code}", response=response)
            response.raise_for_status()
            return response.json()
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as exc:
            if attempt == MAX_RETRIES:
                raise
            wait = 2 ** attempt
            log.warning("Request failed (%s), retry %d/%d in %ds", exc, attempt, MAX_RETRIES, wait)
            time.sleep(wait)
    raise RuntimeError("Unreachable")


def fetch_nvdb_objects(type_id: int, session: requests.Session) -> Iterator[dict[str, Any]]:
    """Yield all NVDB objects of one type inside Stavanger, following pagination."""
    url = f"{NVDB_URL}/{type_id}"
    params: dict[str, Any] = {
        "kommune": MUNICIPALITY_STAVANGER,
        "inkluder": "metadata,egenskaper,relasjoner,lokasjon,geometri",
        "srid": SRID_WGS84,
        "antall": PAGE_SIZE,
    }
    fetched = 0
    while True:
        payload = _get_with_retry(session, url, params)
        objects = payload.get("objekter", [])
        if not objects:
            break
        fetched += len(objects)
        log.info("  type %d: %d objects", type_id, fetched)
        yield from objects

        next_start = payload.get("metadata", {}).get("neste", {}).get("start")
        if not next_start or next_start == params.get("start"):
            break
        params["start"] = next_start
        time.sleep(REQUEST_PAUSE_S)


def _clean_property_name(name: str) -> str:
    """Strip NVDB version suffixes such as '(Ny)' and '(endret)'."""
    return re.sub(r"\s*\((Ny|endret)\)\s*$", "", name).strip()


def _first_coordinate(wkt: str) -> tuple[float | None, float | None]:
    """
    Return (lat, lon) of the first vertex of a WKT geometry in EPSG:4326.

    NVDB may return 4326 coordinates in lat-lon axis order. For Norway the
    latitude (57-72) is always larger than the longitude (4-32), which makes
    the axis order unambiguous.
    """
    numbers = re.findall(r"-?\d+(?:\.\d+)?", wkt or "")
    if len(numbers) < 2:
        return None, None
    a, b = float(numbers[0]), float(numbers[1])
    return (a, b) if a > b else (b, a)


def flatten_nvdb_object(obj: dict[str, Any]) -> dict[str, Any]:
    """Flatten one NVDB object into id, properties, parent relations and location."""
    record: dict[str, Any] = {"nvdb_id": obj.get("id")}

    for prop in obj.get("egenskaper", []):
        name = _clean_property_name(prop.get("navn", ""))
        if name.startswith("Geometri"):
            continue
        record[name] = prop.get("verdi")

    for parent in obj.get("relasjoner", {}).get("foreldre", []):
        parent_type = parent.get("type", {}).get("id")
        parent_ids = parent.get("vegobjekter", [])
        if parent_type and parent_ids:
            record[f"parent_{parent_type}"] = parent_ids[0]

    location = obj.get("lokasjon", {})
    record["kommune"] = (location.get("kommuner") or [None])[0]
    refs = location.get("vegsystemreferanser") or [{}]
    record["road_ref"] = refs[0].get("kortform")
    record["segment_length_m"] = location.get("lengde")

    wkt = obj.get("geometri", {}).get("wkt", "")
    record["lat"], record["lon"] = _first_coordinate(wkt)
    return record


def check_connectivity(session: requests.Session) -> None:
    """
    Fail fast with a clear message when the NVDB host cannot be reached.

    A NameResolutionError means the machine's DNS cannot resolve the host,
    which usually indicates a corporate network, VPN or proxy restriction.
    Proxies are read from the HTTPS_PROXY / HTTP_PROXY environment variables.
    """
    host = NVDB_URL.split("/")[2]
    try:
        session.get(f"https://{host}/vegobjekter/api/v4/vegobjekttyper/570",
                    headers=NVDB_HEADERS, timeout=20).raise_for_status()
    except requests.ConnectionError as exc:
        raise SystemExit(
            f"Cannot reach {host}.\n"
            f"  1. Run 'nslookup {host}' in a terminal to test DNS.\n"
            "  2. On a company network or VPN, disconnect or use another network.\n"
            "  3. Behind a proxy, set it before running, e.g.\n"
            "     os.environ['HTTPS_PROXY'] = 'http://proxy.host:port'\n"
            f"Original error: {exc.__class__.__name__}"
        ) from None
    log.info("NVDB API reachable at %s", host)


def download_nvdb(refresh: bool) -> dict[str, pd.DataFrame]:
    """Download (or load cached) NVDB tables for all configured object types."""
    RAW_NVDB_DIR.mkdir(parents=True, exist_ok=True)
    tables: dict[str, pd.DataFrame] = {}

    with requests.Session() as session:
        check_connectivity(session)
        for type_id, name in NVDB_TYPES.items():
            cache = RAW_NVDB_DIR / f"nvdb_{type_id}_{name}.csv"
            if cache.exists() and not refresh:
                log.info("Loading cached %s", cache.name)
                tables[name] = pd.read_csv(cache, encoding="utf-8-sig", low_memory=False)
                continue

            log.info("Downloading NVDB type %d (%s)", type_id, name)
            records = [flatten_nvdb_object(o) for o in fetch_nvdb_objects(type_id, session)]
            df = pd.DataFrame.from_records(records)
            df.to_csv(cache, index=False, encoding="utf-8-sig")
            log.info("Saved %d rows to %s", len(df), cache.name)
            tables[name] = df

    return tables


# ---------------------------------------------------------------------------
# 2. Cleaning and feature engineering
# ---------------------------------------------------------------------------
NUMERIC_ACCIDENT_COLUMNS = [
    "Fartsgrense", "ÅDT", "Temperatur", "Antall enheter", "Antall kjørefelt",
    "År", "Måned",
]


def prepare_accidents(df: pd.DataFrame) -> pd.DataFrame:
    """Build timestamps, typed numerics and model-ready features for accidents."""
    out = df.copy()
    clock = out.get("Ulykkesklokkeslett", pd.Series(index=out.index, dtype=object))
    out["datetime"] = pd.to_datetime(
        out["Ulykkesdato"].astype(str) + " " + clock.fillna("00:00").astype(str),
        errors="coerce",
    )
    out["time_known"] = clock.notna()

    for col in NUMERIC_ACCIDENT_COLUMNS:
        if col in out:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    out["date"] = out["datetime"].dt.date
    out["year"] = out["datetime"].dt.year
    out["month"] = out["datetime"].dt.month
    out["weekday"] = out["datetime"].dt.day_name()
    out["hour"] = out["datetime"].dt.hour.where(out["time_known"])
    out["is_weekend"] = out["datetime"].dt.dayofweek >= 5
    out["is_rush_hour"] = out["hour"].isin([7, 8, 15, 16, 17])
    out["is_dark_season"] = out["month"].isin([11, 12, 1, 2])

    # Vulnerable road users involved (pedestrian, bicycle, motorcycle, moped)
    vru_cols = [c for c in out.columns if re.match(
        r"Antall (Fotgjengere|Sykkel|MC|Lett MC|Moped|liten elektrisk motorvogn)", c)]
    for col in vru_cols:
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)
    out["n_vulnerable_units"] = out[vru_cols].sum(axis=1) if vru_cols else 0
    out["involves_vulnerable"] = out["n_vulnerable_units"] > 0

    return out.sort_values("datetime").reset_index(drop=True)


def summarise_units(units: pd.DataFrame) -> pd.DataFrame:
    """Aggregate involved units to one row per accident (unit mix features)."""
    if units.empty or "parent_570" not in units:
        return pd.DataFrame(columns=["nvdb_id"])

    category_col = next(
        (c for c in ("Enhetstype, hovedkategori", "Enhetstype") if c in units), None)
    agg = units.groupby("parent_570").agg(n_units_registered=("nvdb_id", "size"))

    if "Tungtransport bil" in units:
        heavy = units["Tungtransport bil"].astype(str).str.lower().isin(["ja", "true", "1"])
        agg["has_heavy_vehicle"] = heavy.groupby(units["parent_570"]).any()

    if "Årsmodell på kjøretøy" in units:
        model_year = pd.to_numeric(units["Årsmodell på kjøretøy"], errors="coerce")
        agg["mean_vehicle_model_year"] = model_year.groupby(units["parent_570"]).mean()

    if category_col:
        mix = pd.crosstab(units["parent_570"], units[category_col])
        mix.columns = [f"units_{_slug(c)}" for c in mix.columns]
        agg = agg.join(mix)

    return agg.reset_index().rename(columns={"parent_570": "nvdb_id"})


def _slug(text: Any) -> str:
    """Convert a Norwegian category label into a safe column suffix."""
    text = str(text).lower()
    for src, dst in (("æ", "ae"), ("ø", "o"), ("å", "a")):
        text = text.replace(src, dst)
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


# ---------------------------------------------------------------------------
# 3. Link accidents to Trafikkdata counting stations
# ---------------------------------------------------------------------------
def _haversine_matrix(lat1, lon1, lat2, lon2) -> np.ndarray:
    """Pairwise great-circle distances in metres between two coordinate sets."""
    lat1, lon1 = np.radians(lat1)[:, None], np.radians(lon1)[:, None]
    lat2, lon2 = np.radians(lat2)[None, :], np.radians(lon2)[None, :]
    a = (np.sin((lat2 - lat1) / 2) ** 2
         + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2)
    return 2 * EARTH_RADIUS_M * np.arcsin(np.sqrt(a))


def link_to_stations(accidents: pd.DataFrame) -> pd.DataFrame:
    """Attach nearest station, distance and same-day traffic volume to each accident."""
    stations_path = PROCESSED_DIR / "traffic_stations.csv"
    daily_path = PROCESSED_DIR / "traffic_daily.csv"
    if not stations_path.exists():
        log.warning("No traffic_stations.csv found - skipping station linking")
        return accidents

    stations = pd.read_csv(stations_path).dropna(subset=["lat", "lon"])
    out = accidents.copy()
    has_xy = out["lat"].notna() & out["lon"].notna()

    dist = _haversine_matrix(out.loc[has_xy, "lat"].to_numpy(), out.loc[has_xy, "lon"].to_numpy(),
                             stations["lat"].to_numpy(), stations["lon"].to_numpy())
    nearest = dist.argmin(axis=1)
    out.loc[has_xy, "station_id"] = stations["point_id"].to_numpy()[nearest]
    out.loc[has_xy, "station_name"] = stations["name"].to_numpy()[nearest]
    out.loc[has_xy, "station_distance_m"] = dist[np.arange(len(nearest)), nearest]

    too_far = out["station_distance_m"] > MAX_STATION_DISTANCE_M
    out.loc[too_far, ["station_id", "station_name"]] = np.nan

    if daily_path.exists():
        daily = pd.read_csv(daily_path)
        daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.date
        daily = daily.rename(columns={"point_id": "station_id", "volume": "station_daily_volume",
                                      "heavy_volume": "station_daily_heavy_volume"})
        out = out.merge(daily[["station_id", "date", "station_daily_volume",
                               "station_daily_heavy_volume"]],
                        on=["station_id", "date"], how="left")

    linked = out["station_id"].notna().sum()
    log.info("Linked %d of %d accidents to a station within %.0f m",
             linked, len(out), MAX_STATION_DISTANCE_M)
    return out


# ---------------------------------------------------------------------------
# 4. Trine aggregated tables
# ---------------------------------------------------------------------------
def read_trine_table(path: Path) -> pd.DataFrame:
    """
    Parse one Trine CSV export into long format.

    Handles the Trine quirks: UTF-8 BOM, ';' separator, stray trailing commas
    and a varying number of dimension columns before the severity columns.
    """
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    rows = [line.rstrip(",").split(";") for line in lines if line.strip()]
    header, body = rows[0], [r for r in rows[1:] if len(r) == len(rows[0])]
    df = pd.DataFrame(body, columns=header)

    measure_cols = [c for c in df.columns if c in TRINE_MEASURES]
    dim_cols = [c for c in df.columns if c not in measure_cols and c not in TRINE_TOTAL_COLUMNS]
    if not measure_cols:
        raise ValueError(f"No known severity columns in {path.name}: {header}")

    long = df.melt(id_vars=dim_cols, value_vars=measure_cols,
                   var_name="measure", value_name="count")
    long["count"] = pd.to_numeric(long["count"], errors="coerce").fillna(0).astype(int)
    long["severity"] = long["measure"].map(lambda m: TRINE_MEASURES[m][0])
    long["unit"] = long["measure"].map(lambda m: TRINE_MEASURES[m][1])

    # Stack dimensions as (dimension, value) pairs, keeping year/municipality separate
    fixed = [c for c in dim_cols if c in ("År", "Kommune")]
    breakdown = [c for c in dim_cols if c not in fixed]
    long["dimensions"] = " x ".join(breakdown)
    for i, col in enumerate(breakdown, start=1):
        long[f"dim{i}_name"] = col
        long[f"dim{i}_value"] = long[col]
    long["source_file"] = path.name
    if "År" in long:
        long["År"] = pd.to_numeric(long["År"], errors="coerce")

    keep = fixed + ["dimensions"] + [c for c in long.columns if re.match(r"dim\d_", c)] + [
        "severity", "unit", "count", "source_file"]
    return long[keep]


def load_all_trine() -> pd.DataFrame:
    """Parse every Trine export in the raw folder into one long table."""
    files = sorted(RAW_TRINE_DIR.glob("*.csv"))
    if not files:
        log.warning("No Trine exports found in %s", RAW_TRINE_DIR)
        return pd.DataFrame()

    frames = []
    for path in files:
        try:
            frames.append(read_trine_table(path))
            log.info("Parsed Trine table %s", path.name)
        except ValueError as exc:
            log.warning("Skipped %s: %s", path.name, exc)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# ---------------------------------------------------------------------------
# 5. Pipeline
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--refresh", action="store_true", help="Re-download NVDB data")
    parser.add_argument("--trine-only", action="store_true", help="Only parse Trine exports")
    args = parser.parse_args()

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    trine = load_all_trine()
    if not trine.empty:
        trine.to_csv(PROCESSED_DIR / "trine_severity_long.csv", index=False, encoding="utf-8-sig")
        log.info("Trine: %d rows from %d files", len(trine), trine["source_file"].nunique())
    if args.trine_only:
        return

    tables = download_nvdb(refresh=args.refresh)

    accidents = prepare_accidents(tables["accidents"])
    accidents.to_csv(PROCESSED_DIR / "accidents_stavanger.csv", index=False, encoding="utf-8-sig")
    tables["accident_units"].to_csv(PROCESSED_DIR / "accident_units_stavanger.csv",
                                    index=False, encoding="utf-8-sig")
    tables["accident_persons"].to_csv(PROCESSED_DIR / "accident_persons_stavanger.csv",
                                      index=False, encoding="utf-8-sig")
    tables["aadt_segments"].to_csv(PROCESSED_DIR / "aadt_segments_stavanger.csv",
                                   index=False, encoding="utf-8-sig")

    enriched = accidents.merge(summarise_units(tables["accident_units"]), on="nvdb_id", how="left")
    enriched = link_to_stations(enriched)
    enriched.to_csv(PROCESSED_DIR / "accidents_enriched.csv", index=False, encoding="utf-8-sig")

    log.info("Done: %d accidents (%s-%s) written to %s",
             len(enriched), enriched["year"].min(), enriched["year"].max(), PROCESSED_DIR)


if __name__ == "__main__":
    main()
