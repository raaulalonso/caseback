"""PPG-DaLiA (Reiss et al., MDPI Sensors 2019), Monash/Zenodo release: wrist BVP + accelerometer while 15 people
do everyday activities (sitting, stairs, table football, cycling, driving, lunch, walking, working), with the
heart rate of a simultaneous chest ECG. CC-BY-4.0, https://zenodo.org/records/3902728

Empatica E4 on the wrist: BVP at 64 Hz, accelerometer at 32 Hz. The release is cut into 8 s windows that slide by
2 s. The loader recovers the recordings and rebuilds each as a continuous stream, with the accelerometer
linearly upsampled to 64 Hz so both signals share one clock.
"""

import shutil
import ssl
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import certifi
import numpy as np

BASE_URL = "https://zenodo.org/api/records/3902728/files"
DEFAULT_CACHE = Path.home() / ".cache" / "caseback" / "ppgdalia"
FS = 64.0
SPLITS = ("TRAIN", "TEST")
_WIN, _HOP = 512, 128          # BVP samples per window / per 2 s shift


@dataclass(frozen=True)
class Windows:
    bvp: np.ndarray       # (n, 512)
    acc: np.ndarray       # (n, 3, 256) at 32 Hz
    hr_bpm: np.ndarray    # (n,)


def parse_ts(text: str) -> Windows:
    lines = text.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.strip().lower() == "@data") + 1
    bvp, acc, hr = [], [], []
    for ln in lines[start:]:
        if not ln.strip():
            continue
        *dims, label = ln.split(":")
        if len(dims) != 4:
            raise ValueError(f"expected 4 channels, got {len(dims)}")
        bvp.append(np.array(dims[0].split(","), dtype=np.float32))
        acc.append(np.stack([np.array(d.split(","), dtype=np.float32) for d in dims[1:]]))
        hr.append(float(label))
    return Windows(np.array(bvp), np.array(acc), np.array(hr))


def cached(split: str = "TEST", cache: Path = DEFAULT_CACHE) -> bool:
    return (cache / f"PPGDalia_{split}.ts").exists()


def load(split: str = "TEST", cache: Path = DEFAULT_CACHE, *, download: bool = True) -> Windows:
    if split not in SPLITS:
        raise ValueError(f"split must be one of {SPLITS}")
    path = cache / f"PPGDalia_{split}.ts"
    if not path.exists():
        if not download:
            raise FileNotFoundError(f"{path} not cached")
        cache.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        ctx = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(f"{BASE_URL}/PPGDalia_{split}.ts/content", context=ctx, timeout=600) as r, \
                tmp.open("wb") as f:
            shutil.copyfileobj(r, f)
        tmp.rename(path)
    return parse_ts(path.read_text())


def recording_ids(w: Windows) -> np.ndarray:
    """Recording index per window: a window that does not continue its predecessor starts a new recording."""
    new = [not (np.array_equal(w.bvp[i, _HOP:], w.bvp[i + 1, :-_HOP])
                and np.array_equal(w.acc[i, :, _HOP // 2:], w.acc[i + 1, :, :-_HOP // 2]))
           for i in range(len(w.bvp) - 1)]
    return np.concatenate([[0], np.cumsum(new)])


def stream(w: Windows, ids: np.ndarray, recording: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Continuous (bvp (n, 1), acc (n, 3) at 64 Hz, hr_label per window) for one recording."""
    idx = np.flatnonzero(ids == recording)
    bvp = np.concatenate([w.bvp[idx[0]]] + [w.bvp[i][-_HOP:] for i in idx[1:]]).astype(float)
    acc = np.concatenate([w.acc[idx[0]]] + [w.acc[i][:, -_HOP // 2:] for i in idx[1:]], axis=1).astype(float)
    t32 = np.arange(acc.shape[1]) / 32.0
    t64 = np.arange(len(bvp)) / FS
    acc64 = np.stack([np.interp(t64, t32, a) for a in acc], axis=1)
    return bvp[:, None], acc64, w.hr_bpm[idx]
