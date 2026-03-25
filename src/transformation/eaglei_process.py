import pandas as pd
from pathlib import Path

# =========================================================
# STEP 1: Set Paths and Load Data
# =========================================================

# Directory containing the raw data files
BASE_DIR = Path("local_data/bronze")
# Final output path for the processed Tennessee dataset
OUTPUT_CSV = Path("local_data/silver/eaglei_tennessee_cleaned_final.csv")

# List of raw CSV files to be processed
files = [
    BASE_DIR / "eaglei_outages_2021.csv",
    BASE_DIR / "eaglei_outages_2022.csv",
    BASE_DIR / "eaglei_outages_2023.csv",
    BASE_DIR / "eaglei_outages_2024.csv",
    BASE_DIR / "eaglei_outages_2025.csv"
]

all_data = []

print("Processing Eagle-i files for all Tennessee counties...")

# =========================================================
# STEP 2: Iterative Processing of Large CSVs
# =========================================================

for file in files:
    try:
        # Read the large CSV file
        df = pd.read_csv(file)
        
        # Filter for Tennessee state and ensure data type consistency
        df_tn = df[df["state"] == "Tennessee"].copy()
        df_tn["fips_code"] = pd.to_numeric(df_tn["fips_code"], errors="coerce")
        df_tn["run_start_time"] = pd.to_datetime(df_tn["run_start_time"])
        
        # Extract the date for daily aggregation
        df_tn["date"] = df_tn["run_start_time"].dt.date
        
        # Calculate the peak (maximum) outages per county per day
        # This reduces data volume while retaining critical grid stress events
        daily_peak = df_tn.groupby(["county", "date"])["customers_out"].max().reset_index()
        
        all_data.append(daily_peak)
        print(f"Processed file: {file.name}")
        
    except Exception as e:
        print(f"Error processing {file.name}: {e}")

# =========================================================
# STEP 3: Consolidate and Export
# =========================================================

# Combine all processed years into one master dataset
df_final = pd.concat(all_data, ignore_index=True)

# Ensure the output directory exists before writing the CSV
OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
df_final.to_csv(OUTPUT_CSV, index=False)

print("-" * 30)
print(f"Export complete: {OUTPUT_CSV}")
print(f"Total processed records: {len(df_final)}")
