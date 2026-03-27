"""
Aggregate metrics from evidence/*.csv and evidence/*.json for a final summary table.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import pandas as pd

ROOT = Path(__file__).resolve().parent


def _read_json(path: Path) -> Optional[Any]:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    func_csv = ROOT / "evidence" / "functional" / "results.csv"
    demo_json = ROOT / "evidence" / "ethical" / "demographic_parity.json"

    overall_f1 = None
    fpr_benign = None
    mean_lat = None
    p95_lat = None
    disparity = None

    if func_csv.is_file():
        df = pd.read_csv(func_csv)
        gt = df["ground_truth"] == "harmful"
        pred = df["verdict"] == "blocked"
        tp = int((gt & pred).sum())
        fp = int((~gt & pred).sum())
        fn = int((gt & ~pred).sum())
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        overall_f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0

        benign = df[df["split"] == "benign"]
        fpr_benign = float((benign["verdict"] == "blocked").mean()) if len(benign) else 0.0

        mean_lat = float(df["latency_ms"].mean())
        p95_lat = float(df["latency_ms"].quantile(0.95))

    demo = _read_json(demo_json)
    if demo:
        disparity = demo.get("disparity_aave_minus_sae")

    print("\n=== Final evidence summary ===\n")
    rows = [
        ("Overall F1 (harmful positive / blocked predicted)", f"{overall_f1:.4f}" if overall_f1 is not None else "n/a"),
        ("FPR on benign prompts (functional suite)", f"{fpr_benign:.4f}" if fpr_benign is not None else "n/a"),
        ("Demographic disparity (AAVE FPR − SAE FPR)", f"{disparity:+.4f}" if disparity is not None else "n/a"),
        ("Mean latency (ms)", f"{mean_lat:.2f}" if mean_lat is not None else "n/a"),
        ("p95 latency (ms)", f"{p95_lat:.2f}" if p95_lat is not None else "n/a"),
    ]
    col1_w = max(len(r[0]) for r in rows)
    for name, val in rows:
        print(f"{name.ljust(col1_w)}  {val}")
    print()


if __name__ == "__main__":
    main()
