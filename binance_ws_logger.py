# encoding: utf-8
"""Real-time BTCUSDT futures data collector using Binance websocket.

This script connects to Binance's futures websocket streams to retrieve
1-minute candlesticks and depth updates for BTCUSDT. It demonstrates a
very simple momentum-based strategy: when the market moves beyond a
specified threshold within a candle, a long or short position is opened.
When an opposite signal appears, the position is closed. Each trade
(entry and exit) is recorded in a CSV file along with the realized PnL.

This example is for educational purposes and omits many production-ready
considerations such as reconnection logic, comprehensive error handling,
and order execution.
"""

import asyncio
import csv
import json
from datetime import datetime
from pathlib import Path

import websockets  # requires the ``websockets`` package


class MomentumStrategy:
    """A toy momentum strategy that reacts to candlestick momentum.

    Depth data is collected for completeness but not actively used in
    the entry/exit logic. This can be extended to incorporate order-flow
    analysis.
    """

    def __init__(self, threshold: float = 0.001, csv_path: str = "trades.csv"):
        self.threshold = threshold
        self.position = None  # 'long' or 'short'
        self.entry_price = None
        self.entry_time = None
        self.csv_path = Path(csv_path)
        # ensure csv has header
        if not self.csv_path.exists():
            with self.csv_path.open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "entry_time",
                    "side",
                    "entry_price",
                    "exit_time",
                    "exit_price",
                    "pnl",
                ])

    def _write_trade(self, side: str, entry: float, exit_: float, entry_t: str, exit_t: str):
        pnl = exit_ - entry if side == "long" else entry - exit_
        with self.csv_path.open("a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([entry_t, side, entry, exit_t, exit_, pnl])

    def on_kline(self, kline: dict):
        price = float(kline["c"])  # close price
        open_price = float(kline["o"])
        time_str = datetime.utcfromtimestamp(kline["T"] / 1000).isoformat()

        if self.position is None:
            # check for momentum breakout
            change = (price - open_price) / open_price
            if change >= self.threshold:
                self.position = "long"
                self.entry_price = price
                self.entry_time = time_str
            elif change <= -self.threshold:
                self.position = "short"
                self.entry_price = price
                self.entry_time = time_str
        else:
            # existing position, look for exit
            change = (price - self.entry_price) / self.entry_price
            if self.position == "long" and change <= -self.threshold:
                self._write_trade(
                    "long", self.entry_price, price, self.entry_time, time_str
                )
                self.position = None
            elif self.position == "short" and change >= self.threshold:
                self._write_trade(
                    "short", self.entry_price, price, self.entry_time, time_str
                )
                self.position = None

    def on_depth(self, depth: dict):
        """Handle order book updates (currently unused)."""
        # Depth updates could be stored or used for advanced order-flow
        # analysis. This placeholder keeps the method for future expansion.
        pass


async def connect_and_run(strategy: MomentumStrategy):
    stream = (
        "wss://fstream.binance.com/stream?streams="
        "btcusdt@kline_1m/btcusdt@depth5@100ms"
    )
    async with websockets.connect(stream) as ws:
        async for message in ws:
            payload = json.loads(message)
            channel = payload.get("stream", "")
            if channel.endswith("kline_1m"):
                strategy.on_kline(payload["data"]["k"])
            elif "depth" in channel:
                strategy.on_depth(payload["data"])


def main():
    strategy = MomentumStrategy(threshold=0.002)
    asyncio.run(connect_and_run(strategy))


if __name__ == "__main__":
    main()
