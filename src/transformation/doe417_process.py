import pandas as pd
import numpy as np
from pathlib import Path

# =========================================================
# STEP 1: Set Paths and Load Data
# =========================================================

# Directory containing the raw data files
BASE_DIR = Path("local_data/bronze")
# Final output path for the processed Tennessee dataset
OUTPUT_CSV = Path("local_data/silver/doe417_tennessee_cleaned_final.csv")

# List of raw Excel files to be processed
files = [
    BASE_DIR / "2021_DOE417.xls",
    BASE_DIR / "2022_DOE417.xls",
    BASE_DIR / "2023_DOE417.xls"
]

all_raw_data = []

print("Loading files and performing data cleaning...")

for file in files:
    try:
        # Read Excel; header=1 skips the initial metadata/title row
        df = pd.read_excel(file, header=1)

        # Standardize column names by removing trailing spaces and aligning keys
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

        # Clean placeholder or error strings by converting them to standard NaN values
        df = df.replace(
            ['Unknown', '#NAME?', 'unknown', 'n/a', 'N/A', 'NA', 'UNK'],
            np.nan
        )

        # Ensure customer outage data is numeric to support quantitative analysis
        if "Number of Customers Affected" in df.columns:
            df["Number of Customers Affected"] = pd.to_numeric(
                df["Number of Customers Affected"],
                errors="coerce"
            ).fillna(0)

        # Track the source year based on the filename
        df["source_year"] = file.stem[:4]

        # -------------------------------------------------
        # STEP 1B: Time Zone Correction (Local to UTC)
        # -------------------------------------------------
        
        # Process event start timestamps
        if "Date Event Began" in df.columns and "Time Event Began" in df.columns:
            df["event_start_utc"] = pd.to_datetime(
                df["Date Event Began"].astype(str).str.strip() + " " + 
                df["Time Event Began"].astype(str).str.strip(),
                errors="coerce"
            )
            # Localize to Central Time (observed) and convert to UTC for standardization
            df["event_start_utc"] = df["event_start_utc"].dt.tz_localize(
                "America/Chicago", ambiguous="NaT", nonexistent="NaT"
            ).dt.tz_convert("UTC")

        # Process restoration timestamps
        if "Date of Restoration" in df.columns and "Time of Restoration" in df.columns:
            df["event_end_utc"] = pd.to_datetime(
                df["Date of Restoration"].astype(str).str.strip() + " " + 
                df["Time of Restoration"].astype(str).str.strip(),
                errors="coerce"
            )
            df["event_end_utc"] = df["event_end_utc"].dt.tz_localize(
                "America/Chicago", ambiguous="NaT", nonexistent="NaT"
            ).dt.tz_convert("UTC")

        all_raw_data.append(df)
        print(f"Loaded: {file}")

    except Exception as e:
        print(f"Error loading {file}: {e}")

# Consolidate all annual data into a single master DataFrame
df_master = pd.concat(all_raw_data, ignore_index=True)

# =========================================================
# STEP 2: Geographic Filtering
# =========================================================

# Filter for all event records pertaining to the state of Tennessee
# This captures all grid-impacting events regardless of specific type
df_final = df_master[
    df_master["Area Affected"].astype(str).str.contains(
        "Tennessee", case=False, na=False
    )
].copy()

# =========================================================
# STEP 3: Missing Value Imputation
# =========================================================

# Fill null values with standard placeholders to maintain dataset consistency
fill_values = {
    "Event Type": "System Operations/Other",
    "Alert Criteria": "Not Specified",
    "Number of Customers Affected": 0
}
df_final = df_final.fillna(value=fill_values)

# =========================================================
# STEP 4: Export Processed Data
# =========================================================

# Ensure the output directory exists before writing the CSV
OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
df_final.to_csv(OUTPUT_CSV, index=False)

print("-" * 30)
print(f"Success: Processed file saved to {OUTPUT_CSV}")
print(f"Total Tennessee records: {len(df_final)}")

