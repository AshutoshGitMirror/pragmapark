"""Offline CVAE-WGAN training + versioning for the digital twin.

PURPOSE (plan P5, Recommended Path "versioned artifact"):
    The CVAE-WGAN generative component was REMOVED FROM RUNTIME. This script is
    the OFFLINE-ONLY path that re-implements it in its best form: train the
    generator against REAL observations with correct CVAE+WGAN-GP objectives,
    evaluate on held-out REAL data, and persist a *versioned* artifact plus a
    TwinModelVersion provenance row. The runtime NEVER imports or calls this.

WHY NOT THE ALTERNATIVE PATH ("rebuild properly as a causal intervention model"):
    The alternative path is gated on "enough labelled intervention data"
    (P(next observed state | current, history, weather, time, lot, price,
    intervention) with real scenario labels + observed outcomes after
    interventions). That data does NOT exist in this project: TwinObservation
    records real occupancy/price but carries no intervention->outcome
    supervision, and the scenario labels are one-hot-by-index, not real.
    Therefore the alternative path is BLOCKED and the recommended path (offline
    versioned artifact + calibrated deterministic baseline at runtime) is the
    implemented best form. This script does NOT claim the generator is a causal
    intervention model; promotion_status stays "experimental".

PRINCIPLE 6: no quality claim without correct objectives + real-data eval.
    Objectives here are correct (CVAE recon+KL; WGAN Wasserstein + gradient
    penalty). Evaluation is on a held-out REAL split only. No simulated value
    is ever used as training target (principle 1).
"""

import argparse
import json
import logging
import os
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("train_twin_generator")

SEED = int(os.getenv("PRAGMA_SEED", "42"))
np.random.seed(SEED)

# Congestion band derived from real occupancy rate (honest, deterministic).
def _congestion_band(occ: float) -> float:
    if occ < 0.40:
        return 0.0
    if occ < 0.65:
        return 0.33
    if occ < 0.85:
        return 0.66
    return 1.0


def build_state_rows(observations):
    """Build 5-dim real state vectors from real TwinObservation rows.

    state = [occupancy_rate, price/50, congestion_band, duration/24, share_ratio]
    Only REAL observations (source != 'simulated') may be passed (principle 1).
    """
    rows = []
    for o in observations:
        occ = float(o.get("occupancy_rate", 0.0) or 0.0)
        price = float(o.get("price", 0.0) or 0.0)
        share = float(o.get("resident_share", 0.0) or 0.0)
        rows.append([
            occ,
            price / 50.0,
            _congestion_band(occ),
            0.0,                 # duration unknown for a single snapshot
            float(np.clip(share, 0.0, 1.0)),
        ])
    return np.asarray(rows, dtype=float)


def _marginal_stats(x):
    return float(np.mean(x)), float(np.std(x) + 1e-9)


def _corr_diff(real, gen, n_seeds=8):
    """Frobenius norm of difference between real and generated corr matrices."""
    real = np.asarray(real, dtype=float)
    # generate n_seeds samples per real row via the generator's randomness
    g = np.asarray(gen, dtype=float)
    if real.shape[0] < 2 or g.shape[0] < 2:
        return None
    cr = np.corrcoef(real.T)
    cg = np.corrcoef(g.T)
    return float(np.linalg.norm(cr - cg, ord="fro"))


def evaluate(generator, val, n_seeds=8):
    """Held-out REAL-data evaluation (principle 6). Returns metrics dict."""
    import numpy as _np
    occ_real = val[:, 0]
    # reconstructions: encode->decode deterministic mean (mu) path
    conds = generator._make_cond_batch(_np.zeros(len(val), dtype=int))
    xc = _np.concatenate([val, conds], axis=1)
    from numpy import tanh
    h1 = tanh(xc @ generator.W_e1 + generator.b_e1)
    mu = h1 @ generator.W_mu + generator.b_mu
    lv = _np.clip(h1 @ generator.W_logvar + generator.b_logvar, -20, 20)
    z = mu  # deterministic mean for eval
    fake = tanh(_np.concatenate([z, conds], axis=1) @ generator.W + generator.b)
    recon_mae = float(_np.mean(_np.abs(fake - val)))
    recon_rmse = float(_np.sqrt(_np.mean((fake - val) ** 2)))

    # Marginal distribution match: mean/std of occupancy marginal real vs gen.
    rm, rs = _marginal_stats(occ_real)
    gm, gs = _marginal_stats(fake[:, 0])
    marginal_mae = abs(rm - gm) + abs(rs - gs)

    # Generated samples for correlation + stability.
    gen_samples = []
    for s in range(n_seeds):
        _np.random.seed(SEED + s)
        zz = _np.random.randn(len(val), generator.latent_dim)
        gsample = tanh(_np.concatenate([zz, conds], axis=1)
                       @ generator.W + generator.b)
        gen_samples.append(gsample)
    gen_stack = _np.stack(gen_samples, axis=0).reshape(-1, val.shape[1])
    corr_fro = _corr_diff(val, gen_stack)

    # Stability: val recon MAE variance across seeds.
    stab = []
    for s in range(n_seeds):
        _np.random.seed(SEED + s)
        zz = _np.random.randn(len(val), generator.latent_dim)
        gs_ = tanh(_np.concatenate([zz, conds], axis=1) @ generator.W + generator.b)
        stab.append(float(_np.mean(_np.abs(gs_ - val))))
    stability_std = float(_np.std(stab)) if len(stab) > 1 else 0.0

    return {
        "recon_mae": recon_mae,
        "recon_rmse": recon_rmse,
        "marginal_mae": marginal_mae,
        "corr_frobenius": corr_fro,
        "stability_std_over_seeds": stability_std,
        "n_val": int(len(val)),
    }


def load_real_observations(db, limit=20000):
    """Load REAL TwinObservation rows (never simulated) from the app DB."""
    from src.digital_twin.orm import TwinObservation
    q = (
        db.query(
            TwinObservation.occupancy_rate,
            TwinObservation.price,
        )
        .filter(TwinObservation.source != "simulated")
        .order_by(TwinObservation.observed_at.asc())
        .limit(limit)
        .all()
    )
    out = []
    for occ, price in q:
        out.append({
            "occupancy_rate": occ,
            "price": price,
            "resident_share": 0.0,
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db-url", default=None,
                    help="DB URL; defaults to the app's configured URL.")
    ap.add_argument("--epochs", type=int, default=400)
    ap.add_argument("--wgan-epochs", type=int, default=200)
    ap.add_argument("--version", default=None,
                    help="Artifact version (default: auto from data cutoff).")
    ap.add_argument("--out-dir", default="data/twin_generator")
    ap.add_argument("--feature-schema-version", default="twin_state_v1")
    args = ap.parse_args()

    from src.api.database import get_db_cm
    from src.digital_twin.generator import Generator
    from src.digital_twin.orm import TwinModelVersion
    from datetime import datetime, timezone

    with get_db_cm() as db:
        rows = load_real_observations(db)
        if len(rows) < 32:
            raise SystemExit(
                "BLOCKER: insufficient REAL observations (%d) to train the "
                "CVAE-WGAN offline. Option-2 rebuild is also blocked (no "
                "labelled intervention data). Keeping Recommended Path." % len(rows))
        data = build_state_rows(rows)
        cutoff_dt = datetime.now(timezone.utc).replace(tzinfo=None)
        cutoff = cutoff_dt.isoformat()

        # Train / val split (held-out real evaluation, principle 6).
        idx = np.random.permutation(len(data))
        n_val = max(1, int(0.2 * len(data)))
        val_idx, train_idx = idx[:n_val], idx[n_val:]
        train, val = data[train_idx], data[val_idx]

        g = Generator()
        losses = []
        for ep in range(args.epochs):
            bs = min(32, len(train))
            sel = train[np.random.choice(len(train), bs, replace=False)]
            losses.append(g.train_step(sel))
        for ep in range(args.wgan_epochs):
            bs = min(32, len(train))
            sel = train[np.random.choice(len(train), bs, replace=False)]
            g.wgan_train_step(sel)

        metrics = evaluate(g, val)
        cvae_final = float(losses[-1]) if losses else 0.0

        version = args.version or ("cvae_wgan_" + cutoff.replace(":", "").replace("-", "").replace("T", "_")[:15])
        artifact = g.save_artifact(
            os.path.join(args.out_dir, version + ".json"),
            version=version,
            training_data_cutoff=cutoff,
            feature_schema_version=args.feature_schema_version,
            validation_metrics={**metrics, "cvae_final_loss": cvae_final,
                                "n_train": int(len(train))},
        )
        # Provenance: TwinModelVersion (promotion stays experimental; not a
        # causal intervention model, no labelled intervention data).
        mv = TwinModelVersion(
            model_name="twin_cvae_wgan",
            artifact_version=version,
            training_data_cutoff=cutoff_dt,
            feature_schema_version=args.feature_schema_version,
            validation_metrics=json.dumps({**metrics, "cvae_final_loss": cvae_final}),
            promotion_status="experimental",
            created_at=cutoff_dt,
        )
        db.add(mv)
        db.commit()
        logger.info("Saved versioned CVAE-WGAN artifact %s (offline-only). "
                    "Val recon_mae=%.4f marginal_mae=%.4f stability_std=%.4f",
                    version, metrics["recon_mae"], metrics["marginal_mae"],
                    metrics["stability_std_over_seeds"])
        print(json.dumps({"version": version, "metrics": metrics,
                          "artifact": artifact["weights"] and "saved"}, indent=2))


if __name__ == "__main__":
    main()
