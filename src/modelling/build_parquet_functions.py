import pandas as pd
from pathlib import Path

# Write parquet
def write_parquet(df: pd.DataFrame, output_path: str) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output, index=False, engine="pyarrow")
    print(f"Wrote {len(df):,} rows to {output}")

# Define Fact Builder Functions

# Individual energy events, comprised of semantic data.
def build_fact_energy_events(doe: pd.DataFrame) -> pd.DataFrame:
    df = doe.copy()

    df["demand_loss"] = pd.to_numeric(df["Demand Loss (MW)"], errors="coerce")
    df["number_affected"] = pd.to_numeric(
        df["customers_affected"], errors="coerce"
    )

    fact_energy_events = df[
        [   "event_start_utc",
            "event_end_utc",
            "alert_criteria",
            "event_type",
            "demand_loss",
            "number_affected",
        ]
    ].copy()
    return fact_energy_events

# Daily outage reports on a county-by-county basis within Tennessee
def build_fact_outage_daily(Eagle: pd.DataFrame) -> pd.DataFrame:
    df = Eagle.copy()

    df = df.rename(columns={
        "date": "date",
        "county": "county",
        "customers_out": "customers_wo_power"
    })

    return df 

# Hourly reports from the ten counties and their largest cities:
def build_fact_weather_city_hourly(tn_weather: pd.DataFrame) -> pd.DataFrame:
    df = tn_weather.copy()

    # Weather measures we want for each city
    measures = [
        "temperature_2m",
        "precipitation",
        "cloud_cover",
        "wind_speed_10m",
        "shortwave_radiation",
    ]

    # Detect available city prefixes from columns like nashville_temperature_2m
    city_measure_map = {}

    for col in df.columns:
        if col == "timestamp":
            continue
        for measure in measures:
            suffix = f"_{measure}"
            if col.endswith(suffix):
                city = col[: -len(suffix)]
                city_measure_map.setdefault(city, {})[measure] = col

    if not city_measure_map:
        raise ValueError("No city weather columns matching the expected patterns were found")

    rows = []

    for city, cols in city_measure_map.items():
        city_df = pd.DataFrame({
            "time_key": df["timestamp"],
            "city_key": city,
            "temperature": df[cols["temperature_2m"]],
            "precipitation": df[cols["precipitation"]],
            "cloud_cover": df[cols["cloud_cover"]],
            "wind_speed": df[cols["wind_speed_10m"]],
            "shortwave_radiation": df[cols["shortwave_radiation"]]
        })
        rows.append(city_df)

    fact_weather_city_hourly = pd.concat(rows, ignore_index=True)

    return fact_weather_city_hourly

# Hour-by-hour data about energy load within TVA
def build_fact_energy_load_hourly(EIA: pd.DataFrame) -> pd.DataFrame:
    df = EIA.copy()

    df["source_id"] = "TVA"  # adjust if needed

    df = df.rename(columns={
        "timestamp": "time_key",
        "net_generation_mwh": "net_gen_mwh",
    })

    fact_energy_load_hourly = df[
        [
            "time_key",
            "source_id",
            "demand_forecast_mwh",
            "actual_demand_mwh",
            "net_gen_mwh",
        ]
    ].copy()

    return fact_energy_load_hourly

# Feature engineered facts about hourly TVA data.

def build_fact_energy_features_hourly(EIA: pd.DataFrame) -> pd.DataFrame:
    df = EIA.copy()

    df["source_id"] = "TVA"   # temporary source key

    # Rename to target schema
    df = df.rename(columns={
        "timestamp": "time_key",
        "Percent Forecast Error": "forecast_error_pct",
        "demand_ramp_rate_pct": "demand_ramp_pct",
        "demand_rolling_mean_24h": "demand_rolling_mean",
        "demand_rolling_std_24h": "demand_rolling_std",
    })

    fact_energy_features_hourly = df[
        [
            "time_key",
            "source_id",
            "net_interchange_mwh",
            "balance_error",
            "forecast_error_pct",
            "demand_ramp_pct",
            "demand_rolling_mean",
            "demand_rolling_std",
            "demand_residual",
            "demand_zscore",
            "hour_sin",
            "hour_cos",
            "month_sin",
            "month_cos",
        ]
    ].copy()

    return fact_energy_features_hourly

"""
The next section is dedicated entirely to building out the dimension tables.
Any keys seen in this section are entirely temporary, and are stand-ins prior to the construction of
the postgres data warehouse in SQL.

"""

# Currently manually creating the TVA, as that is all that we are pulling data for.
def build_dim_grid() -> pd.DataFrame:
    dim_grid = pd.DataFrame({
        "grid_id": ["TVA"],
        "grid_name": ["TVA"]
    })

    dim_grid["grid_id"] = dim_grid["grid_id"].astype("string")
    dim_grid["grid_name"] = dim_grid["grid_name"].astype("string")

    return dim_grid

# Every hour of data within our dataset
def build_dim_time_hourly(EIA: pd.DataFrame = None, tn_weather: pd.DataFrame = None) -> pd.DataFrame:
    timestamp_series = []

    timestamp_series.append(EIA["timestamp"])
    timestamp_series.append(tn_weather["timestamp"])
    all_timestamps = pd.concat(timestamp_series, ignore_index=True).dropna().drop_duplicates()
    all_timestamps = pd.Series(all_timestamps).sort_values().reset_index(drop=True)

    dim_time_hourly = pd.DataFrame({
        "timestamp": all_timestamps
    }) # Merged dataset including the unique timestamps between the EIA and weather datasets.

    # Temporary key
    dim_time_hourly["time_id"] = dim_time_hourly["timestamp"]

    dim_time_hourly["hour_of_day"] = pd.to_datetime(dim_time_hourly["timestamp"]).dt.hour.astype("Int64")
    dim_time_hourly["day_of_week"] = pd.to_datetime(dim_time_hourly["timestamp"]).dt.dayofweek.astype("Int64")
    dim_time_hourly["is_weekend"] = pd.to_datetime(dim_time_hourly["day_of_week"]).isin([5, 6])
    dim_time_hourly["month"] = pd.to_datetime(dim_time_hourly["timestamp"]).dt.month.astype("Int64")
    dim_time_hourly["quarter"] = pd.to_datetime(dim_time_hourly["timestamp"]).dt.quarter.astype("Int64")
    dim_time_hourly["year"] = pd.to_datetime(dim_time_hourly["timestamp"]).dt.year.astype("Int64")

    # ^ Technically this is feature engineering that should be present in the silver layer.

    dim_time_hourly = dim_time_hourly[
        [
            "time_id",
            "timestamp",
            "hour_of_day",
            "day_of_week",
            "is_weekend",
            "month",
            "quarter",
            "year",
        ]
    ].copy()

    return dim_time_hourly


def build_dim_city(cities: pd.DataFrame) -> pd.DataFrame:
    df = cities.copy()

    population_col = None
    for candidate in [
        "population_2025",
        "population_2024",
        "population_2023",
        "population_2022",
        "population_2021",
    ]:
        if candidate in df.columns:
            population_col = candidate
            break

    if population_col is None:
        df["population"] = pd.NA
    else:
        df["population"] = df[population_col]

    df["city_name"] = df["city"]
    df["city_id"] = df["city_name"].str.lower()
    df["state_code"] = df["Geographic Area"]

    df["latitude"] = pd.NA
    df["longitude"] = pd.NA

    dim_city = df[
        [
            "city_id",
            "city_name",
            "state_code",
            "population",
            "latitude",
            "longitude",
        ]
    ].drop_duplicates(subset=["city_id"]).reset_index(drop=True)

    return dim_city


# Pulling county data from the EAGLE dataset, no other data as of yet.

def build_dim_county(Eagle: pd.DataFrame) -> pd.DataFrame:
    df = Eagle.copy()

    county_names = (
        df["county"]
        .astype("string")
        .str.strip()
        .dropna()
        .drop_duplicates()
        .sort_values()
        .reset_index(drop=True)
    )

    dim_county = pd.DataFrame({
        "county_name": county_names
    })

    # Temporary key
    dim_county["county_id"] = dim_county["county_name"].str.lower()
    dim_county["state_code"] = "TN"
    dim_county["fips_code"] = pd.NA
    dim_county["population"] = pd.NA
    dim_county["latitude"] = pd.NA
    dim_county["longitude"] = pd.NA

    dim_county = dim_county[
        [
            "county_id",
            "county_name",
            "state_code",
            "fips_code",
            "population",
            "latitude",
            "longitude",
        ]
    ].copy()

    dim_county["county_id"] = dim_county["county_id"].astype("string")
    dim_county["county_name"] = dim_county["county_name"].astype("string")
    dim_county["state_code"] = dim_county["state_code"].astype("string")
    dim_county["fips_code"] = dim_county["fips_code"].astype("string")
    dim_county["population"] = pd.to_numeric(dim_county["population"], errors="coerce").astype("Int64")

    return dim_county