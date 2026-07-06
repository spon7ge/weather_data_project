{{
    config(materialized='table')
}}

with enriched as (

    select * from {{ ref('int_weather__hourly_enriched') }}

)

select
    {{ dbt_utils.generate_surrogate_key(['location_name', 'observation_hour']) }}  as hourly_weather_sk,

    -- location
    location_name,
    state,
    city,
    latitude,
    longitude,
    timezone,
    weather_model,

    -- time
    observation_hour,
    observation_date,
    hour_of_day,
    day_of_week,
    is_weekend,

    -- temperature
    temperature_2m_f,
    temperature_2m_c,
    temp_3hr_rolling_avg_f,

    -- moisture
    relative_humidity_pct,
    precipitation_in,
    precipitation_probability_pct,
    rain_in,
    showers_in,

    -- sky & wind
    weather_code,
    cloud_cover_pct,
    wind_speed_mph,
    wind_direction_deg,
    wind_gusts_mph,

    -- lineage
    forecast_id,
    load_id,
    ingested_at

from enriched
