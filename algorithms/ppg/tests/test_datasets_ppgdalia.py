import numpy as np
import pytest

from caseback_ppg.datasets import ppgdalia


def _ts(chunks):
    """Windows of 8 s (512 BVP / 256 acc samples) sliding by 2 s over each recording in ``chunks`` (window counts)."""
    rng = np.random.default_rng(0)
    lines = ["@data"]
    lab = 60.0
    for k in chunks:
        bvp = rng.normal(size=512 + 128 * (k - 1))
        acc = rng.normal(size=(3, 256 + 64 * (k - 1)))
        for i in range(k):
            dims = [",".join(f"{v:.3f}" for v in bvp[128 * i:128 * i + 512])]
            dims += [",".join(f"{v:.3f}" for v in a[64 * i:64 * i + 256]) for a in acc]
            lines.append(":".join(dims) + f":{lab}")
            lab += 1
    return "\n".join(lines)


def test_parse_and_recording_ids_and_stream():
    w = ppgdalia.parse_ts(_ts([3, 2]))
    assert w.bvp.shape == (5, 512) and w.acc.shape == (5, 3, 256)
    ids = ppgdalia.recording_ids(w)
    assert list(ids) == [0, 0, 0, 1, 1]
    bvp, acc, labels = ppgdalia.stream(w, ids, 0)
    assert bvp.shape == (512 + 2 * 128, 1) and acc.shape == (512 + 2 * 128, 3)
    assert list(labels) == [60.0, 61.0, 62.0]


def test_parse_rejects_wrong_channel_count():
    with pytest.raises(ValueError):
        ppgdalia.parse_ts("@data\n1,2:3,4:5")


@pytest.mark.dataset
@pytest.mark.skipif(not ppgdalia.cached("TEST"), reason="PPG-DaLiA test split not downloaded")
def test_cached_split_loads():
    w = ppgdalia.load("TEST", download=False)
    assert w.bvp.shape[1] == 512 and 30 < w.hr_bpm.min() and w.hr_bpm.max() < 230
