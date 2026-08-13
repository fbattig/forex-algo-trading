"""Walk-forward (out-of-sample) confirmation of the top mean-reversion candidates."""
import sys
sys.path.insert(0, "C:/cline_forex_hibryd")

from config import load_config
from broker.oanda import OandaClient
from backtest.engine import BacktestEngine
from backtest.metrics import compute_metrics
from screen import fetch_history
from screen_mr import MeanReversion
from analysis.walk_forward import walk_forward

cfg = load_config()
cfg.strategy.trail_enabled = False
client = OandaClient(cfg.oanda)

CANDIDATES = [
    ("AUD_USD", 50, 2.0),
    ("EUR_GBP", 20, 2.0),
    ("EUR_USD", 50, 2.0),
    ("GBP_USD", 20, 2.5),
]

for pair, lb, ns in CANDIDATES:
    df = fetch_history(client, pair, "D", 5)
    sig = MeanReversion(lb, ns).generate_signals(df)
    eng = BacktestEngine(cfg)
    eq = eng.run(sig)
    m = compute_metrics(eq["equity"], eng.trades)
    pf = m["profit_factor"]
    pfs = "inf" if pf == float("inf") else (f"{pf:.2f}" if pf is not None else "n/a")
    print(f"\n{pair} MR lb={lb} sd={ns}  FULL-PERIOD: ret {m['total_return_pct']:7.2f}%  "
          f"dd {m['max_drawdown_pct']:7.2f}%  trades {m['num_trades']:3d}  PF {pfs}")
    print("  Walk-forward (4 out-of-sample chunks, ~15 months each):")
    for (t0, t1, m2) in walk_forward(sig, cfg, n_splits=4):
        pf2 = m2["profit_factor"]
        pfs2 = "inf" if pf2 == float("inf") else (f"{pf2:.2f}" if pf2 is not None else "n/a")
        print(f"    {str(t0.date()):12s} -> {str(t1.date()):12s}  ret {m2['total_return_pct']:7.2f}%  "
              f"dd {m2['max_drawdown_pct']:7.2f}%  trades {m2['num_trades']:3d}  PF {pfs2}")