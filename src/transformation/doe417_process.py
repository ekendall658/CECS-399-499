import pandas as pd
import numpy as np
from pathlib import Path

# =========================================================
# STEP 1: Read Files and Clean Data
# =========================================================

BASE_DIR = Path("local_data/bronze")
OUTPUT_CSV = Path("local_data/silver/tn_weather_weighted_final.csv")

files = [
    BASE_DIR / "2021_DOE417.xls",
    BASE_DIR / "2022_DOE417.xls",
    BASE_DIR / "2023_DOE417.xls"
]

all_raw_data = []

print("Loading files and cleaning Excel errors...")

for file in files:
    try:
        # Read Excel; header=1 skips the first title row
        df = pd.read_excel(file, header=1)

        # Standardize known inconsistent column names
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

        # Clean placeholder/error values
        df = df.replace(
            ['Unknown', '#NAME?', 'unknown', 'n/a', 'N/A', 'NA', 'UNK'],
            np.nan
        )

        # Convert affected customers to numeric
        if "Number of Customers Affected" in df.columns:
            df["Number of Customers Affected"] = pd.to_numeric(
                df["Number of Customers Affected"],
                errors="coerce"
            ).fillna(0)

        # Tag source year from filename
        df["source_year"] = file.stem[:4]

        # -------------------------------------------------
        # STEP 1B: Convert local event times to UTC
        # Tennessee is primarily America/Chicago
        # -------------------------------------------------

        # Start timestamp
        if "Date Event Began" in df.columns and "Time Event Began" in df.columns:
            df["event_start_local"] = pd.to_datetime(
                df["Date Event Began"].astype(str).str.strip() + " " +
                df["Time Event Began"].astype(str).str.strip(),
                errors="coerce"
            )

            df["event_start_local"] = df["event_start_local"].dt.tz_localize(
                "America/Chicago",
                ambiguous="NaT",
                nonexistent="NaT"
            )

            df["event_start_utc"] = df["event_start_local"].dt.tz_convert("UTC")

        else:
            df["event_start_local"] = pd.NaT
            df["event_start_utc"] = pd.NaT

        # End timestamp
        if "Date of Restoration" in df.columns and "Time of Restoration" in df.columns:
            df["event_end_local"] = pd.to_datetime(
                df["Date of Restoration"].astype(str).str.strip() + " " +
                df["Time of Restoration"].astype(str).str.strip(),
                errors="coerce"
            )

            df["event_end_local"] = df["event_end_local"].dt.tz_localize(
                "America/Chicago",
                ambiguous="NaT",
                nonexistent="NaT"
            )

            df["event_end_utc"] = df["event_end_local"].dt.tz_convert("UTC")

        else:
            df["event_end_local"] = pd.NaT
            df["event_end_utc"] = pd.NaT

        # Optional outage duration in hours
        df["outage_duration_hours"] = (
            df["event_end_utc"] - df["event_start_utc"]
        ).dt.total_seconds() / 3600

        all_raw_data.append(df)
        print(f"Loaded: {file}")

    except Exception as e:
        print(f"Error loading {file}: {e}")

if not all_raw_data:
    raise ValueError("No DOE-417 files were loaded successfully.")

# Combine all years
df_master_raw = pd.concat(all_raw_data, ignore_index=True)

# =========================================================
# STEP 2: Filter for Tennessee Weather
# =========================================================

weather_keywords = [
    'weather', 'storm', 'wind', 'ice', 'snow',
    'heat', 'cold', 'flood', 'tornado'
]

# Make sure needed columns exist
for col in ["Area Affected", "Event Type", "Alert Criteria"]:
    if col not in df_master_raw.columns:
        raise KeyError(f"Required column not found: {col}")

# Keep only Tennessee-related rows
df_tn = df_master_raw[
    df_master_raw["Area Affected"].astype(str).str.contains(
        "Tennessee", case=False, na=False
    )
].copy()

# Keep only rows that mention weather-related events
weather_pattern = "|".join(weather_keywords)

df_tn_weather_base = df_tn[
    df_tn["Event Type"].astype(str).str.contains(weather_pattern, case=False, na=False) |
    df_tn["Alert Criteria"].astype(str).str.contains(weather_pattern, case=False, na=False)
].copy()

# =========================================================
# STEP 3: Split into 10 City DataFrames
# =========================================================

city_mapping = {
    "Nashville": ["Nashville", "Davidson"],
    "Memphis": ["Memphis", "Shelby"],
    "Knoxville": ["Knoxville", "Knox"],
    "Chattanooga": ["Chattanooga", "Hamilton"],
    "Clarksville": ["Clarksville", "Montgomery"],
    "Murfreesboro": ["Murfreesboro", "Rutherford"],
    "Franklin": ["Franklin", "Williamson"],
    "Johnson City": ["Johnson City", "Washington", "Carter", "Sullivan"],
    "Jackson": ["Jackson", "Madison"],
    "Bartlett": ["Bartlett", "Shelby"]
}

print("Splitting data into 10 city dataframes...")
city_df_list = []

for city, keywords in city_mapping.items():
    pattern = "|".join(keywords)

    mask = df_tn_weather_base["Area Affected"].astype(str).str.contains(
        pattern, case=False, na=False
    )

    df_temp = df_tn_weather_base[mask].copy()
    df_temp["City"] = city
    city_df_list.append(df_temp)

if not city_df_list:
    raise ValueError("No city-level Tennessee weather data was created.")

df_split_combined = pd.concat(city_df_list, ignore_index=True)

# =========================================================
# STEP 4: Add Population Data
# =========================================================

pop_dict = {
    "City": [
        "Nashville", "Memphis", "Knoxville", "Chattanooga",
        "Clarksville", "Murfreesboro", "Franklin",
        "Johnson City", "Jackson", "Bartlett"
    ],
    "2021": [678134, 633104, 193598, 181163, 170912, 156675, 83096, 67859, 67187, 56998],
    "2022": [683622, 628127, 195889, 184086, 176974, 162398, 85000, 68500, 67500, 57500],
    "2023": [708772, 606551, 200595, 193802, 190229, 172029, 90388, 74263, 69578, 56467],
    "2024": [712000, 604000, 201000, 195000, 192000, 174000, 91000, 74500, 69700, 56300],
    "2025": [715000, 602000, 202000, 196000, 194000, 175000, 92000, 74800, 69800, 56200]
}

df_pop = pd.DataFrame(pop_dict).melt(
    id_vars="City",
    var_name="Year",
    value_name="Population"
)

df_split_combined["Year"] = df_split_combined["source_year"].astype(str)
df_pop["Year"] = df_pop["Year"].astype(str)

df_final = pd.merge(
    df_split_combined,
    df_pop,
    on=["City", "Year"],
    how="left"
)

# =========================================================
# STEP 5: Export Final File
# =========================================================

OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
df_final.to_csv(OUTPUT_CSV, index=False)

print(f"Done! Final file saved as: {OUTPUT_CSV}")
print(f"Final row count: {len(df_final)}")
