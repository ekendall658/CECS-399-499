from pathlib import Path
import pandas as pd
import build_parquet_functions as bpf


def main():
    PROJECT_ROOT = Path(__file__).resolve().parents[2]

    silver_dir = PROJECT_ROOT / "local_data" / "silver"
    gold_dir = PROJECT_ROOT / "local_data" / "gold"

    gold_dir.mkdir(parents=True, exist_ok=True)

    # Load datasets
    EIA = pd.read_csv(silver_dir / "EIA_features_Final.csv")
    Eagle = pd.read_csv(silver_dir / "eaglei_tennessee_cleaned_final.csv")
    tn_weather = pd.read_csv(silver_dir / "tn_weighted_weather_21_25.csv")
    doe = pd.read_csv(silver_dir / "doe417_tennessee_cleaned_final.csv").rename(
        columns={
            "Date Event Began": "date_start",
            "Time Event Began": "time_start",
            "Date of Restoration": "restoration_date",
            "Area Affected": "area_affected",
            "Number of Customers Affected": "customers_affected",
            "Alert Criteria": "alert_criteria",
            "Event Type": "event_type",
        }
    )
    cities = pd.read_csv(silver_dir / "tn_selected_city_population_weights.csv")

    # Build and write parquet datasets
    bpf.write_parquet(
        bpf.build_fact_energy_events(doe),
        output_path=gold_dir / "fact_energy_event.parquet",
    )

    bpf.write_parquet(
        bpf.build_fact_outage_daily(Eagle),
        output_path=gold_dir / "fact_outage_daily.parquet",
    )

    bpf.write_parquet(
        bpf.build_fact_weather_city_hourly(tn_weather),
        output_path=gold_dir / "fact_weather_city_hourly.parquet",
    )

    bpf.write_parquet(
        bpf.build_fact_energy_load_hourly(EIA),
        output_path=gold_dir / "fact_energy_load_hourly.parquet",
    )

    bpf.write_parquet(
        bpf.build_fact_energy_features_hourly(EIA),
        output_path=gold_dir / "fact_energy_features_hourly.parquet",
    )

    bpf.write_parquet(
        bpf.build_dim_grid(),
        output_path=gold_dir / "dim_grid.parquet",
    )

    bpf.write_parquet(
        bpf.build_dim_time_hourly(EIA=EIA, tn_weather=tn_weather),
        output_path=gold_dir / "dim_time_hourly.parquet",
    )

    bpf.write_parquet(
        bpf.build_dim_city(cities),
        output_path=gold_dir / "dim_city.parquet",
    )

    bpf.write_parquet(
        bpf.build_dim_county(Eagle),
        output_path=gold_dir / "dim_county.parquet",
    )

    print(f"All parquet files written to: {gold_dir}")


if __name__ == "__main__":
    main()