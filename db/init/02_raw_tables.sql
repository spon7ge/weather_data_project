-- =============================================================================
-- raw schema — landing tables
--
-- Design principle: append-only, preserve the API payload exactly as received.
-- Downstream parsing, typing, and business logic belong in dbt (analytics).
-- =============================================================================

CREATE TABLE raw.open_meteo_forecast (
    forecast_id       BIGSERIAL PRIMARY KEY,
    ingested_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- request context (denormalized for filtering; full params also in JSON)
    latitude          DOUBLE PRECISION NOT NULL,
    longitude         DOUBLE PRECISION NOT NULL,
    timezone          TEXT,
    weather_model     TEXT,

    source_url        TEXT NOT NULL DEFAULT 'https://api.open-meteo.com/v1/forecast',
    request_params    JSONB NOT NULL,
    response_body     JSONB NOT NULL,

    -- optional lineage fields for scheduled / batch loads
    load_id           UUID,
    ingest_source     TEXT NOT NULL DEFAULT 'python'
);

COMMENT ON TABLE raw.open_meteo_forecast IS
  'One row per API call. response_body is the untouched JSON returned by Open-Meteo.';

COMMENT ON COLUMN raw.open_meteo_forecast.request_params IS
  'Query parameters sent to the API (latitude, longitude, daily, hourly, etc.).';

COMMENT ON COLUMN raw.open_meteo_forecast.response_body IS
  'Full API response JSON. hourly and daily time series live inside this document.';

CREATE INDEX idx_open_meteo_forecast_ingested_at
    ON raw.open_meteo_forecast (ingested_at DESC);

CREATE INDEX idx_open_meteo_forecast_location
    ON raw.open_meteo_forecast (latitude, longitude);

CREATE INDEX idx_open_meteo_forecast_response_body
    ON raw.open_meteo_forecast USING GIN (response_body);
