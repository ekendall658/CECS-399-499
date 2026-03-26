import pandas as pd
import numpy as np

INPUT_PATH = "local_data/silver/tva_eia_21_25_utc.csv"
OUTPUT_PATH = "local_data/silver/EIA_pre_feature.csv"

eia_cols = [
    "demand_forecast_mwh",
    "actual_demand_mwh",
    "net_generation_mwh",
    "net_interchange_mwh"
]

# -----------------------------
# Load data
# -----------------------------
df = pd.read_csv(INPUT_PATH)

# -----------------------------
# Ensure correct dtypes
# -----------------------------
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

for col in eia_cols:
    df[col] = pd.to_numeric(df[col], errors="coerce")

# -----------------------------
# Set index and enforce hourly timeline
# -----------------------------
df = df.set_index("timestamp").sort_index()
df = df.asfreq("h")

# -----------------------------
# Fill only small INTERNAL gaps
# - leaves front/end gaps alone
# - leaves long gaps alone
# -----------------------------
df[eia_cols] = df[eia_cols].interpolate(
    method="time",
    limit=3,
    limit_area="inside"
)

# -----------------------------
# Optional: confirm dtypes
# -----------------------------
print("Dtypes after cleaning:")
print(df[eia_cols].dtypes)

print("\nRemaining missing values:")
print(df[eia_cols].isna().sum())

# -----------------------------
# Save output
# -----------------------------
df.reset_index().to_csv(OUTPUT_PATH, index=False)

print(f"\nSaved cleaned file to: {OUTPUT_PATH}")