#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path
from tsm_dataset import import_dataset

ROOT = Path(__file__).resolve().parents[1]

def main() -> None:
    parser = argparse.ArgumentParser(description="Import the Roberts/Paliwal TSM test set")
    parser.add_argument("--ref-zip", type=Path, required=True)
    parser.add_argument("--test-zip", type=Path, required=True)
    parser.add_argument("--scores", type=Path, required=True)
    parser.add_argument("--destination", type=Path, default=ROOT / "data" / "external" / "tsm_test")
    args = parser.parse_args()
    result = import_dataset(args.ref_zip, args.test_zip, args.scores, args.destination)
    print(result.manifest_csv)

if __name__ == "__main__":
    main()
