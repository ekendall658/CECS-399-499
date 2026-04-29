import boto3
import os
import sys
import pandas as pd
from pathlib import Path
sys.path.append('src/ingestion')

from fetch_eia import fetch_eia_master_data
from fetch_weather_top10 import fetch_comprehensive_weather

# Import weather weights processing
sys.path.append('src/ingestion')
import fetch_weather_weights

# S3 Configuration
s3 = boto3.client(
    's3',
    region_name='us-east-2',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
)
bucket_name = 'energy-lake-cecs'

def upload_to_s3(local_path, s3_key):
    """Upload a file to S3"""
    try:
        s3.upload_file(local_path, bucket_name, s3_key)
        print(f"✅ Uploaded {local_path} to s3://{bucket_name}/{s3_key}")
    except Exception as e:
        print(f"❌ Failed to upload {local_path}: {e}")

def main():
    print("🚀 Starting Ingestion Pipeline...")

    # Ensure local folders exist
    Path("local_data/bronze").mkdir(parents=True, exist_ok=True)
    Path("local_data/silver").mkdir(parents=True, exist_ok=True)

    # Check if EIA_API_KEY is available
    eia_key = os.getenv('EIA_API_KEY')
    if not eia_key:
        print("\n⚠️ EIA_API_KEY not set. Using test data instead.")
        # Create minimal test CSV
        test_df = pd.DataFrame({
            'timestamp': pd.date_range('2021-01-01', periods=10, freq='H'),
            'net_generation_mwh': [1000] * 10,
            'net_interchange_mwh': [50] * 10,
            'actual_demand_mwh': [1050] * 10,
            'demand_forecast_mwh': [1040] * 10
        })
        eia_file = Path("local_data/bronze/tva_eia_21_25.csv")
        test_df.to_csv(eia_file, index=False)
        print(f"✅ Created test EIA file: {eia_file}")
        upload_to_s3(str(eia_file), f'ingestion/{eia_file.name}')
    else:
        # Fetch EIA data
        print("\n📊 Fetching EIA data...")
        df_eia = fetch_eia_master_data()
        if df_eia is not None:
            eia_file = Path("local_data/bronze/tva_eia_21_25.csv")
            df_eia.to_csv(eia_file, index=False)
            upload_to_s3(str(eia_file), f'ingestion/{eia_file.name}')

    # Fetch weather data
    print("\n🌤️ Fetching weather data...")
    try:
        df_weather = fetch_comprehensive_weather()
        if df_weather is not None:
            weather_file = Path("local_data/bronze/tn_weather_top10_21_25.csv")
            df_weather.to_csv(weather_file, index=False)
            upload_to_s3(str(weather_file), f'ingestion/{weather_file.name}')
    except Exception as e:
        print(f"⚠️ Weather fetch skipped: {e}")

    # Fetch weather weights
    print("\n⚖️ Processing weather weights...")
    try:
        fetch_weather_weights.main()  # Call the module's main function
        weights_file = Path('local_data/silver/tn_selected_city_population_weights.csv')
        if weights_file.exists():
            upload_to_s3(str(weights_file), f'ingestion/{weights_file.name}')
    except Exception as e:
        print(f"⚠️ Weather weights processing failed: {e}")

    print("\n✅ Ingestion Pipeline Complete!")

if __name__ == "__main__":
    main()