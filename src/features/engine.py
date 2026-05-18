import pandas as pd
import numpy as np

def process_raw_to_features(raw_path: str):
    """
    Phase 2: Birmingham UCI Dataset Adaptation.
    Handles 'SystemCodeNumber', 'Capacity', 'Occupancy', 'LastUpdated'.
    """
    # 1. Load Birmingham Data (Comma-separated)
    df = pd.read_csv(raw_path)
    
    # 2. Map Column Names explicitly (fixing any hidden whitespace)
    mapping = {
        'SystemCodeNumber': 'lot_id',
        'Capacity': 'capacity',
        'Occupancy': 'occupied',
        'LastUpdated': 'last_updated'
    }
    # If the exact names don't match, we fall back to positional
    if len(df.columns) >= 4:
        df.columns = ['lot_id', 'capacity', 'occupied', 'last_updated']
    else:
        raise ValueError(f"CSV file at {raw_path} has only {len(df.columns)} columns.")

    # 3. Time Series Pre-processing
    df['timestamp'] = pd.to_datetime(df['last_updated'])
    df['ts_bucket'] = df['timestamp'].dt.floor('15min')
    
    # 4. Aggregation (Occupancy rate per lot per time bucket)
    lot_ts = df.groupby(['lot_id', 'ts_bucket']).agg(
        occupied_slots=('occupied', 'mean'),
        total_slots=('capacity', 'max')
    ).reset_index()
    
    lot_ts['occupancy_rate'] = lot_ts['occupied_slots'] / lot_ts['total_slots']
    lot_ts = lot_ts.sort_values(['lot_id', 'ts_bucket'])
    
    # 5. Feature Generation (Rolling Windows)
    g = lot_ts.groupby('lot_id')
    lot_ts['net_flux'] = g['occupied_slots'].diff().fillna(0)
    lot_ts['occ_lag_15m'] = g['occupancy_rate'].shift(1)
    lot_ts['occ_lag_1h']  = g['occupancy_rate'].shift(4)
    
    # 6. Parking Events (PE) Feature Extraction per Gomari et al (2023)
    lot_ts['pe_arrival_rate'] = g['occupied_slots'].transform(
        lambda s: s.diff().clip(lower=0).rolling(4, min_periods=1).mean()
    )
    lot_ts['pe_departure_rate'] = g['occupied_slots'].transform(
        lambda s: (-s.diff()).clip(lower=0).rolling(4, min_periods=1).mean()
    )
    lot_ts['pe_net_flux'] = g['occupied_slots'].transform(lambda s: s.diff().fillna(0))
    lot_ts['pe_turnover'] = g['occupied_slots'].transform(
        lambda s: s.diff().abs().rolling(8, min_periods=1).sum()
    )

    mean_occ = g['occupancy_rate'].transform('mean').shift(1)
    std_occ = g['occupancy_rate'].transform('std').shift(1)
    lot_ts['pe_anomaly'] = ((lot_ts['occupancy_rate'] - mean_occ).abs() > 2 * std_occ).astype(float)
    lot_ts['pe_anomaly'] = lot_ts['pe_anomaly'].fillna(0)

    cusum = g['occupancy_rate'].transform(lambda s: (s - s.rolling(8, min_periods=1).mean()).fillna(0))
    threshold = cusum.rolling(4, min_periods=1).std().fillna(0) * 1.5
    lot_ts['pe_change_point'] = (cusum.abs() > threshold).astype(float)

    # 7. Target: t+15m
    lot_ts['target'] = g['occupancy_rate'].shift(-1)
    
    # 8. Cleaning
    pe_cols = ['pe_arrival_rate', 'pe_departure_rate', 'pe_net_flux', 'pe_turnover', 'pe_anomaly', 'pe_change_point']
    lot_ts = lot_ts.dropna(subset=['target', 'occ_lag_15m', 'occ_lag_1h'])
    lot_ts[pe_cols] = lot_ts[pe_cols].fillna(0)
    
    print(f"Processed {len(lot_ts)} Birmingham observations with {6} PE features.")
    return lot_ts
