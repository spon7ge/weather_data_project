{{
    config(materialized='view')
}}

with hourly as (

    select * from {{ ref('stg_open_meteo__hourly') }}

),

locations as (

    select * from {{ ref('locations') }}

),

-- Keep only the most recently ingested row per (location, hour).
-- This handles reruns of extract.py on the same day gracefully.
deduped as (

    select distinct on (latitude, longitude, observation_hour)
        *
    from hourly
    order by latitude, longitude, observation_hour, ingested_at desc

),

enriched as (

    select
        -- identifiers
        d.forecast_id,
        d.load_id,
        d.ingested_at,

        -- location
        coalesce(l.location_name, d.latitude::text || '_' || d.longitude::text)  as location_name,
        coalesce(l.state,         'UNKNOWN')                                      as state,
        coalesce(l.city,          d.latitude::text || '_' || d.longitude::text)   as city,
        d.latitude,
        d.longitude,
        d.timezone,
        d.weather_model,

        -- time
        d.observation_hour,
        d.hour_index,
        d.observation_hour::date                                                  as observation_date,
        extract(hour  from d.observation_hour)::integer                           as hour_of_day,
        extract(dow   from d.observation_hour)::integer                           as day_of_week,   -- 0 = Sunday
        (extract(dow  from d.observation_hour) in (0, 6))                         as is_weekend,

        -- temperature
        d.temperature_2m_f,
        round((d.temperature_2m_f - 32) * 5.0 / 9.0, 1)                          as temperature_2m_c,

        -- moisture
        d.relative_humidity_pct,
        d.precipitation_in,
        d.precipitation_probability_pct,
        d.rain_in,
        d.showers_in,

        -- sky & wind
        d.weather_code,
        d.cloud_cover_pct,
        d.wind_speed_mph,
        d.wind_direction_deg,
        d.wind_gusts_mph,

        -- 3-hour rolling average temperature per location
        round(
            avg(d.temperature_2m_f) over (
                partition by d.latitude, d.longitude
                order by     d.observation_hour
                rows between 2 preceding and current row
            ),
            2
        )                                                                          as temp_3hr_rolling_avg_f

    from deduped as d
    left join locations as l
        on d.latitude  = l.latitude
        and d.longitude = l.longitude

)

select * from enriched
