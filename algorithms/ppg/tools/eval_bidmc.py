"""Evaluate the HR pipeline against BIDMC. Downloads records to ~/.cache/caseback/bidmc.

    python tools/eval_bidmc.py [--subjects 1-32] [--dump out.json]

Subjects 1-32 are the development set (the pipeline and the subject filter were looked at on them). Subjects 33-53 are
held out: evaluate them once, with the parameters as they are, and report what comes out. There is no subject filter
here; every subject is scored (``eval_hrv_bidmc.py`` has the HRV subject filter).
"""

import argparse
import json
from pathlib import Path

import numpy as np

from caseback_ppg import detect_beats, heart_rate_series
from caseback_ppg.datasets import bidmc


def parse_range(s: str) -> range:
    lo, _, hi = s.partition("-")
    return range(int(lo), int(hi or lo) + 1)


def evaluate(subject: int) -> tuple[float, float]:
    """Return (MAE in bpm, fraction of windows with a reading) for one subject."""
    rec = bidmc.load(subject)
    beats = detect_beats(rec.ppg, rec.fs)
    t, bpm = heart_rate_series(beats, rec.fs, duration_s=len(rec.ppg) / rec.fs)
    # The monitor numerics have dropouts (NaN); interpolate over the good samples only.
    good = ~np.isnan(rec.ref_hr_bpm)
    ref = np.interp(t, rec.ref_t_s[good], rec.ref_hr_bpm[good])
    valid = ~np.isnan(bpm)
    if not valid.any():
        return float("nan"), 0.0
    return float(np.mean(np.abs(bpm[valid] - ref[valid]))), float(valid.mean())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subjects", type=parse_range, default=range(1, 33), help="default: the development set 1-32")
    ap.add_argument("--dump", type=Path, help="write per-subject MAE and coverage as JSON")
    args = ap.parse_args()
    maes, covs = [], []
    print("subject   MAE(bpm)  coverage")
    for s in args.subjects:
        mae, cov = evaluate(s)
        maes.append(mae)
        covs.append(cov)
        print(f"{s:7d}  {mae:8.2f}  {cov:8.1%}")
    if args.dump:
        args.dump.write_text(json.dumps({"subjects": list(args.subjects), "mae": maes, "coverage": covs}))
    maes = np.array(maes)
    print(f"\nmean MAE {np.nanmean(maes):.2f} bpm | median {np.nanmedian(maes):.2f} | "
          f"worst {np.nanmax(maes):.2f} | n={len(maes)}")


if __name__ == "__main__":
    main()
