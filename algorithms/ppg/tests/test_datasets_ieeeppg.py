import numpy as np
import pytest

from caseback_ppg.datasets import ieeeppg


def _ts(n_windows=2, samples=6):
    rng = np.random.default_rng(0)
    lines = ["# comment", "@problem", "@data"]
    for k in range(n_windows):
        dims = [",".join(f"{v:.1f}" for v in rng.normal(size=samples)) for _ in range(5)]
        lines.append(":".join(dims) + f":{60 + k}.5")
    return "\n".join(lines)


def test_parse_ts_shapes_and_labels():
    w = ieeeppg.parse_ts(_ts(3, 6))
    assert w.ppg.shape == (3, 2, 6) and w.acc.shape == (3, 3, 6)
    assert list(w.hr_bpm) == [60.5, 61.5, 62.5]


def test_parse_ts_rejects_wrong_channel_count():
    bad = "@data\n1,2,3:4,5,6:7.0"
    with pytest.raises(ValueError):
        ieeeppg.parse_ts(bad)


@pytest.mark.dataset
@pytest.mark.skipif(not ieeeppg.cached("TEST"), reason="IEEE SPC 2015 test split not downloaded")
def test_cached_split_loads():
    w = ieeeppg.load("TEST", download=False)
    assert w.ppg.shape[1:] == (2, 1000) and 40 < w.hr_bpm.min() and w.hr_bpm.max() < 220


def test_subject_ids_and_stream_rebuild_recordings():
    rng = np.random.default_rng(1)
    hop, n = ieeeppg.HOP, 1000

    def rec(k):                                  # k windows sliding by HOP over a random 5-channel signal
        sig = rng.normal(size=(5, n + hop * (k - 1)))
        return [sig[:, i * hop:i * hop + n] for i in range(k)]
    wins = rec(3) + rec(2)
    x = np.array(wins)
    w = ieeeppg.Windows(ieeeppg.FS, x[:, :2], x[:, 2:], np.arange(5, dtype=float))
    ids = ieeeppg.subject_ids(w)
    assert list(ids) == [0, 0, 0, 1, 1]
    ppg, acc, labels = ieeeppg.stream(w, ids, 0)
    assert ppg.shape == (n + 2 * hop, 2) and acc.shape == (n + 2 * hop, 3)
    assert list(labels) == [0.0, 1.0, 2.0]
    assert np.array_equal(ppg[:n].T, x[0, :2])
