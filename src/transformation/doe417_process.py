import pandas as pd
import numpy as np
from pathlib import Path

# =========================================================
# CONFIGURATION & PATH SETTINGS
# =========================================================
BASE_DIR = Path("local_data/bronze")
OUTPUT_CSV = Path("local_data/silver/doe417_tennessee_cleaned_final.csv")

# Input files for years 2021-2023
FILES = [
    BASE_DIR / "2021_DOE417.xls",
    BASE_DIR / "2022_DOE417.xls",
    BASE_DIR / "2023_DOE417.xls"
]

all_raw_data = []

def combine_date_time(df, date_col, time_col):
    """
    Combines separate date and time columns into a single localized timestamp.
    Handles inconsistent 2023 date formats (e.g., strings vs datetimes).
    """
    # Normalize date to YYYY-MM-DD and strip whitespace from time strings
    d = pd.to_datetime(df[date_col], errors='coerce').dt.strftime('%Y-%m-%d')
    t = df[time_col].astype(str).str.strip()
    return pd.to_datetime(d + " " + t, errors="coerce")

print("Starting DOE-417 Data Transformation...")

# =========================================================
# DATA LOADING & INITIAL CLEANING
# =========================================================
for file in FILES:
    if not file.exists():
        print(f"Warning: {file.name} not found. Skipping...")
        continue
        
    try:
        # Load Excel; header=1 assumes the first row contains metadata/titles
        df = pd.read_excel(file, header=1)
        
        # Standardize inconsistent column headers (handling trailing spaces)
        rename_map = {
            "Event Month": "Month", 
            "Date Event Began ": "Date Event Began",
            "Time Event Began ": "Time Event Began", 
            "Date of Restoration ": "Date of Restoration",
            "Time of Restoration ": "Time of Restoration", 
            "Area Affected ": "Area Affected",
            "Alert Criteria ": "Alert Criteria", 
            "Event Type ": "Event Type",
            "Number of Customers Affected ": "Number of Customers Affected"
        }
        df = df.rename(columns=rename_map)
        
        # Replace non-numeric placeholders with standard NaN values
        invalid_entries = ['Unknown', '#NAME?', 'unknown', 'n/a', 'N/A', 'NA', 'UNK', 'None']
        df = df.replace(invalid_entries, np.nan)

        # Track source year for auditing
        df["source_year"] = int(file.stem[:4])

        # ---------------------------------------------------------
        # TIMEZONE STANDARDIZATION (Local to UTC)
        # ---------------------------------------------------------
        # Localizing timestamps from America/Chicago (Central) to UTC
        if "Date Event Began" in df.columns and "Time Event Began" in df.columns:
            df["event_start_utc"] = combine_date_time(df, "Date Event Began", "Time Event Began")
            df["event_start_utc"] = df["event_start_utc"].dt.tz_localize(
                "America/Chicago", ambiguous="NaT", nonexistent="NaT"
            ).dt.tz_convert("UTC")

        if "Date of Restoration" in df.columns and "Time of Restoration" in df.columns:
            df["event_end_utc"] = combine_date_time(df, "Date of Restoration", "Time of Restoration")
            df["event_end_utc"] = df["event_end_utc"].dt.tz_localize(
                "America/Chicago", ambiguous="NaT", nonexistent="NaT"
            ).dt.tz_convert("UTC")

        all_raw_data.append(df)
        print(f"Successfully loaded: {file.name}")
        
    except Exception as e:
        print(f"Error processing {file.name}: {e}")

# =========================================================
# FINAL AGGREGATION & DATA TYPE ENFORCEMENT
# =========================================================
if all_raw_data:
    df_master = pd.concat(all_raw_data, ignore_index=True)

    # Filter for Tennessee-specific records across all regions
    df_final = df_master[
        df_master["Area Affected"].astype(str).str.contains("Tennessee", case=False, na=False)
    ].copy()

    # Fill critical missing values with logical defaults
    fill_values = {
        "Event Type": "System Operations/Other", 
        "Alert Criteria": "Not Specified", 
        "Number of Customers Affected": 0,
        "Demand Loss (MW)": 0.0
    }
    df_final = df_final.fillna(value=fill_values)

    # --- STRICT DTYPE ENFORCEMENT ---
    # Convert 'Customers Affected' to Integer (since people are not decimals)
    df_final["Number of Customers Affected"] = pd.to_numeric(
        df_final["Number of Customers Affected"], errors='coerce'
    ).fillna(0).astype(int)
    
    # 'Demand Loss' remains Float to represent precision in Megawatts
    df_final["Demand Loss (MW)"] = pd.to_numeric(
        df_final["Demand Loss (MW)"], errors='coerce'
    ).astype(float)

    # Export to Silver Layer
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df_final.to_csv(OUTPUT_CSV, index=False)

    print("-" * 30)
    print(f"Success: Cleaned file saved to {OUTPUT_CSV}")
    print(f"Total Tennessee records: {len(df_final)}")
    print(f"Verified Dtypes: \n{df_final.dtypes[['Number of Customers Affected', 'Demand Loss (MW)']]}")
else:
    print("No data was processed.")