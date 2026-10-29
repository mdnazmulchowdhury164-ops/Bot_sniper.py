from datetime import datetime
import pandas as pd
import pytz
import requests
import streamlit as st
import yfinance as yf

# Page Configuration
st.set_page_config(
    page_title="Nazmul Sniper Trading Bot - Balanced Pro",
    page_icon="🎯",
    layout="centered",
)

# Telegram Configuration
TELEGRAM_TOKEN = "8980085069:AAENlLOKnpEpAQjuXfzood8bR7ghZ4_7kIY"
CHAT_ID = "6327673739"

# 18 Currency Pairs
ALL_SYMBOLS = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X", "USDCHF=X", 
    "NZDUSD=X", "EURGBP=X", "EURJPY=X", "GBPJPY=X", "AUDJPY=X", "EURAUD=X", 
    "EURCAD=X", "GBPAUD=X", "GBPCAD=X", "GBPCHF=X", "AUDCAD=X", "AUDCHF=X"
]

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        st.error(f"Telegram Error: {e}")

def is_market_open():
    tz = pytz.timezone("Asia/Dhaka")
    now = datetime.now(tz)
    if now.weekday() in [5, 6]:
        return False, "Weekend (Market Closed)"
    if 0 <= now.hour < 6:
        return False, "Late Night Off-Market Time (12 AM - 6 AM BD Time) - Low Liquidity"
    return True, "Market Open"

def calculate_indicators(df):
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
    return df

def check_m15_trend(symbol):
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
    tz = pytz.timezone("Asia/Dhaka")
    now = datetime.now(tz)
    minute = now.minute
    next_candle_minute = ((minute // 5) + 1) * 5
    if next_candle_minute == 60:
        next_hour = (now.hour + 1) % 24
        return f"{next_hour:02d}:00:00 BD Time"
    else:
        return f"{now.hour:02d}:{next_candle_minute:02d}:00 BD Time"

# --- UI Design ---
st.title("🎯 Nazmul Sniper Trading Scanner (Optimized)")
st.markdown("ব্যালেন্সড মোড: পর্যাপ্ত সিগন্যাল (৭-১০টি) এবং হাই উইন-রেট নিশ্চিত করতে ফিল্টার অপ্টিমাইজ করা হয়েছে!")

market_status, reason = is_market_open()
if not market_status:
    st.warning(f"⚠️ **Market Status:** {reason}")
else:
    st.success(f"✅ **Market Status:** {reason}")

st.markdown("---")

st.subheader("📊 Select Currency Pairs to Scan")
select_all = st.checkbox("Select All 18 Pairs", value=True)

if select_all:
    selected_symbols = st.multiselect("Choose pairs:", ALL_SYMBOLS, default=ALL_SYMBOLS)
else:
    selected_symbols = st.multiselect("Choose pairs:", ALL_SYMBOLS, default=["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X"])

st.markdown("---")

if st.button("🚀 Scan Market for Balanced Sniper Signals", type="primary"):
    if not selected_symbols:
        st.error("দয়া করে কমপক্ষে একটি পেয়ার সিলেক্ট করুন!")
    else:
        with st.spinner("মার্কেট স্ক্যান করা হচ্ছে, দয়া করে অপেক্ষা করুন..."):
            signal_count = 0
            progress_bar = st.progress(0)
            total = len(selected_symbols)

            for idx, symbol in enumerate(selected_symbols):
                try:
                    data = yf.download(tickers=symbol, period="2d", interval="5m", progress=False)
                    if len(data) < 50: continue

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

                    # অপ্টিমাইজড বডি ফিল্টার (যাতে পর্যাপ্ত সিগন্যাল মিস না হয়)
                    if total_range == 0 or (body / total_range) < 0.20: continue

                    pair_name = symbol.replace("=X", "")
                    m15_trend = check_m15_trend(symbol)
                    entry_time = get_entry_timing()

                    # 🟢 SNIPER BUY / UP (অপ্টিমাইজড রেঞ্জ: 35 থেকে 70)
                    is_bullish_engulfing = (prev['Close'] < prev['Open'] and close > open_price and close > prev['Open'])
                    
                    if is_bullish_engulfing and close >= (ema * 0.999) and macd > macd_sig:
                        if 35 <= rsi <= 70 and m15_trend != "BEARISH":
                            signal_count += 1
                            msg = (
                                f"<b>🟢 SNIPER BUY SIGNAL 🟢</b>\n\n"
                                f"<b>Pair:</b> {pair_name}\n"
                                f"<b>Timeframe:</b> M5\n"
                                f"📊 <b>Filters:</b> RSI: {rsi:.1f} | M15: {m15_trend}\n"
                                f"⏰ <b>Entry Time:</b> <code>{entry_time}</code>"
                            )
                            st.success(f"🟢 **BUY Signal Found:** {pair_name} | RSI: {rsi:.1f}")
                            send_telegram_msg(msg)

                    # 🔴 SNIPER SELL / DOWN (অপ্টিমাইজড রেঞ্জ: 30 থেকে 65)
                    is_bearish_engulfing = (prev['Close'] > prev['Open'] and close < open_price and close < prev['Close'])
                    
                    if is_bearish_engulfing and close <= (ema * 1.001) and macd < macd_sig:
                        if 30 <= rsi <= 65 and m15_trend != "BULLISH":
                            signal_count += 1
                            msg = (
                                f"<b>🔴 SNIPER SELL SIGNAL 🔴</b>\n\n"
                                f"<b>Pair:</b> {pair_name}\n"
                                f"<b>Timeframe:</b> M5\n"
                                f"📊 <b>Filters:</b> RSI: {rsi:.1f} | M15: {m15_trend}\n"
                                f"⏰ <b>Entry Time:</b> <code>{entry_time}</code>"
                            )
                            st.error(f"🔴 **SELL Signal Found:** {pair_name} | RSI: {rsi:.1f}")
                            send_telegram_msg(msg)

                except Exception as e:
                    pass

                progress_bar.progress((idx + 1) / total)

            st.markdown("---")
            if signal_count > 0:
                st.balloons()
                st.success(f"🎉 স্ক্যান সম্পন্ন! মোট ক্যাচ হয়েছে **{signal_count}টি** হাই-কোয়ালিটি সিগন্যাল এবং টেলিগ্রামে পাঠানো হয়েছে।")
            else:
                st.info("ℹ️ এই মুহূর্তে কন্ডিশন ম্যাচ করেনি। এক মিনিট পর আবার স্ক্যান বাটনে ক্লিক করুন!")
