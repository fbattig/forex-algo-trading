# Forex Hybrid Algorithmic Trading System

A transparent, **pure-Python** (no MetaTrader, no MQL5) forex trading system that
combines a rule-based trend-following core with a machine-learning regime filter.
OANDA is the broker of choice (v20 REST API).

## What it does

- Pulls FX data from **OANDA** (if credentials are set), otherwise **Yahoo Finance**,
  otherwise a clearly-labeled **synthetic** generator (so it always runs).
- Runs a **rule-based trend-following strategy** (two options):
  - **Donchian breakout** (default): enter on a 20-day high/low breakout,
    exit on a 10-day low/high breakout, with an initial 2x ATR risk stop.
  - **EMA crossover** (`--strategy ema`): EMA(20)/EMA(50) crossover +
    ADX(14) > 20 trend filter, EMA(200) regime filter, 2x ATR trailing stop.
  - Fixed-fractional risk (1% of equity per trade), spread + slippage modeled.
- Adds an **ML regime filter** (RandomForest) that predicts the forward 3-day
  direction out-of-sample (walk-forward, no lookahead) and gates entries to
  filter out low-quality signals.
- Produces a **rule-based vs hybrid** comparison, Monte Carlo simulation, and
  walk-forward out-of-sample validation, plus equity-curve PNGs in `reports/`.

## Install

```
pip install -r requirements.txt
```

## Run

```
python main.py                    # Donchian breakout, EURUSD + GBPUSD, rule-based + ML
python main.py --strategy ema     # EMA crossover strategy instead
python main.py --pairs EURUSD=X   # single pair
python main.py --no-ml            # rule-based only
python main.py --capital 50000 --risk 0.02
```

## OANDA (broker of choice)

Set credentials via environment variables (PowerShell):

```powershell
$env:OANDA_API_TOKEN = "your-token"
$env:OANDA_ACCOUNT_ID = "101-xxx-xxxx-xxxx"
$env:OANDA_ENV = "practice"   # or "live"
python main.py
```

Or edit `OandaConfig` in `config.py`. When credentials are present the system
uses OANDA historical candles; live order execution methods are implemented in
`broker/oanda.py` (`place_market_order`, `close_position`, etc.) but are not
called during backtesting.

## Project layout

```
broker/        OANDA v20 client
config.py      all tunable parameters
data/          data loading (OANDA -> yfinance -> synthetic)
strategies/    indicators + donchian + ema strategies
backtest/      transparent no-lookahead engine + metrics
ml/            feature engineering + regime filter
risk/          position sizing
analysis/      walk-forward, Monte Carlo, reporting
main.py        CLI entry point
reports/       equity-curve PNGs
```

## Honest note on results

On 2016-2026 daily EURUSD/GBPUSD data, the raw trend-following core is **not
profitable** (that decade was hard for FX trend-following). The ML filter does
meaningfully improve it - e.g. it turns EURUSD from roughly -12.7% to +0.5%.
This is the real, un-curve-fit outcome: the infrastructure and validation are
solid, but a persistent edge still requires strategy research, diversification
across more pairs/timeframes, and months of out-of-sample confirmation before
any live capital.

## Paper trading (live on OANDA practice)

The daily mean-reversion strategy can run live on your OANDA practice account
(demo money - no real risk):

```
python paper_trade.py            # one check-and-act cycle
python paper_trade.py --dry-run  # see what it WOULD do (no orders placed)
python paper_trade.py --loop     # run continuously, act after each daily close
python paper_trade.py --risk-pct 2
```

- Entries are market orders with an attached 2x-ATR stop loss.
- Positions are closed when price reverts to the mean (checked once per day).
- Refuses to trade a LIVE account unless you pass --live.
- All activity is logged to paper_trade.log.
- Tip: schedule `python paper_trade.py` daily (Windows Task Scheduler) shortly
after the New York close, or run --loop in a terminal.

## Important disclaimers

- Backtest results are **not** a guarantee of future performance.
- The synthetic fallback is for pipeline testing only - never treat it as market data.
- Never trade live money until the system passes months of out-of-sample and
  paper-trading validation.