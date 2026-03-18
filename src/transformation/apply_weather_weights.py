from pathlib import Path
import pandas as pd

# =========================================================
# Paths
# =========================================================
WEATHER_FILE = Path("local_data/bronze/tn_weather_top10_21_25.csv")
WEIGHTS_FILE = Path("local_data/silver/tn_selected_city_population_weights.csv")

OUTPUT_CSV = Path("local_data/silver/tn_weighted_weather_21_25.csv")
OUTPUT_PARQUET = Path("local_data/gold/tn_weighted_weather_21_25.parquet")

OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
OUTPUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)

# =========================================================
# Config
# =========================================================
CITIES = [
    "nashville",
    "memphis",
    "knoxville",
    "chattanooga",
    "clarksville",
    "murfreesboro",
    "franklin",
    "johnson_city",
    "jackson",
    "hendersonville",
]

METRICS = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "cloud_cover",
    "wind_speed_10m",
    "shortwave_radiation",
]

YEARS = [2021, 2022, 2023, 2024, 2025]


# =========================================================
# Loaders
# =========================================================
def load_weather():
    if not WEATHER_FILE.exists():
        raise FileNotFoundError(f"Missing weather file: {WEATHER_FILE}")

    df = pd.read_csv(WEATHER_FILE)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df["year"] = df["timestamp"].dt.year

    return df


def load_weights():
    if not WEIGHTS_FILE.exists():
        raise FileNotFoundError(f"Missing weights file: {WEIGHTS_FILE}")

    weights = pd.read_csv(WEIGHTS_FILE)

    expected = ["city"] + [f"weight_{y}" for y in YEARS]
    missing = [c for c in expected if c not in weights.columns]

    if missing:
        raise ValueError(f"Missing weight columns: {missing}")

    return weights


# =========================================================
# Build lookup
# =========================================================
def build_weight_lookup(weights):
    lookup = {}
    for year in YEARS:
        lookup[year] = dict(zip(weights["city"], weights[f"weight_{year}"]))
    return lookup


# =========================================================
# Core logic
# =========================================================
def apply_weights(df, lookup):
    df = df.copy()

    # attach weights per row
    for city in CITIES:
        df[f"{city}_weight"] = df["year"].map(
            lambda y: lookup.get(y, {}).get(city, pd.NA)
        )

    # compute weighted metrics
    for metric in METRICS:
        weighted_col = f"weighted_{metric}"
        df[weighted_col] = 0.0

        for city in CITIES:
            w_col = f"{city}_weight"
            x_col = f"{city}_{metric}"

            if x_col not in df.columns:
                raise ValueError(f"Missing weather column: {x_col}")

            df[x_col] = pd.to_numeric(df[x_col], errors="coerce")
            df[w_col] = pd.to_numeric(df[w_col], errors="coerce")

            df[weighted_col] += df[x_col] * df[w_col]

    return df


# =========================================================
# Main
# =========================================================
def main():
    weather = load_weather()
    weights = load_weights()
    lookup = build_weight_lookup(weights)

    df_final = apply_weights(weather, lookup)

    # save outputs
    df_final.to_csv(OUTPUT_CSV, index=False)
    df_final.to_parquet(OUTPUT_PARQUET, index=False)

    print(f"\nSUCCESS:")
    print(f"Silver CSV → {OUTPUT_CSV}")
    print(f"Gold Parquet → {OUTPUT_PARQUET}\n")

    print(df_final[[
        "timestamp",
        "weighted_temperature_2m",
        "weighted_relative_humidity_2m",
        "weighted_precipitation"
    ]].head())

    print(df_final.columns.tolist())

if __name__ == "__main__":
    main()