from pathlib import Path
import pandas as pd
import re

# =========================================================
# Paths (run this script from the repo root)
# =========================================================
INPUT_CSV = Path("local_data/bronze/Tennessee_pop.csv")
OUTPUT_CSV = Path("local_data/silver/tn_selected_city_population_weights.csv")

# Make sure output folder exists
OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

# =========================================================
# Target cities
# =========================================================
TARGET_PATTERNS = {
    "nashville": r"nashville",
    "memphis": r"memphis",
    "knoxville": r"knoxville",
    "chattanooga": r"chattanooga",
    "clarksville": r"clarksville",
    "murfreesboro": r"murfreesboro",
    "franklin": r"franklin",
    "johnson_city": r"johnson city",
    "jackson": r"jackson",
    "hendersonville": r"hendersonville",
}

YEARS = ["2021", "2022", "2023", "2024"]


def normalize_text(value):
    """Lowercase and normalize spacing for city-name matching."""
    if pd.isna(value):
        return ""
    value = str(value).lower().strip()
    value = re.sub(r"\s+", " ", value)
    return value


def find_header_row(csv_path: Path) -> int:
    """
    Find the row containing 'Geographic Area' so the script still works
    even if the exported CSV includes title rows above the table.
    """
    raw = pd.read_csv(csv_path, header=None, dtype=str)
    matches = raw.index[
        raw.iloc[:, 0].astype(str).str.contains("Geographic Area", na=False)
    ].tolist()

    if not matches:
        raise ValueError("Could not find header row containing 'Geographic Area'.")

    return matches[0]


def load_population_table(csv_path: Path) -> pd.DataFrame:
    """Load and clean the Tennessee population CSV with a two-row header."""
    header_row = find_header_row(csv_path)

    # Read using the two header rows:
    # first = main labels
    # second = year labels under Population Estimate
    df = pd.read_csv(csv_path, skiprows=header_row, header=[0, 1])

    # Drop fully empty columns
    df = df.dropna(axis=1, how="all")

    # Flatten multi-level columns
    flattened_cols = []
    for col in df.columns:
        top = str(col[0]).strip() if pd.notna(col[0]) else ""
        bottom = str(col[1]).strip() if pd.notna(col[1]) else ""

        if top == "Geographic Area":
            flattened_cols.append("Geographic Area")
        elif "April 1, 2020" in top:
            flattened_cols.append("2020_base")
        elif bottom in ["2020", "2021", "2022", "2023", "2024"]:
            flattened_cols.append(bottom)
        else:
            flattened_cols.append(top if top else bottom)

    df.columns = flattened_cols

    required_cols = ["Geographic Area", "2021", "2022", "2023", "2024"]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(
            f"Missing expected columns: {missing}\n"
            f"Columns found: {list(df.columns)}"
        )

    df = df[required_cols].copy()

    # Clean numeric population columns
    for year in YEARS:
        df[year] = (
            df[year]
            .astype(str)
            .str.replace(",", "", regex=False)
            .str.strip()
        )
        df[year] = pd.to_numeric(df[year], errors="coerce")

    df["city_raw"] = df["Geographic Area"].apply(normalize_text)
    return df


def select_target_cities(df: pd.DataFrame) -> pd.DataFrame:
    """Filter the full Census table down to the ten target cities."""
    selected_rows = []

    for city_key, pattern in TARGET_PATTERNS.items():
        match = df[df["city_raw"].str.contains(pattern, regex=True, na=False)].copy()

        if match.empty:
            raise ValueError(f"No Census row matched target city: {city_key}")

        if len(match) > 1:
            print(f"Warning: multiple matches found for '{city_key}'. Using the first:")
            print(match[["Geographic Area"]].head(), "\n")

        row = match.iloc[0].copy()
        row["city"] = city_key
        selected_rows.append(row)

    clean = pd.DataFrame(selected_rows)
    return clean


def add_population_weights(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add same-year weights and carry 2024 forward for 2025.
    Weight = city population / total selected-city population for that year.
    """
    df = df.copy()

    # Carry forward 2024 population for 2025 until official 2025 city estimates exist
    df["2025"] = df["2024"]

    weight_years = YEARS + ["2025"]
    for year in weight_years:
        total_pop = df[year].sum()
        df[f"weight_{year}"] = df[year] / total_pop

    # Rename population columns for clarity
    rename_map = {year: f"population_{year}" for year in weight_years}
    df = df.rename(columns=rename_map)

    final_cols = (
        ["city", "Geographic Area"]
        + [f"population_{year}" for year in weight_years]
        + [f"weight_{year}" for year in weight_years]
    )

    df = df[final_cols].sort_values("city").reset_index(drop=True)

    # Round weights for cleaner CSV output
    weight_cols = [col for col in df.columns if col.startswith("weight_")]
    df[weight_cols] = df[weight_cols].round(6)

    return df


def main():
    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_CSV}")

    df = load_population_table(INPUT_CSV)
    df_selected = select_target_cities(df)
    df_final = add_population_weights(df_selected)

    df_final.to_csv(OUTPUT_CSV, index=False)

    print(f"Saved cleaned population weights file to:\n{OUTPUT_CSV}\n")
    print(df_final)


if __name__ == "__main__":
    main()