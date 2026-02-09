# Uses avg daily volume instead of lietral volume to define minimum absolute volume
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
# === NIFTY 50 to 150 ==
NIFTY_150 = [
"ABB","ADANIGREEN","ADANIPOWER","AMBUJACEM",
"AUROPHARMA","BAJAJHLDNG","BANDHANBNK","BERGEPAINT",
"BHEL","BIOCON","BOSCHLTD","CANBK",
"CHOLAFIN","COLPAL","CONCOR","DABUR",
"DLF","GAIL","GODREJCP","HAVELLS",
"HDFCAMC","HINDPETRO","ICICIGI","ICICIPRULI",
"IGL","INDHOTEL","JINDALSTEL","JSWENERGY",
"LTF","MARICO","MOTHERSON","NAUKRI",
"NHPC","NMDC","PAGEIND","PEL",
"PETRONET","PIDILITIND","PNB","RECLTD",
"SAIL","SBICARD","SHRIRAMFIN","SIEMENS",
"SRF","TORNTPHARM","TORNTPOWER","VOLTAS",
"ABCAPITAL","ABFRL","ACC","ALKEM","APLAPOLLO",
"ASHOKLEY","ASTRAL","ATUL","BALKRISIND","BATAINDIA",
"BEL","BHARATFORG","BIRLACORPN","CANFINHOME",
"COROMANDEL","CROMPTON","CUMMINSIND","DEEPAKNTR",
"ESCORTS","EXIDEIND","FEDERALBNK","GLENMARK",
"GODREJPROP","HINDCOPPER","ICICISEC","IDFCFIRSTB",
"INDIAMART","INDUSTOWER","IRCTC","JBCHEPHARM",
"JINDALSAW","JKCEMENT","JMFINANCIL","JSL",
"KEC","KPITTECH","LALPATHLAB","LAURUSLABS",
"LUPIN","M&MFIN","MANAPPURAM","METROPOLIS",
"MPHASIS","MUTHOOTFIN","NAVINFLUOR"
]

VOLUME_MULTIPLIER = 2.4 
MIN_DAILY_VOL_PCT = 0.002      # 0.2% of avg daily volume
SCAN_INTERVAL_SECONDS = 90
COOLDOWN_HOURS = 2

MARKET_START = time(9, 20)
MARKET_END   = time(15, 5)

tv = TvDatafeed()
last_alert_time = {}   # symbol -> datetime

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

def get_avg_daily_volume(symbol):
    df = tv.get_hist(symbol, "NSE", Interval.in_daily, 10)
    if df is None or len(df) < 5:
        return None
    return df["volume"].tail(5).mean()

# ================= SCAN =================
def scan_once():
    now = datetime.now()

    if not (MARKET_START <= now.time() <= MARKET_END):
        return

    for symbol in NIFTY_150:
        try:
            df = tv.get_hist(symbol, "NSE", Interval.in_5_minute, 50)
        except Exception:
            continue

        if df is None or len(df) < 10:
            continue

        df = normalize(df)

        # same-day & exclude 9:15–9:20
        df = df[
            (df["Datetime"].dt.date == now.date()) &
            (df["Datetime"].dt.time >= time(9, 20))
        ]

        if len(df) < 6:
            continue

        last = df.iloc[-1]
        candle_time = last["Datetime"]

        lookback = min(len(df) - 1, 20)
        if lookback < 5:
            continue

        avg_vol = df["Volume"].iloc[-(lookback+1):-1].mean()
        if avg_vol == 0:
            continue

        current_vol = last["Volume"]
        vol_mult = current_vol / avg_vol

        if vol_mult < VOLUME_MULTIPLIER:
            continue

        if not is_bullish(last):
            continue

        avg_daily_vol = get_avg_daily_volume(symbol)
        if avg_daily_vol is None:
            continue

        min_abs_vol = avg_daily_vol * MIN_DAILY_VOL_PCT
        if current_vol < min_abs_vol:
            continue

        if symbol in last_alert_time:
            if candle_time <= last_alert_time[symbol] + timedelta(hours=COOLDOWN_HOURS):
                continue

        last_alert_time[symbol] = candle_time

        msg = (
            f"🔥 BULLISH VOLUME SPIKE\n"
            f"Stock : {symbol}\n"
            f"Time  : {candle_time.strftime('%H:%M')}\n"
            f"Volume: {int(current_vol)}\n"
            f"Spike : {vol_mult:.2f}× avg\n"
            f"MinVol: {int(min_abs_vol)}"
            f"Lookback: {lookback} candles\n"
        )

        print(msg)
        send_telegram(msg)

# ================= MAIN LOOP =================
print("🟢 Strategy C running (Bullish, RVOL + Scaled Absolute Volume)")

while True:
    scan_once()
    tm.sleep(SCAN_INTERVAL_SECONDS)
