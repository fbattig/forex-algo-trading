"""ML fade-quality filter for mean reversion.

Predicts, out-of-sample (walk-forward, no lookahead), whether fading toward the
rolling mean would revert within a horizon. Used to gate mean-reversion entries:
only take the fade when the model is confident it will revert. This filters out
fades made during strong trends (where mean reversion loses).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier

from .features import build_fade_target, build_features


class FadeFilter:
    def __init__(self, cfg):
        self.cfg = cfg

    def _make_model(self):
        if self.cfg.fade_ml.model == "gradient_boosting":
            return GradientBoostingClassifier(
                n_estimators=150, max_depth=3, learning_rate=0.05, random_state=42)
        return RandomForestClassifier(
            n_estimators=150, max_depth=4, min_samples_leaf=25,
            class_weight="balanced", random_state=42)

    def generate_probabilities(self, df: pd.DataFrame) -> pd.Series:
        cfg = self.cfg
        feats = build_features(df)[cfg.fade_ml.features]
        target = build_fade_target(df, lookback=cfg.mean_reversion.lookback,
                                   horizon=cfg.fade_ml.horizon)
        proba = pd.Series(np.nan, index=df.index)

        feats_valid = feats.notna().all(axis=1).to_numpy()
        train_valid = feats_valid & target.notna().to_numpy()
        train_pos = np.where(train_valid)[0]
        if len(train_pos) == 0:
            return proba

        window = cfg.fade_ml.train_window
        first_ok = int(train_pos[0])
        start_i = first_ok + window
        if start_i >= len(df) - 1:
            return proba

        model = None
        last_fit = -10 ** 9
        for i in range(start_i, len(df)):
            if not feats_valid[i]:
                continue
            if model is None or (i - last_fit) >= cfg.fade_ml.refit_every:
                X = feats.iloc[i - window:i]
                y = target.iloc[i - window:i]
                mask = X.notna().all(axis=1).to_numpy() & y.notna().to_numpy()
                X, y = X[mask], y[mask]
                if len(y) < 100:
                    continue
                model = self._make_model()
                model.fit(X, y)
                last_fit = i
            proba.iloc[i] = float(model.predict_proba(feats.iloc[i:i + 1])[0][1])
        return proba


def apply_fade_filter(signal: pd.Series, proba: pd.Series, threshold: float) -> pd.Series:
    """Gate fade entries: only keep signals where P(revert) >= threshold."""
    s = signal.copy()
    s[(s != 0) & (proba < threshold)] = 0
    s[proba.isna()] = 0
    return s