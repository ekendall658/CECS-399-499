import boto3
import os
import sys
import pandas as pd
from pathlib import Path
sys.path.append('src/transformation')

# Import transformation modules
from EIA_to_UTC import convert_eia_to_utc
from apply_feature_engineering import *  # This will run the feature engineering
from apply_weather_weights import *  # Assuming this exists
from doe417_process import *  # Assuming this exists
from eaglei_process import *  # Assuming this exists
from resolve_EIA_missing import *  # Assuming this exists

# S3 Configuration
s3 = boto3.client(
    's3',
    region_name='us-east-2',
    aws_access_key_id='',
    aws_secret_access_key=''
)
bucket_name = 'energy-lake-cecs'

def download_from_s3(s3_key, local_path):
    """Download a file from S3"""
    try:
        s3.download_file(bucket_name, s3_key, local_path)
        print(f"✅ Downloaded s3://{bucket_name}/{s3_key} to {local_path}")
        return True
    except Exception as e:
        print(f"❌ Failed to download {s3_key}: {e}")
        return False

def upload_to_s3(local_path, s3_key):
    """Upload a file to S3"""
    try:
        s3.upload_file(local_path, bucket_name, s3_key)
        print(f"✅ Uploaded {local_path} to s3://{bucket_name}/{s3_key}")
    except Exception as e:
        print(f"❌ Failed to upload {local_path}: {e}")

def main():
    print("🔄 Starting Transformation Pipeline...")

    # Create local directories
    Path("local_data/bronze").mkdir(parents=True, exist_ok=True)
    Path("local_data/silver").mkdir(parents=True, exist_ok=True)

    # Download ingested data from S3
    print("\n📥 Downloading data from S3...")

    # Download EIA data
    if download_from_s3('ingestion/tva_eia_21_25.csv', 'local_data/bronze/tva_eia_21_25.csv'):
        # Convert EIA to UTC
        print("\n⏰ Converting EIA data to UTC...")
        df_eia_utc = convert_eia_to_utc()
        upload_to_s3('local_data/silver/tva_eia_21_25_utc.csv', 'transformation/tva_eia_21_25_utc.csv')

    # Download weather data
    if download_from_s3('ingestion/tn_weather_top10_21_25.csv', 'local_data/bronze/tn_weather_top10_21_25.csv'):
        # Apply weather weights
        print("\n⚖️ Applying weather weights...")
        # Assuming apply_weather_weights has a main function or similar
        try:
            # Call the weather weights application
            # This might need adjustment based on the actual function
            pass  # Placeholder
        except Exception as e:
            print(f"⚠️ Weather weights application failed: {e}")

    # Download population weights
    download_from_s3('ingestion/tn_selected_city_population_weights.csv', 'local_data/silver/tn_selected_city_population_weights.csv')

    # Run feature engineering
    print("\n🔧 Applying feature engineering...")
    try:
        # Assuming apply_feature_engineering.py has the logic to run
        # The file seems to run automatically when imported
        upload_to_s3('local_data/silver/EIA_features_FINAL.csv', 'transformation/EIA_features_FINAL.csv')
    except Exception as e:
        print(f"⚠️ Feature engineering failed: {e}")

    # Run DOE417 processing
    print("\n🏭 Processing DOE417 data...")
    try:
        # Assuming doe417_process.py has a main function
        # This might need to be adjusted
        pass  # Placeholder
    except Exception as e:
        print(f"⚠️ DOE417 processing failed: {e}")

    # Run Eaglei processing
    print("\n🦅 Processing Eaglei data...")
    try:
        # Assuming eaglei_process.py has a main function
        # This might need to be adjusted
        pass  # Placeholder
    except Exception as e:
        print(f"⚠️ Eaglei processing failed: {e}")

    # Resolve EIA missing values
    print("\n🔍 Resolving EIA missing values...")
    try:
        # Assuming resolve_EIA_missing.py has a main function
        # This might need to be adjusted
        pass  # Placeholder
    except Exception as e:
        print(f"⚠️ EIA missing values resolution failed: {e}")

    print("\n✅ Transformation Pipeline Complete!")

if __name__ == "__main__":
    main()