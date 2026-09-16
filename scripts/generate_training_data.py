"""Generate synthetic training data from device profiles.

Usage:
    python scripts/generate_training_data.py [--per-class 300] [--out path]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Allow ``python scripts/...`` from project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config  # noqa: E402
from src.classifier import generate_synthetic_dataset  # noqa: E402
from src.features import FEATURE_NAMES  # noqa: E402
from src.utils import configure_logging, get_logger  # noqa: E402

log = get_logger(__name__)


def main() -> None:
    p = argparse.ArgumentParser(description="Generate synthetic Chhaya training data")
    p.add_argument("--per-class", type=int, default=300,
                   help="Number of synthetic samples per device class")
    p.add_argument("--out", type=str, default=str(config.TRAINING_DATA_PATH),
                   help="Output CSV path")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    configure_logging()

    log.info("Generating %d samples per class for %d classes...",
             args.per_class, len(config.KNOWN_DEVICE_LABELS))
    X, y = generate_synthetic_dataset(n_per_class=args.per_class, seed=args.seed)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(X, columns=list(FEATURE_NAMES))
    df.insert(0, "label", y)
    df.to_csv(out, index=False)

    log.info("Wrote %d rows to %s", len(df), out)
    print(df.head())
    print(df.groupby("label").size())


if __name__ == "__main__":
    main()
