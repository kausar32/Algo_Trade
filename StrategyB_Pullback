# UPDATED BACKTEST CODE (PULLBACK–EXECUTION VERSION)--- win rate 51%. SL below X, early exit, 2 times a day,
from tvDatafeed import TvDatafeed, Interval
import pandas as pd
from datetime import time
import time as tm

# ================= CONFIG =================
RR = 1.2

ENTRY_START = time(9, 20)
ENTRY_END   = time(14, 45)

MAX_TRADES_PER_DAY = 2
MAX_HOLD_MINUTES = 30

ATR_MULTIPLIER = 1.5
VOLUME_MULTIPLIER = 2.0

PULLBACK_MIN = 0.25
PULLBACK_MAX = 0.40
PULLBACK_WINDOW_MINUTES = 15

EXEC_TF = Interval.in_3_minute   # execution timeframe

tv = TvDatafeed()

NIFTY_100 = [
"ADANIENT","ADANIPORTS","AMBUJACEM","APOLLOHOSP","ASIANPAINT",
"AUROPHARMA","AXISBANK","BAJAJ-AUTO","BAJFINANCE","BAJAJFINSV",
"BANDHANBNK","BANKBARODA","BERGEPAINT","BHARATFORG","BHARTIARTL",
"BHEL","BIOCON","BOSCHLTD","BPCL","BRITANNIA","CANBK","CHOLAFIN",
"CIPLA","COALINDIA","COLPAL","DABUR","DIVISLAB","DLF","DRREDDY",
"EICHERMOT","GAIL","GLENMARK","GODREJCP","GRASIM","HAVELLS",
"HCLTECH","HDFCBANK","HDFCLIFE","HEROMOTOCO","HINDALCO",
"HINDPETRO","HINDUNILVR","ICICIBANK","IDFCFIRSTB","INDUSINDBK",
"INFY","IOC","ITC","JSWSTEEL","KOTAKBANK","LT","LUPIN","M&M",
"MARICO","MARUTI","MCDOWELL-N","NMDC","NTPC","ONGC","PAGEIND",
"PETRONET","PIDILITIND","PNB","POWERGRID","RELIANCE","SBIN",
"SHREECEM","SIEMENS","SUNPHARMA","TATACONSUM","TATAMOTORS",
"TATASTEEL","TECHM","TITAN","TORNTPHARM","ULTRACEMCO","UPL",
"VEDL","WIPRO","ZEEL"
]

# ================= HELPERS =================
def fetch(symbol, interval, bars):
    for _ in range(3):
        df = tv.get_hist(symbol, "NSE", interval, n_bars=bars)
        if df is not None:
            return df
        tm.sleep(1)
    return None

def normalize(df):
    df = df.reset_index()
    if "datetime" in df.columns:
        df.rename(columns={"datetime": "Datetime"}, inplace=True)

    df.rename(columns={
        "open":"Open","high":"High","low":"Low",
        "close":"Close","volume":"Volume"
    }, inplace=True)

    df["Date"] = df["Datetime"].dt.date
    df["Time"] = df["Datetime"].dt.time
    return df

def atr(df, n=14):
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - df["Close"].shift()).abs(),
        (df["Low"] - df["Close"].shift()).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(n).mean()

def bullish_engulfing_with_volume(df, i):
    if i < 20:
        return False

    c, p = df.iloc[i], df.iloc[i-1]
    body = c["Close"] - c["Open"]
    rng = c["High"] - c["Low"]

    avg_rng = (df["High"] - df["Low"]).rolling(10).mean().iloc[i]
    avg_vol = df["Volume"].rolling(20).mean().iloc[i]

    return (
        body > 0 and
        body >= 0.6 * rng and
        c["Close"] > p["Close"] and
        rng >= 1.2 * avg_rng and
        c["Volume"] >= VOLUME_MULTIPLIER * avg_vol
    )

def compute_rsh(prev5, prev15):
    pdh = prev5["High"].max()
    a = prev15["ATR"].iloc[-1]
    if pd.isna(a):
        return None

    fall = pdh - prev5["Low"].min()
    if fall >= ATR_MULTIPLIER * a:
        idx = prev5[prev5["Low"] <= pdh - ATR_MULTIPLIER * a].index[0]
        return prev5.loc[idx:, "High"].max()

    return pdh

def valid_exec_candle(c):
    rng = c["High"] - c["Low"]
    body = c["Close"] - c["Open"]
    return body > 0 and body >= 0.5 * rng

# ================= BACKTEST =================
results = []
daily_trade_count = {}

for symbol in NIFTY_100:

    d5  = fetch(symbol, Interval.in_5_minute, 4000)
    d15 = fetch(symbol, Interval.in_15_minute, 2000)
    d3  = fetch(symbol, EXEC_TF, 6000)

    if d5 is None or d15 is None or d3 is None:
        continue

    d5  = normalize(d5)
    d15 = normalize(d15)
    d3  = normalize(d3)

    d15["ATR"] = atr(d15)

    for day in sorted(d5["Date"].unique()):

        if daily_trade_count.get(day, 0) >= MAX_TRADES_PER_DAY:
            continue

        prev_day = (pd.to_datetime(day) - pd.Timedelta(days=1)).date()
        p5  = d5[d5["Date"] == prev_day]
        p15 = d15[d15["Date"] == prev_day]

        if p5.empty or p15.empty:
            continue

        RSH = compute_rsh(p5, p15)
        if RSH is None:
            continue

        day5 = d5[d5["Date"] == day].reset_index(drop=True)
        day3 = d3[d3["Date"] == day].reset_index(drop=True)

        for i in range(len(day5)):
            x = day5.iloc[i]

            if not (ENTRY_START <= x["Time"] <= ENTRY_END):
                continue
            if x["High"] <= RSH:
                continue
            if not bullish_engulfing_with_volume(day5, i):
                continue

            X_high = x["High"]
            X_low  = x["Low"]
            X_range = X_high - X_low

            pb_low = X_high - PULLBACK_MAX * X_range
            pb_high = X_high - PULLBACK_MIN * X_range

            start_time = x["Datetime"]
            end_time = start_time + pd.Timedelta(minutes=PULLBACK_WINDOW_MINUTES)

            pb_df = day3[
                (day3["Datetime"] > start_time) &
                (day3["Datetime"] <= end_time)
            ]

            pullback_seen = False

            for _, c in pb_df.iterrows():

                if pb_low <= c["Low"] <= pb_high:
                    pullback_seen = True
                    continue

                if pullback_seen and valid_exec_candle(c) and c["Close"] >= X_high * 0.995:
                    entry = c["Close"]
                    # sl = X_low
                    sl = X_high - 0.7 * X_range
                    target = entry + RR * (entry - sl)

                    entry_time = c["Datetime"]
                    exit_deadline = entry_time + pd.Timedelta(minutes=MAX_HOLD_MINUTES)

                    outcome = None

                    for _, f in day3[day3["Datetime"] > entry_time].iterrows():
                        if f["Datetime"] >= exit_deadline:
                            outcome = "TIME_EXIT_PROFIT" if f["Close"] > entry else "TIME_EXIT_LOSS"
                            break
                        if f["Low"] <= sl:
                            outcome = "SL"
                            break
                        if f["High"] >= target:
                            outcome = "TP"
                            break

                    if outcome:
                        results.append(outcome)
                        daily_trade_count[day] = daily_trade_count.get(day, 0) + 1
                    break

# ================= SUMMARY =================
total = len(results)
tp = results.count("TP")
sl = results.count("SL")
tep = results.count("TIME_EXIT_PROFIT")
tel = results.count("TIME_EXIT_LOSS")

print("\n====== NIFTY 100 BACKTEST (PULLBACK EXECUTION – UPDATED) ======")
print("Total Trades        :", total)
print("TP                  :", tp)
print("SL                  :", sl)
print("Time Exit (Profit)  :", tep)
print("Time Exit (Loss)    :", tel)
print("Win Rate %          :", round((tp + tep) / total * 100, 2) if total else 0)
print("==============================================================\n")
