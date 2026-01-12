import ccxt
import time
import requests
import threading
from flask import Flask
import os
from datetime import datetime

app = Flask(__name__)

# פונקציה להפקת זמן נוכחי להודעות (לפי בקשתך)
def get_current_time():
    return datetime.now().strftime("%H:%M:%S")

@app.route('/')
def home():
    return f"Bot is running. Time: {get_current_time()}", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# משיכת המשתנים מה-Environment (הגדרות מהתמונה ב-04:47:03 PM)
TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT', 'AVAX/USDT', 'DOT/USDT', 'MATIC/USDT', 'LINK/USDT']

exchanges = {
    'bybit': ccxt.bybit(),
    'mexc': ccxt.mexc({'options': {'adjustForTimeDifference': True}}),
    'okx': ccxt.okx()
}

def send_telegram_message(message):
    if not TOKEN or not CHAT_ID:
        print(f"[{get_current_time()}] ❌ שגיאה: פרטי הגישה לא נמצאו")
        return
    
    # הוספת השעה להודעה בטלגרם
    timed_message = f"[{get_current_time()}] {message}"
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": timed_message}
    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"[{get_current_time()}] 📡 טלגרם החזיר סטטוס: {response.status_code}")
    except Exception as e:
        print(f"[{get_current_time()}] ❌ שגיאת תקשורת: {e}")

def check_arbitrage():
    print(f"[{get_current_time()}] 🚀 הסורק עלה לאוויר בהצלחה")
    send_telegram_message("הבוט התחבר מחדש ומתחיל סריקה.")
    
    while True:
        for symbol in SYMBOLS:
            prices = {}
            for name, exchange in exchanges.items():
                try:
                    ticker = exchange.fetch_ticker(symbol)
                    prices[name] = ticker['last']
                except:
                    continue

            if len(prices) > 1:
                hi = max(prices, key=prices.get)
                lo = min(prices, key=prices.get)
                diff = ((prices[hi] - prices[lo]) / prices[lo]) * 100
                net_diff = diff - 0.2

                if net_diff > 0.05:
                    msg = (f"💰 הזדמנות נמצאה!\n"
                           f"מטבע: {symbol}\n"
                           f"קנה ב-{lo}: {prices[lo]}\n"
                           f"מכור ב-{hi}: {prices[hi]}\n"
                           f"רווח נטו: {net_diff:.2f}%")
                    send_telegram_message(msg)
        time.sleep(30)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    check_arbitrage()
