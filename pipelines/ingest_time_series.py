import os
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import psycopg2
from psycopg2 import OperationalError
from psycopg2.extras import execute_batch
from dotenv import load_dotenv

PROCESSED_DIR = "data/processed"


def _load_database_url() -> str:
    repo_root = Path(__file__).resolve().parents[1]
    env_path = repo_root / ".env"
    load_dotenv(dotenv_path=env_path, override=True)
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not set. Add it to .env (repo root) or export it in your shell."
        )
    return database_url


def _describe_db_target(database_url: str) -> str:
    try:
        parsed = urlparse(database_url)
        host = parsed.hostname or "(unknown-host)"
        port = parsed.port or 5432
        db = (parsed.path or "").lstrip("/") or "(unknown-db)"
        return f"{host}:{port}/{db}"
    except Exception:
        return "(unparseable DATABASE_URL)"


def ingest_metrics() -> None:
    database_url = _load_database_url()

    print("Loading cleaned CSV files...")
    glucose_df = pd.read_csv(os.path.join(PROCESSED_DIR, "cleaned_glucose.csv"))
    heart_rate_df = pd.read_csv(os.path.join(PROCESSED_DIR, "cleaned_heart_rate.csv"))

    df_combined = (
        pd.merge(glucose_df, heart_rate_df, on="timestamp", how="outer")
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
    df_combined["timestamp"] = pd.to_datetime(df_combined["timestamp"], errors="coerce")
    df_combined["glucose_mg_dl"] = pd.to_numeric(df_combined.get("glucose_mg_dl"), errors="coerce")
    df_combined["heart_rate_bpm"] = pd.to_numeric(df_combined.get("heart_rate_bpm"), errors="coerce")

    # Replace NaN/NaT with real Python None so Postgres gets NULLs.
    df_to_insert = df_combined[["timestamp", "glucose_mg_dl", "heart_rate_bpm"]]
    df_to_insert = df_to_insert.astype(object).where(pd.notnull(df_to_insert), None)

    print(f"Loaded {len(df_to_insert)} combined records.")
    print("Ingesting combined data into SQL database...")

    target = _describe_db_target(database_url)
    print(f"Connecting to PostgreSQL at {target}...")
    try:
        conn = psycopg2.connect(database_url, connect_timeout=10)
    except OperationalError as exc:
        raise OperationalError(
            f"Could not connect to PostgreSQL at {target}. "
            "Verify the Neon DATABASE_URL, network access, and sslmode settings."
        ) from exc

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS time_series_metrics (
                        id SERIAL PRIMARY KEY,
                        timestamp TIMESTAMPTZ NOT NULL,
                        glucose_mg_dl DOUBLE PRECISION,
                        heart_rate_bpm DOUBLE PRECISION,
                        CONSTRAINT time_series_metrics_timestamp_key UNIQUE (timestamp)
                    );
                    """
                )

                # If the table already exists with INTEGER columns from a prior run,
                # widen them to DOUBLE PRECISION to avoid numeric conversion issues.
                cur.execute(
                    """
                    ALTER TABLE time_series_metrics
                        ALTER COLUMN glucose_mg_dl TYPE DOUBLE PRECISION USING glucose_mg_dl::double precision,
                        ALTER COLUMN heart_rate_bpm TYPE DOUBLE PRECISION USING heart_rate_bpm::double precision;
                    """
                )

                insert_query = """
                    INSERT INTO time_series_metrics (timestamp, glucose_mg_dl, heart_rate_bpm)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (timestamp) DO UPDATE SET
                        glucose_mg_dl = EXCLUDED.glucose_mg_dl,
                        heart_rate_bpm = EXCLUDED.heart_rate_bpm;
                """

                records = df_to_insert.values.tolist()
                print("Bulk-inserting combined biometrics into PostgreSQL...")
                execute_batch(cur, insert_query, records, page_size=2000)

        print(f"Successfully ingested {len(df_to_insert)} records into PostgreSQL.")
    finally:
        conn.close()
        print("Database connection closed.")


if __name__ == "__main__":
    ingest_metrics()