# Imports

import pandas as pd # Used for Datetime Conversions
import numpy as np # Array Functions
import psycopg # Dimension Tables (Temporary)
from psycopg2.extras import execute_values # Used for Creating Fact Tables
import psycopg2 # Used for Creating Fact Tables

# Connections

# Establish psycopg connection for Dimension tables
conn = psycopg.connect(
    host="postgres-1.cju08ags2kn7.us-east-2.rds.amazonaws.com",
    port=5432,
    dbname="postgres",
    user="cecs_energy_lake",
    password="94_8y-g2408!gsdf?",
)

# Establish connection for Fact Tables
conn2 = psycopg2.connect(
    host="postgres-1.cju08ags2kn7.us-east-2.rds.amazonaws.com",
    port=5432,
    dbname="postgres",
    user="cecs_energy_lake",
    password="94_8y-g2408!gsdf?",
)


# Parquet file paths:
dim_city = pd.read_parquet("../../local_data/gold/dim_city.parquet")
dim_grid = pd.read_parquet("../../local_data/gold/dim_grid.parquet")
dim_county = pd.read_parquet("../../local_data/gold/dim_city.parquet")
df_time_hourly = pd.read_parquet("../../local_data/gold/dim_time_hourly.parquet")
fact_outage = pd.read_parquet("../../local_data/gold/fact_outage_daily.parquet")
fact_weather = pd.read_parquet("../../local_data/gold/fact_weather_city_hourly.parquet")
fact_energy_load = pd.read_parquet("../../local_data/gold/fact_energy_load_hourly.parquet")
fact_energy_features = pd.read_parquet("../../local_data/gold/fact_energy_features_hourly.parquet")
fact_energy_event = pd.read_parquet("../../local_data/gold/fact_energy_event.parquet")
fact_anomaly = pd.read_parquet("../../local_data/gold/fact_anomaly_detection.parquet")

# Helper Functions

def fetch_dataframe(conn2, sql):
    with conn2.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
        cols = [desc[0] for desc in cur.description]
    return pd.DataFrame(rows, columns=cols)


# Schema Design - Create Tables

create_dim_cities = """
CREATE TABLE IF NOT EXISTS dim_city (
    city_id TEXT PRIMARY KEY,
    city_name TEXT NOT NULL,
    state_code TEXT NOT NULL,
    population INTEGER,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION
);
"""

create_dim_county = """
CREATE TABLE IF NOT EXISTS dim_county (
    county_id TEXT PRIMARY KEY,
    county_name TEXT NOT NULL,
    state_code TEXT NOT NULL,
    fips_code TEXT,
    population INTEGER,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION
);
"""

create_dim_grid = """
CREATE TABLE IF NOT EXISTS dim_grid (
    grid_id TEXT PRIMARY KEY,
    grid_name TEXT NOT NULL
);
"""

create_dim_time_hourly = """
CREATE TABLE IF NOT EXISTS dim_time_hourly(
    time_id TIMESTAMPTZ PRIMARY KEY,
    ts_utc TIMESTAMPTZ NOT NULL,
    hour_of_day INTEGER,
    day_of_week INTEGER,
    is_weekend BOOLEAN,
    month INTEGER,
    quarter INTEGER,
    year INTEGER
);
"""
create_fact_outage_daily = """
CREATE TABLE IF NOT EXISTS fact_outage_daily (
    time_key TIMESTAMPTZ NOT NULL,
    county_id TEXT NOT NULL,
    customers_wo_power INTEGER,
    PRIMARY KEY (time_key, county_id),
    CONSTRAINT fk_fact_outage_daily_time
        FOREIGN KEY (time_key) REFERENCES dim_time_hourly(time_id),
    CONSTRAINT fk_fact_outage_daily_county
        FOREIGN KEY (county_id) REFERENCES dim_county(county_id)
);
"""
create_fact_weather_hourly = """
CREATE TABLE IF NOT EXISTS fact_weather_hourly (
    time_key TIMESTAMPTZ NOT NULL,
    city_id TEXT NOT NULL,
    temperature DOUBLE PRECISION,
    wind_speed DOUBLE PRECISION,
    precipitation DOUBLE PRECISION,
    humidity DOUBLE PRECISION,
    PRIMARY KEY (time_key, city_id),
    CONSTRAINT fk_fact_weather_hourly_time
        FOREIGN KEY (time_key) REFERENCES dim_time_hourly(time_id),
    CONSTRAINT fk_fact_weather_hourly_city
        FOREIGN KEY (city_id) REFERENCES dim_city(city_id)
);
"""
create_fact_energy_load_hourly = """
CREATE TABLE IF NOT EXISTS fact_energy_load_hourly (
    time_key TIMESTAMPTZ NOT NULL,
    grid_id TEXT NOT NULL,
    load_mw DOUBLE PRECISION,
    PRIMARY KEY (time_key, grid_id),
    CONSTRAINT fk_fact_energy_load_time
        FOREIGN KEY (time_key) REFERENCES dim_time_hourly(time_id),
    CONSTRAINT fk_fact_energy_load_grid
        FOREIGN KEY (grid_id) REFERENCES dim_grid(grid_id)
);
"""

create_fact_energy_features_hourly = """
CREATE TABLE IF NOT EXISTS fact_energy_features_hourly (
    time_key TIMESTAMPTZ NOT NULL,
    source_id TEXT NOT NULL,
    net_interchange_mwh DOUBLE PRECISION,
    balance_error DOUBLE PRECISION,
    forecast_error_pct DOUBLE PRECISION,
    demand_ramp_pct DOUBLE PRECISION,
    demand_rolling_mean DOUBLE PRECISION,
    demand_rolling_std DOUBLE PRECISION,
    demand_residual DOUBLE PRECISION,
    demand_zscore DOUBLE PRECISION,
    hour_sin DOUBLE PRECISION,
    hour_cos DOUBLE PRECISION,
    month_sin DOUBLE PRECISION,
    month_cos DOUBLE PRECISION,
    PRIMARY KEY (time_key, source_id),
    CONSTRAINT fk_fact_energy_features_hourly_time
        FOREIGN KEY (time_key) REFERENCES dim_time_hourly(time_id),
    CONSTRAINT fk_fact_energy_features_hourly_source
        FOREIGN KEY (source_id) REFERENCES dim_source(source_id)
);
"""
create_fact_grid_alert_event = """
CREATE TABLE IF NOT EXISTS fact_grid_alert_event (
    event_id BIGSERIAL PRIMARY KEY,
    event_start_utc TIMESTAMPTZ,
    event_end_utc TIMESTAMPTZ,
    alert_criteria TEXT,
    event_type TEXT,
    demand_loss DOUBLE PRECISION,
    number_affected BIGINT
);
"""

create_fact_table = """
CREATE TABLE IF NOT EXISTS fact_anomaly_detection (
    time_key VARCHAR NOT NULL,
    source_id VARCHAR NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    actual_outage_target BIGINT,
    anomaly_score DOUBLE PRECISION,
    anomaly_flag BIGINT,
    primary_driver VARCHAR,
    secondary_driver VARCHAR,
    tertiary_driver VARCHAR,
    raw_demand_delta DOUBLE PRECISION,
    raw_balance_delta DOUBLE PRECISION,
    PRIMARY KEY (time_key, source_id, timestamp)
);
"""

# Schema Design - Insertion

insert_cities = """
INSERT INTO dim_city (
    city_id,
    city_name,
    state_code,
    population,
    latitude,
    longitude
)
VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT (city_id) DO NOTHING;
"""

insert_dim_grid = """
INSERT INTO dim_grid (
    grid_id,
    grid_name
)dim_grid = dim_grid.astype(object).where(pd.notna(dim_grid), None)
dim_county = dim_county.astype(object).where(pd.notna(dim_county), None)
VALUES (%s, %s)
ON CONFLICT (grid_id) DO NOTHING;
"""

insert_dim_county = """
INSERT INTO dim_county (
    county_id,
    county_name,
    state_code,
    fips_code,
    population,
    latitude,
    longitude)

    VALUES (%s, %s, %s, %s, %s, %s, %s)
"""

insert_dim_time_hourly = """
INSERT INTO dim_time_hourly (
    time_id,
    ts_utc,
    hour_of_day,
    day_of_week,
    is_weekend,
    month,
    quarter,
    year
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (time_id) DO NOTHING;
"""

insert_fact_outage_daily = """
INSERT INTO fact_outage_daily (
    time_key,
    county_id,
    customers_wo_power
)
VALUES %s
ON CONFLICT (time_key, county_id) DO NOTHING;
"""

insert_fact_weather_hourly = """
INSERT INTO fact_weather_hourly (
    time_key,
    city_id,
    temperature,
    wind_speed,
    precipitation
)
VALUES %s
ON CONFLICT (time_key, city_id) DO NOTHING;
"""

insert_fact_energy_load_hourly = """
INSERT INTO fact_energy_load_hourly (
    time_key,
    grid_id,
    load_mw
)
VALUES %s
ON CONFLICT (time_key, grid_id) DO NOTHING;
"""

insert_fact_energy_features_hourly = """
INSERT INTO fact_energy_features_hourly (
    time_key,
    source_id,
    net_interchange_mwh,
    balance_error,
    forecast_error_pct,
    demand_ramp_pct,
    demand_rolling_mean,
    demand_rolling_std,
    demand_residual,
    demand_zscore,
    hour_sin,
    hour_cos,
    month_sin,
    month_cos
)
VALUES %s
ON CONFLICT (time_key, source_id) DO NOTHING;
"""

insert_fact_grid_alert_event = """
INSERT INTO fact_grid_alert_event (
    event_start_utc,
    event_end_utc,
    alert_criteria,
    event_type,
    demand_loss,
    number_affected
)
VALUES %s
ON CONFLICT DO NOTHING;
"""

insert_fact = """
INSERT INTO fact_anomaly_detection (
    time_key,
    source_id,
    timestamp,
    actual_outage_target,
    anomaly_score,
    anomaly_flag,
    primary_driver,
    secondary_driver,
    tertiary_driver,
    raw_demand_delta,
    raw_balance_delta
)
VALUES %s
ON CONFLICT (time_key, source_id, timestamp) DO NOTHING;
"""

# Create dim_cities
with conn.cursor() as cur:
    cur.execute(create_dim_cities)
conn.commit()

# Populate SQL Table
with conn.cursor() as cur:
    for row in dim_city.itertuples(index=False):
        cur.execute(insert_cities, tuple(row))

conn.commit()

dim_grid = dim_grid.astype(object).where(pd.notna(dim_grid), None)
dim_county = dim_county.astype(object).where(pd.notna(dim_county), None)

with conn.cursor() as cur:
    cur.execute(create_dim_grid)
    cur.execute(create_dim_county)

    for row in dim_grid.itertuples(index=False):
        cur.execute(insert_dim_grid, tuple(row))

    for row in dim_county.itertuples(index=False):
        cur.execute(insert_dim_county, tuple(row))

conn.commit()

try:
    with conn.cursor() as cur:
        cur.execute(create_dim_time_hourly)
    conn.commit()

    
    df_time_hourly["time_id"] = pd.to_datetime(df_time_hourly["time_id"], utc=True, errors="coerce")
    df_time_hourly["ts_utc"] = pd.to_datetime(df_time_hourly["timestamp"], utc=True, errors="coerce")

    with conn.cursor() as cur:
        for row in df_time_hourly.itertuples(index=False):
            cur.execute(
                insert_dim_time_hourly,
                (
                    row.time_id,
                    row.ts_utc,
                    row.hour_of_day,
                    row.day_of_week,
                    row.is_weekend,
                    row.month,
                    row.quarter,
                    row.year,
                ),
            )
    conn.commit()

except Exception as e:
    conn.rollback()
    print("Original error:", e)


# Map each date to midnight UTC
fact_outage["time_key"] = pd.to_datetime(fact_outage["date"], utc=True).dt.floor("D")

dim_time = fetch_dataframe(conn2, """
    SELECT time_id
    FROM dim_time_hourly
""").rename(columns={"time_id": "time_key"})

dim_county = fetch_dataframe(conn2, """
    SELECT county_id, county_name
    FROM dim_county
""")

# Keep only rows whose time_key exists in dim_time_hourly
fact_outage = fact_outage.merge(
    dim_time,
    on="time_key",
    how="left",
    indicator=True
)

dropped_time = fact_outage[fact_outage["_merge"] == "left_only"]
if not dropped_time.empty:
    print(f"Dropping {len(dropped_time)} rows with time_key not found in dim_time_hourly.")
    print(dropped_time[["date", "time_key"]].drop_duplicates().sort_values("time_key").head(10))

fact_outage = fact_outage[fact_outage["_merge"] == "both"].drop(columns=["_merge"])

# Resolve county_id from county name
fact_outage = fact_outage.merge(
    dim_county,
    left_on="county",
    right_on="county_name",
    how="left",
    indicator=True
)

dropped_county = fact_outage[fact_outage["_merge"] == "left_only"]
if not dropped_county.empty:
    print(f"Dropping {len(dropped_county)} rows with county not found in dim_county.")
    print(dropped_county[["county"]].drop_duplicates().sort_values("county").head(10))

fact_outage = fact_outage[fact_outage["_merge"] == "both"].drop(columns=["_merge", "county_name"])

# Final fact shape
fact_outage = fact_outage[[
    "time_key",
    "county_id",
    "customers_wo_power"
]].drop_duplicates()

rows = list(fact_outage.itertuples(index=False, name=None))

try:
    with conn2.cursor() as cur:
        cur.execute(create_fact_outage_daily)
        execute_values(cur, insert_fact_outage_daily, rows, page_size=1000)

    conn2.commit()
    print(f"Inserted up to {len(rows)} rows into fact_outage_daily.")
except Exception as e:
    conn2.rollback()
    print("Insert failed:", e)


fact_weather["time_key"] = pd.to_datetime(fact_weather["time_key"], utc=True)
fact_weather["city_id"] = fact_weather["city_key"]

dim_time = fetch_dataframe(conn2, "SELECT time_id FROM dim_time_hourly")
valid_time_keys = set(dim_time["time_id"])

dim_city = fetch_dataframe(conn2, "SELECT city_id FROM dim_city")
valid_city_ids = set(dim_city["city_id"])

bad_time = fact_weather[~fact_weather["time_key"].isin(valid_time_keys)]
if not bad_time.empty:
    print(f"Dropping {len(bad_time)} rows with invalid time_key.")
    print(
        bad_time[["time_key"]]
        .drop_duplicates()
        .sort_values("time_key")
        .head(10)
    )

fact_weather = fact_weather[fact_weather["time_key"].isin(valid_time_keys)]

fact_weather = fact_weather[fact_weather["city_id"].isin(valid_city_ids)]

fact_weather = fact_weather[[
    "time_key",
    "city_id",
    "temperature",
    "wind_speed",
    "precipitation"
]].drop_duplicates()

rows = list(fact_weather.itertuples(index=False, name=None))

try:
    with conn.cursor() as cur:
        cur.execute(create_fact_weather_hourly)
        execute_values(cur, insert_fact_weather_hourly, rows, page_size=1000)
    conn.commit()
except Exception as e:
    conn.rollback()
    print("Insert failed:", e)

# Pull dimension keys
dim_time = fetch_dataframe(conn2, "SELECT time_id FROM dim_time_hourly")
valid_time_keys = set(dim_time["time_id"])

dim_grid = fetch_dataframe(conn2, "SELECT grid_id FROM dim_grid")
valid_grid_ids = set(dim_grid["grid_id"])

bad_time = fact_energy_load[~fact_energy_load["time_key"].isin(valid_time_keys)]
if not bad_time.empty:
    print(f"Dropping {len(bad_time)} rows with invalid time_key.")
    print(
        bad_time[["time_key"]]
        .drop_duplicates()
        .sort_values("time_key")
        .head(10)
    )

fact_energy_load = fact_energy_load[fact_energy_load["time_key"].isin(valid_time_keys)]

fact_energy_load = fact_energy_load[[
    "time_key",
    "source_id",
    "demand_forecast_mwh",
    "actual_demand_mwh",
    "net_gen_mwh"
]].drop_duplicates()

rows = list(fact_energy_load.itertuples(index=False, name=None))

try:
    with conn.cursor() as cur:
        cur.execute(create_fact_energy_load_hourly)
        execute_values(cur, insert_fact_energy_load_hourly, rows, page_size=1000)

    conn.commit()
    print(f"Inserted up to {len(rows)} rows into fact_energy_load_hourly.")
except Exception as e:
    conn.rollback()
    print("Insert failed:", e)



# Pull valid time keys from dim_time_hourly
dim_time = fetch_dataframe(conn2, """
    SELECT time_id
    FROM dim_time_hourly
""").rename(columns={"time_id": "time_key"})

# Keep only rows whose time_key exists in dim_time_hourly
fact_energy_features = fact_energy_features.merge(
    dim_time,
    on="time_key",
    how="left",
    indicator=True
)

dropped_time = fact_energy_features[fact_energy_features["_merge"] == "left_only"]
if not dropped_time.empty:
    print(f"Dropping {len(dropped_time)} rows with time_key not found in dim_time_hourly.")
    print(
        dropped_time[["time_key"]]
        .drop_duplicates()
        .sort_values("time_key")
        .head(10)
    )

fact_energy_features = fact_energy_features[fact_energy_features["_merge"] == "both"].drop(columns=["_merge"])

# Final fact shape
fact_energy_features = fact_energy_features[[
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
    "month_cos"
]].drop_duplicates()

rows = list(fact_energy_features.itertuples(index=False, name=None))

try:
    with conn.cursor() as cur:
        cur.execute(create_fact_energy_features_hourly)
        execute_values(cur, insert_fact_energy_features_hourly, rows, page_size=1000)

    conn.commit()
except Exception as e:
    conn.rollback()
    print("Insert failed:", e)

# Parse timestamps
fact_energy_event["event_start_utc"] = pd.to_datetime(fact_energy_event["event_start_utc"], utc=True, errors="coerce")
fact_energy_event["event_end_utc"] = pd.to_datetime(fact_energy_event["event_end_utc"], utc=True, errors="coerce")

# Clean text a bit
for col in ["alert_criteria", "event_type"]:
    fact_energy_event[col] = (
        fact_energy_event[col]
        .astype("string")
        .str.replace("\u00a0", " ", regex=False)
        .str.strip()
    )

# Numeric cleanup
fact_energy_event["demand_loss"] = pd.to_numeric(fact_energy_event["demand_loss"], errors="coerce")
fact_energy_event["number_affected"] = pd.to_numeric(fact_energy_event["number_affected"], errors="coerce")

# Keep desired columns
fact_energy_event = fact_energy_event[[
    "event_start_utc",
    "event_end_utc",
    "alert_criteria",
    "event_type",
    "demand_loss",
    "number_affected"
]].drop_duplicates()

# Convert pandas missing values (including NaT) to Python None
rows = []
for row in fact_energy_event.itertuples(index=False, name=None):
    cleaned = tuple(None if pd.isna(value) else value for value in row)
    rows.append(cleaned)

try:
    with conn.cursor() as cur:
        cur.execute(create_fact_grid_alert_event)
        execute_values(cur, insert_fact_grid_alert_event, rows, page_size=1000)

    conn.commit()
except Exception as e:
    conn.rollback()
    print("Insert failed:", e)

# Ensure correct types
fact_anomaly["timestamp"] = pd.to_datetime(fact_anomaly["timestamp"], errors="coerce")
fact_anomaly["actual_outage_target"] = pd.to_numeric(fact_anomaly["actual_outage_target"], errors="coerce")
fact_anomaly["anomaly_score"] = pd.to_numeric(fact_anomaly["anomaly_score"], errors="coerce")
fact_anomaly["anomaly_flag"] = pd.to_numeric(fact_anomaly["anomaly_flag"], errors="coerce")

# Optional: dedupe at the grain level
fact_anomaly = fact_anomaly.drop_duplicates(subset=[
    "time_key", "source_id", "timestamp"
])

# Convert NaN/NaT → None
rows = []
for row in fact_anomaly.itertuples(index=False, name=None):
    cleaned = tuple(None if pd.isna(v) else v for v in row)
    rows.append(cleaned)

# Insert
try:
    with conn.cursor() as cur:
        cur.execute(create_fact_table)

        execute_values(
            cur,
            insert_fact,   # same VALUES %s style
            rows,
            page_size=1000
        )

    conn.commit()

except Exception as e:
    conn.rollback()
    print("Insert failed:", e)