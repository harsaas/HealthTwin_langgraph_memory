"""Create a demo semantic table with timestamps shifted to match time_series_metrics.

Why:
- Your food log embeddings are in ~Feb 2020, but your biometrics are in ~Jul 2016.
- For a cohesive demo, we clone the semantic timeline into a new table and shift
  its timestamps so tool lookups align with the biometrics window.

What it does:
- Creates `semantic_timeline_food_demo` with the same schema as `semantic_timeline_food`.
- Computes an offset = min(time_series_metrics.timestamp) - min(semantic_timeline_food.event_timestamp).
- Inserts all rows into the demo table with event_timestamp shifted by that offset.

Usage:
  .venv-1\\Scripts\\python.exe pipelines\\create_semantic_food_demo_table.py

Then set env var for the agent/demo run:
  $env:SEMANTIC_TABLE_NAME = "semantic_timeline_food_demo"
"""

from __future__ import annotations

import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=REPO_ROOT / ".env", override=True)

DATABASE_URL = os.getenv("DATABASE_URL")

SRC_TABLE = "semantic_timeline_food"
DEMO_TABLE = "semantic_timeline_food_demo"


def main() -> None:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set. Create a .env or set env var DATABASE_URL.")

    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*), MIN(event_timestamp), MAX(event_timestamp) FROM {SRC_TABLE};")
            src_count, src_min, src_max = cur.fetchone()

            cur.execute("SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM time_series_metrics;")
            ts_count, ts_min, ts_max = cur.fetchone()

            if not src_min or not ts_min:
                raise RuntimeError(
                    "Cannot compute shift offset. Ensure both semantic_timeline_food and time_series_metrics have data."
                )

            offset = ts_min - src_min  # timedelta

            cur.execute(f"CREATE TABLE IF NOT EXISTS {DEMO_TABLE} (LIKE {SRC_TABLE} INCLUDING ALL);")
            cur.execute(f"TRUNCATE TABLE {DEMO_TABLE};")

            cur.execute(
                f"""
                INSERT INTO {DEMO_TABLE} (event_timestamp, text_data, embedding)
                SELECT event_timestamp + %s, text_data, embedding
                FROM {SRC_TABLE}
                ORDER BY event_timestamp ASC;
                """,
                (offset,),
            )

            cur.execute(f"SELECT COUNT(*), MIN(event_timestamp), MAX(event_timestamp) FROM {DEMO_TABLE};")
            demo_count, demo_min, demo_max = cur.fetchone()

        conn.commit()

        print("Created demo semantic table with shifted timestamps:")
        print(f"- Source {SRC_TABLE}: count={src_count}, min={src_min}, max={src_max}")
        print(f"- Metrics time_series_metrics: count={ts_count}, min={ts_min}, max={ts_max}")
        print(f"- Offset applied: {offset}")
        print(f"- Demo {DEMO_TABLE}: count={demo_count}, min={demo_min}, max={demo_max}")
        print("\nNext:")
        print('  PowerShell:  $env:SEMANTIC_TABLE_NAME = "semantic_timeline_food_demo"')
        print("  Run demo:    .venv-1\\Scripts\\python.exe src\\prompts\\test_run.py")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
