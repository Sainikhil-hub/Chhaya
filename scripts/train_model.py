"""Train the Random Forest classifier and save to disk.

Usage:
    python scripts/train_model.py [--data path/to.csv] [--out path/to/model.joblib]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config  # noqa: E402
from src.classifier import GhostPrintClassifier  # noqa: E402
from src.features import FEATURE_NAMES  # noqa: E402
from src.utils import configure_logging, get_logger  # noqa: E402

log = get_logger(__name__)


def main() -> None:
    p = argparse.ArgumentParser(description="Train GhostPrint Random Forest classifier")
    p.add_argument("--data", type=str, default=str(config.TRAINING_DATA_PATH),
                   help="Path to training CSV (must contain a 'label' column)")
    p.add_argument("--out", type=str, default=str(config.MODEL_PATH),
                   help="Output model path (.joblib)")
    p.add_argument("--regen", action="store_true",
                   help="Regenerate synthetic training data first")
    p.add_argument("--per-class", type=int, default=300,
                   help="Synthetic samples per class if --regen")
    args = p.parse_args()

    configure_logging()

    data_path = Path(args.data)
    if args.regen or not data_path.exists():
        if not args.regen:
            log.warning("Training data not found at %s, regenerating.", data_path)
        from src.classifier import generate_synthetic_dataset
        X, y = generate_synthetic_dataset(n_per_class=args.per_class)
        data_path.parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(X, columns=list(FEATURE_NAMES))
        df.insert(0, "label", y)
        df.to_csv(data_path, index=False)
        log.info("Wrote %d samples to %s", len(df), data_path)

    df = pd.read_csv(data_path)
    if "label" not in df.columns:
        raise SystemExit("Training CSV must contain a 'label' column")

    y = df["label"].astype(str).values
    X = df[list(FEATURE_NAMES)].values

    log.info("Loaded %d samples with %d features", len(X), X.shape[1])
    clf = GhostPrintClassifier()
    summary = clf.train(X, y)
    log.info("Test accuracy: %.3f", summary["accuracy"])
    log.info("Per-class report:\n%s", summary["report"])

    out_path = clf.save(args.out)
    log.info("Model saved to %s", out_path)


if __name__ == "__main__":
    main()
