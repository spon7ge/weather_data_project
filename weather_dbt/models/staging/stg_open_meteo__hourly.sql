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

        -- 1-based position in the array; cast to 0-based index when extracting values
        idx                                                                                              as hour_index,

        -- timestamp strings in the API look like "2026-07-05T14:00"
        (f.response_body -> 'hourly' -> 'time'                     ->> (idx - 1))::timestamp            as observation_hour,

        -- temperature & humidity
        (f.response_body -> 'hourly' -> 'temperature_2m'           ->> (idx - 1))::numeric              as temperature_2m_f,
        (f.response_body -> 'hourly' -> 'relative_humidity_2m'     ->> (idx - 1))::integer              as relative_humidity_pct,

        -- precipitation
        (f.response_body -> 'hourly' -> 'precipitation'            ->> (idx - 1))::numeric              as precipitation_in,
        (f.response_body -> 'hourly' -> 'precipitation_probability' ->> (idx - 1))::integer             as precipitation_probability_pct,
        (f.response_body -> 'hourly' -> 'rain'                     ->> (idx - 1))::numeric              as rain_in,
        (f.response_body -> 'hourly' -> 'showers'                  ->> (idx - 1))::numeric              as showers_in,

        -- sky & wind
        (f.response_body -> 'hourly' -> 'weather_code'             ->> (idx - 1))::integer              as weather_code,
        (f.response_body -> 'hourly' -> 'cloud_cover'              ->> (idx - 1))::integer              as cloud_cover_pct,
        (f.response_body -> 'hourly' -> 'wind_speed_10m'           ->> (idx - 1))::numeric              as wind_speed_mph,
        (f.response_body -> 'hourly' -> 'wind_direction_10m'       ->> (idx - 1))::integer              as wind_direction_deg,
        (f.response_body -> 'hourly' -> 'wind_gusts_10m'           ->> (idx - 1))::numeric              as wind_gusts_mph

    from source as f,
        lateral generate_series(
            1,
            jsonb_array_length(f.response_body -> 'hourly' -> 'time')
        ) as idx

)

select * from unnested
