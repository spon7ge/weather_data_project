-- =============================================================================
-- weather_data_project — PostgreSQL schema bootstrap
--
-- raw       : untouched landing zone for API JSON (written by Python ingest)
-- analytics : transformed models built by dbt (read by BI tools)
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS analytics;

COMMENT ON SCHEMA raw IS
  'Landing zone. Stores full, unmodified Open-Meteo API responses as JSONB.';

COMMENT ON SCHEMA analytics IS
  'Transformation zone. dbt builds staging, intermediate, and mart models here.';
