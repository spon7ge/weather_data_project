{{
    config(materialized='view')
}}

with daily as (

    select * from {{ ref('stg_open_meteo__daily') }}

),

locations as (

    select * from {{ ref('locations') }}

),

-- Keep only the most recently ingested row per (location, date).
deduped as (

    select distinct on (latitude, longitude, forecast_date)
        *
    from daily
    order by latitude, longitude, forecast_date, ingested_at desc

),

enriched as (

    select
        -- identifiers
        d.forecast_id,
        d.load_id,
        d.ingested_at,

        -- location
        coalesce(l.location_name, d.latitude::text || '_' || d.longitude::text)   as location_name,
        coalesce(l.state,         'UNKNOWN')                                       as state,
        coalesce(l.city,          d.latitude::text || '_' || d.longitude::text)    as city,
        d.latitude,
        d.longitude,
        d.timezone,
        d.weather_model,

        -- time
        d.forecast_date,
        d.day_index,

        -- weather classification
        d.weather_code,

        -- temperature
        d.temperature_max_f,
        d.temperature_min_f,
        round((d.temperature_max_f + d.temperature_min_f) / 2.0, 1)               as temperature_avg_f,
        round(d.temperature_max_f - d.temperature_min_f, 1)                       as temperature_range_f,
        d.apparent_temp_max_f,
        d.apparent_temp_min_f,

        -- precipitation
        d.precipitation_sum_in,
        d.precipitation_hours,
        d.precipitation_probability_max_pct,

        -- wind
        d.wind_speed_max_mph,
        d.wind_gusts_max_mph,

        -- sun
        d.sunrise_ts,
        d.sunset_ts,
        d.uv_index_max,
        round(d.daylight_duration_s / 3600.0,  2)                                  as daylight_hours,
        round(d.sunshine_duration_s / 3600.0,  2)                                  as sunshine_hours,
        case
            when d.daylight_duration_s > 0
            then round(d.sunshine_duration_s / d.daylight_duration_s * 100.0, 1)
        end                                                                         as sunshine_pct

    from deduped as d
    left join locations as l
        on d.latitude  = l.latitude
        and d.longitude = l.longitude

)

select * from enriched
