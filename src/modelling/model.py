import pandas as pd
import numpy as np
from pathlib import Path
import boto3
import os
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import joblib
import matplotlib.pyplot as plt
import seaborn as sns

# S3 Configuration
s3 = boto3.client(
    's3',
    region_name='us-east-2',
    aws_access_key_id='',
    aws_secret_access_key=''
)
bucket_name = 'energy-lake-cecs'

# Paths
GOLD_LAYER = Path("local_data/gold")
MODEL_OUTPUT = Path("models")
MODEL_OUTPUT.mkdir(exist_ok=True)

def download_gold_data():
    """Download processed data from gold layer in S3"""
    print("📥 Downloading gold layer data from S3...")

    gold_files = [
        'gold/EIA_features_Final.csv',
        'gold/tn_weighted_weather_21_25.parquet',
        'gold/eaglei_tennessee_cleaned_final.csv',
        'gold/doe417_tennessee_cleaned_final.csv'
    ]

    downloaded_files = []
    for s3_key in gold_files:
        local_path = GOLD_LAYER / os.path.basename(s3_key)
        try:
            s3.download_file(bucket_name, s3_key, str(local_path))
            print(f"✅ Downloaded {s3_key}")
            downloaded_files.append(local_path)
        except Exception as e:
            print(f"⚠️ Failed to download {s3_key}: {e}")

    return downloaded_files

def load_gold_data():
    """Load all gold layer data into dataframes"""
    print("🔄 Loading gold layer data...")

    data = {}

    # Load EIA features
    eia_path = GOLD_LAYER / "EIA_features_Final.csv"
    if eia_path.exists():
        data['eia'] = pd.read_csv(eia_path)
        data['eia']['timestamp'] = pd.to_datetime(data['eia']['timestamp'], utc=True)
        print(f"✅ Loaded EIA data: {len(data['eia'])} rows")

    # Load weather data (parquet)
    weather_path = GOLD_LAYER / "tn_weighted_weather_21_25.parquet"
    if weather_path.exists():
        data['weather'] = pd.read_parquet(weather_path)
        data['weather']['timestamp'] = pd.to_datetime(data['weather']['timestamp'], utc=True)
        print(f"✅ Loaded weather data: {len(data['weather'])} rows")

    # Load outage data
    outage_path = GOLD_LAYER / "eaglei_tennessee_cleaned_final.csv"
    if outage_path.exists():
        data['outages'] = pd.read_csv(outage_path)
        data['outages']['date'] = pd.to_datetime(data['outages']['date'])
        print(f"✅ Loaded outage data: {len(data['outages'])} rows")

    return data

def merge_datasets(data):
    """Merge EIA, weather, and outage data for modelling"""
    print("🔗 Merging datasets...")

    if 'eia' not in data or 'weather' not in data:
        print("❌ Missing required datasets for merging")
        return None

    # Merge EIA and weather on timestamp
    merged = pd.merge(
        data['eia'],
        data['weather'],
        on='timestamp',
        how='left'
    )

    # Aggregate outages to hourly level
    if 'outages' in data:
        # Convert daily outages to hourly by dividing by 24
        outages_hourly = data['outages'].copy()
        outages_hourly['timestamp'] = outages_hourly['date']
        outages_hourly = outages_hourly.drop('date', axis=1)
        outages_hourly['customers_out_hourly'] = outages_hourly['customers_out'] / 24

        # Expand to hourly
        outages_expanded = []
        for _, row in outages_hourly.iterrows():
            for hour in range(24):
                timestamp = row['timestamp'] + pd.Timedelta(hours=hour)
                outages_expanded.append({
                    'timestamp': timestamp,
                    'county': row['county'],
                    'customers_out_hourly': row['customers_out_hourly']
                })

        outages_df = pd.DataFrame(outages_expanded)

        # Aggregate by timestamp (sum all counties)
        outages_agg = outages_df.groupby('timestamp')['customers_out_hourly'].sum().reset_index()

        # Merge with main dataset
        merged = pd.merge(
            merged,
            outages_agg,
            on='timestamp',
            how='left'
        ).fillna(0)

    print(f"✅ Merged dataset: {len(merged)} rows, {len(merged.columns)} columns")
    return merged

def prepare_features_target(df):
    """Prepare features and target for modelling"""
    print("🎯 Preparing features and target...")

    # Target: predict actual demand
    target_col = 'actual_demand_mwh'

    # Features: exclude target and non-predictive columns
    exclude_cols = [
        'timestamp', target_col, 'demand_forecast_mwh',
        'Percent Forecast Error', 'balance_error'
    ]

    # Only use rows where target is not null
    df_model = df.dropna(subset=[target_col]).copy()

    # Select features
    feature_cols = [col for col in df_model.columns if col not in exclude_cols]
    X = df_model[feature_cols]
    y = df_model[target_col]

    print(f"✅ Features: {len(feature_cols)} columns")
    print(f"✅ Target: {target_col}")
    print(f"✅ Training samples: {len(X)}")

    return X, y, feature_cols

def train_model(X, y):
    """Train a Random Forest model for demand prediction"""
    print("🤖 Training Random Forest model...")

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, shuffle=False
    )

    # Train model
    model = RandomForestRegressor(
        n_estimators=100,
        max_depth=20,
        random_state=42,
        n_jobs=-1
    )

    model.fit(X_train, y_train)

    # Evaluate
    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)

    print(".2f")
    print(".2f")
    print(".3f")

    return model, X_test, y_test, y_pred

def save_model_and_results(model, X_test, y_test, y_pred, feature_cols):
    """Save model and analysis results"""
    print("💾 Saving model and results...")

    # Save model
    model_path = MODEL_OUTPUT / "demand_prediction_model.pkl"
    joblib.dump(model, model_path)
    print(f"✅ Model saved to {model_path}")

    # Create results dataframe
    results_df = pd.DataFrame({
        'actual': y_test,
        'predicted': y_pred,
        'error': y_test - y_pred,
        'abs_error': abs(y_test - y_pred)
    })

    results_path = MODEL_OUTPUT / "model_predictions.csv"
    results_df.to_csv(results_path, index=False)
    print(f"✅ Predictions saved to {results_path}")

    # Feature importance
    feature_importance = pd.DataFrame({
        'feature': feature_cols,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)

    importance_path = MODEL_OUTPUT / "feature_importance.csv"
    feature_importance.to_csv(importance_path, index=False)
    print(f"✅ Feature importance saved to {importance_path}")

    return model_path, results_path, importance_path

def upload_results_to_s3(files):
    """Upload modelling results to S3"""
    print("☁️ Uploading results to S3...")

    for local_file in files:
        if os.path.exists(local_file):
            s3_key = f"modelling/{os.path.basename(local_file)}"
            try:
                s3.upload_file(str(local_file), bucket_name, s3_key)
                print(f"✅ Uploaded {s3_key}")
            except Exception as e:
                print(f"❌ Failed to upload {local_file}: {e}")

def create_visualizations(results_df, feature_importance):
    """Create and save visualizations"""
    print("📊 Creating visualizations...")

    # Prediction vs Actual plot
    plt.figure(figsize=(12, 6))
    plt.scatter(results_df['actual'], results_df['predicted'], alpha=0.5)
    plt.plot([results_df['actual'].min(), results_df['actual'].max()],
             [results_df['actual'].min(), results_df['actual'].max()],
             'r--', lw=2)
    plt.xlabel('Actual Demand (MWh)')
    plt.ylabel('Predicted Demand (MWh)')
    plt.title('Demand Prediction: Actual vs Predicted')
    plt.tight_layout()
    plot_path = MODEL_OUTPUT / "prediction_scatter.png"
    plt.savefig(plot_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✅ Scatter plot saved to {plot_path}")

    # Feature importance plot
    plt.figure(figsize=(10, 8))
    top_features = feature_importance.head(15)
    sns.barplot(x='importance', y='feature', data=top_features)
    plt.title('Top 15 Feature Importances')
    plt.tight_layout()
    importance_plot_path = MODEL_OUTPUT / "feature_importance.png"
    plt.savefig(importance_plot_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✅ Feature importance plot saved to {importance_plot_path}")

    return [plot_path, importance_plot_path]

def main():
    """Main modelling pipeline"""
    print("🧠 Starting Gold Layer Modelling Pipeline...")

    try:
        # Download data from S3 gold layer
        downloaded_files = download_gold_data()

        # Load data
        data = load_gold_data()

        # Merge datasets
        merged_df = merge_datasets(data)
        if merged_df is None:
            return

        # Prepare features and target
        X, y, feature_cols = prepare_features_target(merged_df)

        # Train model
        model, X_test, y_test, y_pred = train_model(X, y)

        # Save model and results
        model_file, results_file, importance_file = save_model_and_results(
            model, X_test, y_test, y_pred, feature_cols
        )

        # Create visualizations
        results_df = pd.DataFrame({
            'actual': y_test,
            'predicted': y_pred
        })
        feature_importance = pd.DataFrame({
            'feature': feature_cols,
            'importance': model.feature_importances_
        }).sort_values('importance', ascending=False)

        viz_files = create_visualizations(results_df, feature_importance)

        # Upload all results to S3
        all_output_files = [model_file, results_file, importance_file] + viz_files
        upload_results_to_s3(all_output_files)

        print("\n✅ Modelling Pipeline Complete!")
        print("📁 Results saved locally in 'models/' directory")
        print("☁️ Results uploaded to S3 'modelling/' prefix")

    except Exception as e:
        print(f"❌ Modelling pipeline failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()