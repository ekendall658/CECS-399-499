import pandas as pd
import numpy as np
import xgboost as xgb
import warnings
import os
from sklearn.model_selection import RandomizedSearchCV
from sklearn.metrics import classification_report, confusion_matrix

# Suppress warnings for cleaner terminal output
warnings.filterwarnings('ignore')

# ==========================================
# CONFIGURATION & PATHS
# ==========================================
BASE_PATH = '/workspaces/CECS-399-499/local_data/gold/'
SILVER_PATH = '/workspaces/CECS-399-499/local_data/silver/'
OUTPUT_FILE = f'{BASE_PATH}fact_anomaly_detection.parquet'

def load_data():
    print(">>> [1/6] Loading Gold Parquet files and Silver weather...")
    energy_feat = pd.read_parquet(f'{BASE_PATH}fact_energy_features_hourly.parquet')
    energy_load = pd.read_parquet(f'{BASE_PATH}fact_energy_load_hourly.parquet')
    time_dim = pd.read_parquet(f'{BASE_PATH}dim_time_hourly.parquet')
    
    df = pd.merge(energy_feat, energy_load, on=['time_key', 'source_id'])
    df = pd.merge(df, time_dim, left_on='time_key', right_on='time_id', how='left')
    
    weather_csv = pd.read_csv(f'{SILVER_PATH}tn_weighted_weather_21_25.csv')
    
    weighted_cols = [
        'timestamp', 'weighted_temperature_2m', 'weighted_relative_humidity_2m', 
        'weighted_precipitation', 'weighted_cloud_cover', 
        'weighted_wind_speed_10m', 'weighted_shortwave_radiation'
    ]
    weather_csv = weather_csv[weighted_cols]
    
    df['timestamp_join'] = pd.to_datetime(df['timestamp'], utc=True).dt.tz_localize(None)
    weather_csv['timestamp'] = pd.to_datetime(weather_csv['timestamp'], utc=True).dt.tz_localize(None)
    
    df = pd.merge(df, weather_csv, left_on='timestamp_join', right_on='timestamp', how='inner')
    return df.sort_values('timestamp_join').reset_index(drop=True)

def main():
    print("="*60)
    print(" STARTING ANOMALY DETECTION PIPELINE ")
    print("="*60)

    # 1. Ingestion
    df_master = load_data()

    # 2. Feature Engineering
    print(">>> [2/6] Engineering velocity features and mapping targets...")
    df_master['demand_delta_1h'] = df_master['actual_demand_mwh'].diff()
    df_master['balance_delta_1h'] = df_master['balance_error'].diff()
    df_master = df_master.dropna().reset_index(drop=True)

    eagle_dates = set(pd.to_datetime(pd.read_parquet(f'{BASE_PATH}fact_outage_daily.parquet')['date']).dt.date.unique())
    doe_df = pd.read_csv(f'{SILVER_PATH}doe417_tennessee_cleaned_final.csv')
    doe_date_col = [c for c in doe_df.columns if 'date' in c.lower()][0]
    doe_dates = set(pd.to_datetime(doe_df[doe_date_col], format='mixed').dt.date.unique())

    combined_outage_dates = eagle_dates.union(doe_dates)
    df_master['event_date'] = pd.to_datetime(df_master['timestamp_join']).dt.date
    df_master['target'] = df_master['event_date'].apply(lambda x: 1 if x in combined_outage_dates else 0)

    # 3. Setup & Split
    print(">>> [3/6] Defining feature space and chronologically splitting data...")
    all_numeric = df_master.select_dtypes(include=[np.number]).columns.tolist()
    exclude = ['time_id', 'time_key', 'source_id', 'year', 'quarter', 'month', 'hour_of_day', 'day_of_week', 'target']
    FEATURES = [f for f in all_numeric if f not in exclude]
    EXCLUDE_DRIVERS = ['month_sin', 'month_cos', 'hour_sin', 'hour_cos']

    split_idx = int(len(df_master) * 0.6)
    train_df = df_master.iloc[:split_idx].copy()
    test_df = df_master.iloc[split_idx:].copy()

    spw = (len(train_df) - train_df['target'].sum()) / train_df['target'].sum()

    # 4. Model Tuning & Training
    print(f">>> [4/6] Executing RandomizedSearchCV Tuning (SPW: {spw:.2f})...")
    param_grid = {
        'scale_pos_weight': [1.0, 1.5, 2.0, 2.5, spw], 
        'max_depth': [3, 4, 5, 6],                     
        'min_child_weight': [1, 3, 5, 7],              
        'subsample': [0.8, 0.9, 1.0],                  
        'colsample_bytree': [0.7, 0.8, 0.9, 1.0],      
        'gamma': [0, 0.1, 0.2, 0.3]                    
    }

    base_clf = xgb.XGBClassifier(n_estimators=200, learning_rate=0.05, random_state=42, n_jobs=-1)
    
    random_search = RandomizedSearchCV(
        estimator=base_clf, param_distributions=param_grid, 
        n_iter=20, scoring='f1', cv=3, random_state=42, n_jobs=-1
    )
    random_search.fit(train_df[FEATURES], train_df['target'])
    best_clf = random_search.best_estimator_

    # Print Validation
    test_probs = best_clf.predict_proba(test_df[FEATURES])[:, 1]
    test_preds = (test_probs >= 0.5).astype(int)
    cm = confusion_matrix(test_df['target'], test_preds)

    print("\n" + "-"*40)
    print(" TEST SET VALIDATION RESULTS ")
    print("-"*40)
    print(f"True Negatives:  {cm[0][0]}  |  False Positives: {cm[0][1]}")
    print(f"False Negatives: {cm[1][0]}    |  True Positives:  {cm[1][1]}")
    print("-" * 40 + "\n")

    # 5. Full Inference & Native SHAP Extraction
    print(">>> [5/6] Running full inference and native XGBoost SHAP extraction...")
    df_master['anomaly_score'] = best_clf.predict_proba(df_master[FEATURES])[:, 1]
    df_master['is_anomaly'] = (df_master['anomaly_score'] >= 0.5).astype(int)

    booster = best_clf.get_booster()
    dmatrix = xgb.DMatrix(df_master[FEATURES])
    shap_matrix = booster.predict(dmatrix, pred_contribs=True)[:, :-1] # Drop bias column

    filtered_drivers = []
    for i in range(len(df_master)):
        row_shap = pd.Series(shap_matrix[i], index=FEATURES)
        actionable_shap = row_shap.drop(labels=[f for f in EXCLUDE_DRIVERS if f in row_shap.index])
        top_3 = actionable_shap.abs().sort_values(ascending=False).index[:3].tolist()
        filtered_drivers.append(top_3)

    drivers_df = pd.DataFrame(filtered_drivers, columns=['primary_driver', 'secondary_driver', 'tertiary_driver'])
    df_master = pd.concat([df_master, drivers_df], axis=1)

    # 6. Warehouse Export
    print(">>> [6/6] Formatting schema and exporting to Parquet...")
    warehouse_cols = [
        'time_key', 'source_id', 'timestamp_join', 'target', 
        'anomaly_score', 'is_anomaly', 'primary_driver', 
        'secondary_driver', 'tertiary_driver', 'demand_delta_1h', 'balance_delta_1h'
    ]
    fact_anomaly_detection = df_master[warehouse_cols].copy()

    fact_anomaly_detection.columns = [
        'time_key', 'source_id', 'timestamp', 'actual_outage_target',
        'anomaly_score', 'anomaly_flag', 'primary_driver', 'secondary_driver', 
        'tertiary_driver', 'raw_demand_delta', 'raw_balance_delta'
    ]

    fact_anomaly_detection.to_parquet(OUTPUT_FILE, index=False)
    
    print("="*60)
    print(f" SUCCESS: Saved {len(fact_anomaly_detection)} records to:")
    print(f" {OUTPUT_FILE}")
    print("="*60)

if __name__ == "__main__":
    main()