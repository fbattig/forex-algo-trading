"""ML regime filter.

Predicts next-day up/down probability out-of-sample using a walk-forward
procedure (train on past data only, refit every N bars), then gates the
rule-based entry signals to reduce false signals. This is the 'hybrid' layer.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier

from .features import build_features, build_target


class RegimeFilter:
    def __init__(self, cfg):
        self.cfg = cfg

    def _make_model(self):
        if self.cfg.ml.model == "gradient_boosting":
            return GradientBoostingClassifier(
                n_estimators=150, max_depth=3, learning_rate=0.05, random_state=42)
        return RandomForestClassifier(
            n_estimators=150, max_depth=4, min_samples_leaf=25,
            random_state=42)

    def generate_probabilities(self, df: pd.DataFrame) -> pd.Series:
        cfg = self.cfg
        feats = build_features(df)[cfg.ml.features]
        target = build_target(df, horizon=cfg.ml.horizon)
        proba = pd.Series(np.nan, index=df.index)

        valid = feats.notna().all(axis=1).to_numpy()
        valid_pos = np.where(valid)[0]
        if len(valid_pos) == 0:
            return proba

        window = cfg.ml.train_window
        first_ok = int(valid_pos[0])
        start_i = first_ok + window
        if start_i >= len(df) - 1:
            return proba

        model = None
        last_fit = -10 ** 9
        for i in range(start_i, len(df) - 1):
            if not valid[i]:
                continue
            if model is None or (i - last_fit) >= cfg.ml.refit_every:
                X = feats.iloc[i - window:i]
                y = target.iloc[i - window:i]
                if X.isna().any().any() or y.isna().any():
                    continue
                model = self._make_model()
                model.fit(X, y)
                last_fit = i
            x_i = feats.iloc[i:i + 1]
            if x_i.isna().any().any():
                continue
            proba.iloc[i] = float(model.predict_proba(x_i)[0][1])
        return proba


def apply_filter(signal: pd.Series, proba: pd.Series, threshold: float) -> pd.Series:
    """Gate entries: long requires P(up) >= threshold, short requires P(up) <= 1-threshold."""
    s = signal.copy()
    long_ok = proba >= threshold
    short_ok = proba <= (1.0 - threshold)
    s[(s == 1) & ~long_ok] = 0
    s[(s == -1) & ~short_ok] = 0
    s[proba.isna()] = 0
    return s