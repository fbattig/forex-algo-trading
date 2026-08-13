"""OANDA v20 REST client (pure Python, no MetaTrader).

Uses the official OANDA v20 HTTP API via `requests`. Credentials come from
OandaConfig (api_token / account_id / environment).
"""
from __future__ import annotations

import pandas as pd
import requests

from .base import Broker

_BASE_URLS = {
    "practice": "https://api-fxpractice.oanda.com",
    "live": "https://api-fxtrade.oanda.com",
}


def _to_rfc3339(value: str) -> str:
    if "T" not in value:
        return f"{value}T00:00:00Z"
    return value


class OandaClient(Broker):
    def __init__(self, cfg):
        self.cfg = cfg
        self.base = (cfg.api_url or _BASE_URLS.get(cfg.environment, _BASE_URLS["practice"])).rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {cfg.api_token}",
            "Content-Type": "application/json",
        }

    # ---- low-level HTTP helpers ----
    def _request(self, method: str, path: str, params=None, body=None):
        url = self.base + path
        resp = requests.request(method, url, headers=self.headers, params=params, json=body)
        resp.raise_for_status()
        if resp.status_code == 204:
            return {}
        return resp.json()

    def _get(self, path, params=None):
        return self._request("GET", path, params=params)

    def _post(self, path, body=None):
        return self._request("POST", path, body=body)

    def _put(self, path, body=None):
        return self._request("PUT", path, body=body)

    # ---- account ----
    def get_account_id(self) -> str:
        if self.cfg.account_id:
            return self.cfg.account_id
        data = self._get("/v3/accounts")
        return data["accounts"][0]["id"]

    def get_account_summary(self):
        account_id = self.get_account_id()
        return self._get(f"/v3/accounts/{account_id}/summary")

    # ---- market data ----
    def fetch_candles(self, instrument: str, granularity: str = "D", count: int = 5000,
                      start: str | None = None, end: str | None = None) -> pd.DataFrame:
        params = {"granularity": granularity, "count": count, "price": "M"}
        if start:
            params["from"] = _to_rfc3339(start)
        if end:
            params["to"] = _to_rfc3339(end)
        data = self._get(f"/v3/instruments/{instrument}/candles", params)
        rows = []
        for c in data.get("candles", []):
            mid = c["mid"]
            rows.append({
                "Open": float(mid["o"]),
                "High": float(mid["h"]),
                "Low": float(mid["l"]),
                "Close": float(mid["c"]),
                "Volume": int(c.get("volume", 0)),
                "time": pd.to_datetime(c["time"]),
            })
        if not rows:
            return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
        df = pd.DataFrame(rows).set_index("time")
        return df[["Open", "High", "Low", "Close", "Volume"]]

    # ---- trading ----
    def place_market_order(self, instrument: str, units: int):
        account_id = self.get_account_id()
        body = {
            "order": {
                "type": "MARKET",
                "instrument": instrument,
                "units": str(units),
                "timeInForce": "FOK",
                "positionFill": "DEFAULT",
            }
        }
        return self._post(f"/v3/accounts/{account_id}/orders", body)

    def place_market_order_with_sl(self, instrument: str, units: int, stop_price: float):
        """Place a market order with an attached stop loss."""
        account_id = self.get_account_id()
        body = {
            "order": {
                "type": "MARKET",
                "instrument": instrument,
                "units": str(units),
                "timeInForce": "FOK",
                "positionFill": "DEFAULT",
                "stopLossOnFill": {"price": f"{stop_price:.5f}", "timeInForce": "GTC"},
            }
        }
        return self._post(f"/v3/accounts/{account_id}/orders", body)

    def get_open_positions(self):
        account_id = self.get_account_id()
        return self._get(f"/v3/accounts/{account_id}/openPositions")

    def get_open_trades(self):
        account_id = self.get_account_id()
        return self._get(f"/v3/accounts/{account_id}/openTrades")

    def close_position(self, instrument: str):
        account_id = self.get_account_id()
        body = {"longUnits": "ALL", "shortUnits": "ALL"}
        return self._put(f"/v3/accounts/{account_id}/positions/{instrument}/close", body)

    def get_pricing(self, instruments):
        if isinstance(instruments, str):
            instruments = [instruments]
        account_id = self.get_account_id()
        params = {"instruments": ",".join(instruments)}
        return self._get(f"/v3/accounts/{account_id}/pricing", params)