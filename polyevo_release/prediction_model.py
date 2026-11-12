"""Original annealing prediction functions."""
import math
from collections import defaultdict
import numpy as np
from sklearn.linear_model import Ridge

def response(row, outcome):
    return row["published_DSC_crystallinity_pct"] if outcome == "raw_pct" else row["harmonized_net_fusion_enthalpy_J_g"]

def feature_matrix(train, test, mode, form="linear", within=False):
    train_cols = []
    test_cols = []
    if within:
        grades = sorted({r["grade"] for r in train})
        if len(grades) > 1:
            for grade in grades:
                train_cols.append([float(r["grade"] == grade) for r in train])
                test_cols.append([float(r["grade"] == grade) for r in test])
        if all(r["published_baseline_pct"] is not None for r in train + test):
            vals = np.array([r["published_baseline_pct"] for r in train])
            if vals.std() > 1e-10:
                mean, scale = vals.mean(), vals.std()
                train_cols.append([(r["published_baseline_pct"] - mean) / scale for r in train])
                test_cols.append([(r["published_baseline_pct"] - mean) / scale for r in test])
    if mode == "B":
        transforms = [("temp", lambda r: r["anneal_temp_C"]),
                      ("duration_log", lambda r: math.log1p(r["anneal_duration_min"]))]
        for name, transform in transforms:
            vals = np.array([transform(r) for r in train], dtype=float)
            if vals.std() < 1e-10:
                continue
            mean, scale = vals.mean(), vals.std()
            train_cols.append([(transform(r) - mean) / scale for r in train])
            test_cols.append([(transform(r) - mean) / scale for r in test])
            if form == "quadratic" and name == "temp":
                train_cols.append([((transform(r) - mean) / scale) ** 2 for r in train])
                test_cols.append([((transform(r) - mean) / scale) ** 2 for r in test])
    train_x = np.column_stack(train_cols) if train_cols else np.zeros((len(train), 0))
    test_x = np.column_stack(test_cols) if test_cols else np.zeros((len(test), 0))
    return train_x, test_x

def predict(train, test, outcome, mode, form="linear", within=False, equal_papers=False):
    x_train, x_test = feature_matrix(train, test, mode, form, within)
    y = np.array([response(r, outcome) for r in train])
    if equal_papers:
        counts = defaultdict(int)
        for r in train:
            counts[r["paper_id"]] += 1
        n_papers = len(counts)
        weights = np.array([len(train) / (n_papers * counts[r["paper_id"]]) for r in train])
    else:
        weights = np.ones(len(train))
    if x_train.shape[1] == 0:
        return np.full(len(test), np.average(y, weights=weights))
    model = Ridge(alpha=1.0, fit_intercept=True)
    model.fit(x_train, y, sample_weight=weights)
    return model.predict(x_test)
