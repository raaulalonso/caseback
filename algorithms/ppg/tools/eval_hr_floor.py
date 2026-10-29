"""Does lowering the tracker's lower HR limit from 40 to 30 bpm cost accuracy? **TRAIN only** (no option for TEST).

    python tools/eval_hr_floor.py

Plain and learned ``MotionCompensatedHR`` over IEEE SPC 2015 TRAIN and PPG-DaLiA TRAIN with ``hr_range`` (40, 220) and
(30, 220). TRAIN numbers are optimistic (the models saw these recordings), so only the difference between floors is
meaningful. Also prints how many estimates fall below 40 bpm and how many labels do.
"""

import numpy as np
from joblib import Parallel, delayed

from caseback_ppg import MotionCompensatedHR
from caseback_ppg.datasets import ieeeppg, ppgdalia

FLOORS = (40.0, 30.0)


def run(ppg, acc, fs, floor, learned):
    est = (MotionCompensatedHR.learned if learned else MotionCompensatedHR)(fs, hr_range=(floor, 220.0))
    return np.array([u.bpm for u in est.push(ppg, acc)])


def main() -> None:
    w = ieeeppg.load("TRAIN")
    ids = ieeeppg.subject_ids(w)
    sets = {"IEEE SPC 2015 TRAIN": (ieeeppg.FS, [ieeeppg.stream(w, ids, s) for s in range(int(ids.max()) + 1)])}
    d = ppgdalia.load("TRAIN")
    ids = ppgdalia.recording_ids(d)
    sets["PPG-DaLiA TRAIN"] = (ppgdalia.FS, [ppgdalia.stream(d, ids, s) for s in range(int(ids.max()) + 1)])
    for name, (fs, recs) in sets.items():
        ref = np.concatenate([r[2] for r in recs])
        print(f"\n{name}: {len(recs)} recordings, {len(ref)} windows, labels below 40 bpm: {(ref < 40).sum()}, min {ref.min():.1f}")
        for learned in (False, True):
            res = {}
            for floor in FLOORS:
                out = Parallel(n_jobs=-1)(delayed(run)(p, a, fs, floor, learned) for p, a, _ in recs)
                res[floor] = np.concatenate(out)
                per = [np.abs(o - r[2]).mean() for o, r in zip(out, recs)]
                print(f"  {'learned' if learned else 'plain  '} floor {floor:.0f}: MAE {np.abs(res[floor] - ref).mean():.3f} bpm "
                      f"(per recording {min(per):.2f}-{max(per):.2f}), estimates below 40 bpm: {(res[floor] < 40).sum()}")
            print(f"    change from lowering the floor: {np.abs(res[30.0] - ref).mean() - np.abs(res[40.0] - ref).mean():+.3f} bpm")


if __name__ == "__main__":
    main()
