"""Day mode is a short burst every few minutes, not a continuous stream. What does the tracker give in a burst?

    python tools/eval_bursts.py [--dataset ieee|dalia|both] [--lengths 30,45,60,90,120] [--period 300]

**TRAIN only** (IEEE SPC 2015 TRAIN, PPG-DaLiA TRAIN; there is deliberately no option for TEST). Every recording is
cut into bursts of L seconds that start every ``--period`` seconds (default: 300 s for DaLiA, back to back for the
5-minute IEEE recordings). Each burst is processed from a cold start: a fresh ``MotionCompensatedHR`` (plain or
learned; empty canceller and HMM) or, for the peak pipeline, band-pass, beat detection and median IBI over the burst
alone. An estimate needs an 8 s window, so a burst of L seconds yields (L - 8) / 2 + 1 of them at best.

Reported per method and burst length: estimates per burst, bursts with at least one confident estimate (tracker
confidence >= 0.5; the peak pipeline has no confidence, so any non-NaN value counts), time to the first confident
estimate, MAE of all estimates, MAE of the confident ones, MAE of the last estimate of the burst, MAE of the most
confident estimate of the burst (the "one number per burst" the day mode would report), each next to the same
windows of the continuous run over the whole recording. Also the MAE by position in the 30 s burst.

TRAIN numbers are optimistic (both models saw these recordings), so the absolute level says little; the difference
between burst and continuous on the same windows is what this measures. Not a claim about Caseback hardware.
"""

import argparse
from dataclasses import dataclass

import numpy as np
from joblib import Parallel, delayed

from caseback_ppg import MotionCompensatedHR, detect_beats, heart_rate_series
from caseback_ppg.datasets import ieeeppg, ppgdalia
from caseback_ppg.scorer import CandidateScorer

CONF = 0.5
WIN, HOP = 8.0, 2.0
METHODS = ("peaks", "plain", "learned")


@dataclass
class Burst:
    method: str
    length: int
    est: np.ndarray        # estimate per window (NaN = no reading)
    conf: np.ndarray       # confidence (1 for the peak pipeline when there is a reading)
    ref: np.ndarray
    cont: np.ndarray       # continuous-run estimate on the same windows
    cont_conf: np.ndarray


def _run(method: str, ppg: np.ndarray, acc: np.ndarray, fs: float, scorer) -> tuple[np.ndarray, np.ndarray]:
    if method == "peaks":
        _, bpm = heart_rate_series(detect_beats(ppg[:, 0], fs), fs, window_s=WIN, step_s=HOP, duration_s=len(ppg) / fs)
        return bpm, np.where(np.isnan(bpm), 0.0, 1.0)
    est = MotionCompensatedHR(fs) if method == "plain" else MotionCompensatedHR.learned(fs, scorer=scorer)
    ups = est.push(ppg, acc)
    return np.array([u.bpm for u in ups]), np.array([u.confidence for u in ups])


def process(ppg, acc, labels, fs, lengths, period, back_to_back):
    scorer = CandidateScorer.load()
    n_win = len(labels)
    out: list[Burst] = []
    for method in METHODS:
        cont, cont_conf = _run(method, ppg, acc, fs, scorer)
        m = min(len(cont), n_win)
        for length in lengths:
            per = length if back_to_back else period
            n_est = int((length - WIN) // HOP) + 1
            for s0 in np.arange(0, len(ppg) / fs - length + 1e-9, per):
                i0 = int(round(s0 / HOP))
                if i0 + n_est > m:
                    break
                a, b = int(round(s0 * fs)), int(round((s0 + length) * fs))
                est, conf = _run(method, ppg[a:b], acc[a:b], fs, scorer)
                if len(est) < n_est:
                    est, conf = np.pad(est, (0, n_est - len(est)), constant_values=np.nan), np.pad(conf, (0, n_est - len(conf)))
                sl = slice(i0, i0 + n_est)
                out.append(Burst(method, length, est[:n_est], conf[:n_est], labels[sl], cont[sl], cont_conf[sl]))
    return out


def recordings(dataset: str):
    if dataset == "ieee":
        w = ieeeppg.load("TRAIN")
        ids = ieeeppg.subject_ids(w)
        return ieeeppg.FS, [ieeeppg.stream(w, ids, s) for s in range(int(ids.max()) + 1)]
    w = ppgdalia.load("TRAIN")
    ids = ppgdalia.recording_ids(w)
    return ppgdalia.FS, [ppgdalia.stream(w, ids, s) for s in range(int(ids.max()) + 1)]


def _mae(est, ref):
    ok = ~np.isnan(est)
    return float(np.mean(np.abs(est[ok] - ref[ok]))) if ok.any() else float("nan")


def summarise(bursts: list[Burst], method: str, length: int) -> dict:
    bs = [b for b in bursts if b.method == method and b.length == length]
    e = np.concatenate([b.est for b in bs]); r = np.concatenate([b.ref for b in bs])
    c = np.concatenate([b.conf for b in bs]); ce = np.concatenate([b.cont for b in bs])
    cc = np.concatenate([b.cont_conf for b in bs])
    hi = (c >= CONF) & ~np.isnan(e)
    chi = (cc >= CONF) & ~np.isnan(ce)
    first, last_e, last_c, last_r, best_e, best_c, best_r = [], [], [], [], [], [], []
    for b in bs:
        ok = (b.conf >= CONF) & ~np.isnan(b.est)
        first.append(WIN + HOP * int(np.argmax(ok)) if ok.any() else np.nan)
        last_e.append(b.est[-1]); last_c.append(b.cont[-1]); last_r.append(b.ref[-1])
        if ok.any():
            j = int(np.argmax(np.where(ok, b.conf, -1)))
            best_e.append(b.est[j]); best_c.append(b.cont[j]); best_r.append(b.ref[j])
    first = np.array(first)
    return {
        "bursts": len(bs), "est_per_burst": float(np.mean([np.sum(~np.isnan(b.est)) for b in bs])),
        "burst_with_confident": float(np.mean(~np.isnan(first))),
        "t_first_confident": float(np.nanmedian(first)) if (~np.isnan(first)).any() else float("nan"),
        "mae_all": _mae(e, r), "mae_all_cont": _mae(ce, r),
        "mae_conf": _mae(np.where(hi, e, np.nan), r), "cover": float(hi.mean()),
        "mae_conf_cont": _mae(np.where(chi, ce, np.nan), r), "cover_cont": float(chi.mean()),
        "mae_last": _mae(np.array(last_e), np.array(last_r)), "mae_last_cont": _mae(np.array(last_c), np.array(last_r)),
        "mae_best": _mae(np.array(best_e), np.array(best_r)) if best_e else float("nan"),
        "mae_best_cont": _mae(np.array(best_c), np.array(best_r)) if best_e else float("nan"),
        "by_position": [_mae(np.array([b.est[k] for b in bs]), np.array([b.ref[k] for b in bs])) for k in range(len(bs[0].est))],
        "by_position_cont": [_mae(np.array([b.cont[k] for b in bs]), np.array([b.ref[k] for b in bs])) for k in range(len(bs[0].est))],
    }


def report(name: str, bursts: list[Burst], lengths: list[int], tol: float) -> None:
    print(f"\n== {name}: {len(bursts) // (len(METHODS) * len(lengths))} bursts per method and length ==")
    hdr = (f"{'method':8s} {'L s':>4s} {'n est':>5s} {'burst w/ conf':>13s} {'t 1st conf':>10s} | {'MAE all':>7s} {'(cont)':>7s} | "
           f"{'MAE conf':>8s} {'cover':>6s} {'(cont)':>7s} | {'last':>6s} {'(cont)':>7s} | {'best':>6s} {'(cont)':>7s}")
    print(hdr)
    for m in METHODS:
        for L in lengths:
            s = summarise(bursts, m, L)
            print(f"{m:8s} {L:4d} {s['est_per_burst']:5.1f} {s['burst_with_confident']:13.1%} {s['t_first_confident']:9.0f}s | "
                  f"{s['mae_all']:7.2f} {s['mae_all_cont']:7.2f} | {s['mae_conf']:8.2f} {s['cover']:6.1%} {s['mae_conf_cont']:7.2f} | "
                  f"{s['mae_last']:6.2f} {s['mae_last_cont']:7.2f} | {s['mae_best']:6.2f} {s['mae_best_cont']:7.2f}")
    print("\nMAE by estimate position in the shortest burst (t = 8, 10, ... s), burst vs continuous on the same windows")
    L = lengths[0]
    for m in METHODS:
        s = summarise(bursts, m, L)
        print(f"  {m:8s} burst " + " ".join(f"{v:5.1f}" for v in s["by_position"]))
        print(f"  {'':8s} cont  " + " ".join(f"{v:5.1f}" for v in s["by_position_cont"]))
    print(f"\nShortest burst whose last estimate is within {tol:g} bpm of the continuous one on the same windows "
          f"and where >= 90 % of bursts hold a confident estimate:")
    for m in METHODS:
        ok = [L for L in lengths if (s := summarise(bursts, m, L))["burst_with_confident"] >= 0.9
              and s["mae_last"] - s["mae_last_cont"] <= tol]
        print(f"  {m:8s} {min(ok) if ok else 'none of ' + str(lengths)}")


def main() -> None:
    ap = argparse.ArgumentParser(description="TRAIN splits only.")
    ap.add_argument("--dataset", default="both", choices=("ieee", "dalia", "both"))
    ap.add_argument("--lengths", default="30,45,60,90,120", help="burst lengths in seconds, shortest first")
    ap.add_argument("--period", type=float, default=300.0, help="burst start interval in s (DaLiA; IEEE runs back to back)")
    ap.add_argument("--tolerance-bpm", type=float, default=1.0)
    args = ap.parse_args()
    lengths = [int(x) for x in args.lengths.split(",")]
    for ds in (("ieee", "dalia") if args.dataset == "both" else (args.dataset,)):
        fs, recs = recordings(ds)
        res = Parallel(n_jobs=-1)(delayed(process)(p, a, y, fs, lengths, args.period, ds == "ieee") for p, a, y in recs)
        bursts = [b for r in res for b in r]
        report(f"{'IEEE SPC 2015' if ds == 'ieee' else 'PPG-DaLiA'} TRAIN, {len(recs)} recordings, "
               f"{'back to back' if ds == 'ieee' else f'one burst every {args.period:g} s'}", bursts, lengths, args.tolerance_bpm)


if __name__ == "__main__":
    main()
