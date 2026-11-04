"""
traffic_volume_analysis.py
==========================

Fetches hourly traffic volume for Stavanger from the Norwegian Public Roads
Administration (Statens vegvesen) Trafikkdata GraphQL API, cleans it, and
produces exploratory visualizations with matplotlib and seaborn.

Data source
-----------
Dataset page : https://dataut.vegvesen.no/en/dataset/trafikkdata
API endpoint : https://trafikkdata-api.atlas.vegvesen.no/  (GraphQL, no API key)
Interactive  : open the endpoint in a browser for the GraphiQL explorer/schema.
License      : NLOD 2.0 (cite "Statens vegvesen" in the report).

Pipeline
--------
1. List traffic registration points (counting stations) in Stavanger.
2. Download hourly volumes per station (paginated, cached to CSV).
3. Clean: drop hours with low coverage, add calendar features.
4. Build figures and a daily aggregate table for later ML joins with
   accident data.

Usage
-----
    pip install requests pandas matplotlib seaborn
    python traffic_volume_analysis.py                           # defaults
    python traffic_volume_analysis.py --start 2023-01-01 --end 2024-12-31
    python traffic_volume_analysis.py --max-points 5 --refresh  # re-download
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import requests
import seaborn as sns
from matplotlib.colors import LinearSegmentedColormap

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_URL = "https://trafikkdata-api.atlas.vegvesen.no/"
TIMEZONE = ZoneInfo("Europe/Oslo")

COUNTY_ROGALAND = 11          # Fylkesnummer
MUNICIPALITY_STAVANGER = 1103  # Kommunenummer

MIN_COVERAGE_PCT = 50.0        # Hours below this coverage are discarded
HEAVY_VEHICLE_MIN_LENGTH = 5.6  # Metres; vegvesen convention for "heavy"
PAGE_SIZE_LIMIT = 100          # API returns at most 100 edges per page
REQUEST_PAUSE_S = 0.2          # Be polite to a free public API

PROJECT_ROOT = Path(__file__).resolve().parent
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "traffic"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
FIGURE_DIR = PROJECT_ROOT / "figures" / "traffic"

# Plot styling: validated categorical palette and recessive ink colours.
SERIES_BLUE = "#2a78d6"
SERIES_ORANGE = "#eb6834"
SERIES_AQUA = "#1baf7a"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID_COLOUR = "#e4e3df"
SURFACE = "#fcfcfb"
SEQUENTIAL_BLUE = LinearSegmentedColormap.from_list(
    "seq_blue", ["#cde2fb", "#86b6ef", "#3987e5", "#256abf", "#184f95", "#0d366b"]
)

WEEKDAY_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

log = logging.getLogger("traffic")


# ---------------------------------------------------------------------------
# GraphQL queries
# ---------------------------------------------------------------------------
# Values are written inline (Python %-formatting) instead of GraphQL variables.
# The API uses custom scalar types (e.g. PositiveInt), so declared variable
# types such as [Int!] are rejected with VariableTypeMismatch.


def gql_str(value) -> str:
    """Quote a Python value as a GraphQL string literal ("null" for None)."""
    return "null" if value is None else json.dumps(str(value))


POINTS_QUERY = """
{
  trafficRegistrationPoints(
    searchQuery: {
      countyNumbers: [%(county)d]
      isOperational: true
      trafficType: VEHICLE
      registrationFrequency: CONTINUOUS
    }
  ) {
    id
    name
    location {
      municipality { name number }
      roadReference { shortForm }
      coordinates { latLon { lat lon } }
    }
    dataTimeSpan {
      firstData
      latestData { volumeByHour }
    }
  }
}
"""

# Full query: total volume plus the split by vehicle length (heavy share).
HOURLY_QUERY_WITH_LENGTH = """
{
  trafficData(trafficRegistrationPointId: %(id)s) {
    volume {
      byHour(from: %(from)s, to: %(to)s, after: %(after)s) {
        pageInfo { hasNextPage endCursor }
        edges {
          node {
            from
            total {
              volumeNumbers { volume }
              coverage { percentage }
            }
            byLengthRange {
              lengthRange { lowerBound upperBound }
              total { volumeNumbers { volume } }
            }
          }
        }
      }
    }
  }
}
"""

# Fallback query without the length split, used if the schema rejects it.
HOURLY_QUERY_TOTAL_ONLY = """
{
  trafficData(trafficRegistrationPointId: %(id)s) {
    volume {
      byHour(from: %(from)s, to: %(to)s, after: %(after)s) {
        pageInfo { hasNextPage endCursor }
        edges {
          node {
            from
            total {
              volumeNumbers { volume }
              coverage { percentage }
            }
          }
        }
      }
    }
  }
}
"""


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------

class TrafficApiError(RuntimeError):
    """Raised when the API returns GraphQL errors or an HTTP failure."""


class TrafficDataClient:
    """Minimal GraphQL client for the vegvesen Trafikkdata API."""

    def __init__(self, url: str = API_URL, timeout: int = 60, retries: int = 3):
        self.url = url
        self.timeout = timeout
        self.retries = retries
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def execute(self, query: str) -> dict:
        """Run a GraphQL query and return the `data` payload."""
        payload = {"query": query}
        for attempt in range(1, self.retries + 1):
            try:
                resp = self.session.post(self.url, json=payload, timeout=self.timeout)
                resp.raise_for_status()
                body = resp.json()
                if body.get("errors"):
                    messages = "; ".join(e.get("message", str(e)) for e in body["errors"])
                    raise TrafficApiError(messages)
                return body["data"]
            except (requests.ConnectionError, requests.Timeout) as exc:
                wait = 2 ** attempt
                log.warning("Network error (%s), retry %d/%d in %ds",
                            exc, attempt, self.retries, wait)
                time.sleep(wait)
            except requests.HTTPError as exc:
                raise TrafficApiError(f"HTTP {resp.status_code}: {resp.text[:300]}") from exc
        raise TrafficApiError(f"Gave up after {self.retries} attempts")

    # -- Stations -----------------------------------------------------------

    def registration_points(self, county: int, municipality: int | None) -> pd.DataFrame:
        """Return operational continuous vehicle counters, optionally one municipality."""
        data = self.execute(POINTS_QUERY % {"county": county})
        rows = []
        for p in data["trafficRegistrationPoints"]:
            loc = p.get("location") or {}
            muni = loc.get("municipality") or {}
            latlon = ((loc.get("coordinates") or {}).get("latLon")) or {}
            span = p.get("dataTimeSpan") or {}
            rows.append({
                "point_id": p["id"],
                "name": p["name"],
                "municipality": muni.get("name"),
                "municipality_no": muni.get("number"),
                "road_ref": (loc.get("roadReference") or {}).get("shortForm"),
                "lat": latlon.get("lat"),
                "lon": latlon.get("lon"),
                "first_data": span.get("firstData"),
                "latest_hour": (span.get("latestData") or {}).get("volumeByHour"),
            })
        df = pd.DataFrame(rows)
        if municipality is not None and not df.empty:
            df = df[df["municipality_no"] == municipality]
        # Road category is the first letter of the reference: E, R, F, K, P.
        df["road_category"] = df["road_ref"].str[0].map(
            {"E": "European", "R": "National", "F": "County",
             "K": "Municipal", "P": "Private"})
        return df.reset_index(drop=True)

    # -- Hourly volumes -----------------------------------------------------

    def hourly_volume(self, point_id: str, start: datetime, end: datetime,
                      with_length: bool = True) -> pd.DataFrame:
        """Download hourly volumes for one station, following pagination."""
        query = HOURLY_QUERY_WITH_LENGTH if with_length else HOURLY_QUERY_TOTAL_ONLY
        variables = {"id": gql_str(point_id), "from": gql_str(start.isoformat()),
                     "to": gql_str(end.isoformat()), "after": gql_str(None)}
        rows: list[dict] = []
        while True:
            try:
                data = self.execute(query % variables)
            except TrafficApiError as exc:
                if with_length and "byLengthRange" in str(exc):
                    log.warning("Length split unavailable, falling back to totals")
                    return self.hourly_volume(point_id, start, end, with_length=False)
                raise
            conn = data["trafficData"]["volume"]["byHour"]
            for edge in conn["edges"]:
                rows.append(_parse_hour_node(edge["node"]))
            if not conn["pageInfo"]["hasNextPage"]:
                break
            variables["after"] = gql_str(conn["pageInfo"]["endCursor"])
            time.sleep(REQUEST_PAUSE_S)
        df = pd.DataFrame(rows)
        if not df.empty:
            df.insert(0, "point_id", point_id)
        return df


def _parse_hour_node(node: dict) -> dict:
    """Flatten one hourly GraphQL node into a record."""
    total = node.get("total") or {}
    volume = (total.get("volumeNumbers") or {}).get("volume")
    coverage = (total.get("coverage") or {}).get("percentage")

    heavy = None
    if "byLengthRange" in node and node["byLengthRange"]:
        heavy = 0
        for bucket in node["byLengthRange"]:
            lower = (bucket.get("lengthRange") or {}).get("lowerBound") or 0
            vol = ((bucket.get("total") or {}).get("volumeNumbers") or {}).get("volume")
            if lower >= HEAVY_VEHICLE_MIN_LENGTH and vol is not None:
                heavy += vol
    return {"from": node["from"], "volume": volume,
            "coverage_pct": coverage, "heavy_volume": heavy}


# ---------------------------------------------------------------------------
# Extraction with caching
# ---------------------------------------------------------------------------

def fetch_all(client: TrafficDataClient, points: pd.DataFrame, start: datetime,
              end: datetime, refresh: bool) -> pd.DataFrame:
    """Download (or load cached) hourly data for every station."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    frames = []
    tag = f"{start:%Y%m%d}_{end:%Y%m%d}"
    for i, row in points.iterrows():
        cache = RAW_DIR / f"hourly_{row.point_id}_{tag}.csv"
        if cache.exists() and not refresh:
            df = pd.read_csv(cache)
            log.info("[%d/%d] %s: loaded %d rows from cache",
                     i + 1, len(points), row["name"], len(df))
        else:
            log.info("[%d/%d] %s: downloading", i + 1, len(points), row["name"])
            try:
                df = client.hourly_volume(row.point_id, start, end)
            except TrafficApiError as exc:
                log.error("Skipping %s: %s", row.point_id, exc)
                continue
            df.to_csv(cache, index=False)
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# ---------------------------------------------------------------------------
# Cleaning and feature engineering
# ---------------------------------------------------------------------------

def clean_hourly(raw: pd.DataFrame, points: pd.DataFrame) -> pd.DataFrame:
    """Filter low-coverage hours and add calendar features."""
    df = raw.copy()
    df["timestamp"] = pd.to_datetime(df["from"], utc=True).dt.tz_convert(TIMEZONE)
    df = df.drop(columns="from")

    before = len(df)
    df = df[df["volume"].notna() & (df["coverage_pct"] >= MIN_COVERAGE_PCT)]
    log.info("Dropped %d of %d hours below %.0f%% coverage",
             before - len(df), before, MIN_COVERAGE_PCT)

    df = df.merge(points[["point_id", "name", "road_category", "lat", "lon"]],
                  on="point_id", how="left")
    df["date"] = df["timestamp"].dt.date
    df["hour"] = df["timestamp"].dt.hour
    df["weekday"] = pd.Categorical(df["timestamp"].dt.strftime("%a"),
                                   categories=WEEKDAY_ORDER, ordered=True)
    df["is_weekend"] = df["timestamp"].dt.dayofweek >= 5
    df["month"] = df["timestamp"].dt.to_period("M").dt.to_timestamp()
    df["heavy_share"] = df["heavy_volume"] / df["volume"].where(df["volume"] > 0)
    return df.reset_index(drop=True)


def daily_aggregate(hourly: pd.DataFrame) -> pd.DataFrame:
    """Daily traffic per station. Only days with at least 20 valid hours are kept,
    so that partial days do not bias the average daily traffic (ADT)."""
    agg = (hourly.groupby(["point_id", "name", "date"], observed=True)
           .agg(volume=("volume", "sum"),
                heavy_volume=("heavy_volume", "sum"),
                valid_hours=("volume", "size"))
           .reset_index())
    agg = agg[agg["valid_hours"] >= 20].copy()
    agg["date"] = pd.to_datetime(agg["date"])
    agg["weekday"] = pd.Categorical(agg["date"].dt.strftime("%a"),
                                    categories=WEEKDAY_ORDER, ordered=True)
    return agg


# ---------------------------------------------------------------------------
# Visualizations
# ---------------------------------------------------------------------------

def set_style() -> None:
    """Quiet, report-ready styling shared by every figure."""
    sns.set_theme(style="whitegrid", context="notebook")
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "axes.edgecolor": GRID_COLOUR,
        "axes.labelcolor": TEXT_SECONDARY,
        "axes.titlecolor": TEXT_PRIMARY,
        "axes.titleweight": "semibold",
        "axes.titlesize": 13,
        "axes.titlelocation": "left",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "grid.color": GRID_COLOUR,
        "grid.linewidth": 0.8,
        "xtick.color": TEXT_SECONDARY,
        "ytick.color": TEXT_SECONDARY,
        "lines.linewidth": 2,
        "legend.frameon": False,
        "savefig.dpi": 200,
        "savefig.bbox": "tight",
    })


def _thousands(ax, axis: str = "y") -> None:
    fmt = mticker.FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", " "))
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


def _save(fig, name: str) -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURE_DIR / f"{name}.png"
    fig.savefig(path)
    plt.close(fig)
    log.info("Saved %s", path)


def plot_station_adt(daily: pd.DataFrame, top_n: int = 15) -> None:
    """Average daily traffic (ADT) per station, highest first."""
    adt = (daily.groupby("name")["volume"].mean()
           .sort_values(ascending=False).head(top_n).reset_index())
    fig, ax = plt.subplots(figsize=(9, 0.42 * len(adt) + 1.5))
    sns.barplot(data=adt, y="name", x="volume", color=SERIES_BLUE, saturation=1, ax=ax, width=0.7)
    for p, v in zip(ax.patches, adt["volume"]):
        ax.text(p.get_width(), p.get_y() + p.get_height() / 2,
                f"  {v:,.0f}".replace(",", " "), va="center",
                fontsize=9, color=TEXT_SECONDARY)
    ax.set(title=f"Average daily traffic, top {len(adt)} stations in Stavanger",
           xlabel="Vehicles per day", ylabel="")
    ax.grid(axis="y", visible=False)
    _thousands(ax, "x")
    _save(fig, "01_station_adt")


def plot_hourly_profile(hourly: pd.DataFrame) -> None:
    """Mean vehicles per hour of day, weekday vs weekend, all stations."""
    prof = (hourly.assign(day_type=hourly["is_weekend"].map(
                {False: "Weekday", True: "Weekend"}))
            .groupby(["day_type", "hour"])["volume"].mean().reset_index())
    fig, ax = plt.subplots(figsize=(9, 4.5))
    sns.lineplot(data=prof, x="hour", y="volume", hue="day_type",
                 palette={"Weekday": SERIES_BLUE, "Weekend": SERIES_ORANGE},
                 marker="o", markersize=5, ax=ax)
    # Direct label at each series peak keeps identity off colour alone.
    for label in ("Weekday", "Weekend"):
        sub = prof[prof["day_type"] == label]
        if not sub.empty:
            peak = sub.loc[sub["volume"].idxmax()]
            ax.annotate(f"{label} peak {int(peak['hour']):02d}:00",
                        (peak["hour"], peak["volume"]), xytext=(8, 6),
                        textcoords="offset points", fontsize=9, color=TEXT_PRIMARY)
    ax.set(title="Hourly traffic profile: commuter peaks on weekdays",
           xlabel="Hour of day", ylabel="Mean vehicles per hour per station")
    ax.set_xticks(range(0, 24, 2))
    ax.legend(title="")
    _thousands(ax)
    _save(fig, "02_hourly_profile")


def plot_weekday_hour_heatmap(hourly: pd.DataFrame) -> None:
    """Heatmap of mean volume by weekday and hour."""
    pivot = hourly.pivot_table(index="weekday", columns="hour", values="volume",
                               aggfunc="mean", observed=False)
    fig, ax = plt.subplots(figsize=(12, 4))
    sns.heatmap(pivot, cmap=SEQUENTIAL_BLUE, linewidths=1, linecolor=SURFACE,
                cbar_kws={"label": "Mean vehicles per hour", "shrink": 0.8}, ax=ax)
    ax.set(title="When is Stavanger busiest? Mean volume by weekday and hour",
           xlabel="Hour of day", ylabel="")
    ax.tick_params(axis="y", rotation=0)
    _save(fig, "03_weekday_hour_heatmap")


def plot_daily_trend(daily: pd.DataFrame) -> None:
    """Total daily volume across stations with a 7-day rolling mean.
    Uses only stations present on every day to avoid station-count artefacts."""
    days_per_station = daily.groupby("point_id")["date"].nunique()
    stable = days_per_station[days_per_station >= 0.9 * daily["date"].nunique()].index
    series = (daily[daily["point_id"].isin(stable)]
              .groupby("date")["volume"].mean().sort_index())
    rolling = series.rolling(7, center=True).mean()

    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.plot(series.index, series.values, color=SERIES_BLUE, alpha=0.3,
            linewidth=1, label="Daily")
    ax.plot(rolling.index, rolling.values, color=SERIES_BLUE, label="7-day mean")
    ax.set(title=f"Daily traffic over time (mean of {len(stable)} stable stations)",
           xlabel="", ylabel="Vehicles per day per station")
    ax.legend(loc="upper left")
    _thousands(ax)
    _save(fig, "04_daily_trend")


def plot_monthly_pattern(daily: pd.DataFrame) -> None:
    """Seasonality: mean daily traffic per calendar month."""
    df = daily.assign(month=daily["date"].dt.month)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    sns.barplot(data=df, x="month", y="volume", color=SERIES_BLUE,
                saturation=1, errorbar=("ci", 95), err_kws={"color": TEXT_SECONDARY, "linewidth": 1},
                ax=ax, width=0.7)
    ax.set_xticks(range(12))
    ax.set_xticklabels(["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
    ax.set(title="Seasonality: mean daily traffic by month (95% CI)",
           xlabel="", ylabel="Vehicles per day per station")
    _thousands(ax)
    _save(fig, "05_monthly_pattern")


def plot_weekday_distribution(daily: pd.DataFrame) -> None:
    """Spread of daily volume per weekday."""
    fig, ax = plt.subplots(figsize=(9, 4.5))
    sns.boxplot(data=daily, x="weekday", y="volume", color="#86b6ef",
                linewidth=1, fliersize=2, ax=ax,
                medianprops={"color": TEXT_PRIMARY, "linewidth": 1.5})
    ax.set(title="Distribution of daily volume per station by weekday",
           xlabel="", ylabel="Vehicles per day")
    _thousands(ax)
    _save(fig, "06_weekday_distribution")


def plot_heavy_share(daily: pd.DataFrame, top_n: int = 15) -> None:
    """Share of heavy vehicles (>= 5.6 m) per station, if length data exists."""
    if daily["heavy_volume"].fillna(0).sum() == 0:
        log.info("No length-class data, skipping heavy-vehicle figure")
        return
    share = (daily.groupby("name")[["heavy_volume", "volume"]].sum()
             .assign(share=lambda d: 100 * d["heavy_volume"] / d["volume"])
             .sort_values("share", ascending=False).head(top_n).reset_index())
    fig, ax = plt.subplots(figsize=(9, 0.42 * len(share) + 1.5))
    sns.barplot(data=share, y="name", x="share", color=SERIES_ORANGE, saturation=1, ax=ax, width=0.7)
    for p, v in zip(ax.patches, share["share"]):
        ax.text(p.get_width(), p.get_y() + p.get_height() / 2, f"  {v:.1f}%",
                va="center", fontsize=9, color=TEXT_SECONDARY)
    ax.set(title="Heavy-vehicle share (length >= 5.6 m) by station",
           xlabel="Share of all vehicles (%)", ylabel="")
    ax.grid(axis="y", visible=False)
    _save(fig, "07_heavy_vehicle_share")


def plot_station_map(daily: pd.DataFrame, points: pd.DataFrame) -> None:
    """Station locations sized and shaded by ADT (simple lat/lon scatter)."""
    adt = daily.groupby("point_id")["volume"].mean().rename("adt")
    df = points.merge(adt, on="point_id").dropna(subset=["lat", "lon"])
    if df.empty:
        return
    fig, ax = plt.subplots(figsize=(7, 7))
    sc = ax.scatter(df["lon"], df["lat"], s=40 + df["adt"] / df["adt"].max() * 400,
                    c=df["adt"], cmap=SEQUENTIAL_BLUE, edgecolor=SURFACE,
                    linewidth=2, zorder=3)
    for _, r in df.nlargest(6, "adt").iterrows():
        ax.annotate(r["name"], (r["lon"], r["lat"]), xytext=(8, 4),
                    textcoords="offset points", fontsize=8, color=TEXT_PRIMARY)
    cbar = fig.colorbar(sc, ax=ax, shrink=0.7)
    cbar.set_label("Average daily traffic")
    ax.set(title="Counting stations in Stavanger by ADT",
           xlabel="Longitude", ylabel="Latitude")
    ax.set_aspect(1 / 0.5)  # Approximate lon/lat scaling at ~59 deg N
    _save(fig, "08_station_map")


def print_insights(hourly: pd.DataFrame, daily: pd.DataFrame) -> None:
    """Log a short numeric summary to accompany the figures."""
    wk = daily[~daily["weekday"].isin(["Sat", "Sun"])]["volume"].mean()
    we = daily[daily["weekday"].isin(["Sat", "Sun"])]["volume"].mean()
    peak = (hourly[~hourly["is_weekend"]].groupby("hour")["volume"].mean()
            .nlargest(2).index.tolist())
    busiest = daily.groupby("name")["volume"].mean().idxmax()
    log.info("----- Key figures -----")
    log.info("Stations analysed      : %d", daily["point_id"].nunique())
    log.info("Days covered           : %d", daily["date"].nunique())
    log.info("Weekday ADT per station: %.0f", wk)
    log.info("Weekend ADT per station: %.0f (%.0f%% of weekday)", we, 100 * we / wk)
    log.info("Weekday peak hours     : %s", ", ".join(f"{h:02d}:00" for h in sorted(peak)))
    log.info("Busiest station        : %s", busiest)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    today = datetime.now(TIMEZONE).date()
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", default=str(today.replace(year=today.year - 1)),
                    help="Start date YYYY-MM-DD (default: one year ago)")
    ap.add_argument("--end", default=str(today), help="End date YYYY-MM-DD (exclusive)")
    ap.add_argument("--municipality", type=int, default=MUNICIPALITY_STAVANGER,
                    help="Kommunenummer; 0 for the whole county")
    ap.add_argument("--max-points", type=int, default=0,
                    help="Limit number of stations (0 = all), useful for testing")
    ap.add_argument("--refresh", action="store_true", help="Ignore cached CSV files")
    return ap.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%H:%M:%S")
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    args = parse_args()
    start = datetime.fromisoformat(args.start).replace(tzinfo=TIMEZONE)
    end = datetime.fromisoformat(args.end).replace(tzinfo=TIMEZONE)
    if end <= start:
        raise SystemExit("--end must be after --start")

    client = TrafficDataClient()
    points = client.registration_points(COUNTY_ROGALAND, args.municipality or None)
    if points.empty:
        raise SystemExit("No registration points found for the given area")
    if args.max_points:
        points = points.head(args.max_points)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    points.to_csv(PROCESSED_DIR / "traffic_stations.csv", index=False)
    log.info("Found %d stations", len(points))

    raw = fetch_all(client, points, start, end, args.refresh)
    if raw.empty:
        raise SystemExit("No traffic data downloaded")

    hourly = clean_hourly(raw, points)
    daily = daily_aggregate(hourly)
    hourly.to_csv(PROCESSED_DIR / "traffic_hourly_clean.csv", index=False)
    daily.to_csv(PROCESSED_DIR / "traffic_daily.csv", index=False)

    set_style()
    plot_station_adt(daily)
    plot_hourly_profile(hourly)
    plot_weekday_hour_heatmap(hourly)
    plot_daily_trend(daily)
    plot_monthly_pattern(daily)
    plot_weekday_distribution(daily)
    plot_heavy_share(daily)
    plot_station_map(daily, points)
    print_insights(hourly, daily)


if __name__ == "__main__":
    main()
