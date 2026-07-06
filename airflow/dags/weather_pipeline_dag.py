"""
weather_pipeline_dag.py — Orchestrate the Open-Meteo weather pipeline.

Task flow:
  extract → load_check → dbt_run → dbt_test

Schedule: daily at 06:00 UTC.
Extract retries: 3 attempts with 2-minute backoff (API is the fragile step).
"""

from __future__ import annotations

import os
from datetime import timedelta

import pendulum
import psycopg2
from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.python import PythonOperator

# ---------------------------------------------------------------------------
# Paths & connection defaults (overridable via env in docker-compose)
# ---------------------------------------------------------------------------

PROJECT_DIR = os.environ.get("WEATHER_PROJECT_DIR", "/opt/weather_project")
DBT_DIR = f"{PROJECT_DIR}/weather_dbt"
DBT_PROFILES_DIR = os.environ.get("DBT_PROFILES_DIR", "/opt/airflow/config/dbt")
EXPECTED_LOCATIONS = 7

PG = {
    "host": os.environ.get("POSTGRES_HOST", "weather_postgres"),
    "port": int(os.environ.get("POSTGRES_PORT", "5432")),
    "dbname": os.environ.get("POSTGRES_DB", "weather_db"),
    "user": os.environ.get("POSTGRES_USER", "weather"),
    "password": os.environ.get("POSTGRES_PASSWORD", "weather"),
}


def _pg_connection():
    return psycopg2.connect(**PG)


def validate_raw_load(**_) -> None:
    """Confirm today's extract inserted rows for every location."""
    with _pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM raw.open_meteo_forecast
            WHERE ingested_at >= CURRENT_DATE
            """
        )
        (today_rows,) = cur.fetchone()

        cur.execute(
            """
            SELECT COUNT(DISTINCT (latitude, longitude))
            FROM raw.open_meteo_forecast
            WHERE ingested_at >= CURRENT_DATE
            """
        )
        (distinct_locations,) = cur.fetchone()

    if today_rows < EXPECTED_LOCATIONS:
        raise ValueError(
            f"Expected at least {EXPECTED_LOCATIONS} rows ingested today, found {today_rows}"
        )
    if distinct_locations < EXPECTED_LOCATIONS:
        raise ValueError(
            f"Expected {EXPECTED_LOCATIONS} distinct locations today, found {distinct_locations}"
        )


default_args = {
    "owner": "weather",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 0,
}

with DAG(
    dag_id="weather_pipeline",
    description="Open-Meteo extract → load check → dbt run → dbt test",
    schedule="0 6 * * *",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    tags=["weather", "dbt"],
    default_args=default_args,
) as dag:
    extract = BashOperator(
        task_id="extract",
        bash_command=f"cd {PROJECT_DIR} && python extract.py",
        retries=3,
        retry_delay=timedelta(minutes=2),
        retry_exponential_backoff=True,
        max_retry_delay=timedelta(minutes=10),
    )

    load_check = PythonOperator(
        task_id="load_check",
        python_callable=validate_raw_load,
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=(
            f"cd {DBT_DIR} && "
            f"dbt deps --profiles-dir {DBT_PROFILES_DIR} && "
            f"dbt run --profiles-dir {DBT_PROFILES_DIR}"
        ),
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"cd {DBT_DIR} && dbt test --profiles-dir {DBT_PROFILES_DIR}",
    )

    extract >> load_check >> dbt_run >> dbt_test
