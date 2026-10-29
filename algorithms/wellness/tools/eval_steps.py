"""Step counting on OxWalk with subject-independent cross-validation.

    python tools/eval_steps.py [--folds 8] [--save-model] [--dump out.json]

Participants are split into folds; each fold is predicted by a model trained on the other participants only.
Reported against annotated steps (foot video). Three things are compared on the same folds:

* the shipped feature set against the orientation-free one (rotation-invariant features only, see
  ``steps.segment_features``), with the test folds as recorded and with a random 3D rotation applied to every test
  participant (3 seeds; a wrist device can sit in any orientation, OxWalk has one fixed mounting);
* the classic peak counter with the fixed 0.06 g threshold, and the same counter with its threshold and minimum peak
  distance chosen by cross-validation (picked on the training participants of each fold, applied to the test fold),
  so the baseline is not a strawman;
* ``--save-model`` fits ``--save-features`` (default: orientation-free) on all 39 participants and writes caseback_wellness/models/steps.json
  (the shipped model; its accuracy is the cross-validated one, not a fit-on-all one). The 0.5 gate threshold is
  the natural one for a classifier and was not tuned.

Rule for making the orientation-free set the default, fixed before running it: the mean absolute error per participant
may be at most 1.0 percentage points worse than with the per-axis features, on the folds as recorded.
"""

import argparse
import json
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed
from scipy.signal import butter, find_peaks, sosfilt
from scipy.spatial.transform import Rotation
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.model_selection import GroupKFold

from caseback_wellness import steps
from caseback_wellness.datasets import oxwalk

PARAMS = dict(n_estimators=150, max_depth=4, learning_rate=0.08, subsample=0.6, min_samples_leaf=20, random_state=0)
HEIGHTS = (0.01, 0.015, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10, 0.13, 0.17, 0.22, 0.30)     # g
DISTANCES = (5, 7, 9, 12)                                                                        # samples at 25 Hz
FIXED = (0.06, 7)
MARGIN_PP = 1.0
ROTATION_SEEDS = (0, 1, 2)


def peak_baseline(acc: np.ndarray, height: float = FIXED[0], distance: int = FIXED[1]) -> np.ndarray:
    """Classic wrist step counter: band-pass 0.8-3 Hz magnitude, peaks over an amplitude threshold, >= 0.28 s apart."""
    mag = np.linalg.norm(acc, axis=1)
    x = sosfilt(butter(3, [0.8, 3.0], btype="bandpass", fs=25, output="sos"), mag - mag.mean())
    pk, _ = find_peaks(x, height=height, distance=distance)
    n_seg = len(acc) // steps.SEG
    return np.bincount(pk[pk < n_seg * steps.SEG] // steps.SEG, minlength=n_seg).astype(float)


def fit(X: np.ndarray, y: np.ndarray, orientation_free: bool = False) -> steps.StepModel:
    gate = GradientBoostingClassifier(**PARAMS).fit(X, (y > 0).astype(int))
    count = GradientBoostingRegressor(**PARAMS).fit(X[y > 0], y[y > 0])
    return steps.StepModel(steps.TreeEnsemble.from_sklearn(gate), steps.TreeEnsemble.from_sklearn(count),
                           orientation_free=orientation_free)


def per_participant_error(est: np.ndarray, true: np.ndarray) -> np.ndarray:
    return 100 * np.abs(est - true) / true


def summary(name: str, est: np.ndarray, true: np.ndarray) -> None:
    e = per_participant_error(est, true)
    print(f"{name}: mean abs error per participant {e.mean():.1f} %, median {np.median(e):.1f} %, "
          f"pooled total {est.sum():.0f} vs {true.sum():.0f} ({100 * (est.sum() - true.sum()) / true.sum():+.1f} %), "
          f"within 10 %: {np.mean(e <= 10):.0%}, within 20 %: {np.mean(e <= 20):.0%} of participants")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", type=int, default=8)
    ap.add_argument("--save-model", action="store_true")
    ap.add_argument("--save-features", default="orientation-free", choices=("orientation-free", "per-axis"),
                    help="feature set of the model written by --save-model")
    ap.add_argument("--dump", type=Path, help="write per-participant totals as JSON, for the PDF figures")
    args = ap.parse_args()

    accs, ys, gs = [], [], []
    for p in oxwalk.PARTICIPANTS:
        r = oxwalk.load(p)
        accs.append(r.acc); ys.append(steps.segment_labels(r.step_samples, len(r.acc))); gs.append(p)
    y = np.concatenate(ys)
    g = np.concatenate([np.full(len(v), p) for v, p in zip(ys, gs)])
    n_rows = [len(v) for v in ys]

    def features(orientation_free, rot=None):
        out = []
        for i, a in enumerate(accs):
            if rot is not None:
                a = a @ Rotation.random(random_state=1000 * rot + gs[i]).as_matrix().T
            out.append(steps.segment_features(a, orientation_free=orientation_free)[0])
            assert len(out[-1]) == n_rows[i]
        return np.vstack(out)

    X_axis, X_inv = features(False), features(True)
    tests = {"axis": {"orig": X_axis, **{f"rot{s}": features(False, s) for s in ROTATION_SEEDS}},
             "inv": {"orig": X_inv, **{f"rot{s}": features(True, s) for s in ROTATION_SEEDS}}}
    train = {"axis": X_axis, "inv": X_inv}
    print(f"{len(gs)} participants, {len(y)} segments of 2 s ({len(y) * 2 / 3600:.1f} h), {y.sum():.0f} steps")

    def run(tr, te):
        res = {}
        for v in ("axis", "inv"):
            m = fit(train[v][tr], y[tr], v == "inv")
            res[v] = {k: m.predict(X[te]) for k, X in tests[v].items()}
        return te, res
    pred = {v: {k: np.zeros(len(y)) for k in tests[v]} for v in tests}
    folds = list(GroupKFold(args.folds).split(X_axis, y, g))
    for te, res in Parallel(n_jobs=-1)(delayed(run)(tr, te) for tr, te in folds):
        for v in res:
            for k, p_ in res[v].items():
                pred[v][k][te] = p_

    def totals(p_):
        return np.array([p_[g == p].sum() for p in gs])
    true = np.array([y[g == p].sum() for p in gs])

    # classic counter: fixed threshold, and threshold + distance chosen by CV on the training participants
    grid = [(h, d) for h in HEIGHTS for d in DISTANCES]
    base = {hd: np.array([peak_baseline(a, *hd).sum() for a in accs]) for hd in grid}
    gi = {p: i for i, p in enumerate(gs)}
    tuned, chosen = np.zeros(len(gs)), []
    for tr, te in folds:
        tr_p, te_p = sorted({gi[p] for p in g[tr]}), sorted({gi[p] for p in g[te]})
        best = min(grid, key=lambda hd: per_participant_error(base[hd][tr_p], true[tr_p]).mean())
        chosen.append(best)
        tuned[te_p] = base[best][te_p]
    best_in_sample = min(grid, key=lambda hd: per_participant_error(base[hd], true).mean())
    fixed = base[FIXED]

    print(f"\n{'P':>3} {'true':>6} {'axis':>7} {'err%':>7} {'inv':>7} {'err%':>7} {'peaks':>7} {'err%':>7} {'tuned':>7} {'err%':>7}")
    a, b = totals(pred["axis"]["orig"]), totals(pred["inv"]["orig"])
    for i, p in enumerate(gs):
        print(f"{p:3d} {true[i]:6.0f} {a[i]:7.0f} {100 * (a[i] - true[i]) / true[i]:+7.1f} {b[i]:7.0f} "
              f"{100 * (b[i] - true[i]) / true[i]:+7.1f} {fixed[i]:7.0f} {100 * (fixed[i] - true[i]) / true[i]:+7.1f} "
              f"{tuned[i]:7.0f} {100 * (tuned[i] - true[i]) / true[i]:+7.1f}")
    print("\nAs recorded (OxWalk mounting)")
    summary("per-axis features (previously shipped)", a, true)
    summary("orientation-free features", b, true)
    print("\nRandom 3D rotation of every test participant (one rotation per participant, mean over seeds of the same metrics)")
    for v, label in (("axis", "per-axis features"), ("inv", "orientation-free features")):
        errs = [per_participant_error(totals(pred[v][f"rot{s}"]), true) for s in ROTATION_SEEDS]
        pooled = [100 * (totals(pred[v][f"rot{s}"]).sum() - true.sum()) / true.sum() for s in ROTATION_SEEDS]
        print(f"{label}: mean abs error per participant {np.mean([e.mean() for e in errs]):.1f} % "
              f"(seeds {', '.join(f'{e.mean():.1f}' for e in errs)}), pooled total vs annotated {np.mean(pooled):+.1f} %")
    print("\nClassic peak counter")
    summary(f"fixed height {FIXED[0]} g, distance {FIXED[1]}", fixed, true)
    summary("threshold and distance chosen by CV (nested)", tuned, true)
    print(f"  chosen per fold: {', '.join(f'{h:g} g/{d}' for h, d in chosen)}")
    summary(f"best single setting in sample ({best_in_sample[0]:g} g, distance {best_in_sample[1]}; optimistic)",
            base[best_in_sample], true)
    print(f"\nrule: orientation-free is adopted if its mean error is <= per-axis + {MARGIN_PP} pp: "
          f"{per_participant_error(b, true).mean():.1f} vs {per_participant_error(a, true).mean():.1f} -> "
          f"{'adopt' if per_participant_error(b, true).mean() <= per_participant_error(a, true).mean() + MARGIN_PP else 'keep per-axis'}")
    if args.dump:
        args.dump.write_text(json.dumps({
            "participants": list(gs), "true": true.tolist(), "model_axis": a.round(1).tolist(),
            "model_orientation_free": b.round(1).tolist(),
            "model_axis_rotated": [totals(pred["axis"][f"rot{s}"]).round(1).tolist() for s in ROTATION_SEEDS],
            "model_orientation_free_rotated": [totals(pred["inv"][f"rot{s}"]).round(1).tolist() for s in ROTATION_SEEDS],
            "peaks_fixed": fixed.tolist(), "peaks_tuned": tuned.tolist(), "peaks_tuned_settings": [list(c) for c in chosen]}))
    zero = y == 0
    for v, label in (("axis", "per-axis"), ("inv", "orientation-free")):
        p_ = pred[v]["orig"]
        print(f"\n{label}: mean absolute error {np.mean(np.abs(totals(p_) - true) / (y.size / len(true) * 2 / 3600)):.0f} steps/hour per "
              f"participant; steps predicted in segments with no true steps {p_[zero].sum():.0f} "
              f"({100 * p_[zero].sum() / y.sum():.1f} % of all true steps); segment MAE {np.abs(p_ - y).mean():.3f}")
    pk = np.concatenate([peak_baseline(a_, *FIXED) for a_ in accs])
    print(f"peak baseline (fixed): same {pk[zero].sum():.0f} ({100 * pk[zero].sum() / y.sum():.1f} %); "
          f"segment MAE {np.abs(pk - y).mean():.3f}")

    if args.save_model:
        out = Path(steps.MODEL_PATH); out.parent.mkdir(exist_ok=True)
        free = args.save_features == "orientation-free"
        out.write_text(fit(X_inv if free else X_axis, y, free).to_json())
        print(f"\nsaved {out} ({out.stat().st_size / 1e3:.0f} kB), {args.save_features} features")


if __name__ == "__main__":
    main()
