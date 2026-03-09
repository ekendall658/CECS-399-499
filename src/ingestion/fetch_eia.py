import os
import requests
import pandas as pd
import time

# --- CONFIGURATION ---
EIA_API_KEY = os.getenv("EIA_API_KEY")
if not EIA_API_KEY:
    raise ValueError("EIA_API_KEY environment variable is not set.")

BA_CODE = "TVA"
START_DATE = "2021-01-01T00"
END_DATE = "2025-12-31T23"
FILENAME = "tva_eia_21_25.csv"


def fetch_eia_master_data():
    all_data = []
    offset = 0
    rows_per_request = 5000

    print(f"Starting Ingestion for {BA_CODE}...")

    while True:
        url = f"https://api.eia.gov/v2/electricity/rto/region-data/data/?api_key={EIA_API_KEY}"
        params = {
            "frequency": "hourly",
            "data[0]": "value",
            "facets[respondent][]": BA_CODE,
            "facets[type][]": ["D", "DF", "NG", "TI"],
            "start": START_DATE,
            "end": END_DATE,
            "sort[0][column]": "period",
            "sort[0][direction]": "asc",
            "offset": offset,
            "length": rows_per_request
        }

        try:
            r = requests.get(url, params=params)
            res_json = r.json()

            if "error" in res_json:
                print(f"EIA API Error: {res_json['error']}")
                break

            data = res_json["response"]["data"]

            if not data:
                break

            all_data.extend(data)
            print(f"Rows Ingested: {len(all_data)}...")

            if len(data) < rows_per_request:
                break

            offset += rows_per_request
            time.sleep(1)

        except Exception as e:
            print(f"Error: {e}")
            break

    if not all_data:
        return None

    # Step 1: Create DataFrame
    df_raw = pd.DataFrame(all_data)

    # Step 2: Pivot
    df_pivot = df_raw.pivot_table(
        index="period",
        columns="type-name",
        values="value",
        aggfunc="first"
    ).reset_index()

    # Step 3: Dynamic Mapping
    current_cols = df_pivot.columns.tolist()
    rename_map = {"period": "timestamp"}

    for col in current_cols:
        if "Demand Forecast" in col:
            rename_map[col] = "demand_forecast_mwh"
        elif "Net Generation" in col:
            rename_map[col] = "net_generation_mwh"
        elif "Net Interchange" in col:
            rename_map[col] = "net_interchange_mwh"
        elif "Demand" in col and "Forecast" not in col:
            rename_map[col] = "actual_demand_mwh"

    df_pivot = df_pivot.rename(columns=rename_map)

    # Step 4: Timezone Correction and Trimming
    df_pivot["timestamp"] = pd.to_datetime(df_pivot["timestamp"])
    df_pivot["timestamp"] = df_pivot["timestamp"] - pd.Timedelta(hours=5)

    mask = (
        (df_pivot["timestamp"] >= "2021-01-01 00:00:00") &
        (df_pivot["timestamp"] <= "2025-12-31 23:00:00")
    )
    df_pivot = df_pivot.loc[mask].copy()

    # Step 5: Convert all columns after 'timestamp' to numeric
    for col in df_pivot.columns:
        if col != "timestamp":
            df_pivot[col] = pd.to_numeric(df_pivot[col], errors="coerce")

    return df_pivot


if __name__ == "__main__":
    df_eia = fetch_eia_master_data()

    if df_eia is not None:
        df_eia.to_csv(FILENAME, index=False)
        print(f"\nSUCCESS: Data trimmed and saved to {FILENAME}")
        print("\nVerified Columns:")
        print(df_eia.columns.tolist())
        print(df_eia.head())#This is a blank code for initializing
