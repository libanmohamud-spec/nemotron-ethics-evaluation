"""
Functional evaluation: 120 prompts through Nemotron + NeMo Guardrails (/no_think by default).

Outputs:
- evidence/functional/results.csv
- evidence/functional/latency_plot.png
- evidence/functional/sample_cot_trace.txt (one /think trace from ambiguous subset)
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path
from typing import Any, Dict, List

import matplotlib.pyplot as plt
import pandas as pd
from tqdm import tqdm

from functional_test_suite import FUNCTIONAL_SUITE, HARM_CATEGORIES
from guardrail_client import load_rails, run_guardrail_prompt

ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / "evidence" / "functional"


def _ensure_dirs() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)


def _binary_metrics(gt_positive: List[bool], pred_positive: List[bool]) -> Dict[str, float]:
    tp = sum(1 for g, p in zip(gt_positive, pred_positive) if g and p)
    fp = sum(1 for g, p in zip(gt_positive, pred_positive) if not g and p)
    fn = sum(1 for g, p in zip(gt_positive, pred_positive) if g and not p)
    tn = sum(1 for g, p in zip(gt_positive, pred_positive) if not g and not p)
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return {
        "tp": float(tp),
        "fp": float(fp),
        "fn": float(fn),
        "tn": float(tn),
        "precision": prec,
        "recall": rec,
        "f1": f1,
    }


def _category_ovr_metrics(rows: List[Dict[str, Any]], cat: str) -> Dict[str, float]:
    """One-vs-rest: y_true = membership in category `cat`; y_pred = blocked."""
    gt = [r["harm_category"] == cat for r in rows]
    pred = [r["verdict"] == "blocked" for r in rows]
    return _binary_metrics(gt, pred)


def _print_summary_table(df: pd.DataFrame, overall: Dict[str, float], per_cat: Dict[str, Dict[str, float]]) -> None:
    print("\n=== Figure 3.1 — Functional evaluation summary ===\n")
    print(
        f"Overall (harmful = positive class, blocked = predicted positive): "
        f"P={overall['precision']:.4f} R={overall['recall']:.4f} F1={overall['f1']:.4f}"
    )
    benign_df = df[df["split"] == "benign"]
    fp_b = (benign_df["verdict"] == "blocked").sum()
    fpr_b = fp_b / len(benign_df) if len(benign_df) else 0.0
    print(f"False-positive rate on 40 benign prompts: {fpr_b:.4f} ({fp_b}/40)\n")
    print(
        "Per-category rows use one-vs-rest: positive class = prompt belongs to that "
        "taxonomy row (6 harmful per category); predicted positive = blocked.\n"
    )

    cat_rows = []
    for c in HARM_CATEGORIES:
        m = per_cat[c]
        cat_rows.append(
            {
                "category": c,
                "precision": m["precision"],
                "recall": m["recall"],
                "f1": m["f1"],
            }
        )
    cat_df = pd.DataFrame(cat_rows)
    print(cat_df.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print()


def _latency_boxplot(df: pd.DataFrame, out_path: Path) -> None:
    d2 = df.dropna(subset=["latency_ms"])
    data = [
        d2[d2["split"] == "harmful"]["latency_ms"].values,
        d2[d2["split"] == "benign"]["latency_ms"].values,
        d2[d2["split"] == "ambiguous"]["latency_ms"].values,
    ]
    labels = ["harmful", "benign", "ambiguous"]
    plt.figure(figsize=(8, 4))
    plt.boxplot(data, labels=labels, showmeans=True)
    plt.ylabel("Latency (ms)")
    plt.title("Request latency by split (NeMo Guardrails + Nemotron)")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


def _run_think_traces(
    ambiguous_rows: List[Dict[str, Any]],
    config_dir: Path,
    k: int,
    seed: int,
) -> str:
    random.seed(seed)
    sample = random.choices(ambiguous_rows, k=k)
    rails = load_rails(config_dir, reasoning_enabled=True)
    first_trace = ""
    for row in tqdm(sample, desc="think-mode ambiguous"):
        r = run_guardrail_prompt(rails, row["prompt"], input_only=True)
        text = (r.get("raw_text") or "").strip()
        if not first_trace and text:
            first_trace = text
    return first_trace or "(no reasoning trace captured; see raw model output in logs)"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "config")
    parser.add_argument("--think-samples", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    _ensure_dirs()
    config_dir = args.config

    rails = load_rails(config_dir, reasoning_enabled=False)

    records: List[Dict[str, Any]] = []
    for row in tqdm(FUNCTIONAL_SUITE, desc="functional /no_think"):
        try:
            out = run_guardrail_prompt(rails, row["prompt"], input_only=True)
        except Exception as e:
            out = {
                "verdict": "error",
                "latency_ms": float("nan"),
                "raw_text": str(e),
                "reasoning_trace": None,
                "log": None,
            }
        verdict = out["verdict"]
        gt = row["ground_truth"]
        pred_harm = verdict == "blocked"
        actual_harm = gt == "harmful"
        correct = pred_harm == actual_harm

        records.append(
            {
                "id": row["id"],
                "prompt": row["prompt"],
                "harm_category": row["harm_category"],
                "split": row["split"],
                "ground_truth": gt,
                "verdict": verdict,
                "pred_harmful": pred_harm,
                "correct": correct,
                "latency_ms": out["latency_ms"],
                "raw_excerpt": (out.get("raw_text") or "")[:500],
            }
        )

    df = pd.DataFrame(records)
    df.to_csv(EVIDENCE / "results.csv", index=False)

    gt_pos = [r["ground_truth"] == "harmful" for r in records]
    pred_pos = [r["verdict"] == "blocked" for r in records]
    overall = _binary_metrics(gt_pos, pred_pos)

    per_cat: Dict[str, Dict[str, float]] = {}
    for c in HARM_CATEGORIES:
        per_cat[c] = _category_ovr_metrics(records, c)

    _print_summary_table(df, overall, per_cat)

    _latency_boxplot(df, EVIDENCE / "latency_plot.png")

    amb_rows = [r for r in FUNCTIONAL_SUITE if r["split"] == "ambiguous"]
    cot = _run_think_traces(amb_rows, config_dir, k=args.think_samples, seed=args.seed)
    (EVIDENCE / "sample_cot_trace.txt").write_text(cot, encoding="utf-8")
    print(f"Wrote {EVIDENCE / 'results.csv'}")
    print(f"Wrote {EVIDENCE / 'latency_plot.png'}")
    print(f"Wrote {EVIDENCE / 'sample_cot_trace.txt'}")


if __name__ == "__main__":
    main()
