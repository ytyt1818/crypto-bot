import ccxt
import time
import requests
import threading
from flask import Flask
import os

# הגדרת אפליקציית Flask
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!", 200

def run_flask():
    # שימוש בפורט 10000 כברירת מחדל עבור Render
    port = int(os.environ.get("PORT", 10000))
    print(f"Flask server starting on port {port}")
    app.run(host='0.0.0.0', port=port)

# --- הגדרות הבוט שלך ---
TOKEN = "7369970928:AAHny6v0fN7V_hWlT7L3z67S8zI-yY3D7oY"
CHAT_ID = "5334659223"

SYMBOLS = [
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT',
    'ADA/USDT', 'AVAX/USDT', 'DOT/USDT', 'MATIC/USDT', 'LINK/USDT',
    'DOGE/USDT', 'SHIB/USDT', 'LTC/USDT', 'BCH/USDT', 'UNI/USDT',
    'NEAR/USDT', 'TIA/USDT', 'APT/USDT', 'OP/USDT', 'ARB/USDT'
]

exchanges = {
    'bybit': ccxt.bybit(),
    'mexc': ccxt.mexc({'options': {'adjustForTimeDifference': True}}),
    'okx': ccxt.okx()
}

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        response = requests.post(url, json=payload)
        print(f"Telegram status: {response.status_code}")
    except Exception as e:
        print(f"Telegram error: {e}")

def check_arbitrage():
    print("Starting scanner loop...")
    # הודעה שחייבת להופיע בטלגרם אם הכל תקין
    send_telegram_message("🤖 מערכת אותחלה: מתחיל סריקה עם סף בדיקה 0.05%")
    
    while True:
        for symbol in SYMBOLS:
            prices = {}
            for name, exchange in exchanges.items():
                try:
                    ticker = exchange.fetch_ticker(symbol)
                    prices[name] = ticker['last']
                except Exception as e:
                    continue

            if len(prices) > 1:
                highest = max(prices, key=prices.get)
                lowest = min(prices, key=prices.get)
                diff = ((prices[highest] - prices[lowest]) / prices[lowest]) * 100
                avg_fees = 0.2
                net_diff = diff - avg_fees

                if net_diff > 0.05:
                    msg = (f"🔍 נמצא פער (סף נמוך): {symbol}\n"
                           f"קנה ב-{lowest}: {prices[lowest]}\n"
                           f"מכור ב-{highest}: {prices[highest]}\n"
                           f"רווח נטו: {net_diff:.2f}%")
                    send_telegram_message(msg)
        
        print("Completed scan, waiting 30 seconds...")
        time.sleep(30)

if __name__ == "__main__":
    # הפעלת Flask בשרשור נפרד
    threading.Thread(target=run_flask, daemon=True).start()
    # התחלת הסריקה מיד
    check_arbitrage()
