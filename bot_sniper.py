import time
from datetime import datetime
import pandas as pd
import pytz
import requests
import yfinance as yf

# ==========================================
# ⚙️ TELEGRAM & SYMBOLS CONFIGURATION
# ==========================================
TELEGRAM_TOKEN = "8980085069:AAENlLOKnpEpAQjuXfzood8bR7ghZ4_7kIY"
CHAT_ID = "6327673739"

# Updated Currency Pairs (NZD/JPY Removed - Total 18 Pairs)
SYMBOLS = [
    "EURUSD=X",
    "GBPUSD=X",
    "USDJPY=X",
    "AUDUSD=X",
    "USDCAD=X",
    "USDCHF=X",
    "NZDUSD=X",
    "EURGBP=X",
    "EURJPY=X",
    "GBPJPY=X",
    "AUDJPY=X",
    "EURAUD=X",
    "EURCAD=X",
    "GBPAUD=X",
    "GBPCAD=X",
    "GBPCHF=X",
    "AUDCAD=X",
    "AUDCHF=X",
]


def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram Error: {e}")


def is_market_open():
    """Market Open, Weekend & Off-Time Filter (BD Time)"""
    tz = pytz.timezone("Asia/Dhaka")
    now = datetime.now(tz)

    if now.weekday() in [5, 6]:
        return False, "Weekend (Market Closed)"

    if 0 <= now.hour < 6:
        return False, "Late Night Off-Market Time (12 AM - 6 AM BD Time)"

    return True, "Market Open"


def check_forex_news():
    """Forex Factory High-Impact Red Folder News Filter"""
    try:
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            events = response.json()
            now_utc = datetime.now(pytz.utc)

            for event in events:
                if event.get("impact") == "High" and event.get(
                    "currency"
                ) in ["USD", "EUR", "GBP"]:
                    event_time_str = event.get("date")
                    if event_time_str:
                        event_time = datetime.strptime(
                            event_time_str, "%Y-%m-%dT%H:%M:%S%z"
                        )
                        time_diff = (
                            event_time - now_utc
                        ).total_seconds() / 60
                        if -15 <= time_diff <= 15:
                            return (
                                False,
                                f"High Impact News Active: {event.get('title')}",
                            )
    except Exception:
        pass
    return True, "No Red Folder News"


def calculate_indicators(df):
    """Calculates EMA, RSI, MACD, Bollinger Bands, and Stochastic"""
    df["EMA50"] = df["Close"].ewm(span=50, adjust=False).mean()

    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))

    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()

    # Bollinger Bands (20, 2)
    df["BB_Middle"] = df["Close"].rolling(window=20).mean()
    bb_std = df["Close"].rolling(window=20).std()
    df["BB_Upper"] = df["BB_Middle"] + (bb_std * 2)
    df["BB_Lower"] = df["BB_Middle"] - (bb_std * 2)

    # Stochastic Oscillator (14, 3, 3)
    low_min = df["Low"].rolling(window=14).min()
    high_max = df["High"].rolling(window=14).max()
    df["Stoch_K"] = ((df["Close"] - low_min) / (high_max - low_min)) * 100
    df["Stoch_D"] = df["Stoch_K"].rolling(window=3).mean()

    return df


def check_m15_trend(symbol):
    """M15 Trend Filter"""
    try:
        data_m15 = yf.download(
            tickers=symbol, period="2d", interval="15m", progress=False
        )
        if len(data_m15) < 50:
            return "NEUTRAL"

        if isinstance(data_m15.columns, pd.MultiIndex):
            data_m15.columns = data_m15.columns.get_level_values(0)

        data_m15["EMA50"] = data_m15["Close"].ewm(span=50, adjust=False).mean()
        curr_m15 = data_m15.iloc[-1]

        if curr_m15["Close"] > curr_m15["EMA50"]:
            return "BULLISH"
        elif curr_m15["Close"] < curr_m15["EMA50"]:
            return "BEARISH"
    except Exception:
        pass
    return "NEUTRAL"


def get_entry_timing():
    """Exact Next 5-Min Candle Entry Time (BD Time)"""
    tz = pytz.timezone("Asia/Dhaka")
    now = datetime.now(tz)
    minute = now.minute
    next_candle_minute = ((minute // 5) + 1) * 5

    if next_candle_minute == 60:
        next_hour = (now.hour + 1) % 24
        entry_time_str = f"{next_hour:02d}:00:00 BD Time"
    else:
        entry_time_str = f"{now.hour:02d}:{next_candle_minute:02d}:00 BD Time"

    return entry_time_str


def analyze_market(symbol):
    try:
        data = yf.download(
            tickers=symbol, period="2d", interval="5m", progress=False
        )
        if len(data) < 50:
            return

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        df = calculate_indicators(data)

        curr = df.iloc[-1]
        prev = df.iloc[-2]

        close = curr["Close"]
        open_price = curr["Open"]
        high = curr["High"]
        low = curr["Low"]
        ema = curr["EMA50"]
        rsi = curr["RSI"]
        macd = curr["MACD"]
        macd_sig = curr["Signal"]
        bb_lower = curr["BB_Lower"]
        bb_upper = curr["BB_Upper"]
        stoch_k = curr["Stoch_K"]
        stoch_d = curr["Stoch_D"]

        body = abs(close - open_price)
        total_range = high - low

        # Doji Filter (Body < 20%)
        if total_range == 0 or (body / total_range) < 0.20:
            return

        # Exhaustion Filter
        avg_body = abs(df["Close"] - df["Open"]).tail(10).mean()
        if body > (avg_body * 3.2):
            return

        pair_name = symbol.replace("=X", "").replace("GC=F", "GOLD (XAUUSD)")
        m15_trend = check_m15_trend(symbol)
        entry_time = get_entry_timing()

        # 🟢 CALL / BUY SIGNAL
        is_bullish_engulfing = (
            (prev["Close"] < prev["Open"])
            and (close > open_price)
            and (close > prev["Open"])
        )
        is_bullish_pinbar = (
            (close > open_price)
            and ((open_price - low) > 1.8 * body)
            and ((high - close) <= body)
        )

        if (
            (is_bullish_engulfing or is_bullish_pinbar)
            and close > ema
            and macd > macd_sig
        ):
            if (
                m15_trend in ["BULLISH", "NEUTRAL"]
                and 40 < rsi < 70
                and low <= bb_lower * 1.004
                and stoch_k > stoch_d
                and stoch_k < 45
            ):

                msg = (
                    f"<b>🟢 SNIPER BUY / UP SIGNAL 🟢</b>\n\n"
                    f"<b>Pair:</b> {pair_name}\n"
                    f"<b>Timeframe:</b> M5 (Trend: M15 Neutral/Up)\n"
                    f"<b>Signal Quality:</b> 🎯 HIGH CONFIDENCE (Direct Win)\n"
                    f"<b>MTG Status:</b> ❌ Not Needed (Direct Entry)\n\n"
                    f"📊 <b>Metrics:</b> RSI: {rsi:.1f} | Stoch: {stoch_k:.1f} | EMA50: Bullish Trend\n"
                    f"⏰ <b>Exact Entry Time:</b> <code>{entry_time}</code> (00:00 Sec Entry)\n\n"
                    f"⚠️ <i>News & Market Filter Checked!</i>"
                )
                send_telegram_msg(msg)
                return

        # 🔴 PUT / SELL SIGNAL
        is_bearish_engulfing = (
            (prev["Close"] > prev["Open"])
            and (close < open_price)
            and (close < prev["Close"])
        )
        is_bearish_pinbar = (
            (close < open_price)
            and ((high - open_price) > 1.8 * body)
            and ((close - low) <= body)
        )

        if (
            (is_bearish_engulfing or is_bearish_pinbar)
            and close < ema
            and macd < macd_sig
        ):
            if (
                m15_trend in ["BEARISH", "NEUTRAL"]
                and 30 < rsi < 60
                and high >= bb_upper * 0.996
                and stoch_k < stoch_d
                and stoch_k > 55
            ):

                msg = (
                    f"<b>🔴 SNIPER SELL / DOWN SIGNAL 🔴</b>\n\n"
                    f"<b>Pair:</b> {pair_name}\n"
                    f"<b>Timeframe:</b> M5 (Trend: M15 Neutral/Down)\n"
                    f"<b>Signal Quality:</b> 🎯 HIGH CONFIDENCE (Direct Win)\n"
                    f"<b>MTG Status:</b> ❌ Not Needed (Direct Entry)\n\n"
                    f"📊 <b>Metrics:</b> RSI: {rsi:.1f} | Stoch: {stoch_k:.1f} | EMA50: Bearish Trend\n"
                    f"⏰ <b>Exact Entry Time:</b> <code>{entry_time}</code> (00:00 Sec Entry)\n\n"
                    f"⚠️ <i>News & Market Filter Checked!</i>"
                )
                send_telegram_msg(msg)
                return

    except Exception as e:
        print(f"Error processing {symbol}: {e}")


def main():
    print("Scanning Started (18 Pairs)...")

    market_status, reason = is_market_open()
    if not market_status:
        print(f"Skipped: {reason}")
        return

    news_status, news_reason = check_forex_news()
    if not news_status:
        print(f"Skipped: {news_reason}")
        return

    for symbol in SYMBOLS:
        analyze_market(symbol)
        time.sleep(0.3)

    print("Scan finished successfully.")


if __name__ == "__main__":
    main()
