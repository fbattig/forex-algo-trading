"""Email notifications and trade charts for the paper trader."""
from __future__ import annotations

import os
import smtplib
import ssl
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def make_trade_chart(instrument, df, lookback=20, num_std=2.0, path="reports/last_trade.png",
                     entry_idx=None, entry_price=None, entry_side=None,
                     exit_idx=None, exit_price=None):
    """Render a price chart with the rolling mean, bands, and entry/exit markers."""
    close = df["Close"]
    ma = close.rolling(lookback).mean()
    std = close.rolling(lookback).std()
    upper = ma + num_std * std
    lower = ma - num_std * std

    n = min(120, len(df))
    win = df.iloc[-n:]
    c = win["Close"]
    m = ma.iloc[-n:]
    u = upper.iloc[-n:]
    l = lower.iloc[-n:]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(c.index, c.values, lw=1.5, color="black", label="Close")
    ax.plot(m.index, m.values, lw=1.0, color="blue", alpha=0.7, label=f"Mean ({lookback})")
    ax.plot(u.index, u.values, lw=0.8, color="gray", alpha=0.6, linestyle="--", label=f"±{num_std}σ")
    ax.plot(l.index, l.values, lw=0.8, color="gray", alpha=0.6, linestyle="--")

    if entry_idx is not None and entry_price is not None:
        t = df.index[entry_idx]
        marker = "^" if entry_side == 1 else "v"
        color = "green" if entry_side == 1 else "red"
        label = f"Entry ({'LONG' if entry_side == 1 else 'SHORT'})"
        ax.scatter(t, entry_price, marker=marker, s=140, color=color, zorder=5, label=label)
    if exit_idx is not None and exit_price is not None:
        t = df.index[exit_idx]
        ax.scatter(t, exit_price, marker="x", s=120, color="purple", zorder=5, label="Exit")

    ax.set_title(f"{instrument} - mean reversion trade")
    ax.set_ylabel("Price")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path


def send_email(cfg, subject, body, attachments=None):
    """Send an email via SMTP. Returns (ok, message)."""
    if not cfg.email.configured:
        return False, "email not configured"
    msg = MIMEMultipart()
    msg["From"] = cfg.email.sender
    msg["To"] = cfg.email.recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    for p in (attachments or []):
        with open(p, "rb") as f:
            img = MIMEImage(f.read(), name=os.path.basename(p))
            img.add_header("Content-Disposition", "attachment", filename=os.path.basename(p))
            msg.attach(img)

    context = ssl.create_default_context()
    with smtplib.SMTP(cfg.email.smtp_host, cfg.email.smtp_port, timeout=30) as server:
        server.starttls(context=context)
        server.login(cfg.email.sender, cfg.email.password)
        server.send_message(msg)
    return True, "sent"