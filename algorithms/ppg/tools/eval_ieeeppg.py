"""Heart-rate accuracy on wrist PPG during exercise (IEEE SPC 2015), against the chest-ECG label.

    python tools/eval_ieeeppg.py [--split TEST|TRAIN]

Downloads the split (60-80 MB) to ~/.cache/caseback/ieeeppg on first use. Two methods are compared on the
same windows:

* peaks: the resting-PPG pipeline (band-pass, peak detection, median IBI) on one 8 s window, no accelerometer;
* wrist: ``MotionCompensatedHR`` (NLMS motion canceller + spectral HMM tracker), causal and streaming, plain
  (parameters tuned on TRAIN) and ``.learned()`` (learned candidate scorer trained on IEEE + DaLiA TRAIN only).
  TRAIN numbers are optimistic (the models saw those recordings); TEST is the honest one.
"""

import argparse
import json
from pathlib import Path

import numpy as np

from caseback_ppg import MotionCompensatedHR, detect_beats, heart_rate_series
from caseback_ppg.datasets import ieeeppg


def peaks_estimate(ppg: np.ndarray, fs: float) -> float:
    beats = detect_beats(ppg, fs)
    _, bpm = heart_rate_series(beats, fs, window_s=8.0, duration_s=len(ppg) / fs)
    return float(bpm[-1]) if len(bpm) else float("nan")


def line(name: str, est: np.ndarray, ref: np.ndarray) -> None:
    ok = ~np.isnan(est)
    err = np.abs(est[ok] - ref[ok])
    print(f"  {name:34s} MAE {err.mean():6.2f}  median {np.median(err):6.2f}  "
          f"<=5 bpm {np.mean(err <= 5):6.1%}  (n={ok.sum()})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="TEST", choices=ieeeppg.SPLITS)
    ap.add_argument("--dump", type=Path, help="write per-recording MAE (plain, learned) as JSON, for the PDF figures")
    args = ap.parse_args()
    w = ieeeppg.load(args.split)
    ids = ieeeppg.subject_ids(w)
    ref = w.hr_bpm
    print(f"{args.split}: {len(ref)} windows, {ids.max() + 1} recordings, HR {ref.min():.0f}-{ref.max():.0f} bpm")

    peaks = np.array([peaks_estimate(w.ppg[i, 0], w.fs) for i in range(len(ref))])
    plain, wrist, conf = np.zeros(len(ref)), np.zeros(len(ref)), np.zeros(len(ref))
    for s in range(ids.max() + 1):
        ppg, acc, labels = ieeeppg.stream(w, ids, s)
        ups = MotionCompensatedHR(w.fs).push(ppg, acc)
        assert len(ups) == len(labels), (len(ups), len(labels))
        plain[ids == s] = [u.bpm for u in ups]
        ups = MotionCompensatedHR.learned(w.fs).push(ppg, acc)
        wrist[ids == s] = [u.bpm for u in ups]
        conf[ids == s] = [u.confidence for u in ups]

    print("\nOverall")
    line("constant = median label", np.full(len(ref), np.median(ref)), ref)
    line("peaks, no accelerometer", peaks, ref)
    line("wrist: NLMS + spectral tracker", plain, ref)
    line("wrist: learned candidate scorer", wrist, ref)

    print("\nPer recording (learned)")
    for s in range(ids.max() + 1):
        m = ids == s
        err = np.abs(wrist[m] - ref[m])
        print(f"  {s:2d}  MAE {err.mean():5.2f}  <=5 bpm {np.mean(err <= 5):6.1%}  "
              f"HR {ref[m].min():.0f}-{ref[m].max():.0f}")

    if args.dump:
        per = lambda est: [float(np.abs(est[ids == k] - ref[ids == k]).mean()) for k in range(ids.max() + 1)]  # noqa: E731
        args.dump.write_text(json.dumps({"split": args.split, "plain": per(plain), "learned": per(wrist)}))
    hi = conf >= 0.5
    print("\nConfidence gate (posterior mass within 3 bpm of the estimate)")
    line("confidence >= 0.5 (answered)", np.where(hi, wrist, np.nan), ref)
    print(f"  answered {hi.mean():.1%} of windows")


if __name__ == "__main__":
    main()
