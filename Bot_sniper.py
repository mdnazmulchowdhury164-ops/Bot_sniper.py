from datetime import datetime
import os
import time
import pandas as pd
import pytz
import requests
import yfinance as yf

# Telegram Configuration (GitHub Secrets থেকে অটো রিড করবে)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# Gold এবং NZD/JPY বাদে বাকি ১৯টি কারেন্সি পেয়ার
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
  if not TELEGRAM_TOKEN or not CHAT_ID:
    print("Telegram credentials missing!")
    return
  url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
  payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
  try:
    requests.post(url, json=payload, timeout=10)
  except Exception as e:
    print(f"Telegram Error: {e}")


def is_market_open():
  """Market Open & Weekend Filter (BD Time)"""
  tz = pytz.timezone("Asia/Dhaka")
  now = datetime.now(tz)

  # শনি ও রবিবার মার্কেট বন্ধ
  if now.weekday() in [5, 6]:
    return False, "Weekend (Market Closed)"

  # রাত ১২টা থেকে সকাল ৬টা পর্যন্ত অফ-টাইম ফিল্টার
  if 0 <= now.hour < 6:
    return False, "Late Night Off-Market Time (12 AM - 6 AM BD Time)"

  return True, "Market Open"


def calculate_indicators(df):
  """Calculates EMA, RSI, MACD, and Volume MA"""
  df["EMA50"] = df["Close"].ewm(span=50, adjust=False).mean()

  delta = df["Close"].diff()
  gain = delta.where(delta > 0, 0).rolling(window=14).mean()
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
  """M15 Trend Filter for High Confidence"""
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
  """Exact Next 5-Min Candle Entry Time"""
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
    data = yf.download(tickers=symbol, period="2d", interval="5m", progress=False)
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

    body = abs(close - open_price)
    total_range = high - low

    # Doji Filter (Body < 25%)
    if total_range == 0 or (body / total_range) < 0.25:
      return

    # Exhaustion Filter
    avg_body = abs(df["Close"] - df["Open"]).tail(10).mean()
    if body > (avg_body * 2.8):
      return

    # Pivot Points S&R
    pp = (curr["High"] + curr["Low"] + curr["Close"]) / 3
    r1 = (2 * pp) - curr["Low"]
    s1 = (2 * pp) - curr["High"]

    pair_name = symbol.replace("=X", "")
    m15_trend = check_m15_trend(symbol)
    entry_time = get_entry_timing()

    curr_vol = curr.get("Volume", 0)
    vol_ma = curr.get("Vol_MA", 0)
    has_good_volume = curr_vol >= (vol_ma * 0.9) if vol_ma > 0 else True

    # 🟢 CALL / UP SIGNAL (Sniper Optimized)
    is_bullish_engulfing = (
        (prev["Close"] < prev["Open"])
        and (close > open_price)
        and (close > prev["Open"])
        and (open_price < prev["Close"])
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

      if m15_trend == "BULLISH" and 42 < rsi < 65 and macd > 0 and has_good_volume:
        quality = "🎯 SNIPER ULTRA HIGH CONFIDENCE (Direct Win)"
        mtg = "❌ Not Needed (Strictly Direct Entry)"
      else:
        return

      msg = (
          f"<b>🟢 SNIPER BUY / UP SIGNAL 🟢</b>\n\n"
          f"<b>Pair:</b> {pair_name}\n"
          f"<b>Timeframe:</b> M5\n"
          f"<b>Signal Quality:</b> {quality}\n"
          f"<b>MTG Status:</b> {mtg}\n\n"
          f"📊 <b>Filters:</b> EMA 50 Above | RSI: {rsi:.1f} | M15 Trend:"
          f" {m15_trend}\n"
          f"⏰ <b>Exact Entry Time:</b> <code>{entry_time}</code> (00:00 Sec"
          f" Entry)\n\n"
          f"⚠️ <i>Check Forex Factory for Red Folder News before entry!</i>"
      )
      send_telegram_msg(msg)
      return

    # 🔴 PUT / DOWN SIGNAL (Sniper Optimized)
    is_bearish_engulfing = (
        (prev["Close"] > prev["Open"])
        and (close < open_price)
        and (close < prev["Close"])
        and (open_price > prev["Open"])
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

      if m15_trend == "BEARISH" and 35 < rsi < 58 and macd < 0 and has_good_volume:
        quality = "🎯 SNIPER ULTRA HIGH CONFIDENCE (Direct Win)"
        mtg = "❌ Not Needed (Strictly Direct Entry)"
      else:
        return

      msg = (
          f"<b>🔴 SNIPER SELL / DOWN SIGNAL 🔴</b>\n\n"
          f"<b>Pair:</b> {pair_name}\n"
          f"<b>Timeframe:</b> M5\n"
          f"<b>Signal Quality:</b> {quality}\n"
          f"<b>MTG Status:</b> {mtg}\n\n"
          f"📊 <b>Filters:</b> EMA 50 Above | RSI: {rsi:.1f} | M15 Trend:"
          f" {m15_trend}\n"
          f"⏰ <b>Exact Entry Time:</b> <code>{entry_time}</code> (00:00 Sec"
          f" Entry)\n\n"
          f"⚠️ <i>Check Forex Factory for Red Folder News before entry!</i>"
      )
      send_telegram_msg(msg)
      return

  except Exception as e:
    print(f"Error processing {symbol}: {e}")


def main():
  market_status, reason = is_market_open()
  if not market_status:
    print(f"Bot Paused: {reason}")
    return

  print(
      "Scanning 19 Currency Pairs automatically on GitHub Actions (Sniper"
      " Mode)..."
  )
  for symbol in SYMBOLS:
    analyze_market(symbol)
    time.sleep(2)


if __name__ == "__main__":
  main()
