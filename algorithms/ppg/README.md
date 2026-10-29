# caseback-ppg

PPG algorithms for Caseback: band-pass filtering, beat detection, heart rate and time-domain HRV, wrist heart rate with
motion compensation, and SpO2. Pure NumPy/SciPy, no hardware needed. Runs on the phone side of the protocol.

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]" && pytest -v
```

## Pipeline

```text
raw PPG -> bandpass (0.5-8 Hz) -> detect_beats (sub-sample peaks) -> beats_to_ibi -> clean_ibi
                                                                        |-> heart_rate_series  (median IBI, 8 s window)
                                                                        '-> hrv_metrics        (SDNN, RMSSD, pNN50)
```

`clean_ibi` drops impossible or outlier intervals instead of repairing them, and `hrv_metrics`
skips successive-difference pairs that straddle a dropped interval. Windows with no valid
interval return NaN so "no reading" is never confused with a value.

`detect_beats(..., fiducial="upslope")` times each beat at the steepest rise of the pulse instead of its flat peak.

## Wrist heart rate with motion

`MotionCompensatedHR` (`caseback_ppg/wrist.py`) is causal and streaming: causal band-pass 0.4-4 Hz, an NLMS canceller
that subtracts the part of the PPG predictable from the last 0.38 s of the 3-axis accelerometer, a spectrum of the
last 8 s every 2 s, and an HMM forward filter over 40-220 bpm. It outputs `bpm` and `confidence` (posterior mass
within 3 bpm). `MotionCompensatedHR.learned(fs)` adds a learned candidate scorer (`scorer.py`): each spectral peak is
scored as "is this the pulse?" from how it relates to the accelerometer spectrum, to the un-cancelled spectrum and to its
sub/harmonics, by a small gradient-boosted classifier exported as JSON trees (`caseback_ppg/models/scorer.json`,
trained by `tools/train_scorer.py`).

## SpO2

`caseback_ppg/spo2.py` computes the ratio of ratios from red and IR PPG (slope of red AC against IR AC, so noise does not
bias it), gates on perfusion index, red/IR coherence and accelerometer activity (NaN instead of a wrong number) and
converts with a calibration curve. `fit_calibration` fits a curve on paired recordings against a reference oximeter.

## Tools

The public datasets are downloaded by the tools into `~/.cache/caseback/<name>` and are never committed.

| Tool | What it does |
|---|---|
| `tools/eval_bidmc.py`, `tools/eval_hrv_bidmc.py` | Heart rate and HRV against BIDMC (finger PPG at rest) |
| `tools/eval_ieeeppg.py`, `tools/eval_ppgdalia.py` | Wrist heart rate with motion against IEEE SPC 2015 and PPG-DaLiA |
| `tools/eval_bursts.py`, `tools/eval_hr_floor.py`, `tools/eval_sample_rate.py` | Short bursts, the lower heart-rate limit and lower sampling rates |
| `tools/eval_ci.py`, `tools/bootstrap.py` | Bootstrap confidence intervals over recordings or subjects |
| `tools/train_scorer.py` | Trains the candidate scorer |
| `tools/analyze_recording.py` | Runs the wrist pipeline over a CSV from `firmware/prototype-recorder`; with `--ref reference.csv` (columns `t_s,bpm`) it prints the difference against a reference |
