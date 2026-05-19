import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import time
import logging
import threading

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

def hybrid_loop(interval: float = 5.0):
    from src.pipeline.orchestrator import pipeline
    from src.features.engine import add_features
    import pandas as pd
    import numpy as np

    logger.info("Hybrid 6-layer loop started")
    while True:
        try:
            data_path = "data/raw/birmingham_parking.csv"
            df = pd.read_csv(data_path, nrows=5) if os.path.exists(data_path) else None
            if df is not None:
                test_features = pd.Series({
                    "occupancy_rate": 0.5,
                    "occupied_slots": 250,
                    "total_slots": 500,
                })
                pred = pipeline._predict_occupancy(test_features)

                test_state = {"zone_id": "zone_0", "occupancy_rate": pred,
                              "price": pipeline.driver_search_lots([{
                                  "lot_id": "test_lot", "name": "Test Lot",
                                  "current_occupancy": pred, "current_price": 10.0,
                                  "total_slots": 500, "base_price": 10.0,
                              }])}

                status = pipeline.status()
                logger.info(f"Loop | pred={pred:.3f} | chain={status['blockchain']['chain_length']} blocks")

        except Exception as e:
            logger.error(f"Loop error: {e}")

        time.sleep(interval)

if __name__ == "__main__":
    hybrid_loop()
