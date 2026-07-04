-- =============================================================================
-- analytics schema — dbt target
--
-- dbt will create objects here, typically:
--
--   staging/     stg_open_meteo__hourly, stg_open_meteo__daily
--   intermediate/  int_weather__hourly_enriched (optional)
--   marts/       fct_hourly_weather, dim_locations, agg_daily_weather
--
-- This file only documents the intended layout; dbt owns all DDL in analytics.
-- =============================================================================

COMMENT ON SCHEMA analytics IS
  'dbt models: staging → intermediate → marts. BI tools connect here, not raw.';
