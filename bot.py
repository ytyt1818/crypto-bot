import ccxt
import time
import requests
import threading
from flask import Flask
import os
from datetime import datetime

app = Flask(__name__)

def get_current_time():
    # מחזיר שעה בפורמט HH:MM:SS (למשל 18:25:01)
    return datetime.now().strftime("%H:%M:%S")

@app.route('/')
def home():
    return f"Bot is running. Current Time: {get_current_time()}", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

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
        print(f"[{get_current_time()}] ❌ שגיאה: פרטי גישה חסרים")
        return
    
    timed_message = f"[{get_current_time()}] {message}"
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": timed_message}
    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"[{get_current_time()}] 📡 טלגרם: {response.status_code}")
    except Exception as e:
        print(f"[{get_current_time()}] ❌ שגיאה בשליחה: {e}")

def check_arbitrage():
    print(f"[{get_current_time()}] 🚀 הבוט הופעל")
    
    # הודעה ראשונה מיד עם העלייה (כפי שביקשת)
    send_telegram_message("✅ הבוט עלה לאוויר ומתחיל בסריקה.")
    
    last_heartbeat = time.time()
    
    while True:
        # בדיקה אם עברו 30 דקות (1800 שניות) מאז הדיווח האחרון
        if time.time() - last_heartbeat >= 1800:
            send_telegram_message("🔄 דיווח תקופתי: הבוט פעיל וסורק.")
            last_heartbeat = time.time()

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
                    msg = (f"💰 פער נמצא!\n"
                           f"מטבע: {symbol}\n"
                           f"קנה ב-{lo}: {prices[lo]}\n"
                           f"מכור ב-{hi}: {prices[hi]}\n"
                           f"רווח נטו: {net_diff:.2f}%")
                    send_telegram_message(msg)
        
        time.sleep(30)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    check_arbitrage()
