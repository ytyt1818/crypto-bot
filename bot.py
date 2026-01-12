import ccxt
import time
import requests
import threading
from flask import Flask
import os

# הגדרת שרת אינטרנט קטן כדי ש-Render יראה שהבוט "חי"
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!", 200

def run_flask():
    # Render מעבירה את הפורט במשתנה סביבה, אם לא קיים נשתמש ב-8080
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- הגדרות הבוט שלך ---
TOKEN = "7369970928:AAHny6v0fN7V_hWlT7L3z67S8zI-yY3D7oY"
CHAT_ID = "5334659223"

# רשימת המטבעות הנוכחית שלך
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
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram error: {e}")

def check_arbitrage():
    # הודעת הפעלה כדי לדעת שהעדכון הצליח
    send_telegram_message("🤖 הבוט עודכן לסף בדיקה של 0.05% וממשיך לסרוק...")
    
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
                highest = max(prices, key=prices.get)
                lowest = min(prices, key=prices.get)
                
                # חישוב הפער באחוזים
                diff = ((prices[highest] - prices[lowest]) / prices[lowest]) * 100
                
                # עמלה משולבת מוערכת (קנייה + מכירה)
                avg_fees = 0.2
                net_diff = diff - avg_fees

                # סף הבדיקה החדש שלך: 0.05%
                if net_diff > 0.05:
                    msg = (f"🔍 בדיקת מערכת (סף נמוך): {symbol}\n"
                           f"קנה ב-{lowest}: {prices[lowest]}\n"
                           f"מכור ב-{highest}: {prices[highest]}\n"
                           f"רווח נטו (אחרי עמלות): {net_diff:.2f}%")
                    send_telegram_message(msg)
        
        print("Scanning in progress... No ports issues.")
        time.sleep(30) # בדיקה כל 30 שניות

if __name__ == "__main__":
    # הפעלת שרת האינטרנט בשרשור נפרד
    threading.Thread(target=run_flask).start()
    # הפעלת סורק הארביטראז'
    check_arbitrage()
