import ccxt
import time
import requests
import threading
from flask import Flask
import os
from datetime import datetime

app = Flask(__name__)

def get_current_time():
    return datetime.now().strftime("%H:%M:%S")

@app.route('/')
def home():
    return f"Bot is running. Time: {get_current_time()}", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# משיכת המשתנים מה-Environment וניקוי רווחים
TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
CHAT_ID = os.environ.get("CHAT_ID", "").strip()

def send_telegram_message(message):
    # שורה שחייבת להופיע ביומנים כדי להוכיח שהקוד רץ
    print(f"[{get_current_time()}] 🚀 ניסיון שליחה לטלגרם ל-ID: {CHAT_ID}")
    
    if not TOKEN or not CHAT_ID:
        print(f"[{get_current_time()}] ❌ שגיאה: TOKEN או CHAT_ID חסרים בהגדרות Render")
        return
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": f"[{get_current_time()}] {message}"}
    
    try:
        # הגדלת ה-timeout כדי למנוע קריסות
        response = requests.post(url, json=payload, timeout=20)
        # זה הדיווח הקריטי בלוגים
        print(f"[{get_current_time()}] 📡 סטטוס טלגרם: {response.status_code}")
        if response.status_code != 200:
            print(f"[{get_current_time()}] ⚠️ טלגרם סירב לבקשה: {response.text}")
    except Exception as e:
        print(f"[{get_current_time()}] ❌ שגיאת תקשורת חמורה: {e}")

def check_arbitrage():
    # סימן הזיהוי שחיפשת - הוא נמצא ממש כאן בשורה הבאה!
    print(f"[{get_current_time()}] 💎 גרסה סופית - הבוט התניע!")
    
    # הודעה מיידית לבדיקה
    send_telegram_message("✅ הבוט התחבר בהצלחה בגרסה המעודכנת ביותר!")
    
    SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT', 'AVAX/USDT', 'DOT/USDT', 'MATIC/USDT', 'LINK/USDT']
    exchanges = {
        'bybit': ccxt.bybit(),
        'mexc': ccxt.mexc({'options': {'adjustForTimeDifference': True}}),
        'okx': ccxt.okx()
    }
    
    last_heartbeat = time.time()
    while True:
        # הודעת "אני חי" כל 30 דקות
        if time.time() - last_heartbeat >= 1800:
            send_telegram_message("🔄 דיווח חצי-שעתי: הבוט סורק ופעיל.")
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
                hi, lo = max(prices, key=prices.get), min(prices, key=prices.get)
                net_diff = ((prices[hi] - prices[lo]) / prices[lo]) * 100 - 0.2
                if net_diff > 0.05:
                    send_telegram_message(f"💰 פער ב-{symbol}: רווח מוערך {net_diff:.2f}%")
        
        # המתנה של 30 שניות בין סריקות
        time.sleep(30)

if __name__ == "__main__":
    # הרצת Flask ברקע למניעת כיבוי השרת
    threading.Thread(target=run_flask, daemon=True).start()
    # הרצת הבוט
    check_arbitrage()
