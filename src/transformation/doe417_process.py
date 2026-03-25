import pandas as pd
import numpy as np
from pathlib import Path

# =========================================================
# STEP 1: Set Paths and Load Data
# =========================================================
BASE_DIR = Path("local_data/bronze")
OUTPUT_CSV = Path("local_data/silver/doe417_tennessee_cleaned_final.csv")

files = [
    BASE_DIR / "2021_DOE417.xls",
    BASE_DIR / "2022_DOE417.xls",
    BASE_DIR / "2023_DOE417.xls"
]

all_raw_data = []

def combine_date_time(df, date_col, time_col):
    """Robust parsing for date and time, handling 2023 format inconsistencies"""
    d = pd.to_datetime(df[date_col], errors='coerce').dt.strftime('%Y-%m-%d')
    t = df[time_col].astype(str).str.strip()
    return pd.to_datetime(d + " " + t, errors="coerce")

print("Loading files and performing data cleaning...")

for file in files:
    try:
        df = pd.read_excel(file, header=1)
        rename_map = {
            "Event Month": "Month", "Date Event Began ": "Date Event Began",
            "Time Event Began ": "Time Event Began", "Date of Restoration ": "Date of Restoration",
            "Time of Restoration ": "Time of Restoration", "Area Affected ": "Area Affected",
            "Alert Criteria ": "Alert Criteria", "Event Type ": "Event Type",
            "Number of Customers Affected ": "Number of Customers Affected"
        }
        df = df.rename(columns=rename_map)
        df = df.replace(['Unknown', '#NAME?', 'unknown', 'n/a', 'N/A', 'NA', 'UNK'], np.nan)

        if "Number of Customers Affected" in df.columns:
            df["Number of Customers Affected"] = pd.to_numeric(df["Number of Customers Affected"], errors="coerce").fillna(0)

        df["source_year"] = file.stem[:4]

        # Time Zone Correction (Local Central Time to UTC)
        if "Date Event Began" in df.columns and "Time Event Began" in df.columns:
            df["event_start_utc"] = combine_date_time(df, "Date Event Began", "Time Event Began")
            df["event_start_utc"] = df["event_start_utc"].dt.tz_localize("America/Chicago", ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")

        if "Date of Restoration" in df.columns and "Time of Restoration" in df.columns:
            df["event_end_utc"] = combine_date_time(df, "Date of Restoration", "Time of Restoration")
            df["event_end_utc"] = df["event_end_utc"].dt.tz_localize("America/Chicago", ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")

        all_raw_data.append(df)
        print(f"Loaded: {file}")
    except Exception as e:
        print(f"Error loading {file}: {e}")

df_master = pd.concat(all_raw_data, ignore_index=True)
# Filter for all records in Tennessee
df_final = df_master[df_master["Area Affected"].astype(str).str.contains("Tennessee", case=False, na=False)].copy()

fill_values = {"Event Type": "System Operations/Other", "Alert Criteria": "Not Specified", "Number of Customers Affected": 0}
df_final = df_final.fillna(value=fill_values)

OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
df_final.to_csv(OUTPUT_CSV, index=False)

print("-" * 30)
print(f"Success: Processed file saved to {OUTPUT_CSV}")
print(f"Total Tennessee records: {len(df_final)}")