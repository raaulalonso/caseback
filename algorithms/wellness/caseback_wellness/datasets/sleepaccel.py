"""Walch et al. 2019: Apple Watch motion and heart rate with polysomnography sleep labels, PhysioNet, ODC-By 1.0.

31 people, one night each (University of Michigan, 2017-2019). Acceleration about 50 Hz (g), heart rate every few
seconds (bpm, with spurious values), labels every 30 s: 0 wake, 1 N1, 2 N2, 3 N3, 4 N4, 5 REM, -1 unscored.
All times are seconds since the start of the polysomnography. https://physionet.org/content/sleep-accel/1.0.0/
Download the zip to ``~/.cache/caseback/sleepaccel`` (read from the zip or from the extracted folder ``z``).
"""

import io
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

DEFAULT_CACHE = Path.home() / ".cache" / "caseback" / "sleepaccel"
ZIP_NAME = "sleep-accel.zip"
_ROOT = "motion-and-heart-rate-from-a-wrist-worn-wearable-and-labeled-sleep-from-polysomnography-1.0.0"
EPOCH_S = 30

# PSG stage -> 0 wake, 1 light (N1+N2), 2 deep (N3+N4), 3 REM; unscored -> -1
STAGE_MAP = {0: 0, 1: 1, 2: 1, 3: 2, 4: 2, 5: 3, -1: -1}


@dataclass(frozen=True)
class Night:
    subject: str
    acc_t: np.ndarray      # (n,) seconds
    acc: np.ndarray        # (n, 3) g
    hr_t: np.ndarray       # (m,) seconds
    hr: np.ndarray         # (m,) bpm
    stages: np.ndarray     # (epochs,) 0 wake, 1 light, 2 deep, 3 REM, -1 unscored


def _folder(cache: Path) -> Path:
    return cache / "z" / _ROOT


def _read(cache: Path, member: str) -> bytes:
    f = _folder(cache) / member
    if f.exists():
        return f.read_bytes()
    with zipfile.ZipFile(cache / ZIP_NAME) as z:
        return z.read(f"{_ROOT}/{member}")


def available(cache: Path = DEFAULT_CACHE) -> bool:
    return (cache / ZIP_NAME).exists() or _folder(cache).exists()


def subjects(cache: Path = DEFAULT_CACHE) -> list[str]:
    if _folder(cache).exists():
        return sorted(p.name.split("_")[0] for p in (_folder(cache) / "labels").glob("*_labeled_sleep.txt"))
    with zipfile.ZipFile(cache / ZIP_NAME) as z:
        return sorted(n.split("/")[-1].split("_")[0] for n in z.namelist()
                      if "/labels/" in n and n.endswith("_labeled_sleep.txt"))


def load(subject: str, cache: Path = DEFAULT_CACHE) -> Night:
    m = np.loadtxt(io.BytesIO(_read(cache, f"motion/{subject}_acceleration.txt")))
    h = np.loadtxt(io.BytesIO(_read(cache, f"heart_rate/{subject}_heartrate.txt")), delimiter=",")
    lab = np.loadtxt(io.BytesIO(_read(cache, f"labels/{subject}_labeled_sleep.txt")))
    stages = np.array([STAGE_MAP[int(s)] for s in lab[:, 1]])
    return Night(subject, m[:, 0], m[:, 1:4], h[:, 0], h[:, 1], stages)
