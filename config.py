"""Central configuration for the Forex hybrid algorithmic trading system.

All tunable parameters live here so you can experiment without touching the
core logic. OANDA credentials can be set via environment variables or a .env
file (OANDA_API_KEY / OANDA_API_TOKEN, OANDA_ACCOUNT_ID, OANDA_API_URL,
OANDA_ENV).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class DataConfig:
    # Yahoo Finance symbols (fallback when OANDA is not configured)
    pairs: List[str] = field(default_factory=lambda: ["EURUSD=X", "GBPUSD=X"])
    # OANDA instrument names (broker of choice)
    oanda_instruments: List[str] = field(default_factory=lambda: ["EUR_USD", "GBP_USD"])
    interval: str = "1d"           # yfinance interval
    oanda_granularity: str = "D"   # OANDA granularity (D = daily)
    start: str = "2016-01-01"
    end: str | None = None


@dataclass
class StrategyConfig:
    # EMA trend-following params
    ema_fast: int = 20
    ema_slow: int = 50
    ema_trend: int = 200
    adx_period: int = 14
    adx_threshold: float = 20.0
    # shared ATR / stop params
    atr_period: int = 14
    atr_stop_mult: float = 2.0
    trail_enabled: bool = True


@dataclass
class DonchianConfig:
    entry_window: int = 20   # breakout above N-day high / below N-day low
    exit_window: int = 10    # exit breakout on M-day low / high


@dataclass
class MeanReversionConfig:
    lookback: int = 20        # rolling mean/std window
    num_std: float = 2.0      # entry threshold in standard deviations


@dataclass
class RiskConfig:
    initial_capital: float = 100_000.0
    risk_per_trade: float = 0.01   # 1% of equity per trade
    spread_pips: float = 0.8       # round-trip cost model
    slippage_pips: float = 0.5
    max_positions: int = 1


@dataclass
class MLConfig:
    enabled: bool = True
    model: str = "random_forest"   # "random_forest" | "gradient_boosting"
    train_window: int = 750        # bars of training history (rolling)
    refit_every: int = 50          # refit the model every N bars (walk-forward)
    prob_threshold: float = 0.50   # min confidence to take a trade (0.5 = direction agreement)
    horizon: int = 3               # forward horizon (bars) the ML predicts
    features: List[str] = field(default_factory=lambda: [
        "ret_1", "ret_5", "ret_10", "ret_20",
        "vol_20", "atr_ratio", "adx", "rsi_14",
        "ema_dist_200", "ema_spread", "mom_10",
    ])


@dataclass
class OandaConfig:
    api_token: str = ""
    account_id: str = ""
    api_url: str = ""              # optional custom base URL (e.g. from .env)
    environment: str = "practice"  # "practice" | "live"

    @property
    def configured(self) -> bool:
        return bool(self.api_token)


@dataclass
class Config:
    data: DataConfig = field(default_factory=DataConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    donchian: DonchianConfig = field(default_factory=DonchianConfig)
    mean_reversion: MeanReversionConfig = field(default_factory=MeanReversionConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    ml: MLConfig = field(default_factory=MLConfig)
    oanda: OandaConfig = field(default_factory=OandaConfig)


def _parse_env_file(path: str) -> dict:
    """Parse a simple KEY=VALUE .env file (no interpolation)."""
    out = {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    out[key] = value
    except OSError:
        pass
    return out


def load_config(env_file: str | None = None) -> Config:
    """Build a Config. OANDA credentials are read from (in order of precedence):
    1. process environment variables
    2. a .env file (project directory, or env_file if given)
    """
    cfg = Config()

    if env_file is None:
        candidates = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
            os.path.join(os.getcwd(), ".env"),
        ]
    else:
        candidates = [env_file]

    dotenv = {}
    for c in candidates:
        dotenv = _parse_env_file(c)
        if dotenv:
            break

    def pick(*names):
        for n in names:
            if os.environ.get(n):
                return os.environ[n]
        for n in names:
            if dotenv.get(n):
                return dotenv[n]
        return ""

    cfg.oanda.api_token = pick("OANDA_API_TOKEN", "OANDA_API_KEY")
    cfg.oanda.account_id = pick("OANDA_ACCOUNT_ID")
    cfg.oanda.api_url = pick("OANDA_API_URL")
    env = pick("OANDA_ENV")
    cfg.oanda.environment = env if env in ("practice", "live") else "practice"
    return cfg