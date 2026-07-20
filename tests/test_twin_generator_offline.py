"""Tests for the OFFLINE-ONLY CVAE-WGAN generator artifact + versioning (P5).

These verify the best-form re-implementation of the removed generative part:
correct CVAE+WGAN objectives run offline, a *versioned* artifact is saved and
reloads to identical weights, held-out real-data evaluation produces metrics,
and — critically — the runtime never imports the generator (principles 5/6).
"""

import json
import os
import tempfile

import numpy as np

from src.digital_twin.generator import Generator
from scripts.train_twin_generator import build_state_rows, evaluate


def _fake_real_observations(n=200, seed=7):
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(n):
        occ = float(np.clip(rng.beta(2, 2), 0, 1))
        price = float(np.clip(10 + occ * 30 + rng.normal(0, 2), 5, 50))
        rows.append({"occupancy_rate": occ, "price": price,
                     "resident_share": 0.0})
    return rows


def test_build_state_rows_shape_and_bounds():
    rows = _fake_real_observations(50)
    x = build_state_rows(rows)
    assert x.shape == (50, 5)
    assert (x[:, 0] >= 0).all() and (x[:, 0] <= 1).all()
    # congestion band is one of the 4 honest levels
    assert set(np.unique(x[:, 2])).issubset({0.0, 0.33, 0.66, 1.0})


def test_cvae_train_step_reduces_recon_loss():
    x = build_state_rows(_fake_real_observations(256))
    g = Generator()
    first = g.train_step(x[:32])
    for _ in range(300):
        sel = x[np.random.choice(len(x), 32, replace=False)]
        last = g.train_step(sel)
    assert last <= first  # objective actually optimises on REAL data


def test_wgan_train_step_returns_real_losses():
    x = build_state_rows(_fake_real_observations(128))
    g = Generator()
    out = g.wgan_train_step(x[:32])
    # WGAN losses must be computed (not the empty-batch zero stub)
    assert set(out) == {"critic_loss", "gen_loss", "gradient_penalty"}
    assert out["gradient_penalty"] >= 0.0
    assert np.isfinite(out["critic_loss"]) and np.isfinite(out["gen_loss"])


def test_artifact_save_load_roundtrip_is_identical():
    x = build_state_rows(_fake_real_observations(256))
    g = Generator()
    for _ in range(100):
        g.train_step(x[np.random.choice(len(x), 32, replace=False)])
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "v1.json")
        artifact = g.save_artifact(
            path, version="v1", training_data_cutoff="2026-01-01T00:00:00",
            feature_schema_version="twin_state_v1",
            validation_metrics={"recon_mae": 0.1})
        assert os.path.exists(path)
        with open(path) as f:
            on_disk = json.load(f)
        assert on_disk["version"] == "v1"
        assert on_disk["model_name"] == "twin_cvae_wgan"
        assert on_disk["training_data_cutoff"] == "2026-01-01T00:00:00"
        assert on_disk["feature_schema_version"] == "twin_state_v1"

        version, g2 = Generator.load_artifact(path)
        assert version == "v1"
        # reloaded weights must be identical -> deterministic synth match
        for k, v in g._weights_dict().items():
            assert np.allclose(v, g2._weights_dict()[k])
    assert artifact["hyperparams"]["latent_dim"] == g.latent_dim


def test_held_out_evaluation_reports_required_metrics():
    x = build_state_rows(_fake_real_observations(300))
    train, val = x[:240], x[240:]
    g = Generator()
    for _ in range(200):
        g.train_step(train[np.random.choice(len(train), 32, replace=False)])
    m = evaluate(g, val)
    # principle 6: correct-objective + real-data eval metrics present
    for key in ("recon_mae", "recon_rmse", "marginal_mae",
                "stability_std_over_seeds", "n_val"):
        assert key in m
    assert m["n_val"] == len(val)
    assert m["recon_mae"] >= 0.0


def test_generator_is_not_imported_by_runtime_package():
    # P5/principle 6: offline-only. The public package must NOT export Generator.
    import src.digital_twin as dt
    assert "Generator" not in getattr(dt, "__all__", [])
    assert not hasattr(dt, "Generator")


def test_runtime_routes_do_not_instantiate_generator():
    # The legacy DT route must not build a runtime generator instance.
    import src.api.routes.digital_twin as dtr
    src = open(dtr.__file__).read()
    assert "pipeline.generator" not in src
    assert "synthesize_scenario" not in src
