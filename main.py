import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv("POSTGRES_HOST", "localhost"),
    port=os.getenv("POSTGRES_PORT", "5432"),
    dbname=os.getenv("POSTGRES_DB", "weather_db"),
    user=os.getenv("POSTGRES_USER", "weather"),
    password=os.getenv("POSTGRES_PASSWORD", "weather"),
)

with conn.cursor() as cur:
    cur.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name IN ('raw', 'analytics')")
    print("Schemas:", [row[0] for row in cur.fetchall()])

conn.close()