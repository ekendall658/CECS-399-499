import pandas as pd
from pathlib import Path

# =========================================================
# STEP 1: File Paths and Configuration
# =========================================================

# Pointing to the raw data stored in the bronze directory
FILES = [
    Path("local_data/bronze/eaglei_outages_2021.csv"),
    Path("local_data/bronze/eaglei_outages_2022.csv"),
    Path("local_data/bronze/eaglei_outages_2023.csv"),
    Path("local_data/bronze/eaglei_outages_2024.csv"),
    Path("local_data/bronze/eaglei_outages_2025.csv"),
]

# Read large files in chunks to optimize memory usage
CHUNK_SIZE = 200_000

# Standardize timestamps to UTC before converting to Central Time
ASSUME_TZ_IF_NAIVE = "UTC"
TARGET_TZ = "US/Central"

# Final output path for the cleaned Tennessee dataset
OUT_TN_FINAL = Path("local_data/silver/eaglei_tennessee_cleaned_final.csv")

# Standard column names expected in the source files
STATE_COL = "state"
COUNTY_COL = "county"
TIME_COL = "run_start_time"

def detect_outage_col(columns):
    """Detect which column represents the number of customers out."""
    cols = [c.strip() for c in columns]
    candidates = ["customers_out", "sum"]
    for c in candidates:
        if c in cols: return c
    for c in cols:
        if "customer" in c.lower(): return c
    raise ValueError(f"Could not detect outage column. Columns are: {cols}")

def process_one_file(file_path: Path, out_path: Path, write_header: bool) -> bool:
    """Read a single file in chunks and append cleaned TN data to the output."""
    print(f"\nProcessing file: {file_path.name}")
    outage_col = None 

    for chunk in pd.read_csv(file_path, chunksize=CHUNK_SIZE):
        if outage_col is None:
            outage_col = detect_outage_col(chunk.columns)

        # Filter for Tennessee state data without regional restrictions
        chunk = chunk[chunk[STATE_COL] == "Tennessee"].copy()
        if chunk.empty:
            continue

        # Convert to datetime objects and handle invalid formats
        chunk[TIME_COL] = pd.to_datetime(chunk[TIME_COL], errors="coerce")
        chunk = chunk.dropna(subset=[TIME_COL])

        # Standardize timezone to UTC then convert to Central Time
        if chunk[TIME_COL].dt.tz is None:
            chunk[TIME_COL] = chunk[TIME_COL].dt.tz_localize(
                ASSUME_TZ_IF_NAIVE, ambiguous="NaT", nonexistent="NaT"
            )
        chunk[TIME_COL] = chunk[TIME_COL].dt.tz_convert(TARGET_TZ)

        # Extract date for daily aggregation
        chunk["date"] = chunk[TIME_COL].dt.date
        
        # Aggregate to find the daily peak outage per county
        daily = chunk.groupby([COUNTY_COL, "date"], as_index=False)[outage_col].max()

        # Standardize column naming and ensure numeric data types
        daily = daily.rename(columns={outage_col: "customers_out"})
        daily["customers_out"] = daily["customers_out"].fillna(0).astype(int)

        # Append to the final CSV file
        daily.to_csv(out_path, mode="a", header=write_header, index=False)
        write_header = False

    return write_header

def main():
    """Main execution block to process all files and export results."""
    OUT_TN_FINAL.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing output file to start a fresh run
    if OUT_TN_FINAL.exists():
        OUT_TN_FINAL.unlink()

    write_header = True

    # Iteratively process each file in the source list
    for fp in FILES:
        if not fp.exists():
            print(f"File not found: {fp}")
            continue
        write_header = process_one_file(fp, OUT_TN_FINAL, write_header)

    print("-" * 30)
    print(f"Export complete: {OUT_TN_FINAL}")
    
    # Display final record count for verification
    if OUT_TN_FINAL.exists():
        final_df = pd.read_csv(OUT_TN_FINAL)
        print(f"Total processed records: {len(final_df)}")

if __name__ == "__main__":
    main()
