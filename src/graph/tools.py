import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re

import psycopg2
from pgvector.psycopg2 import register_vector
from langchain_openai import OpenAIEmbeddings
from langchain_core.tools import tool
from dotenv import load_dotenv

# Load .env deterministically from repo root
repo_root = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=repo_root / ".env", override=True)
DATABASE_URL = os.getenv("DATABASE_URL")

# You can override this at runtime for demos:
#   PowerShell: $env:SEMANTIC_TABLE_NAME = "semantic_timeline_food_demo"
SEMANTIC_TABLE_NAME = os.getenv("SEMANTIC_TABLE_NAME", "semantic_timeline_food").strip() or "semantic_timeline_food"

def get_connection():
    return psycopg2.connect(DATABASE_URL)


_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def _dataset_reference_now(cur) -> datetime:
    """Use the most recent event in the dataset as the reference 'now'."""
    cur.execute(f"SELECT MAX(event_timestamp) FROM {SEMANTIC_TABLE_NAME};")
    row = cur.fetchone()
    if row and row[0]:
        return row[0]
    return datetime.now()


def _extract_time_window(question: str, reference_now: datetime) -> tuple[datetime, datetime] | None:
    """Return a [start, end) window derived from the question, or None if no time intent detected."""
    q = question.strip().lower()

    # Explicit date (common formats)
    explicit = re.search(r"(\d{4}-\d{2}-\d{2})", q)
    if explicit:
        day = datetime.fromisoformat(explicit.group(1)).date()
        start = datetime.combine(day, datetime.min.time(), tzinfo=reference_now.tzinfo)
        end = start + timedelta(days=1)
        return start, end

    explicit_us = re.search(r"(\d{1,2}/\d{1,2}/\d{4})", q)
    if explicit_us:
        day = datetime.strptime(explicit_us.group(1), "%m/%d/%Y").date()
        start = datetime.combine(day, datetime.min.time(), tzinfo=reference_now.tzinfo)
        end = start + timedelta(days=1)
        return start, end

    # Relative keywords
    if "yesterday" in q:
        day = (reference_now - timedelta(days=1)).date()
        start = datetime.combine(day, datetime.min.time(), tzinfo=reference_now.tzinfo)
        end = start + timedelta(days=1)
        return start, end
    if "today" in q:
        day = reference_now.date()
        start = datetime.combine(day, datetime.min.time(), tzinfo=reference_now.tzinfo)
        end = start + timedelta(days=1)
        return start, end

    # Weekday references (e.g., "last tuesday morning")
    weekday = next((name for name in _WEEKDAYS.keys() if name in q), None)
    if weekday:
        target_wd = _WEEKDAYS[weekday]
        ref_date = reference_now.date()
        ref_wd = reference_now.weekday()

        days_back = (ref_wd - target_wd) % 7
        if days_back == 0:
            days_back = 7

        target_date = ref_date - timedelta(days=days_back)
        start = datetime.combine(target_date, datetime.min.time(), tzinfo=reference_now.tzinfo)
        end = start + timedelta(days=1)

        # Time-of-day tightening
        if "morning" in q:
            start = start + timedelta(hours=4)
            end = start + timedelta(hours=8)  # 4am-12pm
        elif "afternoon" in q:
            start = start + timedelta(hours=12)
            end = start + timedelta(hours=5)  # 12pm-5pm
        elif "evening" in q:
            start = start + timedelta(hours=17)
            end = start + timedelta(hours=4)  # 5pm-9pm
        elif "night" in q:
            start = start + timedelta(hours=21)
            end = start + timedelta(hours=7)  # 9pm-4am

        return start, end

    return None

@tool
def search_semantic_timeline(user_question: str) -> dict:
    """
    Searches the pgvector database to find the closest lifestyle event/meal 
    log that matches the user's intent or question.
    """
    conn = get_connection()
    register_vector(conn)
    cur = conn.cursor()
    try:
        reference_now = _dataset_reference_now(cur)
        window = _extract_time_window(user_question, reference_now)

        # If the question contains a time reference, prefer selecting the closest log by timestamp.
        if window:
            start, end = window
            center = start + (end - start) / 2
            cur.execute(
                """
                SELECT event_timestamp, text_data
                FROM {table}
                WHERE event_timestamp >= %s::timestamptz AND event_timestamp < %s::timestamptz
                ORDER BY ABS(EXTRACT(EPOCH FROM (event_timestamp - %s::timestamptz))) ASC
                LIMIT 1;
                """.format(table=SEMANTIC_TABLE_NAME),
                (start, end, center),
            )
            result = cur.fetchone()
            if result:
                timestamp, text = result
                return {
                    "success": True,
                    "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
                    "matched_log": text,
                }

            # If the narrowed window (e.g. "Saturday evening") is empty, fall back to the closest
            # log on that same day before doing an embedding-based search.
            day_start = datetime.combine(center.date(), datetime.min.time(), tzinfo=center.tzinfo)
            day_end = day_start + timedelta(days=1)
            cur.execute(
                """
                SELECT event_timestamp, text_data
                FROM {table}
                WHERE event_timestamp >= %s::timestamptz AND event_timestamp < %s::timestamptz
                ORDER BY ABS(EXTRACT(EPOCH FROM (event_timestamp - %s::timestamptz))) ASC
                LIMIT 1;
                """.format(table=SEMANTIC_TABLE_NAME),
                (day_start, day_end, center),
            )
            result = cur.fetchone()
            if result:
                timestamp, text = result
                return {
                    "success": True,
                    "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
                    "matched_log": text,
                }

        # Fall back to semantic similarity search
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        query_vector = embeddings.embed_query(user_question)

        # Vector distance search using Cosine distance (<=>)
        cur.execute(
            """
            SELECT event_timestamp, text_data
            FROM {table}
            ORDER BY embedding <=> %s::vector
            LIMIT 1;
            """.format(table=SEMANTIC_TABLE_NAME),
            (query_vector,),
        )
        # embedding is the vector column in the table (the stored embedding for each row).
        # ::vector casts the parameter to the pgvector type
        # <=> is a pgvector distance operator (distance between two vectors). Smaller distance = more similar.
        # %s is a psycopg2 parameter placeholder. You pass query_vector from embeddings.embed_query(user_question)

        result = cur.fetchone()
    finally:
        cur.close()
        conn.close()
    
    if result:
        timestamp, text = result
        return {
            "success": True,
            "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
            "matched_log": text
        }
    return {"success": False, "message": "No matching lifestyle logs found."}

@tool
def fetch_biometric_metrics(event_timestamp_str: str, window_hours: int = 3) -> dict:
    """
    Queries raw SQL time-series biometric streams in a specific window of hours 
    following a designated timestamp. Returns structural statistical peaks.
    """
    # Parse the timestamp string returned by search_semantic_timeline
    # Expected format: ISO-8601 (preferred, may include timezone) or "YYYY-MM-DD HH:MM:SS"
    ts_str = event_timestamp_str.strip()
    if ts_str.endswith("Z"):
        ts_str = ts_str[:-1] + "+00:00"
    start_ts = datetime.fromisoformat(ts_str)
    if start_ts.tzinfo is None:
        start_ts = start_ts.replace(tzinfo=timezone.utc)
    end_ts = start_ts + timedelta(hours=int(window_hours))

    conn = get_connection()
    cur = conn.cursor()
    
    # Extract structural math markers out of the relational time-series table
    cur.execute("""
        SELECT 
            MAX(glucose_mg_dl) as max_glucose,
            MIN(glucose_mg_dl) as min_glucose,
            AVG(glucose_mg_dl) as avg_glucose,
            AVG(heart_rate_bpm) as avg_heart_rate
        FROM time_series_metrics
        WHERE timestamp >= %s::timestamptz AND timestamp < %s::timestamptz;
    """, (start_ts, end_ts))
    
    max_gl, min_gl, avg_gl, avg_hr = cur.fetchone()
    cur.close()
    conn.close()
    
    return {
        "peak_glucose_mg_dl": float(max_gl) if max_gl is not None else None,
        "baseline_glucose_mg_dl": float(min_gl) if min_gl is not None else None,
        "average_glucose_mg_dl": float(avg_gl) if avg_gl is not None else None,
        "average_heart_rate_bpm": float(avg_hr) if avg_hr is not None else None,
    }