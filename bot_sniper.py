import time
from datetime import datetime
import pandas as pd
import pytz
import requests
import yfinance as yf

# Telegram Configuration
TELEGRAM_TOKEN = "8980085069:AAENlLOKnpEpAQjuXfzood8bR7ghZ4_7kIY"
CHAT_ID = "6327673739"

# 18 Forex Pairs (Gold 'GC=F' and 'NZDJPY=X' Removed)
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


def is_trading_session():
    """Active Window: 1:30 PM (13:30) to 9:30 PM (21:30) BD Time, Mon-Fri"""
    tz = pytz.timezone("Asia/Dhaka")
    now = datetime.now(tz)

    if now.weekday() in [5, 6]:
        return False, "Weekend (Market Closed)"

    current_minutes = now.hour * 60 + now.minute
    start_minutes = 13 * 60 + 30  # 1:30 PM BD Time
    end_minutes = 21 * 60 + 30    # 9:30 PM BD Time

    if not (start_minutes <= current_minutes <= end_minutes):
        return False, "Outside Active Window (1:30 PM - 9:30 PM BD Time)"

    return True, "Active Session (1:30 PM - 9:30 PM BD Time)"


def calculate_indicators(df):
    """Calculates EMA50, RSI, MACD, and Volume MA"""
    df["EMA50"] = df["Close"].ewm(span=50, adjust=False).mean()

    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))

    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()

    if "Volume" in df.columns:
        df["Vol_MA"] = df["Volume"].rolling(window=10).mean()
    else:
        df["Vol_MA"] = 0

    return df


def check_m15_trend(symbol):
    """M15 Trend Filter"""
    try:
        data_m15 = yf.download(
            tickers=symbol, period="2d", interval="15m", progress=False
        )
        if data_m15 is None or len(data_m15) < 50:
            return "NEUTRAL"

        if isinstance(data_m15.columns, pd.MultiIndex):
            data_m15.columns = data_m15.columns.get_level_values(0)

        data_m15["EMA50"] = data_m15["Close"].ewm(span=50, adjust=False).mean()
        curr_m15 = data_m15.iloc[-1]

        if float(curr_m15["Close"]) > float(curr_m15["EMA50"]):
            return "BULLISH"
        elif float(curr_m15["Close"]) < float(curr_m15["EMA50"]):
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
        if data is None or len(data) < 50:
            return

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        df = calculate_indicators(data)

        curr = df.iloc[-1]
        prev = df.iloc[-2]

        close = float(curr["Close"])
        open_price = float(curr["Open"])
        high = float(curr["High"])
        low = float(curr["Low"])
        ema = float(curr["EMA50"])
        rsi = float(curr["RSI"])
        macd = float(curr["MACD"])
        macd_sig = float(curr["Signal"])

        body = abs(close - open_price)
        total_range = high - low

        # Doji Filter (Body < 25%)
        if total_range == 0 or (body / total_range) < 0.25:
            return

        # Exhaustion Filter
        avg_body = float(abs(df["Close"] - df["Open"]).tail(10).mean())
        if avg_body > 0 and body > (avg_body * 2.8):
            return

        # Pivot Points S&R
        pp = (high + low + close) / 3
        r1 = (2 * pp) - low
        s1 = (2 * pp) - high

        pair_name = symbol.replace("=X", "")
        m15_trend = check_m15_trend(symbol)
        entry_time = get_entry_timing()

        curr_vol = float(curr.get("Volume", 0) or 0)
        vol_ma = float(curr.get("Vol_MA", 0) or 0)
        has_good_volume = curr_vol >= (vol_ma * 0.9) if vol_ma > 0 else True

        # 🟢 CALL / UP SIGNAL
        is_bullish_engulfing = (
            (float(prev["Close"]) < float(prev["Open"]))
            and (close > open_price)
            and (close > float(prev["Open"]))
            and (open_price < float(prev["Close"]))
        )
        is_bullish_pinbar = (
            (close > open_price)
            and ((open_price - low) > 2.0 * body)
            and ((high - close) < body)
        )

        if (
            (is_bullish_engulfing or is_bullish_pinbar)
            and close > ema
            and macd > macd_sig
        ):
            if close >= r1:
                return

            if (
                m15_trend == "BULLISH"
                and 42 < rsi < 65
                and macd > 0
                and has_good_volume
            ):
                quality = "🎯 HIGH CONFIDENCE SETUP (Direct Entry)"
                mtg = "❌ Not Needed (Direct Entry)"
            else:
                return

            msg = (
                f"<b>🟢 BUY / UP SIGNAL (5M) 🟢</b>\n\n"
                f"<b>Pair:</b> {pair_name}\n"
                f"<b>Timeframe:</b> M5\n"
                f"<b>Signal Quality:</b> {quality}\n"
                f"<b>MTG Status:</b> {mtg}\n\n"
                f"📊 <b>Filters:</b> EMA 50 Above | RSI: {rsi:.1f} | M15 Trend: {m15_trend}\n"
                f"⏰ <b>Exact Entry Time:</b> <code>{entry_time}</code> (00:00 Sec Entry)\n\n"
                f"⚠️ <i>No guaranteed win rate. Trade with strict money management.</i>"
            )
            send_telegram_msg(msg)
            return

        # 🔴 PUT / DOWN SIGNAL
        is_bearish_engulfing = (
            (float(prev["Close"]) > float(prev["Open"]))
            and (close < open_price)
            and (close < float(prev["Close"]))
            and (open_price > float(prev["Open"]))
        )
        is_bearish_pinbar = (
            (close < open_price)
            and ((high - open_price) > 2.0 * body)
            and ((close - low) < body)
        )

        if (
            (is_bearish_engulfing or is_bearish_pinbar)
            and close < ema
            and macd < macd_sig
        ):
            if close <= s1:
                return

            if (
                m15_trend == "BEARISH"
                and 35 < rsi < 58
                and macd < 0
                and has_good_volume
            ):
                quality = "🎯 HIGH CONFIDENCE SETUP (Direct Entry)"
                mtg = "❌ Not Needed (Direct Entry)"
            else:
                return

            msg = (
                f"<b>🔴 SELL / DOWN SIGNAL (5M) 🔴</b>\n\n"
                f"<b>Pair:</b> {pair_name}\n"
                f"<b>Timeframe:</b> M5\n"
                f"<b>Signal Quality:</b> {quality}\n"
                f"<b>MTG Status:</b> {mtg}\n\n"
                f"📊 <b>Filters:</b> EMA 50 Below | RSI: {rsi:.1f} | M15 Trend: {m15_trend}\n"
                f"⏰ <b>Exact Entry Time:</b> <code>{entry_time}</code> (00:00 Sec Entry)\n\n"
                f"⚠️ <i>No guaranteed win rate. Trade with strict money management.</i>"
            )
            send_telegram_msg(msg)
            return

    except Exception as e:
        print(f"Error processing {symbol}: {e}")


def main():
    session_ok, reason = is_trading_session()
    if not session_ok:
        print(f"Bot Paused: {reason}")
        return

    print("Scanning 18 Forex Pairs (1:30 PM - 9:30 PM BD Time)...")
    for symbol in SYMBOLS:
        analyze_market(symbol)
        time.sleep(0.3)


if __name__ == "__main__":
    main()
