"""OxWalk: free-living wrist accelerometry with steps annotated from foot-facing video.

39 adults, about 1 h each, Axivity AX3 on the dominant wrist, 25 Hz and 100 Hz versions, one "1" per step at
heel strike. Small et al., University of Oxford, CC-BY, DOI 10.5287/bodleian:ORQ2abnbR
(https://ora.ox.ac.uk/objects/uuid:19d3cb34-e2b3-4177-91b6-1bad0e0163e7). Download OxWalk_Dec2022.zip and put it in
``~/.cache/caseback/oxwalk`` (or the extracted folder); it is read straight from the zip.
"""

import io
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

DEFAULT_CACHE = Path.home() / ".cache" / "caseback" / "oxwalk"
ZIP_NAME = "OxWalk_Dec2022.zip"
FS = 25.0
PARTICIPANTS = tuple(range(1, 40))


@dataclass(frozen=True)
class Recording:
    participant: int
    fs: float
    acc: np.ndarray          # (n, 3) in g
    step_samples: np.ndarray  # sample indices of annotated heel strikes


def available(cache: Path = DEFAULT_CACHE) -> bool:
    return (cache / ZIP_NAME).exists() or (cache / "ox" / "OxWalk_Dec2022").exists()


def _read(cache: Path, member: str) -> bytes:
    folder = cache / "ox" / "OxWalk_Dec2022"
    if (folder / member).exists():
        return (folder / member).read_bytes()
    with zipfile.ZipFile(cache / ZIP_NAME) as z:
        return z.read(f"OxWalk_Dec2022/{member}")


def load(participant: int, cache: Path = DEFAULT_CACHE) -> Recording:
    raw = _read(cache, f"Wrist_25Hz/P{participant:02d}_wrist25.csv")
    # timestamps are irregular text; the file is resampled to exactly 25 Hz, so the row index is the clock
    data = np.genfromtxt(io.BytesIO(raw), delimiter=",", skip_header=1, usecols=(1, 2, 3, 4))
    return Recording(participant, FS, data[:, :3].astype(float), np.flatnonzero(data[:, 3] > 0.5))
