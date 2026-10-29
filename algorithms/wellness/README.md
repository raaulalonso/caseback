# caseback-wellness

Steps, sleep, skin temperature and readiness for Caseback. Pure NumPy/SciPy at inference (scikit-learn only to fit the
models); depends on `caseback-ppg` for the exported tree-ensemble runtime. No hardware needed.

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ../ppg && pip install -e ".[dev,train]" && pytest -v
```

Public datasets are downloaded by hand into `~/.cache/caseback/<name>` and never committed. The models are evaluated
subject-independently: each person is predicted by a model that never saw that person.

| Metric | Module | Method | Data |
|---|---|---|---|
| Steps | `steps.py` | 2 s segments, gate + count boosted trees, 25 Hz | OxWalk |
| Sleep stages | `sleep.py` | epoch features + boosted trees + Markov smoother | Walch et al. 2019 |
| Skin temperature | `skin_temp.py` | NTC conversion, on-wrist mask, nightly deviation | |
| Readiness | `readiness.py` | z-scores against a personal baseline | |

Steps: [OxWalk](https://ora.ox.ac.uk/objects/uuid:19d3cb34-e2b3-4177-91b6-1bad0e0163e7) (CC-BY), dominant-wrist Axivity AX3
at 25 Hz. Features per 2 s segment come from a 4 s context plus +-11 s of bout context: axis-summed spectra, periodicity,
jerk, posture, built to be independent of how the disc is oriented. A classifier decides whether the segment has steps and
a regressor trained on those segments says how many.

```bash
python tools/eval_steps.py --save-model        # grouped cross-validation by participant
python tools/eval_sleep.py                     # sleep staging, subject-independent cross-validation
```

The fitted models are in `caseback_wellness/models/` (`steps.json`, `sleep.json`).
