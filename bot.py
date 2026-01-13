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

TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
CHAT_ID = os.environ.get("CHAT_ID", "").strip()

def send_telegram_message(message):
    if not TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=15)
    except:
        pass

def check_arbitrage():
    print(f"[{get_current_time()}] 💎 הבוט התניע! סף רווח נטו חדש: 0.2%")
    send_telegram_message(f"✅ הבוט עודכן לסף רווח של 0.2% נטו (לאחר עמלות). [{get_current_time()}]")
    
    SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT', 'AVAX/USDT', 'DOT/USDT', 'MATIC/USDT', 'LINK/USDT', 'PEPE/USDT']
    exchanges = {
        'Bybit': ccxt.bybit(),
        'MEXC': ccxt.mexc({'options': {'adjustForTimeDifference': True}}),
        'OKX': ccxt.okx()
    }
    
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
                hi_name = max(prices, key=prices.get)
                lo_name = min(prices, key=prices.get)
                price_hi = prices[hi_name]
                price_lo = prices[lo_name]
                
                raw_diff = ((price_hi - price_lo) / price_lo) * 100
                net_diff = raw_diff - 0.2  # עמלות קבועות
                
                # עדכון הסף ל-0.2% נטו ומעלה
                if net_diff >= 0.2:
                    msg = (
                        f"💰 *הזדמנות רווח!* ({symbol})\n"
                        f"📊 *רווח נטו:* {net_diff:.2f}% (אחרי עמלות)\n"
                        f"📈 *הפרש גולמי:* {raw_diff:.2f}%\n"
                        f"-----------------------\n"
                        f"🛒 קנה ב-{lo_name}: {price_lo}\n"
                        f"💰 מכור ב-{hi_name}: {price_hi}\n"
                        f"⏰ שעה: {get_current_time()}"
                    )
                    send_telegram_message(msg)
        
        time.sleep(30)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    check_arbitrage()
