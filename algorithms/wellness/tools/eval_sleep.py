"""Sleep staging on Walch et al. 2019 (31 nights, polysomnography labels) with subject-independent cross-validation.

    python tools/eval_sleep.py [--folds 8] [--nested] [--save-model] [--dump out.json]

Each night is predicted by a model trained on other people's nights only (transition matrix and class prior
included). Stages: wake / light (N1+N2) / deep (N3+N4) / REM. Epochs the PSG left unscored are ignored, and so are
epochs inside an accelerometer gap longer than 60 s (no motion data: they are not trained on, not scored, and the
smoother bridges them).

The smoother is one (strength, prior power) pair chosen on these out-of-fold predictions among six pairs, and the
feature set was iterated on the same 31 nights, so the headline is selected on the folds it is reported on.
``--nested`` measures how much of that the six-pair choice explains: for each outer fold the pair is chosen on
inner cross-validation of the other nights only and applied to the outer fold. It does not cover the feature
iteration. ``--save-model`` fits on all 31 nights and writes caseback_wellness/models/sleep.json.
"""

import argparse
import json
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import GroupKFold

from caseback_ppg.trees import MulticlassEnsemble
from caseback_wellness import sleep
from caseback_wellness.datasets import sleepaccel

PARAMS = dict(n_estimators=200, max_depth=3, learning_rate=0.05, subsample=0.7, min_samples_leaf=30, random_state=0)
NAMES = ("wake", "light", "deep", "REM")


def kappa(y, p, k):
    cm = np.zeros((k, k))
    np.add.at(cm, (y, p), 1)
    po = np.trace(cm) / cm.sum()
    pe = (cm.sum(0) * cm.sum(1)).sum() / cm.sum() ** 2
    return (po - pe) / (1 - pe)


def report(title, y, p, k=4):
    print(f"\n{title}")
    print(f"  accuracy {np.mean(y == p):.1%}   Cohen kappa {kappa(y, p, k):.3f}")
    for c in range(k):
        m = y == c
        if m.any():
            pr = np.mean(y[p == c] == c) if (p == c).any() else float("nan")
            print(f"    {NAMES[c] if k == 4 else ('wake', 'NREM', 'REM')[c]:6s} recall {np.mean(p[m] == c):6.1%}  precision {pr:6.1%}  (n={m.sum()})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", type=int, default=8)
    ap.add_argument("--save-model", action="store_true")
    ap.add_argument("--nested", action="store_true", help="also choose the smoother inside each outer fold")
    ap.add_argument("--dump", type=Path, help="write the hypnogram of the median-accuracy night as JSON, for the PDF figures")
    args = ap.parse_args()

    subs = sleepaccel.subjects()
    Xs, ys, vs = [], [], []
    for s in subs:
        n = sleepaccel.load(s)
        X, names = sleep.night_features(n)
        Xs.append(X); ys.append(n.stages); vs.append(sleep.epoch_coverage(n.acc_t, n.acc, len(n.stages)) >= 0.5)
    n_ep = sum(len(y) for y in ys)
    print(f"{len(subs)} nights, {n_ep} epochs of 30 s ({n_ep / 120:.0f} h), {sum((y < 0).sum() for y in ys)} unscored ignored, "
          f"{sum((~v).sum() for v in vs)} more without motion data (accelerometer gap > 60 s; nights with any: "
          f"{sum(bool((~v).any()) for v in vs)}, worst {min(v.mean() for v in vs):.0%} covered)")

    def fit(idx, cols):
        lab = np.concatenate([ys[i] for i in idx]); X = np.vstack([Xs[i] for i in idx])[:, cols]
        ok = (lab >= 0) & np.concatenate([vs[i] for i in idx])
        m = GradientBoostingClassifier(**PARAMS).fit(X[ok], lab[ok])
        return MulticlassEnsemble.from_sklearn(m), sleep.transition_matrix([ys[i] for i in idx]), np.bincount(lab[ok], minlength=4) / ok.sum()

    def cv(cols, subset=None, n_folds=args.folds, seed=0):
        subset = list(range(len(subs))) if subset is None else list(subset)
        folds = np.array_split(np.random.default_rng(seed).permutation(subset), n_folds)

        def run(te):
            clf, T, prior = fit(sorted(set(subset) - set(te)), cols)
            return {int(i): (clf.predict_proba(Xs[i][:, cols]), T, prior) for i in te}
        out = {}
        for d in Parallel(n_jobs=-1)(delayed(run)(f) for f in folds):
            out.update(d)
        return out

    all_cols = list(range(len(names)))
    variants = {"full": all_cols,
                "motion only (no heart rate)": [i for i, n in enumerate(names) if not n.startswith("hr")],
                "no time-since-start": [i for i, n in enumerate(names) if n != "hours"]}
    results = {}
    for name, cols in variants.items():
        results[name] = cv(cols)
        print(f"cv done: {name}", flush=True)

    def evaluate(res, strength, power, idx=None):
        return {i: (sleep.smooth_stages(res[i][0], res[i][1], res[i][2], strength, power, vs[i]) if strength else res[i][0]).argmax(axis=1)
                for i in (range(len(subs)) if idx is None else idx)}

    def pooled(P, covered=True):
        keep = [i for i in P]
        m = [(ys[i] >= 0) & (vs[i] if covered else True) for i in keep]
        return np.concatenate([ys[i][k] for i, k in zip(keep, m)]), np.concatenate([P[i][k] for i, k in zip(keep, m)])

    full = results["full"]
    grid = [(s_, g_) for g_ in (0.25, 0.5, 0.75) for s_ in (0.5, 1.0)]
    best = max(grid, key=lambda sg: kappa(*pooled(evaluate(full, *sg)), 4))
    print(f"\nsmoother (strength, prior power) chosen on out-of-fold kappa among {len(grid)} pairs: {best}")
    if args.nested:
        for name in ("full", "no time-since-start"):
            cols = variants[name]
            folds = np.array_split(np.random.default_rng(0).permutation(len(subs)), args.folds)
            P, picks = {}, []
            for f, te in enumerate(folds):
                tr = sorted(set(range(len(subs))) - set(te))
                inner = cv(cols, tr, n_folds=args.folds - 1, seed=100 + f)
                pick = max(grid, key=lambda sg: kappa(*pooled(evaluate(inner, *sg, idx=tr)), 4))
                clf, T, prior = fit(tr, cols)
                P.update(evaluate({int(i): (clf.predict_proba(Xs[i][:, cols]), T, prior) for i in te}, *pick, idx=[int(i) for i in te]))
                picks.append(pick)
            y_n, p_n = pooled(P)
            y_o, p_o = pooled(evaluate(results[name], *best))
            print(f"[{name}] nested selection of the smoother: kappa {kappa(y_n, p_n, 4):.3f}, accuracy {np.mean(y_n == p_n):.1%} "
                  f"(selected on all folds: {kappa(y_o, p_o, 4):.3f}, {np.mean(y_o == p_o):.1%}); "
                  f"pair chosen per outer fold: {', '.join(str(p) for p in picks)}", flush=True)

    if args.dump:
        Pf = evaluate(full, *best)
        acc = np.array([np.mean(Pf[i][ys[i] >= 0] == ys[i][ys[i] >= 0]) for i in range(len(subs))])
        k = int(np.argmin(np.abs(acc - np.median(acc))))
        args.dump.write_text(json.dumps({"night_index": k, "accuracy": float(acc[k]), "median_accuracy": float(np.median(acc)),
                                         "epoch_s": sleep.EPOCH_S, "true": ys[k].tolist(), "predicted": Pf[k].tolist()}))
    for name, res in results.items():
        P = evaluate(res, *best)
        y, p = pooled(P)
        report(f"[{name}] 4 stages, smoothed", y, p)
        if name == "full":
            ya, pa = pooled(P, covered=False)
            print(f"  (all {len(ya)} scored epochs, including those without motion data: accuracy {np.mean(ya == pa):.1%}, "
                  f"kappa {kappa(ya, pa, 4):.3f})")
            report("[full] 4 stages, unsmoothed", *pooled(evaluate(res, 0, 0)))
            y3 = np.where(y == 3, 2, np.where(y > 0, 1, 0))
            p3 = np.where(p == 3, 2, np.where(p > 0, 1, 0))
            report("[full] 3 stages wake/NREM/REM", y3, p3, 3)
            ys_, ps_ = (y > 0).astype(int), (p > 0).astype(int)
            print(f"\n[full] sleep vs wake: sensitivity (sleep found) {np.mean(ps_[ys_ == 1]):.1%}, "
                  f"specificity (wake found) {np.mean(1 - ps_[ys_ == 0]):.1%}, kappa {kappa(ys_, ps_, 2):.3f}")
            # night level
            tst_t, tst_p, rem_t, rem_p, deep_t, deep_p, eff_t, eff_p = [], [], [], [], [], [], [], []
            for i, yn in enumerate(ys):
                ok = (yn >= 0) & vs[i]
                a, b = sleep.summarise(yn[ok]), sleep.summarise(P[i][ok])
                tst_t.append(a.total_sleep_min); tst_p.append(b.total_sleep_min)
                rem_t.append(a.rem_min); rem_p.append(b.rem_min); deep_t.append(a.deep_min); deep_p.append(b.deep_min)
                eff_t.append(a.efficiency); eff_p.append(b.efficiency)
            for label, t, q in (("total sleep (min)", tst_t, tst_p), ("REM (min)", rem_t, rem_p), ("deep (min)", deep_t, deep_p)):
                t, q = np.array(t), np.array(q)
                print(f"  night level {label:18s} mean abs error {np.abs(q - t).mean():5.1f}  bias {np.mean(q - t):+6.1f}  "
                      f"(mean true {t.mean():.0f})")
            t, q = np.array(eff_t), np.array(eff_p)
            print(f"  night level efficiency        mean abs error {np.abs(q - t).mean():5.3f}  bias {np.mean(q - t):+6.3f}")
    base = np.bincount(pooled({i: ys[i] for i in range(len(subs))})[0], minlength=4)
    print(f"\nreference: always predicting light sleep gives {base[1] / base.sum():.1%} accuracy and kappa 0; "
          f"always 'asleep' gives {(1 - base[0] / base.sum()):.1%} sleep/wake accuracy.")

    if args.save_model:
        clf, T, prior = fit(list(range(len(subs))), all_cols)
        out = Path(sleep.__file__).with_name("models") / "sleep.json"; out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps({"classifier": json.loads(clf.to_json()), "trans": T.tolist(), "prior": prior.tolist(),
                                   "strength": best[0], "prior_power": best[1], "features": names}))
        print(f"\nsaved {out} ({out.stat().st_size / 1e3:.0f} kB)")


if __name__ == "__main__":
    main()
