# Takes flexible last 20 - 5 minutes candles --> earliest alert at 9:50
# ✅ Strategy C — Bullish, Dynamic Lookback (Live-Only)
from tvDatafeed import TvDatafeed, Interval
from datetime import datetime, time, timedelta
import time as tm
import requests

# ================= TELEGRAM =================
BOT_TOKEN = "YOUR_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg}, timeout=5)

# ================= CONFIG =================
NIFTY_100 = [
    "ADANIENT","ADANIPORTS","AMBUJACEM","APOLLOHOSP","ASIANPAINT",
    "AUROPHARMA","AXISBANK","BAJAJ-AUTO","BAJAJFINANCE","BAJAJFINSV",
    "BANDHANBNK","BANKBARODA","BERGEPAINT","BHARATFORG","BHARTIARTL",
    "BPCL","BRITANNIA","CANBK","CHOLAFIN","CIPLA","COALINDIA",
    "DABUR","DIVISLAB","DRREDDY","EICHERMOT","GAIL","GRASIM",
    "HCLTECH","HDFCBANK","HDFCLIFE","HEROMOTOCO","HINDALCO",
    "HINDUNILVR","ICICIBANK","INDUSINDBK","INFY","ITC","JSWSTEEL",
    "KOTAKBANK","LT","M&M","MARUTI","NTPC","ONGC","POWERGRID",
    "RELIANCE","SBIN","SUNPHARMA","TATAMOTORS","TATASTEEL",
    "TECHM","TITAN","ULTRACEMCO","UPL","WIPRO"
]

VOLUME_MULTIPLIER = 2.2
SCAN_INTERVAL_SECONDS = 60
COOLDOWN_HOURS = 2

# ---- Optional absolute volume filter (disabled) ----
# MIN_ABSOLUTE_VOLUME = 200000

MARKET_START = time(9, 20)
MARKET_END   = time(15, 5)

tv = TvDatafeed()  # nologin

last_alert_time = {}  # symbol -> datetime

# ================= HELPERS =================
def normalize(df):
    df = df.reset_index()
    df.rename(columns={
        "datetime":"Datetime",
        "open":"Open","high":"High","low":"Low",
        "close":"Close","volume":"Volume"
    }, inplace=True)
    return df

def is_bullish(c):
    body = c["Close"] - c["Open"]
    rng = c["High"] - c["Low"]
    return body > 0 and rng > 0 and body >= 0.4 * rng

# ================= SCAN =================
def scan_once():
    now = datetime.now()

    # ---- Market hours only ----
    if not (MARKET_START <= now.time() <= MARKET_END):
        return

    for symbol in NIFTY_100:
        try:
            df = tv.get_hist(symbol, "NSE", Interval.in_5_minute, 50)
        except Exception:
            continue

        if df is None or len(df) < 10:
            continue

        df = normalize(df)

        # ---- Same-day only & exclude 9:15–9:20 candle ----
        df = df[
            (df["Datetime"].dt.date == now.date()) &
            (df["Datetime"].dt.time >= time(9, 20))
        ]

        if len(df) < 6:   # need at least 5 prior candles + current
            continue

        last = df.iloc[-1]
        candle_time = last["Datetime"]

        # ---- Dynamic lookback (min 5, cap 20) ----
        lookback = min(len(df) - 1, 20)
        if lookback < 5:
            continue

        avg_volume = df["Volume"].iloc[-(lookback+1):-1].mean()
        if avg_volume == 0:
            continue

        current_volume = last["Volume"]
        vol_mult = current_volume / avg_volume

        # ---- Optional absolute volume filter (OFF) ----
        # if current_volume < MIN_ABSOLUTE_VOLUME:
        #     continue

        # ---- Bullish + volume spike ----
        if vol_mult < VOLUME_MULTIPLIER:
            continue
        if not is_bullish(last):
            continue

        # ---- Live cooldown ----
        if symbol in last_alert_time:
            if candle_time <= last_alert_time[symbol] + timedelta(hours=COOLDOWN_HOURS):
                continue

        last_alert_time[symbol] = candle_time

        msg = (
            f"🔥 BULLISH VOLUME SPIKE\n"
            f"Stock : {symbol}\n"
            f"Time  : {candle_time.strftime('%H:%M')}\n"
            f"Volume: {int(current_volume)}\n"
            f"Spike : {vol_mult:.2f}× avg\n"
            f"Lookback candles: {lookback}"
        )

        print(msg)
        send_telegram(msg)

# ================= MAIN LOOP =================
print("🟢 Strategy C running (Bullish, Dynamic Lookback, Live-Only)")

while True:
    scan_once()
    tm.sleep(SCAN_INTERVAL_SECONDS)
