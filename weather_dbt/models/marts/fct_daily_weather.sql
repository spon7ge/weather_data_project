{{
    config(materialized='table')
}}

with enriched as (

    select * from {{ ref('int_weather__daily_enriched') }}

)

select
    {{ dbt_utils.generate_surrogate_key(['location_name', 'forecast_date']) }}  as daily_weather_sk,

    -- location
    location_name,
    state,
    city,
    latitude,
    longitude,
    timezone,
    weather_model,

    -- time
    forecast_date,

    -- weather classification
    weather_code,

    -- temperature
    temperature_max_f,
    temperature_min_f,
    temperature_avg_f,
    temperature_range_f,
    apparent_temp_max_f,
    apparent_temp_min_f,

    -- precipitation
    precipitation_sum_in,
    precipitation_hours,
    precipitation_probability_max_pct,

    -- wind
    wind_speed_max_mph,
    wind_gusts_max_mph,

    -- sun
    sunrise_ts,
    sunset_ts,
    uv_index_max,
    daylight_hours,
    sunshine_hours,
    sunshine_pct,

    -- lineage
    forecast_id,
    load_id,
    ingested_at

from enriched
