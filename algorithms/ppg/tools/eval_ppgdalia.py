"""Heart-rate accuracy on PPG-DaLiA (wrist BVP + accelerometer, everyday activities) against chest-ECG heart rate.

    python tools/eval_ppgdalia.py [--split TEST|TRAIN]

Plain: the estimator tuned on IEEE SPC 2015 with nothing re-tuned (the 48-tap NLMS canceller, 0.38 s at 125 Hz,
becomes 25 taps at 64 Hz). Learned: ``MotionCompensatedHR.learned()``, whose candidate scorer was trained on
IEEE + DaLiA TRAIN only. Different sensor (Empatica E4, one green channel), activities and people from IEEE.
"""

import argparse
import json
from pathlib import Path

import numpy as np

from caseback_ppg import MotionCompensatedHR
from caseback_ppg.datasets import ppgdalia


def line(name: str, est: np.ndarray, ref: np.ndarray) -> None:
    ok = ~np.isnan(est)
    err = np.abs(est[ok] - ref[ok])
    print(f"  {name:36s} MAE {err.mean():6.2f}  median {np.median(err):6.2f}  "
          f"<=5 bpm {np.mean(err <= 5):6.1%}  (n={ok.sum()})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="TEST", choices=ppgdalia.SPLITS)
    ap.add_argument("--dump", type=Path, help="write per-recording MAE and recording 0's series as JSON, for the PDF figures")
    args = ap.parse_args()
    w = ppgdalia.load(args.split)
    ids = ppgdalia.recording_ids(w)
    ref = w.hr_bpm
    print(f"{args.split}: {len(ref)} windows, {ids.max() + 1} recordings, HR {ref.min():.0f}-{ref.max():.0f} bpm")

    plain, est, conf = np.zeros(len(ref)), np.zeros(len(ref)), np.zeros(len(ref))
    for s in range(ids.max() + 1):
        ppg, acc, labels = ppgdalia.stream(w, ids, s)
        ups = MotionCompensatedHR(ppgdalia.FS, taps=round(0.384 * ppgdalia.FS)).push(ppg, acc)
        assert len(ups) == len(labels), (len(ups), len(labels))
        plain[ids == s] = [u.bpm for u in ups]
        ups = MotionCompensatedHR.learned(ppgdalia.FS).push(ppg, acc)
        est[ids == s] = [u.bpm for u in ups]
        conf[ids == s] = [u.confidence for u in ups]

    if args.dump:
        per = lambda e: [float(np.abs(e[ids == k] - ref[ids == k]).mean()) for k in range(ids.max() + 1)]  # noqa: E731
        m = ids == 0
        args.dump.write_text(json.dumps({
            "split": args.split, "plain": per(plain), "learned": per(est),
            "series": {"step_s": 2, "ref": np.round(ref[m], 1).tolist(), "plain": plain[m].tolist(),
                       "learned": est[m].tolist(), "conf": np.round(conf[m], 2).tolist()}}))
    print("\nOverall")
    line("constant = median label", np.full(len(ref), np.median(ref)), ref)
    line("plain (tuned on IEEE only)", plain, ref)
    line("learned candidate scorer", est, ref)
    hi = conf >= 0.5
    line("confidence >= 0.5", np.where(hi, est, np.nan), ref)
    print(f"  answered {hi.mean():.1%} of windows")

    print("\nPer recording")
    for s in range(ids.max() + 1):
        m = ids == s
        err = np.abs(est[m] - ref[m])
        print(f"  {s:2d}  MAE {err.mean():5.2f}  <=5 bpm {np.mean(err <= 5):6.1%}  n={m.sum():5d}  "
              f"HR {ref[m].min():.0f}-{ref[m].max():.0f}")


if __name__ == "__main__":
    main()
