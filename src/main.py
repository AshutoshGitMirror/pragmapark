import argparse
import uvicorn
import sys
import os
import random
import numpy as np

SEED = int(os.getenv("PRAGMA_SEED", "42"))
random.seed(SEED)
np.random.seed(SEED)

sys.path.append(os.getcwd())


def run_api(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):  # nosec B104
    from src.api import app
    uvicorn.run(app, host=host, port=port, reload=reload, server_header=False)


def run_training():
    from src.models.train_real import train_chronological_ensemble
    from src.features.engine import process_raw_to_features
    RAW_PATH = "data/raw/birmingham_parking.csv"
    features = process_raw_to_features(RAW_PATH)
    train_chronological_ensemble(features)


def run_rl():
    from src.rl.train_control import train_neural_control
    train_neural_control()


def run_hybrid():
    from src.hybrid_loop import run_hybrid_loop
    run_hybrid_loop()


def run_chronological():
    from src.chronological_analysis import run_chronological_analysis
    run_chronological_analysis()


def run_marl():
    from src.rl.multi_agent import QMIXMARL, ConnectedVehicle
    import numpy as np
    num_zones = 4
    capacities = [np.random.randint(200, 600) for _ in range(num_zones)]
    marl = QMIXMARL(num_zones, capacities)
    vehicles = [
        ConnectedVehicle(f"CV_{i}", np.random.randint(0, num_zones), "downtown")
        for i in range(20)
    ]
    marl.register_vehicles(vehicles)
    marl.train(episodes=800)
    validation = marl.validate()
    print(f"\nMARL Validation: {validation}")


def run_dashboard(host: str = "0.0.0.0", port: int = 8050):  # nosec B104
    from src.dashboard.app import run_dashboard as dash
    dash(host=host, port=port)


def main():
    parser = argparse.ArgumentParser(description="Gemini Smart Parking System")
    parser.add_argument("mode", nargs="?", default="api",
                        choices=["api", "train", "rl", "hybrid", "chrono", "marl", "dash"],
                        help="Execution mode")
    parser.add_argument("--host", default="0.0.0.0")  # nosec B104
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")

    args = parser.parse_args()

    modes = {
        "api": lambda: run_api(args.host, args.port, args.reload),
        "train": run_training,
        "rl": run_rl,
        "hybrid": run_hybrid,
        "chrono": run_chronological,
        "marl": run_marl,
        "dash": lambda: run_dashboard(args.host, args.port),
    }

    modes[args.mode]()


if __name__ == "__main__":
    main()
