import pandas as pd
import numpy as np
from pathlib import Path

# STEP 1: Read Files and Clean Data
# Read the original 2021-2023 DOE-417 files

BASE_DIR = Path("local_data/bronze")
files = [
    BASE_DIR / "2021_DOE417.xls",
    BASE_DIR / "2022_DOE417.xls",
    BASE_DIR / "2023_DOE417.xls"
]

OUTPUT_CSV = Path("local_data/silver/tn_weather_weighted_final.csv")

all_raw_data = []

print("Loading files and cleaning Excel errors...")
for file in files:
    try:
        # header=1 skips the first title row in Excel
        df = pd.read_excel(file, sheet_name="Sheet1", header=1)

        # FIX: In 2023, the column name is 'Event Month'. Change it back to 'Month'.
        if "Event Month" in df.columns:
            df = df.rename(columns={"Event Month": "Month"})

        # CLEANING: Replace Excel errors like #NAME? or 'Unknown' with empty values
        df = df.replace(['Unknown', '#NAME?', 'unknown', 'n/a', 'N/A'], np.nan)

        # CLEANING: Convert customer counts to numbers. If it's text, turn it into 0.
        if "Number of Customers Affected" in df.columns:
            df["Number of Customers Affected"] = pd.to_numeric(
                df["Number of Customers Affected"],
                errors='coerce'
            ).fillna(0)

        # Tag each row with the year from the filename
        df["source_year"] = file.stem[:4]

        all_raw_data.append(df)

    except Exception as e:
        print(f"Error loading {file}: {e}")

# Combine all 3 years into one temporary table
df_master_raw = pd.concat(all_raw_data, ignore_index=True)

# STEP 2: Filter for Tennessee Weather
weather_keywords = ['weather', 'storm', 'wind', 'ice', 'snow', 'heat', 'cold', 'flood', 'tornado']

# Keep only Tennessee rows that mention weather keywords
df_tn = df_master_raw[
    df_master_raw['Area Affected'].astype(str).str.contains('Tennessee', case=False, na=False)
].copy()

df_tn_weather_base = df_tn[
    df_tn['Event Type'].astype(str).str.contains('|'.join(weather_keywords), case=False, na=False) |
    df_tn['Alert Criteria'].astype(str).str.contains('|'.join(weather_keywords), case=False, na=False)
].copy()

# STEP 3: Split into 10 City DataFrames
# Map cities to their counties for better accuracy
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
    # Find rows matching this specific city or its county
    mask = df_tn_weather_base['Area Affected'].astype(str).str.contains(
        '|'.join(keywords), case=False, na=False
    )

    # Create a separate DataFrame for this city and add a 'City' label
    df_temp = df_tn_weather_base[mask].copy()
    df_temp['City'] = city

    city_df_list.append(df_temp)

# STEP 4: Combine Cities and Add Population Data
# Combine the 10 city dataframes into one easy-to-use master table
df_split_combined = pd.concat(city_df_list, ignore_index=True)

# Population data (2021-2025) for future weighted calculations
pop_dict = {
    "City": ["Nashville", "Memphis", "Knoxville", "Chattanooga", "Clarksville", "Murfreesboro", "Franklin", "Johnson City", "Jackson", "Bartlett"],
    "2021": [678134, 633104, 193598, 181163, 170912, 156675, 83096, 67859, 67187, 56998],
    "2022": [683622, 628127, 195889, 184086, 176974, 162398, 85000, 68500, 67500, 57500],
    "2023": [708772, 606551, 200595, 193802, 190229, 172029, 90388, 74263, 69578, 56467],
    "2024": [712000, 604000, 201000, 195000, 192000, 174000, 91000, 74500, 69700, 56300],
    "2025": [715000, 602000, 202000, 196000, 194000, 175000, 92000, 74800, 69800, 56200]
}

df_pop = pd.DataFrame(pop_dict).melt(id_vars="City", var_name="Year", value_name="Population")

# Merge weather data with the population table
df_split_combined['Year'] = df_split_combined['source_year'].astype(str)
df_pop['Year'] = df_pop['Year'].astype(str)

df_final = pd.merge(df_split_combined, df_pop, on=["City", "Year"], how="left")

# STEP 5: Export Final File
OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
df_final.to_csv(OUTPUT_CSV, index=False)

print(f"Done! Final file saved as: {OUTPUT_CSV}")
