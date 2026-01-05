import ccxt
import time
import requests
import os

# --- הגדרות ---
# הערה: בשרת אמיתי כדאי להשתמש ב-Environment Variables, אבל כרגע נשאיר את זה ככה לנוחותך
TELEGRAM_TOKEN = '8220270822:AAE8KKxTVSPBE77ShcMtENgFuUvxWx0j_qY'
TELEGRAM_CHAT_ID = '-1003576351766'
THRESHOLD = 0.25  # סף התראה לרווח נטו (אחרי עמלות) ב-%
AVG_FEES = 0.2    # עמלה משולבת מוערכת (קנייה + מכירה) ב-%

SYMBOLS = [
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT', 'ADA/USDT', 
    'AVAX/USDT', 'DOT/USDT', 'DOGE/USDT', 'PEPE/USDT', 'SHIB/USDT',
    'NEAR/USDT', 'FET/USDT', 'LINK/USDT', 'MATIC/USDT', 'ARB/USDT',
    'OP/USDT', 'INJ/USDT', 'TIA/USDT', 'RNDR/USDT', 'SUI/USDT'
]

EXCHANGES = ['bybit', 'mexc', 'okx']

# יצירת חיבורים לבורסות
exchange_instances = {name: getattr(ccxt, name)({'enableRateLimit': True}) for name in EXCHANGES}

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except:
        return False

def run_bot():
    print(f"🚀 הבוט הופעל בענן וסורק {len(SYMBOLS)} מטבעות...")
    send_telegram_msg(f"☁️ הבוט הופעל בהצלחה בשרת הענן! סורק כעת {len(SYMBOLS)} נכסים.")
    
    while True:
        for symbol in SYMBOLS:
            prices = {}
            for name, ex in exchange_instances.items():
                try:
                    ticker = ex.fetch_ticker(symbol)
                    prices[name] = ticker['last']
                except:
                    continue
            
            if len(prices) >= 2:
                high_ex = max(prices, key=prices.get)
                low_ex = min(prices, key=prices.get)
                
                gross_spread = ((prices[high_ex] - prices[low_ex]) / prices[low_ex]) * 100
                net_profit = gross_spread - AVG_FEES
                
                if net_profit >= THRESHOLD:
                    msg = (f"💰 הזדמנות רווח! ({symbol})\n"
                           f"📊 רווח נטו: {net_profit:.2f}% (אחרי עמלות)\n"
                           f"📈 הפרש גולמי: {gross_spread:.2f}%\n"
                           f"-----------------------\n"
                           f"🛒 קנה ב-{low_ex.upper()}: {prices[low_ex]}\n"
                           f"💰 מכור ב-{high_ex.upper()}: {prices[high_ex]}")
                    send_telegram_msg(msg)
        
        # המתנה של 30 שניות בין סריקות כדי לא לחסום את ה-IP בשרת החינמי
        time.sleep(30)

if __name__ == "__main__":
    run_bot()
