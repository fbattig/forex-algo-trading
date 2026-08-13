"""Console reporting and equity-curve plotting."""
from __future__ import annotations


def _fmt(v, digits=2):
    if v is None:
        return "n/a"
    if isinstance(v, float):
        if v == float("inf"):
            return "inf"
        return f"{v:,.{digits}f}"
    return str(v)


def _pct(v):
    if v is None:
        return "n/a"
    return f"{v:.2f}%"


def print_metrics(m: dict, label: str):
    print(f"\n  ---- {label} ----")
    print(f"  Final equity       : ${m.get('final_equity', 0):,.0f}")
    print(f"  Total return       : {_pct(m.get('total_return_pct'))}")
    print(f"  CAGR               : {_pct(m.get('cagr_pct'))}")
    print(f"  Sharpe (annualized): {_fmt(m.get('sharpe'))}")
    print(f"  Max drawdown       : {_pct(m.get('max_drawdown_pct'))}")
    print(f"  Trades             : {m.get('num_trades')}")
    print(f"  Win rate           : {_pct(m.get('win_rate_pct'))}")
    print(f"  Profit factor      : {_fmt(m.get('profit_factor'))}")
    print(f"  Avg win            : ${_fmt(m.get('avg_win'), 0)}")
    print(f"  Avg loss           : ${_fmt(m.get('avg_loss'), 0)}")
    print(f"  Expectancy/trade   : ${_fmt(m.get('expectancy'))}")


def plot_equity(series, label: str, path: str, benchmark=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(series.index, series.values, lw=1.3, label=label)
    if benchmark is not None:
        ax.plot(benchmark.index, benchmark.values, lw=1.0, alpha=0.7, label="rule-based (no ML)")
    ax.set_title(f"Equity curve - {label}")
    ax.set_ylabel("Equity (USD)")
    ax.set_xlabel("Date")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path