"""Robustness check: regenerate the synthetic world with several seeds and evaluate each in a fresh temp DB.
Usage (from backend/):  python scripts/multi_seed_eval.py 1 2 3 4 5 6 7 8"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent


def one(seed: int) -> dict:
    tmp = tempfile.mkdtemp()
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{tmp}/e.sqlite3", "GROUND_TRUTH_PATH": f"{tmp}/gt.json"}
    run = lambda *a: subprocess.run([sys.executable, "manage.py", *a], cwd=BACKEND, env=env, check=True, capture_output=True, text=True)  # noqa: E731
    run("migrate", "-v0")
    run("seed_demo", "--seed-value", str(seed), "--detect")
    run("evaluate", "--write", f"{tmp}/r.json")
    return json.load(open(f"{tmp}/r.json"))


if __name__ == "__main__":
    rows = []
    for seed in [int(s) for s in sys.argv[1:]] or [1, 2, 3, 4, 5]:
        o = (r := one(seed))["overall"]
        rows.append((o["precision"], o["recall"], o["f1"]))
        print(f"seed {seed:>3}: precision={o['precision']:.3f} recall={o['recall']:.3f} F1={o['f1']:.3f} hard-neg FP={r['hard_negatives']['false_positives_at_min_level']} (fp={o['fp']} fn={o['fn']})")
    n = len(rows)
    print(f"mean   : precision={sum(r[0] for r in rows) / n:.3f} recall={sum(r[1] for r in rows) / n:.3f} F1={sum(r[2] for r in rows) / n:.3f}")
