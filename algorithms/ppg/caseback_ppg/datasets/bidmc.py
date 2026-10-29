"""BIDMC PPG and Respiration dataset (PhysioNet, ODC-By 1.0).

53 ICU recordings of 8 min: finger PPG at 125 Hz plus 1 Hz monitor numerics. Heart rate
reference is the ECG-derived ``HR`` numeric. This is resting finger PPG, so it validates
the beat/HR pipeline but says nothing about wrist motion artifact.

https://physionet.org/content/bidmc/1.0.0/
"""

import csv
import shutil
import ssl
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import certifi
import numpy as np

BASE_URL = "https://physionet.org/files/bidmc/1.0.0/bidmc_csv"
FS = 125.0
N_SUBJECTS = 53
DEFAULT_CACHE = Path.home() / ".cache" / "caseback" / "bidmc"


@dataclass(frozen=True)
class Record:
    subject: int
    fs: float
    ppg: np.ndarray
    ref_t_s: np.ndarray
    ref_hr_bpm: np.ndarray


def _fetch(name: str, cache: Path) -> Path:
    path = cache / name
    if not path.exists():
        cache.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        # certifi: python.org builds on macOS ship without root certificates.
        ctx = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(f"{BASE_URL}/{name}", context=ctx, timeout=60) as r, tmp.open("wb") as f:
            shutil.copyfileobj(r, f)
        tmp.rename(path)
    return path


def _columns(path: Path) -> dict[str, np.ndarray]:
    with path.open(newline="") as f:
        reader = csv.reader(f)
        header = [h.strip() for h in next(reader)]
        data = np.array(list(reader), dtype=float)
    return {h: data[:, i] for i, h in enumerate(header)}


def cached(subject: int, cache: Path = DEFAULT_CACHE) -> bool:
    return all((cache / f"bidmc_{subject:02d}_{k}.csv").exists() for k in ("Signals", "Numerics"))


def load(subject: int, cache: Path = DEFAULT_CACHE, *, download: bool = True) -> Record:
    if not 1 <= subject <= N_SUBJECTS:
        raise ValueError(f"subject must be 1..{N_SUBJECTS}")
    if not download and not cached(subject, cache):
        raise FileNotFoundError(f"BIDMC subject {subject} not in {cache}")
    sig = _columns(_fetch(f"bidmc_{subject:02d}_Signals.csv", cache))
    num = _columns(_fetch(f"bidmc_{subject:02d}_Numerics.csv", cache))
    return Record(subject, FS, sig["PLETH"], num["Time [s]"], num["HR"])
