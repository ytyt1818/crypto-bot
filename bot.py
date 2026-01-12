import ccxt
import time
import requests
import threading
from flask import Flask
import os

# 1. הגדרת שרת אינטרנט יציב עבור Render
app = Flask(__name__)

@app.route('/')
def home():
    # דף סטטוס פשוט כדי שנוכל לוודא שהבוט חי דרך הדפדפן
    return "✅ Crypto Bot is Live and Scanning!", 200

def run_flask():
    # Render תמיד מצפה לפורט 10000 בתוכנית החינמית
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# 2. משיכת נתונים מאובטחת - מבטיח שלא תחסם ע"י GitHub שוב
TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# 3. הגדרות בורסות ורשימת מטבעות
SYMBOLS = [
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT',
    'ADA/USDT', 'AVAX/USDT', 'DOT/USDT', 'MATIC/USDT', 'LINK/USDT'
]

exchanges = {
    'bybit': ccxt.bybit(),
    'mexc': ccxt.mexc({'options': {'adjustForTimeDifference': True}}),
    'okx': ccxt.okx()
}

def send_telegram_message(message):
    """פונקציה חסינה לשליחת הודעות עם דיווח שגיאות ליומנים"""
    if not TOKEN or not CHAT_ID:
        print("❌ שגיאה קריטית: חסר TOKEN או CHAT_ID בהגדרות ה-Environment!")
        return
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        response = requests.post(url, json=payload, timeout=10)
        # מדפיס ל-Logs ב-Render כדי שנדע בוודאות שההודעה יצאה
        print(f"📡 Telegram API: Status {response.status_code}")
    except Exception as e:
        print(f"❌ שגיאת תקשורת לטלגרם: {e}")

def check_arbitrage():
    """הלולאה המרכזית של סריקת הארביטראז'"""
    print("🚀 הבוט מתחיל סריקה סופית ומאובטחת...")
    
    # הודעת "אני חי" לטלגרם - אם קיבלת אותה, הכל עובד מושלם
    send_telegram_message("🤖 הבוט הופעל בהצלחה! סורק כעת פערים מעל 0.05%.")
    
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
                hi_exch = max(prices, key=prices.get)
                lo_exch = min(prices, key=prices.get)
                
                diff = ((prices[hi_exch] - prices[lo_exch]) / prices[lo_exch]) * 100
                net_diff = diff - 0.2  # הורדת עמלות ממוצעת

                # סף נמוך מאוד כדי לוודא שאתה מקבל הודעות
                if net_diff > 0.05:
                    msg = (f"💰 הזדמנות ארביטראז'!\n"
                           f"מטבע: {symbol}\n"
                           f"קנה ב-{lo_exch}: {prices[lo_exch]}\n"
                           f"מכור ב-{hi_exch}: {prices[hi_exch]}\n"
                           f"רווח נטו מוערך: {net_diff:.2f}%")
                    send_telegram_message(msg)
        
        # המתנה של 30 שניות בין סבבי סריקה
        time.sleep(30)

if __name__ == "__main__":
    # הפעלת שרת האינטרנט בשרשור נפרד כדי שלא יעצור את הסריקה
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    
    # הפעלת הלולאה המרכזית
    check_arbitrage()
