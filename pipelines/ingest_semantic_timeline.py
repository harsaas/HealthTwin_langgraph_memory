import os
from pathlib import Path

import pandas as pd
import psycopg2
from pgvector.psycopg2 import register_vector
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv

# Load database environment settings
repo_root = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=repo_root / ".env", override=True)
DATABASE_URL = os.getenv("DATABASE_URL")
PROCESSED_DIR = "data/processed"
TABLE_NAME = "semantic_timeline_food"

def ingest_semantic_data():
    print("⏳ Reading cleaned food and lifestyle journals...")
    df_food = pd.read_csv(os.path.join(PROCESSED_DIR, "cleaned_food_log.csv"))
    
    if df_food.empty:
        print("❌ No journal entries found inside cleaned_food_log.csv.")
        return

    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set. Add it to .env in the repo root.")
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set. Add it to .env to create embeddings.")

    # Processed food log is expected to already be clean with columns:
    # timestamp, food_item, carbs_g
    df_food["event_timestamp"] = pd.to_datetime(df_food["timestamp"], errors="coerce")
    df_food["text_data"] = df_food["food_item"].astype(str)

    df_food = df_food.dropna(subset=["event_timestamp", "food_item"]).reset_index(drop=True)
    if df_food.empty:
        print("❌ No valid rows after cleaning (missing timestamp or food_item).")
        return

    print("🐘 Activating pgvector structures in your Postgres database...")
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    # Initialize extension and target table
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id SERIAL PRIMARY KEY,
            event_timestamp TIMESTAMPTZ NOT NULL,
            text_data TEXT NOT NULL,
            embedding VECTOR(1536)
        );
        CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_timestamp ON {TABLE_NAME} (event_timestamp);
    """)
    conn.commit()

    print("🧠 Inverting text entries into high-dimensional vector embeddings...")
    embeddings_model = OpenAIEmbeddings(model="text-embedding-3-small")
    texts = df_food["text_data"].astype(str).tolist()
    vectors = embeddings_model.embed_documents(texts)

    print("📥 Committing context entries and vectors into PostgreSQL...")
    # register_vector allows psycopg2 to translate Python arrays into Postgres vector types seamlessly
    register_vector(conn)

    insert_query = f"""
        INSERT INTO {TABLE_NAME} (event_timestamp, text_data, embedding)
        VALUES (%s, %s, %s);
    """

    for idx, row in df_food.iterrows():
        cur.execute(
            insert_query,
            (
                pd.Timestamp(row["event_timestamp"]).to_pydatetime(),
                str(row["text_data"]),
                vectors[idx],
            ),
        )

    conn.commit()
    cur.close()
    conn.close()
    print(f"✅ Semantic memory ingestion complete! Embedded and loaded {len(df_food)} journal events.")

if __name__ == "__main__":
    ingest_semantic_data()