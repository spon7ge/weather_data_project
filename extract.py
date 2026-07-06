"""
extract.py — Open-Meteo → raw JSON files → raw.open_meteo_forecast (Postgres)

Design principles:
  - Extraction is intentionally "dumb": fetch, save, insert. No cleaning.
  - Raw JSON is written to disk first; Postgres load is secondary.
    If the DB load fails, you can replay from disk without re-hitting the API.
  - Errors per location are caught and logged; other locations still proceed.
"""

import json
import logging
import os
import uuid
from datetime import date
from pathlib import Path

import psycopg2
import psycopg2.extras
import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------

LOCATIONS = [
    {"name": "los_angeles", "latitude": 34.05,  "longitude": -118.24, "timezone": "America/Los_Angeles"},
    {"name": "new_york",    "latitude": 40.71,  "longitude": -74.01,  "timezone": "America/New_York"},
    {"name": "chicago",     "latitude": 41.85,  "longitude": -87.65,  "timezone": "America/Chicago"},
    {"name": "miami",       "latitude": 25.77,  "longitude": -80.19,  "timezone": "America/New_York"},
    {"name": "seattle",     "latitude": 47.61,  "longitude": -122.33, "timezone": "America/Los_Angeles"},
    {"name": "denver",      "latitude": 39.74,  "longitude": -104.98, "timezone": "America/Denver"},
    {"name": "austin",      "latitude": 30.27,  "longitude": -97.74,  "timezone": "America/Chicago"},
]

# ---------------------------------------------------------------------------
# API configuration
# ---------------------------------------------------------------------------

API_URL = "https://api.open-meteo.com/v1/forecast"
API_TIMEOUT_SECONDS = 30

# Shared (non-location-specific) parameters sent to every request.
# Timezone, latitude, and longitude are merged in per location.
BASE_PARAMS: dict = {
    "daily": [
        "weather_code",
        "temperature_2m_max",
        "temperature_2m_min",
        "apparent_temperature_max",
        "apparent_temperature_min",
        "precipitation_sum",
        "precipitation_hours",
        "precipitation_probability_max",
        "wind_speed_10m_max",
        "wind_gusts_10m_max",
        "sunrise",
        "sunset",
        "uv_index_max",
        "daylight_duration",
        "sunshine_duration",
    ],
    "hourly": [
        "temperature_2m",
        "relative_humidity_2m",
        "precipitation",
        "precipitation_probability",
        "rain",
        "showers",
        "weather_code",
        "cloud_cover",
        "wind_speed_10m",
        "wind_direction_10m",
        "wind_gusts_10m",
    ],
    "models": "gfs_seamless",
    "wind_speed_unit": "mph",
    "precipitation_unit": "inch",
    "temperature_unit": "fahrenheit",
    "forecast_days": 7,
}

# ---------------------------------------------------------------------------
# HTTP session — auto-retry on transient server errors
# ---------------------------------------------------------------------------

def build_http_session(
    total_retries: int = 3,
    backoff_factor: float = 0.5,
) -> requests.Session:
    retry_strategy = Retry(
        total=total_retries,
        backoff_factor=backoff_factor,
        # Retry on these HTTP status codes (4xx rate-limit + 5xx server errors)
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

# ---------------------------------------------------------------------------
# API fetch
# ---------------------------------------------------------------------------

def fetch_location(
    session: requests.Session,
    location: dict,
) -> tuple[dict, dict]:
    """Call the API for one location.

    Returns (response_body_dict, request_params_dict).
    Raises requests.RequestException on failure (after retries).
    """
    params = {
        **BASE_PARAMS,
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "timezone": location["timezone"],
    }
    log.info(
        "Fetching %-15s  lat=%-7s  lon=%s",
        location["name"],
        location["latitude"],
        location["longitude"],
    )
    resp = session.get(API_URL, params=params, timeout=API_TIMEOUT_SECONDS)
    resp.raise_for_status()
    return resp.json(), params

# ---------------------------------------------------------------------------
# Raw JSON persistence
# ---------------------------------------------------------------------------

RAW_DIR = Path("raw")


def save_raw_json(location_name: str, run_date: str, payload: dict) -> Path:
    """Write the API response to disk and return the file path."""
    RAW_DIR.mkdir(exist_ok=True)
    filepath = RAW_DIR / f"weather_{location_name}_{run_date}.json"
    with open(filepath, "w") as fh:
        json.dump(payload, fh, indent=2)
    log.info("Saved  %s", filepath)
    return filepath

# ---------------------------------------------------------------------------
# Postgres helpers
# ---------------------------------------------------------------------------

def get_pg_connection() -> psycopg2.extensions.connection:
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "weather_db"),
        user=os.getenv("POSTGRES_USER", "weather"),
        password=os.getenv("POSTGRES_PASSWORD", "weather"),
    )


_INSERT_SQL = """
    INSERT INTO raw.open_meteo_forecast
        (latitude, longitude, timezone, weather_model,
         source_url, request_params, response_body, load_id, ingest_source)
    VALUES
        (%(latitude)s, %(longitude)s, %(timezone)s, %(weather_model)s,
         %(source_url)s, %(request_params)s, %(response_body)s, %(load_id)s, %(ingest_source)s)
"""


def insert_to_postgres(
    conn: psycopg2.extensions.connection,
    location: dict,
    request_params: dict,
    response_body: dict,
    load_id: str,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            _INSERT_SQL,
            {
                "latitude": location["latitude"],
                "longitude": location["longitude"],
                "timezone": location["timezone"],
                "weather_model": request_params.get("models", "gfs_seamless"),
                "source_url": API_URL,
                "request_params": psycopg2.extras.Json(request_params),
                "response_body": psycopg2.extras.Json(response_body),
                "load_id": load_id,
                "ingest_source": "python",
            },
        )
    conn.commit()
    log.info("Inserted %-15s into raw.open_meteo_forecast", location["name"])

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    run_date = date.today().isoformat()
    load_id = str(uuid.uuid4())

    log.info("=" * 60)
    log.info("Extraction run  date=%s  load_id=%s", run_date, load_id)
    log.info("Locations: %d", len(LOCATIONS))
    log.info("=" * 60)

    # Connect to Postgres once; reuse across all locations
    try:
        conn = get_pg_connection()
        log.info("Connected to Postgres")
    except psycopg2.OperationalError as exc:
        log.error("Cannot connect to Postgres: %s", exc)
        log.error("Is the Docker container running?  docker compose up -d")
        raise SystemExit(1) from exc

    session = build_http_session()
    success: list[str] = []
    failed: list[str] = []

    for location in LOCATIONS:
        name = location["name"]
        try:
            # 1. Hit the API (retries built into session)
            response_body, request_params = fetch_location(session, location)

            # 2. Persist raw JSON to disk — this is the safety net
            save_raw_json(name, run_date, response_body)

            # 3. Load into Postgres (close to as-is)
            insert_to_postgres(conn, location, request_params, response_body, load_id)

            success.append(name)

        except requests.exceptions.Timeout:
            log.error("TIMEOUT  %s — skipping", name)
            failed.append(name)

        except requests.exceptions.HTTPError as exc:
            log.error("HTTP error  %s  status=%s — skipping", name, exc.response.status_code)
            failed.append(name)

        except requests.exceptions.RequestException as exc:
            log.error("Request error  %s: %s — skipping", name, exc)
            failed.append(name)

        except psycopg2.Error as exc:
            log.error("DB error  %s: %s — skipping", name, exc)
            conn.rollback()
            failed.append(name)

        except Exception as exc:  # noqa: BLE001
            log.error("Unexpected error  %s: %s — skipping", name, exc)
            failed.append(name)

    conn.close()

    log.info("=" * 60)
    log.info(
        "Done.  success=%d  failed=%d  %s",
        len(success),
        len(failed),
        failed if failed else "",
    )
    log.info("=" * 60)

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
