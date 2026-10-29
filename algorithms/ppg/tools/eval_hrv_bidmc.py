"""HRV from PPG pulse intervals against HRV from ECG R-R intervals, on BIDMC (finger PPG, ICU, at rest).

    python tools/eval_hrv_bidmc.py [--subjects 1-32] [--dump out.json]   # needs the subjects cached (eval_bidmc.py downloads them)

A subject is kept only if the mean HR of both series is within 3 bpm of the bedside monitor's, so a bad detection
on either side is not scored as HRV error. The PPG side uses the steepest-upstroke fiducial (better timing than the peak: tried peak and three upstroke
bands, the 0.5-4 Hz upstroke chosen). Both series go through the same cleaning (``clean_ibi``) and both peak times are refined to sub-sample. The ECG side
uses a simple lead-II R-peak detector that is not validated, so differences are pulse-rate variability vs. an
approximate heart-rate variability, not a certified comparison. Whole-recording metrics (about 8 min per subject).
"""

import argparse
import csv
import json
from pathlib import Path

import numpy as np
from scipy.signal import butter, find_peaks, sosfiltfilt

from caseback_ppg import beats_to_ibi, clean_ibi, detect_beats, hrv_metrics
from caseback_ppg.datasets import bidmc

FS = bidmc.FS


def r_beats(subject: int) -> np.ndarray:
    """Pan-Tompkins-style QRS detector on lead II, with T-wave rejection and sub-sample refinement."""
    with (bidmc.DEFAULT_CACHE / f"bidmc_{subject:02d}_Signals.csv").open(newline="") as f:
        rows = list(csv.reader(f))
    header = [h.strip() for h in rows[0]]
    ecg = np.array(rows[1:], dtype=float)[:, header.index("II")]
    bp = sosfiltfilt(butter(2, [5, 15], btype="bandpass", fs=FS, output="sos"), ecg)
    energy = np.convolve(np.gradient(bp) ** 2, np.ones(int(0.15 * FS)) / int(0.15 * FS), mode="same")
    pk, _ = find_peaks(energy, distance=int(0.25 * FS), height=np.percentile(energy, 90) * 0.15)
    h = energy[pk]
    local = np.array([np.median(h[max(0, i - 8):i + 9]) for i in range(len(h))])
    pk = pk[h >= 0.35 * local]                                    # drop T waves and noise well below their neighbours
    w = int(0.08 * FS)
    out = []
    for i in pk:                                                   # snap to the R apex (either polarity)
        lo, hi = max(i - w, 1), min(i + w, len(bp) - 2)
        j = lo + int(np.argmax(np.abs(bp[lo:hi])))
        a_, b_, c_ = abs(bp[j - 1]), abs(bp[j]), abs(bp[j + 1])
        den = a_ - 2 * b_ + c_
        out.append(j + (0.5 * (a_ - c_) / den if den != 0 else 0.0))
    return np.unique(np.round(np.array(out), 3))


def metrics(beats: np.ndarray):
    t, ibi = beats_to_ibi(beats, FS)
    tc, ic = clean_ibi(t, ibi)
    return hrv_metrics(ic, tc)


def parse_range(s: str) -> range:
    lo, _, hi = s.partition("-")
    return range(int(lo), int(hi or lo) + 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subjects", type=parse_range, default=range(1, 33), help="default: the development set 1-32")
    ap.add_argument("--dump", type=Path, help="write per-subject HRV and the dropped subjects (with reasons) as JSON")
    args = ap.parse_args()
    rows, skipped, no_metrics = [], [], []
    for s in args.subjects:
        if not bidmc.cached(s):
            continue
        rec = bidmc.load(s, download=False)
        ecg_beats = r_beats(s)
        p, e = metrics(detect_beats(rec.ppg, rec.fs, fiducial="upslope")), metrics(ecg_beats)
        pk = metrics(detect_beats(rec.ppg, rec.fs))                  # same subjects, peak fiducial, for comparison
        if p is None or e is None or pk is None:
            no_metrics.append(s)
            continue
        monitor = np.nanmean(rec.ref_hr_bpm)                       # independent check of the ECG side
        if abs(e.mean_hr_bpm - monitor) > 3.0 or abs(p.mean_hr_bpm - monitor) > 3.0:
            skipped.append((s, e.mean_hr_bpm, p.mean_hr_bpm, monitor))
            continue
        rows.append((s, e.rmssd_ms, p.rmssd_ms, e.sdnn_ms, p.sdnn_ms, e.mean_hr_bpm, p.mean_hr_bpm, pk.rmssd_ms, pk.sdnn_ms))
    a = np.array(rows)
    if args.dump:
        args.dump.write_text(json.dumps({
            "subjects": a[:, 0].astype(int).tolist(),
            "rmssd_ecg": a[:, 1].round(2).tolist(), "rmssd_ppg": a[:, 2].round(2).tolist(),
            "rmssd_ppg_peak": a[:, 7].round(2).tolist(),
            "sdnn_ecg": a[:, 3].round(2).tolist(), "sdnn_ppg": a[:, 4].round(2).tolist(),
            "skipped": [{"subject": x[0], "ecg_mean_hr": round(float(x[1]), 2), "ppg_mean_hr": round(float(x[2]), 2),
                         "monitor_mean_hr": round(float(x[3]), 2)} for x in skipped],
            "no_metrics": no_metrics}))
    print(f"{len(a)} subjects kept; {len(skipped)} skipped because ECG-derived or PPG-derived mean HR is >3 bpm from the "
          f"monitor's ({', '.join(str(x[0]) for x in skipped)}); {len(no_metrics)} with too few valid intervals "
          f"({', '.join(map(str, no_metrics)) or 'none'})\n")
    for s_, e_hr, p_hr, mon in skipped:
        side = "+".join(n for n, v in (("ECG", e_hr), ("PPG", p_hr)) if abs(v - mon) > 3.0)
        print(f"  dropped {s_}: ECG {e_hr:.1f}, PPG {p_hr:.1f}, monitor {mon:.1f} bpm ({side} off)")
    print(f"{'S':>3} {'RMSSD ecg':>10} {'ppg':>7} {'SDNN ecg':>9} {'ppg':>7}")
    for r in a:
        print(f"{int(r[0]):3d} {r[1]:10.1f} {r[2]:7.1f} {r[3]:9.1f} {r[4]:7.1f}")
    for name, i, col in (("RMSSD (ms), peak fiducial", 1, 7), ("RMSSD (ms)", 1, 2), ("SDNN (ms), peak fiducial", 3, 8),
                         ("SDNN (ms)", 3, 4), ("mean HR (bpm)", 5, 6)):
        ref, est = a[:, i], a[:, col]
        err = est - ref
        print(f"\n{name}: Pearson r {np.corrcoef(ref, est)[0, 1]:.3f}, mean abs error {np.abs(err).mean():.2f}, "
              f"bias {err.mean():+.2f}, median relative error {np.median(np.abs(err) / ref):.1%}, "
              f"within 20 %: {np.mean(np.abs(err) / ref <= 0.2):.0%}")


if __name__ == "__main__":
    main()
