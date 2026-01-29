import telebot
import time
import os
import ccxt
import logging
import threading
from datetime import datetime, timedelta
from flask import Flask
from concurrent.futures import ThreadPoolExecutor

# 1. ניהול לוגים מקצועי
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# 2. שרת בריאות למניעת שגיאות Port ב-Render
app = Flask(__name__)
@app.route('/')
def health(): return "SYSTEM_ONLINE", 200

# 3. הגדרות וסנכרון זמן
TOKEN = os.getenv('TELEGRAM_TOKEN')
bot = telebot.TeleBot(TOKEN)

state = {
    "profit_threshold": 0.3,
    "exchanges_list": ['binance', 'bybit', 'kucoin', 'okx', 'mexc', 'bingx'],
    "chat_id": None,
    "symbol": "BTC/USDT"
}

def get_is_time():
    return (datetime.utcnow() + timedelta(hours=2)).strftime('%H:%M:%S')

# 4. מנוע סריקה מקבילי (High Performance)
ex_instances = {}
for ex in state["exchanges_list"]:
    try:
        ex_instances[ex] = getattr(ccxt, ex)({'enableRateLimit': True})
    except: logger.error(f"Failed to init {ex}")

def scan_prices():
    while True:
        if state["chat_id"]:
            try:
                def get_p(id):
                    t = ex_instances[id].fetch_ticker(state["symbol"])
                    return {'id': id, 'bid': t['bid'], 'ask': t['ask'], 'ok': True}
                
                with ThreadPoolExecutor(max_workers=len(ex_instances)) as exe:
                    res = [r for r in exe.map(lambda x: get_p(x), ex_instances.keys()) if r['ok']]
                
                if len(res) > 1:
                    l, h = min(res, key=lambda x: x['ask']), max(res, key=lambda x: x['bid'])
                    p = ((h['bid'] - l['ask']) / l['ask']) * 100
                    if p >= state["profit_threshold"]:
                        msg = f"🚀 *הזדמנות!* {p:.2f}%\n🛒 {l['id']}: {l['ask']}\n💰 {h['id']}: {h['bid']}"
                        bot.send_message(state["chat_id"], msg, parse_mode='Markdown')
            except: pass
        time.sleep(20)

# 5. ניהול פקודות (Interface)
@bot.message_handler(commands=['status', 'start'])
def status(m):
    state["chat_id"] = m.chat.id
    bot.reply_to(m, f"✅ *מערכת באוויר*\nזמן: `{get_is_time()}`\nבורסות: {len(ex_instances)}\nסף: {state['profit_threshold']}%", parse_mode='Markdown')

@bot.message_handler(commands=['set_profit'])
def set_p(m):
    try:
        state['profit_threshold'] = float(m.text.split()[1])
        bot.reply_to(m, f"✅ סף עודכן ל-`{state['profit_threshold']}%`")
    except: pass

# 6. מנגנון הרצה חסין תקלות ו-Conflict
def run_bot():
    while True:
        try:
            bot.remove_webhook() # מנקה את ה-Conflict 409 מיד
            logger.info("Bot logic started - Conflict Cleared")
            bot.infinity_polling(timeout=25, long_polling_timeout=20)
        except Exception as e:
            logger.error(f"Conn Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000))), daemon=True).start()
    threading.Thread(target=scan_prices, daemon=True).start()
    run_bot()
