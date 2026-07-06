# Power BI — Weather Pipeline Dashboard

Connect Power BI directly to the **analytics** schema in Postgres. All visuals below use dbt marts — no raw JSON parsing in Power BI.

## Connection

| Setting  | Value        |
|----------|--------------|
| Server   | `localhost`  |
| Port     | `5432`       |
| Database | `weather_db` |
| User     | `weather`    |
| Password | `weather`    |

**Quick start (Windows):** double-click `weather_postgres.pbids` to open Power BI Desktop with the connection pre-filled. Then authenticate with the credentials above and select these tables from the **analytics** schema:

- `fct_hourly_weather`
- `fct_daily_weather`
- `temperature_anomalies`
- `daily_temperature_summary`
- `locations` (seed reference)

> **Mac note:** Power BI Desktop is Windows-only. Use a Windows VM, Power BI Service with an on-prem gateway, or run `python generate_dashboard_preview.py` for a browser dashboard on the same Postgres data.

## Dashboard story

**Question:** *How do forecast temperatures and precipitation compare across seven US cities this week?*

Keep the page to one screen — four visuals plus optional KPI cards.

---

### 1. Hourly temperature trend by location

| Field | Value |
|-------|-------|
| Visual | **Line chart** |
| Table | `fct_hourly_weather` |
| X-axis | `observation_hour` |
| Y-axis | `temperature_2m_f` (average) |
| Legend | `location_name` |

**Tip:** Format Y-axis as whole numbers with °F suffix. Sort legend alphabetically or by latitude.

---

### 2. Daily anomaly vs cross-location average

| Field | Value |
|-------|-------|
| Visual | **Clustered bar chart** |
| Table | `temperature_anomalies` |
| X-axis | `location_name` |
| Y-axis | `avg_temp_anomaly_f` |
| Legend / small multiples | `forecast_date` |
| Color | `temperature_anomaly_category` |

Add a **constant line at 0** on the Y-axis. Positive values = warmer than the network average that day.

Optional DAX measure (copy into a measure):

```dax
Anomaly Label =
VAR delta = SELECTEDVALUE ( temperature_anomalies[avg_temp_anomaly_f] )
RETURN
    IF ( delta > 0, "+" & FORMAT ( delta, "0.0" ) & "°F warmer", FORMAT ( delta, "0.0" ) & "°F" )
```

---

### 3. Precipitation patterns by location

| Field | Value |
|-------|-------|
| Visual | **Clustered column chart** |
| Table | `fct_daily_weather` |
| X-axis | `location_name` |
| Y-axis | `precipitation_sum_in` (sum) |
| Legend | `forecast_date` |

Sort locations by total precipitation descending to highlight the wettest cities.

---

### 4. Anomaly heatmap (location × date)

| Field | Value |
|-------|-------|
| Visual | **Matrix** with conditional formatting |
| Table | `temperature_anomalies` |
| Rows | `location_name` |
| Columns | `forecast_date` |
| Values | `avg_temp_anomaly_f` |

Apply a diverging color scale (blue ← 0 → red).

---

### 5. KPI cards (optional)

Use `daily_temperature_summary` for headline numbers:

| Card | Field |
|------|-------|
| Network avg temp | `avg_temp_f` (latest `forecast_date`) |
| Hottest city | `hottest_city` + `hottest_city_high_f` |
| Wettest city | `wettest_city` + `wettest_city_precip_in` |

Filter all cards to the latest `forecast_date` with a page-level filter or DAX:

```dax
Latest Forecast Date = MAX ( daily_temperature_summary[forecast_date] )
```

---

## Build checklist

1. `docker compose up -d` — Postgres running with analytics tables populated
2. Open `weather_postgres.pbids` (or connect manually)
3. Import the five analytics tables (Import mode recommended for this dataset size)
4. Add the four visuals above to one page
5. Title the report **US Weather Forecast — Analytics**
6. Save as `weather_dashboard.pbix`
7. Screenshot the report page for your checkpoint

## HTML preview (Mac / quick checkpoint)

```bash
cd powerbi
pip install -r requirements.txt
python generate_dashboard_preview.py
open dashboard_preview.html
```

This reads the same Postgres marts and renders equivalent charts in the browser.

## Data model (no relationships required)

All marts share `location_name` and date fields but are intentionally denormalized — each visual uses a single table. No star-schema joins needed for this dashboard.

| Table | Rows (approx) | Use |
|-------|---------------|-----|
| `fct_hourly_weather` | ~1,200 | Hourly temp lines |
| `fct_daily_weather` | ~50 | Precipitation columns |
| `temperature_anomalies` | ~50 | Anomaly bars / heatmap |
| `daily_temperature_summary` | ~7 | KPI cards |
