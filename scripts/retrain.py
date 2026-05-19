import pandas as pd
import numpy as np
import os
import sys
sys.path.insert(0, os.getcwd())


def retrain_ml(data_path: str = "data/raw/birmingham_parking.csv"):
    from src.features.engine import process_raw_to_features
    from src.models.train_real import train_chronological_ensemble
    features = process_raw_to_features(data_path)
    mae = train_chronological_ensemble(features)
    print(f"Retraining complete. MAE: {mae:.5f}")
    return mae


if __name__ == "__main__":
    retrain_ml()
