import pandas as pd
from pathlib import Path

# 1) File list

FILES = [
    "eaglei_outages_2021.csv",
    "eaglei_outages_2022.csv",
    "eaglei_outages_2023.csv",
    "eaglei_outages_2024.csv",
    "eaglei_outages_2025.csv",
]

# Read big files safely
CHUNK_SIZE = 200_000

# Timezone policy:
# If timestamps have no timezone info, assume they are UTC, then convert to Central.
ASSUME_TZ_IF_NAIVE = "UTC"
TARGET_TZ = "US/Central"

# Output files
OUT_TN_DAILY = "eagle_tn_daily_2021_2025.csv"
OUT_10CITY_DAILY = "eagle_10city_daily_2021_2025.csv"

# Column names we expect to exist
STATE_COL = "state"
COUNTY_COL = "county"
TIME_COL = "run_start_time"

# 2) County -> city mapping (10 locations)

CITY_COUNTY_MAP = {
    "Davidson": "Nashville",
    "Shelby": "Memphis",      # Bartlett is also Shelby
    "Knox": "Knoxville",
    "Hamilton": "Chattanooga",
    "Montgomery": "Clarksville",
    "Rutherford": "Murfreesboro",
    "Williamson": "Franklin",
    "Washington": "Johnson City",
    "Madison": "Jackson",
}

# If we want Bartlett as its own location (still Shelby County),
# we duplicate Shelby rows into a separate "Bartlett" city.
INCLUDE_BARTLETT = True


def detect_outage_col(columns):
    """
    Detect which column represents outage magnitude.

    Different years use different names, so we try common candidates.
    """
    cols = [c.strip() for c in columns]

    candidates = [
        "customers_out",
        "sum",            
    ]

    # exact match first
    for c in candidates:
        if c in cols:
            return c

    # fallback: any column containing "customer"
    for c in cols:
        if "customer" in c.lower():
            return c

    raise ValueError(f"Could not detect outage column. Columns are: {cols}")


def process_one_file(file_path: Path, out_path: Path, write_header: bool) -> bool:
    """
    Stream-read one file and append TN daily county peak outages to out_path.
    """

    print(f"\nProcessing file: {file_path.name}")

    outage_col = None  # detected from the first chunk

    for chunk in pd.read_csv(file_path, chunksize=CHUNK_SIZE):

        # Detect outage column once per file (based on the first chunk)
        if outage_col is None:
            outage_col = detect_outage_col(chunk.columns)
            print(f"Detected outage column for {file_path.name}: {outage_col}")

        # Keep only Tennessee rows
        chunk = chunk[chunk[STATE_COL] == "Tennessee"]
        if chunk.empty:
            continue

        # Parse timestamps
        chunk[TIME_COL] = pd.to_datetime(chunk[TIME_COL], errors="coerce")
        chunk = chunk.dropna(subset=[TIME_COL])

        # Standardize timezone
        if chunk[TIME_COL].dt.tz is None:
            chunk[TIME_COL] = chunk[TIME_COL].dt.tz_localize(
                ASSUME_TZ_IF_NAIVE, ambiguous="NaT", nonexistent="NaT"
            )
        chunk[TIME_COL] = chunk[TIME_COL].dt.tz_convert(TARGET_TZ)

        # Daily bucket
        chunk["date"] = chunk[TIME_COL].dt.date

        # DAILY PEAK (max) outages per county
        daily = chunk.groupby([COUNTY_COL, "date"], as_index=False)[outage_col].max()

        # Standardize output column name so all years match
        daily = daily.rename(columns={outage_col: "customers_out"})

        # Append results
        daily.to_csv(out_path, mode="a", header=write_header, index=False)
        write_header = False

    return write_header


def build_10city_dataset(tn_daily_path: Path, out_10city_path: Path):
    """
    Convert county-level TN daily file into 10-city daily file using mapping.
    """

    df = pd.read_csv(tn_daily_path)

    # Map county -> city
    df["city"] = df[COUNTY_COL].map(CITY_COUNTY_MAP)

    # Keep only mapped counties
    df_city = df.dropna(subset=["city"]).copy()

    # Optional: duplicate Shelby County rows for Bartlett
    if INCLUDE_BARTLETT:
        shelby = df[df[COUNTY_COL] == "Shelby"].copy()
        if not shelby.empty:
            shelby["city"] = "Bartlett"
            df_city = pd.concat([df_city, shelby], ignore_index=True)

    # Select and sort columns
    df_city = df_city[["city", "date", "customers_out", COUNTY_COL]].sort_values(["city", "date"])

    df_city.to_csv(out_10city_path, index=False)

    print("\n10-city dataset saved:", out_10city_path)
    print("Cities present:", sorted(df_city["city"].unique().tolist()))
    print("Rows:", len(df_city))


def main():
    tn_out = Path(OUT_TN_DAILY)
    city_out = Path(OUT_10CITY_DAILY)

    # Start fresh each run
    if tn_out.exists():
        tn_out.unlink()
    if city_out.exists():
        city_out.unlink()

    write_header = True

    # Process each file that exists
    for f in FILES:
        fp = Path(f)
        if not fp.exists():
            print(f"Missing file: {f}")
            continue
        write_header = process_one_file(fp, tn_out, write_header)

    print("\nTN daily county file saved:", tn_out)

    # Build the 10-city file
    build_10city_dataset(tn_out, city_out)

    print("\nAll done.")


if __name__ == "__main__":
    main()