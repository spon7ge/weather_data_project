# Screenshots

Add these three images to this folder for the README checkpoint:

| File | What to capture |
|------|-----------------|
| `airflow_dag_success.png` (or `.svg`) | Airflow UI → **weather_pipeline** DAG → latest run with all four tasks green |
| `dbt_lineage.png` (or `.svg`) | dbt docs lineage graph for `fct_hourly_weather` or project overview |
| `dashboard.png` (or `.svg`) | Power BI report page **or** `powerbi/dashboard_preview.html` in the browser |

SVG placeholders are committed; replace them with PNG screenshots for your final checkpoint.

Generate the HTML dashboard preview:

```bash
cd powerbi && pip install -r requirements.txt && python generate_dashboard_preview.py
open dashboard_preview.html
```
