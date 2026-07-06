{{
    config(materialized='table')
}}

with daily as (

    select * from {{ ref('fct_daily_weather') }}

),

-- Calculate the cross-location average for every forecast date.
-- A location that is warmer/cooler than this average is anomalous.
with_cross_avg as (

    select
        *,
        round(avg(temperature_avg_f) over (partition by forecast_date), 2)   as cross_avg_temp_f,
        round(avg(temperature_max_f) over (partition by forecast_date), 2)   as cross_avg_high_f,
        round(avg(temperature_min_f) over (partition by forecast_date), 2)   as cross_avg_low_f,
        count(*)             over (partition by forecast_date)                as locations_on_date
    from daily

)

select
    location_name,
    state,
    city,
    forecast_date,

    -- actual temperatures
    temperature_avg_f,
    temperature_max_f,
    temperature_min_f,

    -- reference averages
    cross_avg_temp_f,
    cross_avg_high_f,
    cross_avg_low_f,

    -- anomaly deltas (positive = warmer than average)
    round(temperature_avg_f - cross_avg_temp_f, 2)              as avg_temp_anomaly_f,
    round(temperature_max_f - cross_avg_high_f, 2)              as high_temp_anomaly_f,
    round(temperature_min_f - cross_avg_low_f,  2)              as low_temp_anomaly_f,

    -- categorical label using ±2°F / ±5°F thresholds
    case
        when temperature_avg_f >= cross_avg_temp_f + 5  then 'much_warmer'
        when temperature_avg_f >= cross_avg_temp_f + 2  then 'warmer'
        when temperature_avg_f <= cross_avg_temp_f - 5  then 'much_cooler'
        when temperature_avg_f <= cross_avg_temp_f - 2  then 'cooler'
        else                                                 'near_average'
    end                                                         as temperature_anomaly_category,

    locations_on_date,

    -- lineage
    daily_weather_sk,
    ingested_at

from with_cross_avg
order by forecast_date, avg_temp_anomaly_f desc
