#!/usr/bin/env python3
"""
Generate a standalone HTML dashboard preview from analytics marts.

Mirrors the Power BI visuals in powerbi/README.md — useful on Mac where
Power BI Desktop is unavailable, or as a quick checkpoint before building
the .pbix in Power BI.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import psycopg2

PG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "dbname": os.getenv("POSTGRES_DB", "weather_db"),
    "user": os.getenv("POSTGRES_USER", "weather"),
    "password": os.getenv("POSTGRES_PASSWORD", "weather"),
}

OUT = Path(__file__).parent / "dashboard_preview.html"

LOCATION_ORDER = [
    "los_angeles",
    "new_york",
    "chicago",
    "miami",
    "seattle",
    "denver",
    "austin",
]

COLORS = {
    "los_angeles": "#E4572E",
    "new_york": "#4C78A8",
    "chicago": "#72B7B2",
    "miami": "#F58518",
    "seattle": "#54A24B",
    "denver": "#B279A2",
    "austin": "#EECA3B",
}

ANOMALY_COLORS = {
    "much_warmer": "#B22222",
    "warmer": "#E4572E",
    "near_average": "#888888",
    "cooler": "#4C78A8",
    "much_cooler": "#1D4E89",
}


def fetch(sql: str) -> pd.DataFrame:
    with psycopg2.connect(**PG) as conn:
        return pd.read_sql(sql, conn)


def chart_hourly_temps(hourly: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for loc in LOCATION_ORDER:
        subset = hourly[hourly["location_name"] == loc].sort_values("observation_hour")
        if subset.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=subset["observation_hour"],
                y=subset["temperature_2m_f"],
                mode="lines",
                name=loc.replace("_", " ").title(),
                line=dict(color=COLORS.get(loc, "#333"), width=2),
            )
        )
    fig.update_layout(
        title="Hourly temperature trend by location",
        xaxis_title="Observation hour (UTC)",
        yaxis_title="Temperature (°F)",
        legend=dict(orientation="h", y=-0.25),
        height=420,
        margin=dict(b=100),
    )
    return fig


def chart_anomalies(anomalies: pd.DataFrame) -> go.Figure:
    latest = anomalies["forecast_date"].max()
    subset = anomalies[anomalies["forecast_date"] == latest].copy()
    subset["location_label"] = subset["location_name"].str.replace("_", " ").str.title()
    subset = subset.sort_values("avg_temp_anomaly_f", ascending=True)
    bar_colors = subset["temperature_anomaly_category"].map(ANOMALY_COLORS).fillna("#888")

    fig = go.Figure(
        go.Bar(
            x=subset["avg_temp_anomaly_f"],
            y=subset["location_label"],
            orientation="h",
            marker_color=bar_colors,
            text=subset["avg_temp_anomaly_f"].map(lambda v: f"{v:+.1f}°F"),
            textposition="outside",
            hovertemplate=(
                "%{y}<br>Anomaly: %{x:+.1f}°F<br>Actual avg: %{customdata[0]:.1f}°F"
                "<br>Cross-loc avg: %{customdata[1]:.1f}°F<extra></extra>"
            ),
            customdata=subset[["temperature_avg_f", "cross_avg_temp_f"]].values,
        )
    )
    fig.add_vline(x=0, line_dash="dash", line_color="#666")
    fig.update_layout(
        title=f"Daily temperature anomaly vs cross-location average ({latest})",
        xaxis_title="Avg temp anomaly (°F)",
        yaxis_title="",
        height=380,
    )
    return fig


def chart_precipitation(daily: pd.DataFrame) -> go.Figure:
    daily = daily.copy()
    daily["location_label"] = daily["location_name"].str.replace("_", " ").str.title()
    fig = go.Figure()
    for forecast_date, group in daily.groupby("forecast_date"):
        fig.add_trace(
            go.Bar(
                x=group["location_label"],
                y=group["precipitation_sum_in"],
                name=str(forecast_date),
            )
        )
    fig.update_layout(
        title="Daily precipitation by location",
        xaxis_title="Location",
        yaxis_title="Precipitation (in)",
        legend_title="Forecast date",
        barmode="group",
        height=400,
    )
    return fig


def chart_anomaly_heatmap(anomalies: pd.DataFrame) -> go.Figure:
    pivot = anomalies.pivot(
        index="location_name",
        columns="forecast_date",
        values="avg_temp_anomaly_f",
    )
    pivot.index = [x.replace("_", " ").title() for x in pivot.index]
    pivot = pivot.reindex([x.replace("_", " ").title() for x in LOCATION_ORDER if x in anomalies["location_name"].values])

    fig = go.Figure(
        go.Heatmap(
            z=pivot.values,
            x=[str(c) for c in pivot.columns],
            y=pivot.index.tolist(),
            colorscale="RdBu_r",
            zmid=0,
            colorbar_title="°F vs avg",
            hovertemplate="Location: %{y}<br>Date: %{x}<br>Anomaly: %{z:+.1f}°F<extra></extra>",
        )
    )
    fig.update_layout(
        title="Temperature anomaly heatmap (location × date)",
        xaxis_title="Forecast date",
        yaxis_title="",
        height=360,
    )
    return fig


def kpi_cards(summary: pd.DataFrame, daily: pd.DataFrame) -> str:
    latest = summary["forecast_date"].max()
    row = summary[summary["forecast_date"] == latest].iloc[0]
    total_precip = daily[daily["forecast_date"] == latest]["precipitation_sum_in"].sum()
    cards = [
        ("Forecast dates", str(len(summary))),
        ("Locations tracked", str(int(row["location_count"]))),
        ("Network avg temp", f"{row['avg_temp_f']:.1f}°F"),
        ("Hottest city", f"{row['hottest_city'].replace('_', ' ').title()} ({row['hottest_city_high_f']:.0f}°F)"),
        ("Wettest city", f"{row['wettest_city'].replace('_', ' ').title()} ({row['wettest_city_precip_in']:.2f}\")"),
        ("Total precip (all cities)", f"{total_precip:.2f}\""),
    ]
    html = '<div class="kpi-row">'
    for label, value in cards:
        html += f'<div class="kpi"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div></div>'
    html += "</div>"
    return html


def build_html(figures: list[go.Figure], kpis: str) -> str:
    charts = "\n".join(
        f'<div class="chart">{pio.to_html(fig, include_plotlyjs=False, full_html=False)}</div>'
        for fig in figures
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Weather Pipeline — Analytics Dashboard</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    body {{ font-family: "Segoe UI", system-ui, sans-serif; margin: 0; background: #f5f6f8; color: #1a1a1a; }}
    header {{ background: #1d3557; color: #fff; padding: 1.25rem 2rem; }}
    header h1 {{ margin: 0 0 .25rem; font-size: 1.5rem; }}
    header p {{ margin: 0; opacity: .85; font-size: .95rem; }}
    main {{ max-width: 1200px; margin: 0 auto; padding: 1.5rem; }}
    .kpi-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: .75rem; margin-bottom: 1.5rem; }}
    .kpi {{ background: #fff; border-radius: 8px; padding: 1rem; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
    .kpi-label {{ font-size: .75rem; text-transform: uppercase; letter-spacing: .04em; color: #666; }}
    .kpi-value {{ font-size: 1.15rem; font-weight: 600; margin-top: .35rem; }}
    .chart {{ background: #fff; border-radius: 8px; padding: .5rem; margin-bottom: 1.25rem; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
    footer {{ text-align: center; padding: 1rem; color: #666; font-size: .85rem; }}
  </style>
</head>
<body>
  <header>
    <h1>US Weather Forecast Dashboard</h1>
    <p>Live from PostgreSQL <code>analytics</code> schema — same marts as Power BI</p>
  </header>
  <main>
    {kpis}
    {charts}
  </main>
  <footer>
    Source: analytics.fct_hourly_weather, fct_daily_weather, temperature_anomalies, daily_temperature_summary
  </footer>
</body>
</html>"""


def main() -> None:
    hourly = fetch(
        """
        SELECT location_name, observation_hour, temperature_2m_f
        FROM analytics.fct_hourly_weather
        ORDER BY observation_hour
        """
    )
    daily = fetch(
        """
        SELECT location_name, forecast_date, precipitation_sum_in
        FROM analytics.fct_daily_weather
        ORDER BY forecast_date, location_name
        """
    )
    anomalies = fetch(
        """
        SELECT location_name, forecast_date, temperature_avg_f, cross_avg_temp_f,
               avg_temp_anomaly_f, temperature_anomaly_category
        FROM analytics.temperature_anomalies
        ORDER BY forecast_date, location_name
        """
    )
    summary = fetch("SELECT * FROM analytics.daily_temperature_summary ORDER BY forecast_date")

    figures = [
        chart_hourly_temps(hourly),
        chart_anomalies(anomalies),
        chart_precipitation(daily),
        chart_anomaly_heatmap(anomalies),
    ]
    html = build_html(figures, kpi_cards(summary, daily))
    OUT.write_text(html, encoding="utf-8")
    print(f"Wrote {OUT}  ({len(hourly)} hourly / {len(daily)} daily rows)")


if __name__ == "__main__":
    main()
