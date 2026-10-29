"""Sleep staging from wrist motion and heart rate, per 30 s epoch, and night summaries.

Stages: 0 wake, 1 light (N1+N2), 2 deep (N3), 3 REM. Features per epoch come from the accelerometer (activity,
jerk, movement bursts, posture change) and from heart rate (cleaned, normalised to the night, smoothed, local
variability and trend), with context from neighbouring epochs and the time since the recording started.
A gradient-boosted classifier gives probabilities; a Markov smoother whose transitions come from labelled nights
turns them into a hypnogram. Meant to run after the night on the whole recording: the features are not causal
(heart rate is normalised with the whole night's median and spread, the "active" threshold is the night's 75th percentile
of activity, the smoother looks both ways), so nothing here works as a live or partial-night estimate. The heart rate in
the validation data is Apple Watch's own processed output, not what Caseback's peak pipeline or wrist tracker produces.

Validated on Walch et al. 2019 only (31 people, Apple Watch, one lab night each): see tools/eval_sleep.py for the
subject-independent numbers. Sleep-window detection (:func:`detect_sleep_window`) and the sleep score are not
validated (no daytime data, no ground truth for a "score"); they are simple documented rules.
"""

import json
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from caseback_ppg.trees import MulticlassEnsemble

EPOCH_S = 30
MODEL_PATH = Path(__file__).with_name("models") / "sleep.json"
STAGE_NAMES = ("wake", "light", "deep", "REM")


def clean_hr(t: np.ndarray, hr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Drop impossible values and spikes (> 20 bpm from the median of the neighbouring +-5 min)."""
    ok = (hr >= 30) & (hr <= 200)
    t, hr = t[ok], hr[ok]
    keep = np.ones(len(hr), bool)
    for i in range(len(hr)):
        lo, hi = np.searchsorted(t, [t[i] - 300, t[i] + 300])
        if hi - lo >= 5 and abs(hr[i] - np.median(hr[lo:hi])) > 20:
            keep[i] = False
    return t[keep], hr[keep]


def _rolling(x: np.ndarray, half: int, fn=np.nanmean) -> np.ndarray:
    p = np.pad(x, (half, half), mode="edge")
    idx = np.arange(len(x))[:, None] + np.arange(2 * half + 1)[None, :]
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)              # all-NaN windows (long gaps) give NaN
        return fn(p[idx], axis=1)


def _since_last(active: np.ndarray, cap: int = 60) -> np.ndarray:
    out = np.full(len(active), cap, float); last = -cap
    for i, a in enumerate(active):
        if a:
            last = i
        out[i] = min(i - last, cap)
    return out


ACC_FS = 25.0            # every accelerometer feature is computed on a uniform 25 Hz grid (the BMI270 idle rate)


MAX_GAP_S = 60.0         # accelerometer gaps longer than this are left missing, not interpolated


def to_uniform_25hz(acc_t: np.ndarray, acc: np.ndarray, n_epochs: int,
                    max_gap_s: float = MAX_GAP_S) -> tuple[np.ndarray, np.ndarray]:
    """Bin-average irregular or faster samples onto a 25 Hz grid over the epochs, so sample-to-sample differences mean
    the same thing whether the sensor ran at 25, 50 or 100 Hz. Empty bins are filled by interpolation only inside gaps
    of at most ``max_gap_s`` seconds (including at the start and end of the recording); longer gaps stay NaN."""
    n = int(n_epochs * EPOCH_S * ACC_FS)
    idx = np.floor(acc_t * ACC_FS).astype(int)
    ok = (idx >= 0) & (idx < n)
    cnt = np.bincount(idx[ok], minlength=n).astype(float)
    out = np.zeros((n, 3))
    for k in range(3):
        out[:, k] = np.bincount(idx[ok], weights=acc[ok, k], minlength=n)
    have = cnt > 0
    if not have.any():
        return np.arange(n) / ACC_FS, np.full((n, 3), np.nan)
    out[have] /= cnt[have, None]
    pos = np.arange(n)
    for k in range(3):
        out[:, k] = np.interp(pos, pos[have], out[have, k])
    prev = np.maximum.accumulate(np.where(have, pos, -1))
    nxt = np.minimum.accumulate(np.where(have, pos, n)[::-1])[::-1]
    out[~have & (nxt - prev - 1 > max_gap_s * ACC_FS)] = np.nan
    return (pos + 0.5) / ACC_FS, out


def epoch_coverage(acc_t, acc, n_epochs: int, max_gap_s: float = MAX_GAP_S) -> np.ndarray:
    """Fraction of each 30 s epoch with usable accelerometer data (not inside a gap longer than ``max_gap_s``).
    Epochs near 0 have no motion information; their features are a fill value, not a reading."""
    t, a = to_uniform_25hz(np.asarray(acc_t, float), np.asarray(acc, float), n_epochs, max_gap_s)
    return (~np.isnan(a[:, 0])).reshape(n_epochs, -1).mean(axis=1)


def epoch_features(acc_t, acc, hr_t, hr, n_epochs: int, max_gap_s: float = MAX_GAP_S) -> tuple[np.ndarray, list[str]]:
    """Feature matrix (n_epochs, F) for epochs [30 e, 30 (e + 1)) seconds after the start of the recording.

    Accelerometer gaps longer than ``max_gap_s`` are not interpolated: epochs without data get NaN motion features
    internally and 0 in the returned matrix (like a missing heart rate); :func:`epoch_coverage` says which they are."""
    acc_t, acc = to_uniform_25hz(np.asarray(acc_t, float), np.asarray(acc, float), n_epochs, max_gap_s)
    edges = np.arange(n_epochs + 1) * EPOCH_S
    b = np.searchsorted(acc_t, edges)
    mag = np.linalg.norm(acc, axis=1)
    d = np.abs(np.diff(acc, axis=0, prepend=acc[:1])).sum(axis=1)
    valid = ~np.isnan(mag)
    act, jerk_max = np.full(n_epochs, np.nan), np.full(n_epochs, np.nan)
    mstd, bursts = np.full(n_epochs, np.nan), np.full(n_epochs, np.nan)
    grav = np.full((n_epochs, 3), np.nan)
    for e in range(n_epochs):
        lo, hi = b[e], b[e + 1]
        if valid[lo:hi].sum() < 5:
            continue
        de = d[lo:hi][~np.isnan(d[lo:hi])]
        act[e] = de.mean(); jerk_max[e] = de.max()
        mstd[e] = mag[lo:hi][valid[lo:hi]].std(); bursts[e] = (de > 0.05).mean()
        grav[e] = acc[lo:hi][valid[lo:hi]].mean(axis=0)
    gn = grav / (np.linalg.norm(grav, axis=1, keepdims=True) + 1e-9)
    tilt = np.r_[0.0, np.degrees(np.arccos(np.clip((gn[1:] * gn[:-1]).sum(axis=1), -1, 1)))]
    tilt[np.isnan(act)] = np.nan

    t_mid = (np.arange(n_epochs) + 0.5) * EPOCH_S
    ht, hv = clean_hr(np.asarray(hr_t, float), np.asarray(hr, float))
    if len(ht) >= 2:
        hr_e = np.interp(t_mid, ht, hv)
        near = np.abs(t_mid[:, None] - ht[None, :]).min(axis=1) if len(ht) < 4000 else \
            np.abs(t_mid - ht[np.clip(np.searchsorted(ht, t_mid), 0, len(ht) - 1)])
    else:
        hr_e, near = np.full(n_epochs, np.nan), np.full(n_epochs, 1e4)
    med = np.nanmedian(hr_e); mad = np.nanmedian(np.abs(hr_e - med)) + 1.0
    hr_z = (hr_e - med) / mad
    feats = {
        "act": act, "jerk_max": jerk_max, "mag_std": mstd, "bursts": bursts, "tilt": tilt,
        "log_act": np.log10(act + 1e-4),
        "hr": hr_e, "hr_z": hr_z, "hr_age": np.minimum(near, 600.0),
        "hr_m5": _rolling(hr_e, 5), "hr_m15": _rolling(hr_e, 15), "hr_sd10": _rolling(hr_e, 10, np.nanstd),
        "hr_slope": _rolling(hr_e, 5) - np.roll(_rolling(hr_e, 5), 10),
        "hr_vs_min": hr_e - np.nanpercentile(hr_e, 10), "hr_rel_local": hr_e - _rolling(hr_e, 30),
        "hours": t_mid / 3600.0,
    }
    for h in (2, 5, 20):
        feats[f"act_m{2 * h + 1}"] = _rolling(act, h)
        feats[f"act_max{2 * h + 1}"] = _rolling(act, h, np.nanmax)
        feats[f"tilt_m{2 * h + 1}"] = _rolling(tilt, h)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        thr = np.nanpercentile(act, 75) if np.isfinite(act).any() else np.inf
    active = act > thr
    feats["since_active"] = _since_last(active)
    feats["until_active"] = _since_last(active[::-1])[::-1]
    names = list(feats)
    return np.nan_to_num(np.column_stack([feats[k] for k in names]), nan=0.0), names


def night_features(night, n_epochs: int | None = None) -> tuple[np.ndarray, list[str]]:
    n = len(night.stages) if n_epochs is None else n_epochs
    return epoch_features(night.acc_t, night.acc, night.hr_t, night.hr, n)


def detect_sleep_window(act: np.ndarray, *, min_minutes: float = 180.0, max_gap_minutes: float = 30.0,
                        still_ratio: float = 3.0, ceiling: float = 0.012,
                        max_hours: float = 14.0) -> tuple[int, int] | None:
    """Main sleep period from per-epoch activity over a day or more (``act`` from :func:`epoch_features`).

    An epoch is "still" when its +-5 min median activity is below both ``still_ratio`` times the recording's 10th
    percentile and the absolute ``ceiling`` (g per 40 ms; asleep in the Walch data: median 0.004, 90th percentile
    0.007; awake: 90th percentile 0.07). Still stretches separated by less than ``max_gap_minutes`` are merged and the
    longest one between ``min_minutes`` and ``max_hours`` long is returned as (first epoch, last epoch inclusive).
    Not validated: the public dataset has no daytime, so this is a documented rule tested on synthetic data only.
    """
    a = np.asarray(act, dtype=float)
    if len(a) < 2 * int(min_minutes * 2):
        return None
    smooth = _rolling(a, 10, np.nanmedian)
    still = smooth < min(still_ratio * max(np.nanpercentile(a, 10), 1e-6), ceiling)
    gap = int(max_gap_minutes * 2)
    runs, start, last = [], None, None
    for i, v in enumerate(still):
        if v:
            if start is None:
                start = i
            elif i - last > gap:
                runs.append((start, last)); start = i
            last = i
    if start is not None:
        runs.append((start, last))
    runs = [r for r in runs if min_minutes * 2 <= (r[1] - r[0] + 1) <= max_hours * 120]
    return max(runs, key=lambda r: r[1] - r[0]) if runs else None


def transition_matrix(stage_sequences: list[np.ndarray], k: int = 4, smooth: float = 1.0) -> np.ndarray:
    T = np.full((k, k), smooth)
    for s in stage_sequences:
        s = s[s >= 0]
        np.add.at(T, (s[:-1], s[1:]), 1)
    return T / T.sum(axis=1, keepdims=True)


def smooth_stages(proba: np.ndarray, trans: np.ndarray, prior: np.ndarray, strength: float = 1.0,
                  prior_power: float = 0.5, valid: np.ndarray | None = None) -> np.ndarray:
    """Forward-backward posterior over stages. ``proba`` is the classifier output, divided by ``prior ** prior_power``
    so the Markov chain does not count the class prior twice (1.0 removes it fully, which over-predicts the rare
    stages by ~30 min a night; 0.5 balances them). ``strength`` < 1 flattens the evidence. Epochs where ``valid`` is
    False (no motion data, see :func:`epoch_coverage`) carry no evidence: the chain bridges them with its transitions."""
    em = (proba / prior[None, :] ** prior_power) ** strength
    if valid is not None:
        em = np.where(np.asarray(valid, bool)[:, None], em, 1.0)
    em /= em.sum(axis=1, keepdims=True)
    n, k = em.shape
    a = np.zeros((n, k)); b = np.ones((n, k))
    a[0] = prior * em[0]; a[0] /= a[0].sum()
    for i in range(1, n):
        a[i] = em[i] * (a[i - 1] @ trans); a[i] /= a[i].sum()
    for i in range(n - 2, -1, -1):
        b[i] = trans @ (em[i + 1] * b[i + 1]); b[i] /= b[i].sum()
    post = a * b
    return post / post.sum(axis=1, keepdims=True)


@dataclass(frozen=True)
class SleepSummary:
    time_in_bed_min: float
    total_sleep_min: float
    efficiency: float
    onset_latency_min: float
    waso_min: float
    light_min: float
    deep_min: float
    rem_min: float


def summarise(stages: np.ndarray) -> SleepSummary:
    """Night summary from a hypnogram (0 wake, 1 light, 2 deep, 3 REM per 30 s epoch)."""
    s = np.asarray(stages)
    m = EPOCH_S / 60.0
    asleep = s > 0
    if not asleep.any():
        return SleepSummary(len(s) * m, 0.0, 0.0, len(s) * m, 0.0, 0.0, 0.0, 0.0)
    first, last = int(np.argmax(asleep)), len(s) - 1 - int(np.argmax(asleep[::-1]))
    tst = asleep.sum() * m
    return SleepSummary(len(s) * m, tst, tst / (len(s) * m), first * m, (~asleep[first:last + 1]).sum() * m,
                        (s == 1).sum() * m, (s == 2).sum() * m, (s == 3).sum() * m)


def sleep_score(sm: SleepSummary, need_min: float = 480.0) -> float:
    """0-100 design score (not validated): 45 % duration vs need, 25 % efficiency, 15 % deep and 15 % REM share
    against 15-20 % and 20-25 % of sleep (full credit at the lower bound)."""
    if sm.total_sleep_min <= 0:
        return 0.0
    dur = min(sm.total_sleep_min / need_min, 1.0)
    eff = min(max((sm.efficiency - 0.6) / 0.3, 0.0), 1.0)
    deep = min((sm.deep_min / sm.total_sleep_min) / 0.15, 1.0)
    rem = min((sm.rem_min / sm.total_sleep_min) / 0.20, 1.0)
    return round(100 * (0.45 * dur + 0.25 * eff + 0.15 * deep + 0.15 * rem), 1)


@dataclass(frozen=True)
class SleepModel:
    classifier: MulticlassEnsemble
    trans: np.ndarray
    prior: np.ndarray
    strength: float = 0.5
    prior_power: float = 0.5

    def stage(self, X: np.ndarray, valid: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
        """(stage per epoch, smoothed probabilities). ``valid`` marks epochs with motion data (``epoch_coverage``);
        the stage of the others is only what the neighbours imply and should not be reported as a measurement."""
        post = smooth_stages(self.classifier.predict_proba(X), self.trans, self.prior, self.strength, self.prior_power,
                             valid)
        return post.argmax(axis=1), post

    @classmethod
    def load(cls, path=None) -> "SleepModel":
        path = path or MODEL_PATH
        d = json.loads(path.read_text())
        return cls(MulticlassEnsemble.from_json(json.dumps(d["classifier"])), np.array(d["trans"]),
                   np.array(d["prior"]), d["strength"], d["prior_power"])
