# This was for backtest nifty 100 --working --> takes 3 trades per day in nifty 100 --Accuracy ~ 38%

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
from tvDatafeed import TvDatafeed, Interval
import pandas as pd
from datetime import time
import time as tm

# ================= CONFIG =================
RR = 1.5 
ENTRY_START = time(9, 30)
ENTRY_END   = time(14, 45)

EARLY_EXIT_CANDLES = 6   # 30 minutes
EARLY_EXIT_R = 0.5

MAX_TRADES_PER_DAY = 3

tv = TvDatafeed()

# ================= HELPERS =================
def fetch(symbol, interval, bars):
    for _ in range(3):
        df = tv.get_hist(
            symbol=symbol,
            exchange="NSE",
            interval=interval,
            n_bars=bars
        )
        if df is not None:
            return df
        tm.sleep(2)
    return None

def normalize(df):
    df = df.reset_index()
    if "datetime" in df.columns:
        df.rename(columns={"datetime": "Datetime"}, inplace=True)

    rename = {}
    for c in df.columns:
        if c.lower() == "open": rename[c] = "Open"
        if c.lower() == "high": rename[c] = "High"
        if c.lower() == "low": rename[c] = "Low"
        if c.lower() == "close": rename[c] = "Close"
        if c.lower() == "volume": rename[c] = "Volume"

    df.rename(columns=rename, inplace=True)
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

def bullish_engulfing(df, i):
    if i < 20:
        return False
    c, p = df.iloc[i], df.iloc[i-1]

    body_c = abs(c["Close"] - c["Open"])
    body_p = abs(p["Close"] - p["Open"])
    rng = c["High"] - c["Low"]

    avg_rng = (df["High"] - df["Low"]).rolling(10).mean().iloc[i]
    avg_vol = df["Volume"].rolling(20).mean().iloc[i]

    return (
        c["Close"] > c["Open"] and
        c["Close"] > p["Close"] and
        body_c > body_p and
        body_c >= 0.6 * rng and
        rng >= 1.2 * avg_rng and
        c["Volume"] >= 1.5 * avg_vol
    )

def compute_rsh(prev5, prev15):
    pdh = prev5["High"].max()
    a = prev15["ATR"].iloc[-1]
    if pd.isna(a):
        return None

    fall = pdh - prev5["Low"].min()
    if fall >= a:
        idx = prev5[prev5["Low"] <= pdh - a].index[0]
        return prev5.loc[idx:, "High"].max()
    return pdh

# ================= BACKTEST =================
results = []
daily_trade_count = {}

for symbol in NIFTY_100:

    d5 = fetch(symbol, Interval.in_5_minute, 3000)
    d15 = fetch(symbol, Interval.in_15_minute, 1500)

    if d5 is None or d15 is None:
        continue

    d5 = normalize(d5)
    d15 = normalize(d15)
    d15["ATR"] = atr(d15)

    for day in sorted(d5["Date"].unique()):

        if daily_trade_count.get(day, 0) >= MAX_TRADES_PER_DAY:
            continue

        prev_day = (pd.to_datetime(day) - pd.Timedelta(days=1)).date()
        p5 = d5[d5["Date"] == prev_day]
        p15 = d15[d15["Date"] == prev_day]

        if p5.empty or p15.empty:
            continue

        RSH = compute_rsh(p5, p15)
        if RSH is None:
            continue

        day_df = d5[d5["Date"] == day].reset_index(drop=True)

        for i in range(len(day_df)):
            r = day_df.iloc[i]

            if not (ENTRY_START <= r["Time"] <= ENTRY_END):
                continue
            if r["High"] <= RSH:
                continue
            if not bullish_engulfing(day_df, i):
                continue

            entry = r["Close"]
            sl = r["Low"]
            risk = entry - sl
            target = entry + RR * risk

            result = None
            exit_price = None
            moved = False

            # ---- EARLY EXIT WINDOW ----
            for j in range(i+1, min(i+1+EARLY_EXIT_CANDLES, len(day_df))):
                c = day_df.iloc[j]
                if c["High"] >= entry + EARLY_EXIT_R * risk:
                    moved = True
                    break
                if c["Low"] <= sl:
                    result = "SL"
                    exit_price = sl
                    break

            if result == "SL":
                results.append("SL")
            elif not moved:
                c = day_df.iloc[min(i+EARLY_EXIT_CANDLES, len(day_df)-1)]
                exit_price = c["Close"]
                results.append(
                    "EARLY_EXIT_PROFIT" if exit_price > entry else "EARLY_EXIT_LOSS"
                )
            else:
                for j in range(i+1, len(day_df)):
                    c = day_df.iloc[j]
                    if c["Low"] <= sl:
                        result = "SL"
                        break
                    if c["High"] >= target:
                        result = "TP"
                        break
                results.append(result)

            daily_trade_count[day] = daily_trade_count.get(day, 0) + 1
            break

# ================= SUMMARY =================
total = len(results)
tp = results.count("TP")
sl = results.count("SL")
eep = results.count("EARLY_EXIT_PROFIT")
eel = results.count("EARLY_EXIT_LOSS")

print("\n====== NIFTY 100 BACKTEST (MAX 3 TRADES/DAY) ======")
print("Total Trades        :", total)
print("TP                  :", tp)
print("SL                  :", sl)
print("Early Exit (Profit) :", eep)
print("Early Exit (Loss)   :", eel)
print("Win Rate %          :", round((tp + eep) / total * 100, 2) if total else 0)
print("===============================================\n")
