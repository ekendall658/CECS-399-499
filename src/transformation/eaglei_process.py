import pandas as pd
import numpy as np
from pathlib import Path

# =========================================================
# STEP 1: CONFIGURATION & PATH SETTINGS
# =========================================================

# List of massive raw CSV files (Bronze Layer)
FILES = [
    Path("local_data/bronze/eaglei_outages_2021.csv"),
    Path("local_data/bronze/eaglei_outages_2022.csv"),
    Path("local_data/bronze/eaglei_outages_2023.csv"),
    Path("local_data/bronze/eaglei_outages_2024.csv"),
    Path("local_data/bronze/eaglei_outages_2025.csv"),
]

# Performance Tuning: Chunking to handle 5GB+ total data within memory limits
CHUNK_SIZE = 200_000
ASSUME_TZ_IF_NAIVE = "UTC"
TARGET_TZ = "US/Central"

# Final destination for cleaned Tennessee data (Silver Layer)
OUT_TN_FINAL = Path("local_data/silver/eaglei_tennessee_cleaned_final.csv")

# Constant column keys to maintain schema consistency
STATE_COL = "state"
COUNTY_COL = "county"
TIME_COL = "run_start_time"

def detect_outage_col(columns):
    """
    Scans the dataframe columns to identify the outage count field.
    Handles schema variations across different years (e.g., 'sum' vs 'customers_out').
    """
    cols = [c.strip() for c in columns]
    candidates = ["customers_out", "sum", "customer_out", "outages"]
    for c in candidates:
        if c in cols: return c
    for c in cols:
        if "customer" in c.lower(): return c
    raise ValueError(f"Required outage column not detected in: {cols}")

def process_one_file(file_path: Path, out_path: Path, write_header: bool) -> bool:
    """
    Reads large CSVs in chunks, filters for Tennessee, converts timezones,
    and performs preliminary daily peak aggregation.
    """
    print(f"\n[INGESTION] Processing source: {file_path.name}")
    outage_col = None 

    for chunk in pd.read_csv(file_path, chunksize=CHUNK_SIZE):
        if outage_col is None:
            outage_col = detect_outage_col(chunk.columns)

        # 1. Geographic Filtering
        chunk = chunk[chunk[STATE_COL] == "Tennessee"].copy()
        if chunk.empty:
            continue

        # 2. Advanced DateTime Standardization
        chunk[TIME_COL] = pd.to_datetime(chunk[TIME_COL], errors="coerce")
        chunk = chunk.dropna(subset=[TIME_COL])

        # Localize naive UTC and convert to Central Time (Target TZ)
        if chunk[TIME_COL].dt.tz is None:
            chunk[TIME_COL] = chunk[TIME_COL].dt.tz_localize(
                ASSUME_TZ_IF_NAIVE, ambiguous="NaT", nonexistent="NaT"
            )
        chunk[TIME_COL] = chunk[TIME_COL].dt.tz_convert(TARGET_TZ)

        # 3. Daily Peak Aggregation per Chunk
        chunk["date"] = chunk[TIME_COL].dt.date
        daily = chunk.groupby([COUNTY_COL, "date"], as_index=False)[outage_col].max()
        
        # 4. Standardizing Outage Column and Type
        daily = daily.rename(columns={outage_col: "customers_out"})
        daily["customers_out"] = pd.to_numeric(daily["customers_out"], errors="coerce").fillna(0).astype(int)

        # Append to disk to maintain low memory footprint
        daily.to_csv(out_path, mode="a", header=write_header, index=False)
        write_header = False

    return write_header

def main():
    """Main execution pipeline for Eagle-i data transformation."""
    OUT_TN_FINAL.parent.mkdir(parents=True, exist_ok=True)
    
    # --- PART A: CHUNK-BASED INGESTION ---
    if any(fp.exists() for fp in FILES):
        if OUT_TN_FINAL.exists():
            OUT_TN_FINAL.unlink() # Refresh the Silver layer file
        
        write_header = True
        for fp in FILES:
            if fp.exists():
                write_header = process_one_file(fp, OUT_TN_FINAL, write_header)
            else:
                print(f"Skipping: {fp.name} (File not found)")
    else:
        print("Note: No raw files detected in 'bronze'. Skipping ingestion.")

    # --- PART B: FINAL DATA POLISHING & DTYPE ENFORCEMENT ---
    if OUT_TN_FINAL.exists():
        print("\n[FINALIZING] Consolidating records and enforcing dtypes...")
        final_df = pd.read_csv(OUT_TN_FINAL)
        
        # Deduplicate: Ensure only one 'peak' record per county/day across all chunks
        final_df = final_df.groupby([COUNTY_COL, "date"], as_index=False)["customers_out"].max()
        
        # Enforce Integer Dtype (Correcting any float artifacts from CSV reading)
        final_df["customers_out"] = final_df["customers_out"].astype(int)
        
        # Professional sorting for clean data delivery
        final_df = final_df.sort_values(by=["date", COUNTY_COL])
        
        # Final Export
        final_df.to_csv(OUT_TN_FINAL, index=False)

        print("-" * 30)
        print(f"Total Unique Records: {len(final_df)}")
        print(f"Verified Dtype for 'customers_out': {final_df['customers_out'].dtype}")
        print(f"SUCCESS: {OUT_TN_FINAL.name} is ready for delivery.")
    else:
        print("ERROR: Execution failed. Output file not found.")

if __name__ == "__main__":
    main()