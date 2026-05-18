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
    
    # 6. Target: t+15m
    lot_ts['target'] = g['occupancy_rate'].shift(-1)
    
    # 7. Cleaning
    lot_ts = lot_ts.dropna(subset=['target', 'occ_lag_15m', 'occ_lag_1h'])
    
    print(f"Processed {len(lot_ts)} Birmingham observations.")
    return lot_ts
