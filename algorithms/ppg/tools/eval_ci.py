"""Confidence intervals by bootstrap over recordings (or subjects) for the reported accuracy figures.

    python tools/eval_ci.py

Reads only stored results, so it runs nothing on any split:

* ``tools/pdf_data/wrist_ieee.json`` / ``wrist_dalia.json``: per-recording MAE of the TEST splits (10 and 5 recordings);
  ``wrist_test_window_counts.json`` gives the windows per recording, which turns the mean over recordings into the
  pooled window-level MAE that the README quotes.
* ``bidmc_dev_*.json`` (subjects 1-32) and ``bidmc_heldout_*.json`` (33-53): per-subject HR MAE and HRV.

Windows of 8 s slide by 2 s, so consecutive windows share 6 s and the window count overstates the precision; the
recording is the unit that resamples. With 5 or 10 recordings the intervals are wide and the percentile bootstrap is
itself optimistic (compare the t interval and the range).
"""

import json
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr
from bootstrap import bootstrap_ci, t_interval, weighted_mean_ci

DATA = Path(__file__).resolve().parents[3] / "tools" / "pdf_data"


def line(name: str, ci: tuple[float, float, float], unit: str = "bpm") -> None:
    print(f"  {name:44s} {ci[0]:7.2f} {unit}  95 % CI [{ci[1]:.2f}, {ci[2]:.2f}]")


def wrist() -> None:
    counts = json.loads((DATA / "wrist_test_window_counts.json").read_text())
    for label, file, key in (("IEEE SPC 2015 TEST", "wrist_ieee.json", "ieee_test_windows_per_recording"),
                             ("PPG-DaLiA TEST", "wrist_dalia.json", "dalia_test_windows_per_recording")):
        d = json.loads((DATA / file).read_text())
        w = np.array(counts[key], float)
        print(f"\n{label}: {len(w)} recordings, {int(w.sum())} windows (overlapping, so not independent)")
        for m in ("plain", "learned"):
            v = np.array(d[m])
            line(f"{m}, pooled MAE (recording-weighted)", weighted_mean_ci(v, w))
            line(f"{m}, mean of recordings", bootstrap_ci(v))
            line(f"{m}, mean of recordings, t interval", t_interval(v))
            print(f"  {'':44s} range over recordings {v.min():.2f}-{v.max():.2f}")


def bidmc() -> None:
    for label, tag in (("BIDMC subjects 1-32 (development)", "dev"), ("BIDMC subjects 33-53 (held out)", "heldout")):
        hr = json.loads((DATA / f"bidmc_{tag}_hr.json").read_text())
        v = np.array(hr["mae"])
        print(f"\n{label}: {len(v)} subjects")
        line("HR MAE, mean over subjects", bootstrap_ci(v))
        line("HR MAE, median over subjects", bootstrap_ci(v, np.median))
        line("HR MAE, mean over subjects, t interval", t_interval(v))
        print(f"  {'coverage, mean over subjects':44s} {100 * np.mean(hr['coverage']):7.1f} %")
        h = json.loads((DATA / f"bidmc_{tag}_hrv.json").read_text())
        n = len(h["subjects"])
        print(f"  HRV, {n} subjects kept, {len(h['skipped'])} dropped by the mean-HR filter "
              f"({', '.join(str(x['subject']) for x in h['skipped']) or 'none'})")
        for name, ref, est in (("RMSSD", "rmssd_ecg", "rmssd_ppg"), ("SDNN", "sdnn_ecg", "sdnn_ppg")):
            xy = np.column_stack([h[ref], h[est]])
            line(f"{name} Pearson r vs ECG R-R", bootstrap_ci(xy, lambda a: np.corrcoef(a[:, 0], a[:, 1])[0, 1]), "")
            line(f"{name} Spearman rho (rank, less driven by outliers)", bootstrap_ci(xy, lambda a: spearmanr(a[:, 0], a[:, 1])[0]), "")
            line(f"{name} mean abs error", bootstrap_ci(xy, lambda a: np.abs(a[:, 1] - a[:, 0]).mean()), "ms")
            line(f"{name} bias (PPG - ECG)", bootstrap_ci(xy, lambda a: (a[:, 1] - a[:, 0]).mean()), "ms")


if __name__ == "__main__":
    wrist()
    bidmc()
