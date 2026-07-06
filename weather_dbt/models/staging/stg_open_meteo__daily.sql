{{
    config(materialized='view')
}}

with source as (

    select * from {{ source('raw', 'open_meteo_forecast') }}

),

unnested as (

    select
        f.forecast_id,
        f.ingested_at,
        f.latitude,
        f.longitude,
        f.timezone,
        f.weather_model,
        f.load_id,

        idx                                                                                                        as day_index,

        -- date string like "2026-07-05"
        (f.response_body -> 'daily' -> 'time'                           ->> (idx - 1))::date                      as forecast_date,

        -- weather classification
        (f.response_body -> 'daily' -> 'weather_code'                   ->> (idx - 1))::integer                   as weather_code,

        -- temperature (°F)
        (f.response_body -> 'daily' -> 'temperature_2m_max'             ->> (idx - 1))::numeric                   as temperature_max_f,
        (f.response_body -> 'daily' -> 'temperature_2m_min'             ->> (idx - 1))::numeric                   as temperature_min_f,
        (f.response_body -> 'daily' -> 'apparent_temperature_max'       ->> (idx - 1))::numeric                   as apparent_temp_max_f,
        (f.response_body -> 'daily' -> 'apparent_temperature_min'       ->> (idx - 1))::numeric                   as apparent_temp_min_f,

        -- precipitation
        (f.response_body -> 'daily' -> 'precipitation_sum'              ->> (idx - 1))::numeric                   as precipitation_sum_in,
        (f.response_body -> 'daily' -> 'precipitation_hours'            ->> (idx - 1))::numeric                   as precipitation_hours,
        (f.response_body -> 'daily' -> 'precipitation_probability_max'  ->> (idx - 1))::integer                   as precipitation_probability_max_pct,

        -- wind
        (f.response_body -> 'daily' -> 'wind_speed_10m_max'             ->> (idx - 1))::numeric                   as wind_speed_max_mph,
        (f.response_body -> 'daily' -> 'wind_gusts_10m_max'             ->> (idx - 1))::numeric                   as wind_gusts_max_mph,

        -- sun — ISO strings like "2026-07-05T06:34" (local time, no tz suffix)
        (f.response_body -> 'daily' -> 'sunrise'                        ->> (idx - 1))::timestamp                 as sunrise_ts,
        (f.response_body -> 'daily' -> 'sunset'                         ->> (idx - 1))::timestamp                 as sunset_ts,

        -- sky
        (f.response_body -> 'daily' -> 'uv_index_max'                   ->> (idx - 1))::numeric                   as uv_index_max,
        (f.response_body -> 'daily' -> 'daylight_duration'              ->> (idx - 1))::numeric                   as daylight_duration_s,
        (f.response_body -> 'daily' -> 'sunshine_duration'              ->> (idx - 1))::numeric                   as sunshine_duration_s

    from source as f,
        lateral generate_series(
            1,
            jsonb_array_length(f.response_body -> 'daily' -> 'time')
        ) as idx

)

select * from unnested
