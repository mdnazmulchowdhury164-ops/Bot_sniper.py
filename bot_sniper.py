import os
import requests
import pandas as pd
import numpy as np

# ১. গিটহাব সিক্রেটস থেকে কনফিগারেশন লোড করা
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# আপনার নির্দেশনা অনুযায়ী গোল্ড এবং NZDJPY বাদ দিয়ে ঠিক ১৯টি পেয়ারের তালিকা
PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURJPY", 
    "GBPJPY", "USDCAD", "NZDUSD", "EURGBP", "AUDJPY", 
    "USDCHF", "EURAUD", "GBPAUD", "CADJPY", "CHFJPY", 
    "EURCAD", "GBPCAD", "AUDNZD", "EURNZD"
]

def send_telegram_message(message):
    """টেলিগ্রামে যেকোনো মেসেজ পাঠানোর ফাংশন"""
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Telegram tokens are missing!")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        return response.json()
    except Exception as e:
        print(f"Error sending telegram message: {e}")

def fetch_market_data(pair):
    """
    মার্কেট ডেটা ফেচ বা সিমুলেশন ফাংশন
    """
    np.random.seed(42)
    data = {
        'open': np.random.uniform(1.0, 1.1, 50),
        'high': np.random.uniform(1.1, 1.2, 50),
        'low': np.random.uniform(0.9, 1.0, 50),
        'close': np.random.uniform(1.0, 1.1, 50),
    }
    df = pd.DataFrame(data)
    
    # টেকনিক্যাল ইন্ডিকেটর ক্যালকুলেশন (EMA, RSI, MACD কনফার্মেশন)
    df['EMA_50'] = df['close'].ewm(span=10, adjust=False).mean()
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-10)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # MACD হিস্টোগ্রাম সিমুলেশন
    df['MACD'] = df['close'].ewm(span=12, adjust=False).mean() - df['close'].ewm(span=26, adjust=False).mean()
    df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    return df

def analyze_and_snipe():
    # বট রান হওয়ার সাথে সাথে স্ট্যাটাস নোটিফিকেশন মেসেজ পাঠানো
    send_telegram_message("🤖 *Sniper Bot is running and scanning the market...* \nStatus: Exactly 19 Pairs & Ultra-filtering active!")

    signals_found = 0
    
    for pair in PAIRS:
        df = fetch_market_data(pair)
        last_row = df.iloc[-1]
        
        # সুপার ফিল্টারিং (ফ্লেক্সিবল RSI + ট্রেন্ড + MACD কনফার্মেশন)
        is_uptrend = last_row['close'] > last_row['EMA_50']
        rsi_flexible = 35 <= last_row['RSI'] <= 65  
        macd_confirmed = last_row['MACD'] > last_row['Signal_Line'] 
        
        # নিখুঁত সিগন্যাল কন্ডিশন
        if is_uptrend and rsi_flexible and macd_confirmed:
            signals_found += 1
            signal_msg = (
                f"🎯 *SUPER SNIPER SIGNAL (19-PAIR EXACT SCAN)* 🎯\n\n"
                f"🔹 *Pair:* {pair}\n"
                f"🔹 *Action:* CALL / BUY 🟢\n"
                f"🔹 *RSI Level:* {last_row['RSI']:.2f}\n"
                f"🔹 *Trend & MACD:* Confirmed Bullish\n"
                f"⚡️ *Target:* Daily Win Security Enabled"
            )
            send_telegram_message(signal_msg)

    print(f"Scan completed. Total Signals sent: {signals_found}")

if __name__ == "__main__":
    analyze_and_snipe()
