# clean the raw data and save it to the processed folder
import os
import pandas as pd

# Define your paths
RAW_DIR = "data/raw"
PROCESSED_DIR = "data/processed"

def clean_glucose():
    """Cleans Dexcom CGM data (Recorded roughly every 5 mins)."""
    # load raw data
    df = pd.read_csv(os.path.join(RAW_DIR, "Dexcom_016.csv"))
    # Convert timestamp to datetime
    df["timestamp"] = pd.to_datetime(df["Timestamp (YYYY-MM-DDThh:mm:ss)"], errors="coerce")
    df["glucose_mg_dl"] = pd.to_numeric(df["Glucose Value (mg/dL)"], errors="coerce")
    if "Event Type" in df.columns:
        df = df[df["Event Type"].astype(str).str.upper() == "EGV"]
    cleaned_df = df[["timestamp", "glucose_mg_dl"]].dropna()
    cleaned_df.to_csv(os.path.join(PROCESSED_DIR, "cleaned_glucose.csv"), index=False)
    print(f"✅ Saved {len(cleaned_df)} glucose records.")

def clean_heart_rate():
    """Cleans Apple Watch heart rate data (Recorded roughly every 5 mins)."""
    df = pd.read_csv(os.path.join(RAW_DIR, "HR_016.csv"), skipinitialspace=True)
    df["timestamp"] = pd.to_datetime(df["datetime"], errors="coerce")
    df["heart_rate_bpm"] = pd.to_numeric(df["hr"], errors="coerce")
    cleaned_df = df[["timestamp", "heart_rate_bpm"]].dropna()
    cleaned_df.to_csv(os.path.join(PROCESSED_DIR, "cleaned_heart_rate.csv"), index=False)
    print(f"✅ Saved {len(cleaned_df)} heart rate records.")

def clean_food_log():
    """Cleans food log data (Recorded manually, so timestamps may be inconsistent)."""
    df = pd.read_csv(os.path.join(RAW_DIR, "Food_Log_016.csv"))
    df["timestamp"] = pd.to_datetime(df["time_begin"], errors="coerce")
    df["food_item"] = df["logged_food"].fillna(df["searched_food"])
    df["carbs_g"] = pd.to_numeric(df["total_carb"], errors="coerce")
    cleaned_df = df[["timestamp", "food_item", "carbs_g"]].dropna(subset=["timestamp", "food_item"])
    cleaned_df.to_csv(os.path.join(PROCESSED_DIR, "cleaned_food_log.csv"), index=False)
    print(f"✅ Saved {len(cleaned_df)} food log records.")

if __name__ == "__main__":
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    clean_glucose()
    clean_heart_rate()
    clean_food_log()

