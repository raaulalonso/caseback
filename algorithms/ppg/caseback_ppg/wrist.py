"""Heart rate from wrist PPG during motion, using the accelerometer. Causal and streaming.

Pipeline, per PPG channel:

1. causal band-pass 0.4-4 Hz on PPG and on the three accelerometer axes;
2. NLMS adaptive canceller: the part of the PPG that is linearly predictable from the last ``taps``
   accelerometer samples (motion artifact) is subtracted;
3. every ``hop_s`` seconds, a Hann-windowed spectrum of the last ``window_s`` seconds of residual;
4. channel spectra are normalised and averaged, then fused over time by an HMM forward filter on a 1 bpm
   grid (Laplace transition, so the estimate follows the pulse instead of jumping to motion peaks).

Only past samples are used, so the same code can run live on the phone. There is no look-ahead, and
the first estimate appears after ``window_s`` seconds.

The plain version (``MotionCompensatedHR(fs)``) was tuned on the IEEE SPC 2015 TRAIN split only. The recommended one,
:meth:`MotionCompensatedHR.learned`, replaces the raw spectrum with a learned per-candidate score (``scorer.py``).
"""

from dataclasses import dataclass

import numpy as np
from scipy.signal import butter, sosfilt, sosfiltfilt

_NFFT = 8192


@dataclass(frozen=True)
class HRUpdate:
    t_end_s: float        # time of the last sample of the window this estimate uses
    bpm: float
    confidence: float     # posterior mass within +-3 bpm of the estimate, 0..1


@dataclass(frozen=True)
class WindowSpectra:
    """Spectra of one window on the bpm grid, each normalised to a maximum of 1: PPG after motion cancellation
    (mean over channels), PPG before cancellation, and accelerometer (mean over the three axes)."""
    grid: np.ndarray
    cancelled: np.ndarray
    raw: np.ndarray
    acc: np.ndarray
    acc_std: float       # std of the accelerometer magnitude in the window, in the input units


class MotionCompensatedHR:
    """Streaming wrist heart-rate estimator. Feed samples with :meth:`push`.

    ``hr_range`` is the tracker's grid of allowed heart rates (default 40-220 bpm). A resting or sleeping heart rate
    below 40 bpm is clipped to 40. Lowering the floor to 30 was tried on TRAIN only (``tools/eval_hr_floor.py``): no
    change on IEEE, but +0.21 bpm (learned) and +0.62 bpm (plain) MAE on PPG-DaLiA, more than the 0.1 bpm allowed, and
    no TRAIN label is below 41.9 bpm to gain from it, so the default stays at 40. The peak pipeline (``ibi.py``)
    accepts intervals down to 30 bpm.
    """

    def __init__(self, fs: float = 125.0, *, window_s: float = 8.0, hop_s: float = 2.0, taps: int = 48,
                 mu: float = 0.02, sigma_bpm: float = 4.0, power: float = 1.0, floor: float = 1e-3,
                 band: tuple[float, float] = (0.4, 4.0), hr_range: tuple[float, float] = (40.0, 220.0),
                 jump: float = 0.0, scorer=None, on_spectrum=None):
        self.fs, self.taps, self.mu, self.power, self.floor = fs, taps, mu, power, floor
        self.win, self.hop = int(round(window_s * fs)), int(round(hop_s * fs))
        self.grid = np.arange(hr_range[0], hr_range[1] + 1.0)
        d = np.abs(self.grid[:, None] - self.grid[None, :])
        k = np.exp(-d / sigma_bpm)
        k = k / k.sum(axis=0, keepdims=True)
        # ``jump``: probability mass spread uniformly, so the tracker can recover from a wrong lock
        self._trans = (1.0 - jump) * k + jump / len(self.grid)
        self._scorer, self._on_spectrum = scorer, on_spectrum
        self._sos = butter(3, band, btype="bandpass", fs=fs, output="sos")
        self._fbpm = np.fft.rfftfreq(_NFFT, 1 / fs) * 60.0
        self._hann = np.hanning(self.win)
        self.reset()

    @classmethod
    def learned(cls, fs: float = 125.0, **kw) -> "MotionCompensatedHR":
        """Default configuration: learned candidate scorer, canceller spanning 0.384 s, HMM scale 2 bpm.

        Trained on IEEE SPC 2015 TRAIN and PPG-DaLiA TRAIN (``tools/train_scorer.py``); needs the PPG channel(s) and a
        3-axis accelerometer at the same rate ``fs``.

        **``fs`` must be >= 32 Hz.** The scorer was trained on 125 Hz (IEEE) and 64 Hz (DaLiA) streams and the canceller,
        band-pass (0.4-4 Hz) and spectra are meant for those rates. Below 32 Hz this is unsupported. 25 Hz was only
        tried by decimating the IEEE TRAIN recordings with an anti-alias filter (``tools/eval_sample_rate.py``, TRAIN
        only, optimistic because the model saw those recordings): a real 25 sps AFE has no such filter, so that figure
        is a lower bound on the loss, and no 25 Hz data from real hardware or from a held-out split exists.
        """
        from .scorer import CandidateScorer
        kw.setdefault("taps", max(4, round(0.384 * fs)))
        kw.setdefault("sigma_bpm", 2.0)
        kw.setdefault("scorer", CandidateScorer.load())
        return cls(fs, **kw)

    def reset(self) -> None:
        self._zi_ppg = self._zi_acc = None
        self._acc_hist = np.zeros((self.taps - 1, 3))
        self._w = None
        self._res = np.zeros((0, 0))
        self._raw = np.zeros((0, 0))
        self._accw = np.zeros((0, 3))
        self._res_start = 0          # absolute index of _res[0]
        self._total = 0
        self._next_end = self.win
        self._post = None

    def push(self, ppg: np.ndarray, acc: np.ndarray) -> list[HRUpdate]:
        """Add ``n`` samples: ``ppg`` shaped (n,) or (n, channels), ``acc`` shaped (n, 3).

        Returns the estimates completed by these samples (zero, one or several).
        """
        ppg = np.asarray(ppg, dtype=float)
        ppg = ppg[:, None] if ppg.ndim == 1 else ppg
        acc = np.asarray(acc, dtype=float)
        if acc.shape != (len(ppg), 3):
            raise ValueError(f"acc must be ({len(ppg)}, 3), got {acc.shape}")
        if self._w is None:
            self._w = np.zeros((ppg.shape[1], self.taps * 3))
            self._zi_ppg = np.zeros((self._sos.shape[0], 2, ppg.shape[1]))
            self._zi_acc = np.zeros((self._sos.shape[0], 2, 3))
            self._res = np.zeros((ppg.shape[1], 0))
            self._raw = np.zeros((ppg.shape[1], 0))
        p, self._zi_ppg = sosfilt(self._sos, ppg, axis=0, zi=self._zi_ppg)
        a, self._zi_acc = sosfilt(self._sos, acc, axis=0, zi=self._zi_acc)
        e = self._cancel(p, a)
        self._res = np.concatenate([self._res, e.T], axis=1)
        self._raw = np.concatenate([self._raw, p.T], axis=1)
        self._accw = np.concatenate([self._accw, a], axis=0)
        self._total += len(ppg)
        out = []
        while self._next_end <= self._total:
            hi = self._next_end - self._res_start
            sl = slice(hi - self.win, hi)
            out.append(self._estimate(self._res[:, sl], self._raw[:, sl], self._accw[sl], self._next_end))
            self._next_end += self.hop
        keep = self._total - self._next_end + self.win        # samples still needed by future windows
        drop = self._res.shape[1] - keep
        if drop > 0:
            self._res, self._raw, self._accw = self._res[:, drop:], self._raw[:, drop:], self._accw[drop:]
            self._res_start += drop
        return out

    def _cancel(self, p: np.ndarray, a: np.ndarray) -> np.ndarray:
        ext = np.concatenate([self._acc_hist, a], axis=0)
        self._acc_hist = ext[-(self.taps - 1):] if self.taps > 1 else ext[:0]
        e = np.empty_like(p)
        w, mu, taps = self._w, self.mu, self.taps
        for n in range(len(p)):
            u = ext[n:n + taps][::-1].ravel()
            err = p[n] - w @ u
            w += (mu * err / (u @ u + 1e-6))[:, None] * u
            e[n] = err
        return e

    def _spectrum(self, window: np.ndarray) -> np.ndarray:
        """Mean over rows of the normalised power spectrum on the bpm grid."""
        spec = np.empty((window.shape[0], len(self.grid)))
        for c, x in enumerate(window):
            x = sosfiltfilt(self._sos, x)
            s = np.abs(np.fft.rfft((x - x.mean()) * self._hann, _NFFT)) ** 2
            s = np.interp(self.grid, self._fbpm, s)
            spec[c] = s / max(s.max(), 1e-12)
        return spec.mean(axis=0)

    def _estimate(self, window: np.ndarray, raw: np.ndarray, acc: np.ndarray, end_sample: int) -> HRUpdate:
        fused = self._spectrum(window)
        if self._scorer is not None or self._on_spectrum is not None:
            a = self._spectrum(acc.T)
            ws = WindowSpectra(self.grid, fused, self._spectrum(raw),
                               a / max(a.max(), 1e-12), float(np.linalg.norm(acc, axis=1).std()))
            if self._on_spectrum is not None:
                self._on_spectrum(ws)
        emission = ((self._scorer(ws) if self._scorer is not None else fused) + self.floor) ** self.power
        post = emission / emission.sum() if self._post is None else emission * (self._trans @ self._post)
        self._post = post / post.sum()
        k = int(self._post.argmax())
        near = np.abs(self.grid - self.grid[k]) <= 3
        return HRUpdate(end_sample / self.fs, float(self.grid[k]), float(self._post[near].sum()))


def track_wrist_hr(ppg: np.ndarray, acc: np.ndarray, fs: float = 125.0, **kw) -> list[HRUpdate]:
    """Run :class:`MotionCompensatedHR` over a whole recording: ppg (n, channels), acc (n, 3)."""
    return MotionCompensatedHR(fs, **kw).push(ppg, acc)
