{{
    config(materialized='table')
}}

with daily as (

    select * from {{ ref('fct_daily_weather') }}

),

per_day_agg as (

    select
        forecast_date,
        count(distinct location_name)                       as location_count,
        round(avg(temperature_avg_f),       1)              as avg_temp_f,
        round(avg(temperature_max_f),       1)              as avg_high_f,
        round(avg(temperature_min_f),       1)              as avg_low_f,
        max(temperature_max_f)                              as hottest_high_f,
        min(temperature_min_f)                              as coldest_low_f,
        round(avg(temperature_range_f),     1)              as avg_temp_range_f,
        round(avg(precipitation_sum_in),    3)              as avg_precipitation_in,
        max(precipitation_sum_in)                           as max_precipitation_in,
        round(avg(wind_speed_max_mph),      1)              as avg_max_wind_mph,
        max(wind_gusts_max_mph)                             as peak_gust_mph,
        round(avg(uv_index_max),            1)              as avg_uv_index,
        round(avg(sunshine_hours),          2)              as avg_sunshine_hours,
        round(avg(daylight_hours),          2)              as avg_daylight_hours
    from daily
    group by forecast_date

),

hottest as (

    select distinct on (forecast_date)
        forecast_date,
        location_name   as hottest_city,
        temperature_max_f as hottest_city_high_f
    from daily
    order by forecast_date, temperature_max_f desc

),

coldest as (

    select distinct on (forecast_date)
        forecast_date,
        location_name   as coldest_city,
        temperature_min_f as coldest_city_low_f
    from daily
    order by forecast_date, temperature_min_f asc

),

wettest as (

    select distinct on (forecast_date)
        forecast_date,
        location_name   as wettest_city,
        precipitation_sum_in as wettest_city_precip_in
    from daily
    order by forecast_date, precipitation_sum_in desc

)

select
    a.forecast_date,
    a.location_count,
    a.avg_temp_f,
    a.avg_high_f,
    a.avg_low_f,
    a.hottest_high_f,
    h.hottest_city,
    h.hottest_city_high_f,
    a.coldest_low_f,
    c.coldest_city,
    c.coldest_city_low_f,
    a.avg_temp_range_f,
    a.avg_precipitation_in,
    a.max_precipitation_in,
    w.wettest_city,
    w.wettest_city_precip_in,
    a.avg_max_wind_mph,
    a.peak_gust_mph,
    a.avg_uv_index,
    a.avg_sunshine_hours,
    a.avg_daylight_hours
from per_day_agg     as a
left join hottest    as h on a.forecast_date = h.forecast_date
left join coldest    as c on a.forecast_date = c.forecast_date
left join wettest    as w on a.forecast_date = w.forecast_date
order by a.forecast_date
