"""How much accuracy does a lower PPG/accelerometer sampling rate cost? (power research, the design notes)

    python tools/eval_sample_rate.py

The recordings are 125 Hz; they are decimated with an anti-alias polyphase filter and the pipeline is re-run.
A real AFE sampling at 25 sps has no such filter, so the loss measured here is a lower bound.

* BIDMC (resting finger PPG): HR MAE and coverage, and HRV against the ECG R-R series, as in ``eval_hrv_bidmc.py``.
* IEEE SPC 2015 wrist PPG, **TRAIN only** (there is deliberately no option for TEST): plain and learned
  ``MotionCompensatedHR``. TRAIN numbers are optimistic because both models saw those recordings at 125 Hz, so only
  the change with the rate is meaningful. Recordings whose stream length is not divisible by the decimation factor
  are skipped, so use factors 1, 2, 5, 10.
"""

import importlib.util
from fractions import Fraction
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly

from caseback_ppg import MotionCompensatedHR, beats_to_ibi, clean_ibi, detect_beats, heart_rate_series, hrv_metrics
from caseback_ppg.datasets import bidmc, ieeeppg

BIDMC_RATES = (125.0, 62.5, 41.6667, 31.25, 25.0, 20.0)      # 12.5 Hz is below the 8 Hz band-pass of detect_beats
WRIST_FACTORS = (1, 2, 5, 10)                                  # 125, 62.5, 25, 12.5 Hz

_spec = importlib.util.spec_from_file_location("eval_hrv_bidmc", Path(__file__).with_name("eval_hrv_bidmc.py"))
_hrv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hrv)


def decimate(x: np.ndarray, fs_new: float, fs: float = 125.0, axis: int = 0) -> np.ndarray:
    ratio = Fraction(fs_new / fs).limit_denominator(1000)
    return x if ratio == 1 else resample_poly(x, ratio.numerator, ratio.denominator, axis=axis)


def hr_mae(rec: bidmc.Record, ppg: np.ndarray, fs: float) -> tuple[float, float]:
    t, bpm = heart_rate_series(detect_beats(ppg, fs), fs, duration_s=len(ppg) / fs)
    good = ~np.isnan(rec.ref_hr_bpm)
    ref = np.interp(t, rec.ref_t_s[good], rec.ref_hr_bpm[good])
    valid = ~np.isnan(bpm)
    return (float(np.mean(np.abs(bpm[valid] - ref[valid]))), float(valid.mean())) if valid.any() else (np.nan, 0.0)


def ppg_hrv(ppg: np.ndarray, fs: float):
    t, ibi = beats_to_ibi(detect_beats(ppg, fs, fiducial="upslope"), fs)
    t, ibi = clean_ibi(t, ibi)
    return hrv_metrics(ibi, t)


def bidmc_sweep() -> None:
    subjects = [s for s in range(1, 33) if bidmc.cached(s)]      # development set only; 33-53 are held out
    recs = {s: bidmc.load(s, download=False) for s in subjects}
    ecg = {s: _hrv.metrics(_hrv.r_beats(s)) for s in subjects}
    print(f"BIDMC, {len(subjects)} development subjects (resting finger PPG)")
    print(f"{'fs Hz':>7} {'HR MAE':>7} {'cover':>6} | {'n':>3} {'RMSSD r':>8} {'med rel':>8} {'SDNN r':>7} {'med rel':>8}")
    for fs in BIDMC_RATES:
        hr = [hr_mae(recs[s], decimate(recs[s].ppg, fs), fs) for s in subjects]
        rows = []
        for s in subjects:
            e, p = ecg[s], ppg_hrv(decimate(recs[s].ppg, fs), fs)
            if e is None or p is None:
                continue
            mon = np.nanmean(recs[s].ref_hr_bpm)
            if abs(e.mean_hr_bpm - mon) > 3 or abs(p.mean_hr_bpm - mon) > 3:
                continue
            rows.append((e.rmssd_ms, p.rmssd_ms, e.sdnn_ms, p.sdnn_ms))
        a = np.array(rows)
        print(f"{fs:7.2f} {np.nanmean([h[0] for h in hr]):7.2f} {np.mean([h[1] for h in hr]):6.1%} | {len(a):3d} "
              f"{np.corrcoef(a[:, 0], a[:, 1])[0, 1]:8.3f} {np.median(np.abs(a[:, 1] - a[:, 0]) / a[:, 0]):8.1%} "
              f"{np.corrcoef(a[:, 2], a[:, 3])[0, 1]:7.3f} {np.median(np.abs(a[:, 3] - a[:, 2]) / a[:, 2]):8.1%}")


def wrist_sweep() -> None:
    w = ieeeppg.load("TRAIN")
    ids = ieeeppg.subject_ids(w)
    n = int(ids.max()) + 1
    print(f"\nIEEE SPC 2015 TRAIN only: {len(w.hr_bpm)} windows, {n} recordings")
    for q in WRIST_FACTORS:
        fs = 125.0 / q
        errs: dict[str, list[np.ndarray]] = {"plain": [], "learned": []}
        for s in range(n):
            ppg, acc, labels = ieeeppg.stream(w, ids, s)
            if q > 1:
                ppg, acc = resample_poly(ppg, 1, q, axis=0), resample_poly(acc, 1, q, axis=0)
            for name, est in (("plain", MotionCompensatedHR(fs)), ("learned", MotionCompensatedHR.learned(fs))):
                ups = est.push(ppg, acc)
                if len(ups) == len(labels):
                    errs[name].append(np.abs(np.array([u.bpm for u in ups]) - labels))
        cells = [f"{name} MAE {np.concatenate(e).mean():5.2f} ({len(e)}/{n} rec)" for name, e in errs.items() if e]
        print(f"fs {fs:6.2f} Hz  " + " | ".join(cells))


if __name__ == "__main__":
    bidmc_sweep()
    wrist_sweep()
