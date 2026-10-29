"""Run the wrist HR pipeline over a recording from firmware/prototype-recorder and compare it with a reference.

    python tools/analyze_recording.py recording.csv
    python tools/analyze_recording.py recording.csv --ref reference.csv --offset-s 0

``recording.csv`` is what the recorder prints over USB serial (lines starting with ``#`` are ignored).
``reference.csv`` has two columns, ``t_s,bpm``, with ``t_s`` counted from the same moment as the recording
(the Fitbit export has wall-clock times: subtract the time you started the recording, or pass ``--offset-s``).

The reported error is only against the reference you give it. A Fitbit is another wrist sensor, not ground truth.
"""

import argparse

import numpy as np

from caseback_ppg import spo2_window, track_wrist_hr


def load(path: str) -> dict[str, np.ndarray]:
    with open(path) as f:
        lines = [ln for ln in f if ln.strip() and not ln.startswith("#")]
    header = lines[0].strip().split(",")
    rows = [ln.strip().split(",") for ln in lines[1:]]
    rows = [r for r in rows if len(r) == len(header)]
    data = np.array(rows, dtype=float)
    return {name: data[:, i] for i, name in enumerate(header)}


def measured_fs(ms: np.ndarray) -> float:
    return (len(ms) - 1) / ((ms[-1] - ms[0]) / 1000.0)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("recording")
    ap.add_argument("--ref", help="CSV with columns t_s,bpm")
    ap.add_argument("--offset-s", type=float, default=0.0, help="added to the reference times")
    args = ap.parse_args()

    d = load(args.recording)
    fs = measured_fs(d["ms"])
    n = len(d["ms"])
    print(f"{n} samples, {n / fs:.1f} s, measured rate {fs:.2f} Hz")
    if abs(fs - 100.0) > 5.0:
        print("warning: the rate is far from the nominal 100 Hz, samples may have been lost")

    ppg = d["green"][:, None]
    acc = np.stack([d["ax_g"], d["ay_g"], d["az_g"]], axis=1)
    updates = track_wrist_hr(ppg, acc, fs)
    t = np.array([u.t_end_s for u in updates])
    bpm = np.array([u.bpm for u in updates])
    conf = np.array([u.confidence for u in updates])
    print(f"{len(updates)} heart-rate estimates, median {np.median(bpm):.1f} bpm" if len(updates) else "no estimates")

    win = int(20 * fs)
    spo2 = [spo2_window(d["red"][i:i + win], d["ir"][i:i + win], fs).spo2
            for i in range(0, n - win + 1, win)]
    ok = [v for v in spo2 if not np.isnan(v)]
    print(f"SpO2 (not validated, trend only): {len(ok)} of {len(spo2)} 20 s windows gave a value")

    print(f"NTC ADC: mean {d['ntc_adc12'].mean():.0f} of 4095 (needs the 10 kOhm divider to mean anything)")

    if args.ref and len(updates):
        ref = np.loadtxt(args.ref, delimiter=",", skiprows=1)
        t_ref, bpm_ref = ref[:, 0] + args.offset_s, ref[:, 1]
        idx = np.searchsorted(t_ref, t)
        idx = np.clip(idx, 1, len(t_ref) - 1)
        nearer = np.where(np.abs(t_ref[idx - 1] - t) <= np.abs(t_ref[idx] - t), idx - 1, idx)
        near = np.abs(t_ref[nearer] - t) <= 5.0
        err = np.abs(bpm[near] - bpm_ref[nearer][near])
        if err.size:
            print(f"vs reference: MAE {err.mean():.2f} bpm over {err.size} windows "
                  f"(median {np.median(err):.2f}, worst {err.max():.1f})")
        else:
            print("no estimate has a reference value within 5 s: check the time offset")


if __name__ == "__main__":
    main()
