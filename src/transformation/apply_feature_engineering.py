import pandas as pd
import numpy as np
from pathlib import Path

# =========================================================
# STEP 1: Set Paths and Load Data
# =========================================================
INPUT_CSV  = Path("local_data/silver/EIA_pre_feature.csv")
OUTPUT_CSV = Path("local_data/silver/EIA_features_FINAL.csv")

df = pd.read_csv(INPUT_CSV)

df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
df = df.sort_values('timestamp').reset_index(drop=True)
df = df.set_index('timestamp')

print(f"Loaded {len(df)} rows | {df.index.min()} to {df.index.max()}")
print(f"Null counts before feature engineering:\n{df.isnull().sum()}\n")

# =========================================================
# STEP 2: Balance Error
# =========================================================
# EIA sign convention: positive interchange = net outflow (export)
#                      negative interchange = net inflow  (import)
# Balance error should be ~0 under normal grid operation
# Large deviations = grid event, sensor fault, or reporting error

df['balance_error'] = (
    (df['net_generation_mwh'] - df['net_interchange_mwh'])
    - df['actual_demand_mwh']
)

# =========================================================
# STEP 3: Percent Forecast Error (PFE)
# =========================================================
# Positive = actual was higher than forecast (under-predicted)
# Negative = actual was lower than forecast (over-predicted)

df['percent_forecast_error'] = (
    (df['actual_demand_mwh'] - df['demand_forecast_mwh'])
    / df['demand_forecast_mwh']
    * 100
)

# =========================================================
# STEP 4: Demand Ramp Rate
# =========================================================
# Percentage change in actual demand between consecutive intervals
# Captures speed of change — sudden spikes/drops are anomaly signals

df['demand_ramp_rate_pct'] = (
    df['actual_demand_mwh']
    .pct_change(fill_method=None)
    * 100
)

# =========================================================
# STEP 5: Demand Residual & Rolling Standard Deviation
# =========================================================
# Rolling 24h mean = expected demand based on recent history
# Residual = actual minus that expectation (removes daily cycle)
# Rolling 24h std = how volatile demand has been recently

df['demand_rolling_mean_24h'] = (
    df['actual_demand_mwh']
    .rolling('24h', min_periods=1)
    .mean()
)

df['demand_rolling_std_24h'] = (
    df['actual_demand_mwh']
    .rolling('24h', min_periods=1)
    .std()
)

df['demand_residual'] = (
    df['actual_demand_mwh'] - df['demand_rolling_mean_24h']
)

df['demand_zscore'] = (
    df['demand_residual'] / df['demand_rolling_std_24h']
)

# =========================================================
# STEP 6: Cyclical Time Encoding
# =========================================================
# Sin + cos encoding wraps hour and month onto a circle
# so the model understands hour 23 and hour 0 are adjacent
# Always need BOTH sin and cos together

df['hour']  = df.index.hour
df['month'] = df.index.month

df['hour_sin']  = np.sin(2 * np.pi * df['hour']  / 24)
df['hour_cos']  = np.cos(2 * np.pi * df['hour']  / 24)
df['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
df['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)

df = df.drop(columns=['hour', 'month'])

# =========================================================
# STEP 7: Summary & Save
# =========================================================
feature_cols = [
    'balance_error',
    'percent_forecast_error',
    'demand_ramp_rate_pct',
    'demand_rolling_mean_24h',
    'demand_rolling_std_24h',
    'demand_residual',
    'demand_zscore',
    'hour_sin', 'hour_cos',
    'month_sin', 'month_cos',
]

print("Feature engineering complete.")
print(f"New columns added: {feature_cols}\n")
print("Sample stats for engineered features:")
print(df[feature_cols].describe().round(3))
print(f"\nNull counts after feature engineering:\n{df[feature_cols].isnull().sum()}")

df.to_csv(OUTPUT_CSV)
print(f"\nSaved to: {OUTPUT_CSV}")
print(f"Output shape: {df.shape} ({df.shape[1]} total columns)")