import pandas as pd
import os

INPUT_FILE = "tva_eia_21_25.csv"
OUTPUT_FILE = "tva_eia_21_25_utc.csv"


def convert_eia_to_utc(input_file=INPUT_FILE, output_file=OUTPUT_FILE):
    df = pd.read_csv(input_file)

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["timestamp"] = df["timestamp"] + pd.Timedelta(hours=5)
    df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")

    df = df.sort_values("timestamp")
    df = df.set_index("timestamp")

    full_range = pd.date_range(
        start="2021-01-01 00:00",
        end="2025-12-31 23:00",
        freq="h",
        tz="UTC"
    )

    df = df.reindex(full_range)
    df.index.name = "timestamp"
    df = df.reset_index()

    df = df.rename(columns={
        "Day-ahead demand forecast": "demand_forecast_mwh",
        "Net generation": "net_generation_mwh",
        "Total interchange": "net_interchange_mwh"
    })

    for col in df.columns:
        if col != "timestamp":
            df[col] = pd.to_numeric(df[col], errors="coerce")

    save_path = os.path.join(os.getcwd(), output_file)
    df.to_csv(save_path, index=False)

    print(f"SUCCESS: Data saved to {save_path}")
    print(df.info())
    print(df.head())

    return df


if __name__ == "__main__":
    convert_eia_to_utc()