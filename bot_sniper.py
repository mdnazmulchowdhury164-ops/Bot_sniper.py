from datetime import datetime
import time
import pytz
import requests
import yfinance as yf

# Telegram Configuration
TELEGRAM_TOKEN = "8636180917:AAFB5ntb274YsxnBFUa5HKUgQqGdBSK2cXw"
CHAT_ID = "6574248669"

# Your Original 19 Currency Pairs + Gold (Exact Quotex Available Pairs)
SYMBOLS = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X", "USDCHF=X", 
    "NZDUSD=X", "EURGBP=X", "EURJPY=X", "GBPJPY=X", "AUDJPY=X", "EURAUD=X", 
    "EURCAD=X", "GBPAUD=X", "GBPCAD=X", "GBPCHF=X", "AUDCAD=X", "AUDCHF=X", 
    "NZDJPY=X", "GC=F" # Gold (XAUUSD)
]

def send_telegram_msg(message):
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
    
    if now.weekday() in [5, 6]:
        return False, "Weekend (Market Closed)"
    
    if 0 <= now.hour < 6:
        return False, "Late Night Off-Market Time (12 AM - 6 AM BD Time)"
        
    return True, "Market Open"

def calculate_indicators(df):
    """Calculates EMA, RSI, MACD, and Volume MA"""
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    if 'Volume' in df.columns:
        df['Vol_MA'] = df['Volume'].rolling(window=10).mean()
    else:
        df['Vol_MA'] = 0
        
    return df

def check_m15_trend(symbol):
    """M15 Trend Filter for High Confidence"""
    try:
        data_m15 = yf.download(tickers=symbol, period="2d", interval="15m", progress=False)
        if len(data_m15) < 50: return "NEUTRAL"
        
        if isinstance(data_m15.columns, pd.MultiIndex):
            data_m15.columns = data_m15.columns.get_level_values(0)
            
        data_m15['EMA50'] = data_m15['Close'].ewm(span=50, adjust=False).mean()
        curr_m15 = data_m15.iloc[-1]
        
        if curr_m15['Close'] > curr_m15['EMA50']: return "BULLISH"
        elif curr_m15['Close'] < curr_m15['EMA50']: return "BEARISH"
    except Exception: pass
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
        market_status, reason = is_market_open()
        if not market_status:
            return

        data = yf.download(tickers=symbol, period="2d", interval="5m", progress=False)
        if len(data) < 50: return

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        df = calculate_indicators(data)
        
        curr = df.iloc[-1]
        prev = df.iloc[-2]

        close = curr['Close']
        open_price = curr['Open']
        high = curr['High']
        low = curr['Low']
        ema = curr['EMA50']
        rsi = curr['RSI']
        macd = curr['MACD']
        macd_sig = curr['Signal']

        body = abs(close - open_price)
        total_range = high - low

        # Balanced Doji Filter
        if total_range == 0 or (body / total_range) < 0.18: return

        pair_name = symbol.replace("=X", "").replace("GC=F", "GOLD (XAUUSD)")
        m15_trend = check_m15_trend(symbol)
        entry_time = get_entry_timing()

        # 🟢 CALL / UP SIGNAL (Balanced for 7-10+ High Accuracy Signals)
        is_bullish_engulfing = (prev['Close'] < prev['Open']) and (close > open_price) and (close >= prev['Open'])
        is_bullish_pinbar = (close > open_price) and ((open_price - low) > 1.5 * body) and ((high - close) < body * 2)

        if (is_bullish_engulfing or is_bullish_pinbar) and close >= (ema * 0.999) and macd > macd_sig:
            # Optimized RSI Range for higher frequency & direct win
            if m15_trend != "BEARISH" and 35 <= rsi <= 72:
                quality = "🎯 SNIPER HIGH CONFIDENCE (Direct Win)"
                mtg = "❌ Not Needed (Strictly Direct Entry)"
            else:
                return

            msg = (
                f"<b>🟢 SNIPER BUY / UP SIGNAL 🟢</b>\n\n"
                f"<b>Pair:</b> {pair_name}\n"
                f"<b>Timeframe:</b> M5\n"
                f"<b>Signal Quality:</b> {quality}\n"
                f"<b>MTG Status:</b> {mtg}\n\n"
                f"📊 <b>Filters:</b> EMA 50 | RSI: {rsi:.1f} | M15 Trend: {m15_trend}\n"
                f"⏰ <b>Exact Entry Time:</b> <code>{entry_time}</code> (00:00 Sec Entry)\n\n"
                f"⚠️ <i>Check Forex Factory for Red Folder News before entry!</i>"
            )
            send_telegram_msg(msg)
            time.sleep(1)
            return

        # 🔴 PUT / DOWN SIGNAL (Balanced for 7-10+ High Accuracy Signals)
        is_bearish_engulfing = (prev['Close'] > prev['Open']) and (close < open_price) and (close <= prev['Open'])
        is_bearish_pinbar = (close < open_price) and ((high - open_price) > 1.5 * body) and ((close - low) < body * 2)

        if (is_bearish_engulfing or is_bearish_pinbar) and close <= (ema * 1.001) and macd < macd_sig:
            # Optimized RSI Range for higher frequency & direct win
            if m15_trend != "BULLISH" and 28 <= rsi <= 65:
                quality = "🎯 SNIPER HIGH CONFIDENCE (Direct Win)"
                mtg = "❌ Not Needed (Strictly Direct Entry)"
            else:
                return

            msg = (
                f"<b>🔴 SNIPER SELL / DOWN SIGNAL 🔴</b>\n\n"
                f"<b>Pair:</b> {pair_name}\n"
                f"<b>Timeframe:</b> M5\n"
                f"<b>Signal Quality:</b> {quality}\n"
                f"<b>MTG Status:</b> {mtg}\n\n"
                f"📊 <b>Filters:</b> EMA 50 | RSI: {rsi:.1f} | M15 Trend: {m15_trend}\n"
                f"⏰ <b>Exact Entry Time:</b> <code>{entry_time}</code> (00:00 Sec Entry)\n\n"
                f"⚠️ <i>Check Forex Factory for Red Folder News before entry!</i>"
            )
            send_telegram_msg(msg)
            time.sleep(1)
            return

    except Exception as e:
        print(f"Error processing {symbol}: {e}")

def main():
    market_status, reason = is_market_open()
    if not market_status:
        print(f"Bot Paused: {reason}")
        return

    print("Scanning Quotex 20 Pairs with Balanced Sniper Filters...")
    for symbol in SYMBOLS:
        analyze_market(symbol)

if __name__ == "__main__":
    main()
