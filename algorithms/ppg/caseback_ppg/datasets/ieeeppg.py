"""IEEE Signal Processing Cup 2015 wrist-PPG dataset (Zhang et al., TROIKA), Monash/Zenodo version.

Wrist PPG (2 green-LED channels) and 3-axis acceleration recorded during intensive exercise, cut into
8 s windows at 125 Hz, each labelled with the heart rate from a simultaneous chest ECG. This is the
motion-corrupted counterpart of the resting finger PPG in :mod:`caseback_ppg.datasets.bidmc`.

Licence CC-BY-4.0 (Zenodo). Please cite: Z. Zhang, Z. Pi, B. Liu, "TROIKA: A general framework for heart
rate monitoring using wrist-type photoplethysmographic signals during intensive physical exercise",
IEEE Trans. Biomed. Eng. 62(2):522-531, 2015.

https://zenodo.org/records/3902710
"""

import shutil
import ssl
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import certifi
import numpy as np

BASE_URL = "https://zenodo.org/api/records/3902710/files"
FS = 125.0
DEFAULT_CACHE = Path.home() / ".cache" / "caseback" / "ieeeppg"
SPLITS = ("TRAIN", "TEST")


@dataclass(frozen=True)
class Windows:
    fs: float
    ppg: np.ndarray      # (n, 2, samples)
    acc: np.ndarray      # (n, 3, samples)
    hr_bpm: np.ndarray   # (n,)


def parse_ts(text: str) -> Windows:
    """Parse the sktime ``.ts`` text: one window per line, dimensions joined by ':' and the label last."""
    lines = text.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.strip().lower() == "@data") + 1
    series, labels = [], []
    for ln in lines[start:]:
        if not ln.strip():
            continue
        *dims, label = ln.split(":")
        series.append([np.array(d.split(","), dtype=float) for d in dims])
        labels.append(float(label))
    x = np.array(series)
    if x.ndim != 3 or x.shape[1] != 5:
        raise ValueError(f"expected (windows, 5 channels, samples), got {x.shape}")
    return Windows(FS, x[:, :2], x[:, 2:], np.array(labels))


HOP = 250  # windows are 8 s long and start every 2 s


def subject_ids(w: Windows) -> np.ndarray:
    """Recording index per window. The Monash file carries no subject id, but windows of one recording
    overlap by 6 s, so a window that does not continue its predecessor starts a new recording."""
    x = np.concatenate([w.ppg, w.acc], axis=1)
    new = [not np.array_equal(x[i, :, HOP:], x[i + 1, :, :-HOP]) for i in range(len(x) - 1)]
    return np.concatenate([[0], np.cumsum(new)])


def stream(w: Windows, ids: np.ndarray, subject: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Continuous (ppg (n, 2), acc (n, 3), hr_label per window) for one recording, rebuilt from its windows."""
    idx = np.flatnonzero(ids == subject)
    x = np.concatenate([w.ppg, w.acc], axis=1)
    c = np.concatenate([x[idx[0]]] + [x[i][:, -HOP:] for i in idx[1:]], axis=1)
    return c[:2].T, c[2:].T, w.hr_bpm[idx]


def cached(split: str = "TEST", cache: Path = DEFAULT_CACHE) -> bool:
    return (cache / f"IEEEPPG_{split}.ts").exists()


def load(split: str = "TEST", cache: Path = DEFAULT_CACHE, *, download: bool = True) -> Windows:
    if split not in SPLITS:
        raise ValueError(f"split must be one of {SPLITS}")
    path = cache / f"IEEEPPG_{split}.ts"
    if not path.exists():
        if not download:
            raise FileNotFoundError(f"{path} not cached")
        cache.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        ctx = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(f"{BASE_URL}/IEEEPPG_{split}.ts/content", context=ctx, timeout=300) as r, \
                tmp.open("wb") as f:
            shutil.copyfileobj(r, f)
        tmp.rename(path)
    return parse_ts(path.read_text())
