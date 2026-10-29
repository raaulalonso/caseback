"""Runs only when BIDMC record 1 is already cached: `python tools/eval_bidmc.py --subjects 1`."""

import numpy as np
import pytest

from caseback_ppg import detect_beats, heart_rate_series
from caseback_ppg.datasets import bidmc

pytestmark = pytest.mark.dataset


@pytest.mark.skipif(not bidmc.cached(1), reason="BIDMC subject 1 not downloaded")
def test_subject_1_hr_close_to_ecg_reference():
    rec = bidmc.load(1, download=False)
    t, bpm = heart_rate_series(detect_beats(rec.ppg, rec.fs), rec.fs, duration_s=len(rec.ppg) / rec.fs)
    ref = np.interp(t, rec.ref_t_s, rec.ref_hr_bpm)
    ok = ~np.isnan(bpm)
    assert ok.mean() > 0.9
    assert np.mean(np.abs(bpm[ok] - ref[ok])) < 3.0
