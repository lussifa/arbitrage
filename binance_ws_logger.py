import asyncio
import csv
import json
from datetime import datetime

import aiohttp
import requests

# Proxy configuration
PROXY_HOST = "10.131.182.105"
PROXY_PORT = 8080
PROXY_URI = f"http://{PROXY_HOST}:{PROXY_PORT}"
PROXIES = {
    "http": PROXY_URI,
    "https": PROXY_URI,
}

# Trading pair
SYMBOL = "btcusdt"

# CSV log file
LOG_FILE = "trading_log.csv"

# Simple trade state
target_position = None  # "LONG" or "SHORT"
entry_price = None

def log_event(event_type, data, profit=None):
    """Append an event to the CSV log."""
    with open(LOG_FILE, "a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        timestamp = datetime.utcnow().isoformat()
        writer.writerow([timestamp, event_type, json.dumps(data), profit])

async def fetch_server_time():
    """Fetch server time via REST to verify proxy usage."""
    try:
        resp = requests.get("https://api.binance.com/api/v3/time", proxies=PROXIES, timeout=5)
        resp.raise_for_status()
        log_event("rest_time", resp.json())
    except Exception as exc:
        log_event("rest_error", {"error": str(exc)})

async def handle_kline(session):
    global target_position, entry_price
    url = f"wss://stream.binance.com:9443/ws/{SYMBOL}@kline_1m"
    async with session.ws_connect(url, proxy=PROXY_URI) as ws:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                k = data.get("k", {})
                if k.get("x"):
                    open_p = float(k.get("o"))
                    close_p = float(k.get("c"))
                    log_event("kline", k)
                    if target_position is not None:
                        # close existing position
                        profit = close_p - entry_price if target_position == "LONG" else entry_price - close_p
                        log_event("trade_close", {"position": target_position, "price": close_p}, profit)
                        target_position = None
                        entry_price = None
                    # open new position based on momentum
                    if close_p > open_p:
                        target_position = "LONG"
                        entry_price = close_p
                        log_event("trade_open", {"position": "LONG", "price": close_p})
                    elif close_p < open_p:
                        target_position = "SHORT"
                        entry_price = close_p
                        log_event("trade_open", {"position": "SHORT", "price": close_p})
            elif msg.type == aiohttp.WSMsgType.ERROR:
                break

async def handle_order_book(session):
    url = f"wss://stream.binance.com:9443/ws/{SYMBOL}@depth"
    async with session.ws_connect(url, proxy=PROXY_URI) as ws:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                log_event("order_book", data)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                break

async def main():
    await fetch_server_time()
    async with aiohttp.ClientSession() as session:
        await asyncio.gather(
            handle_kline(session),
            handle_order_book(session),
        )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
