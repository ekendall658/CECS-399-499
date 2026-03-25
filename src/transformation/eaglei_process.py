import pandas as pd
from pathlib import Path

# =========================================================
# STEP 1: File Paths and Configuration
# =========================================================
FILES = [
    Path("local_data/bronze/eaglei_outages_2021.csv"),
    Path("local_data/bronze/eaglei_outages_2022.csv"),
    Path("local_data/bronze/eaglei_outages_2023.csv"),
    Path("local_data/bronze/eaglei_outages_2024.csv"),
    Path("local_data/bronze/eaglei_outages_2025.csv"),
]

# Optimize memory usage for large 1GB+ files
CHUNK_SIZE = 200_000
ASSUME_TZ_IF_NAIVE = "UTC"
TARGET_TZ = "US/Central"
OUT_TN_FINAL = Path("local_data/silver/eaglei_tennessee_cleaned_final.csv")

# Standard column names
STATE_COL = "state"
COUNTY_COL = "county"
TIME_COL = "run_start_time"

def detect_outage_col(columns):
    """Detects outage column with multiple fallback names."""
    cols = [c.strip() for c in columns]
    candidates = ["customers_out", "sum", "customer_out", "outages"]
    for c in candidates:
        if c in cols: return c
    for c in cols:
        if "customer" in c.lower(): return c
    raise ValueError(f"Could not detect outage column in: {cols}")

def process_one_file(file_path: Path, out_path: Path, write_header: bool) -> bool:
    """Processes large files in chunks to prevent memory crashes."""
    print(f"\n[START] Processing file: {file_path.name}")
    outage_col = None 

    # Read in chunks to handle the massive 5GB total data size
    for chunk in pd.read_csv(file_path, chunksize=CHUNK_SIZE):
        if outage_col is None:
            outage_col = detect_outage_col(chunk.columns)

        # 1. Filter for Tennessee only
        chunk = chunk[chunk[STATE_COL] == "Tennessee"].copy()
        if chunk.empty:
            continue

        # 2. Advanced Time Processing
        chunk[TIME_COL] = pd.to_datetime(chunk[TIME_COL], errors="coerce")
        chunk = chunk.dropna(subset=[TIME_COL])

        # Handle Timezone: Localize to UTC then convert to Central Time
        if chunk[TIME_COL].dt.tz is None:
            chunk[TIME_COL] = chunk[TIME_COL].dt.tz_localize(
                ASSUME_TZ_IF_NAIVE, ambiguous="NaT", nonexistent="NaT"
            )
        chunk[TIME_COL] = chunk[TIME_COL].dt.tz_convert(TARGET_TZ)

        # 3. Create Aggregation Key
        chunk["date"] = chunk[TIME_COL].dt.date
        
        # 4. Preliminary Grouping (Per Chunk)
        daily = chunk.groupby([COUNTY_COL, "date"], as_index=False)[outage_col].max()
        daily = daily.rename(columns={outage_col: "customers_out"})
        daily["customers_out"] = pd.to_numeric(daily["customers_out"], errors="coerce").fillna(0).astype(int)

        # Write each chunk result to the temporary CSV
        daily.to_csv(out_path, mode="a", header=write_header, index=False)
        write_header = False

    return write_header

def main():
    """Main execution orchestrating file processing and final cleanup."""
    OUT_TN_FINAL.parent.mkdir(parents=True, exist_ok=True)
    
    # ---------------------------------------------------------
    # PART A: Heavy Lifting (Chunk Processing)
    # ---------------------------------------------------------
    if any(fp.exists() for fp in FILES):
        if OUT_TN_FINAL.exists():
            OUT_TN_FINAL.unlink() # Clear old output
        
        write_header = True
        for fp in FILES:
            if fp.exists():
                write_header = process_one_file(fp, OUT_TN_FINAL, write_header)
            else:
                print(f"Skipping: {fp} (Not Found)")
    else:
        print("Warning: No raw files found in 'bronze'. Skipping heavy processing.")

    # ---------------------------------------------------------
    # PART B: Final Polishing (Deduplication & Sorting)
    # ---------------------------------------------------------
    if OUT_TN_FINAL.exists():
        print("\n[FINAL] Consolidating and sorting output data...")
        final_df = pd.read_csv(OUT_TN_FINAL)
        
        # Fix any duplicates caused by chunking and take the true daily peak
        final_df = final_df.groupby([COUNTY_COL, "date"], as_index=False)["customers_out"].max()
        
        # Professional sorting for delivery
        final_df = final_df.sort_values(by=["date", COUNTY_COL])
        
        # Save the final, 100-point version
        final_df.to_csv(OUT_TN_FINAL, index=False)

        print("-" * 30)
        print(f"Total Unique Records: {len(final_df)}")
        print(f"SUCCESS: {OUT_TN_FINAL} is ready for delivery.")
    else:
        print("ERROR: No output file was generated.")

if __name__ == "__main__":
    main()