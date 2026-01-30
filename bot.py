import telebot
import time
import os
import ccxt
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from flask import Flask

# 1. ניהול לוגים לניטור ב-Render
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# 2. שרת Flask לפתרון בעיית ה-Port ב-Render
app = Flask(__name__)
@app.route('/')
def health(): return "SYSTEM_OPERATIONAL", 200

TOKEN = os.getenv('TELEGRAM_TOKEN')
bot = telebot.TeleBot(TOKEN)

# 3. הגדרות מנוע הסריקה
state = {
    "is_running": True,
    "profit_threshold": 0.3,
    "symbol": "ETH/USDT",
    "chat_id": None,
    "exchanges": ['binance', 'bybit', 'kucoin', 'okx', 'mexc', 'bingx']
}

# אתחול בורסות
exchange_objs = {}
for ex_id in state["exchanges"]:
    try:
        ex_instances = getattr(ccxt, ex_id)({'enableRateLimit': True})
        exchange_objs[ex_id] = ex_instances
    except: logger.error(f"Failed to load {ex_id}")

def get_time():
    return (datetime.utcnow() + timedelta(hours=2)).strftime('%H:%M:%S')

# 4. מנוע הסריקה המקבילי (שולח הודעות לקבוצה)
def arbitrage_engine():
    logger.info("Arbitrage Engine Started...")
    while True:
        if state["is_running"] and state["chat_id"]:
            try:
                def fetch(ex_id):
                    t = exchange_objs[ex_id].fetch_ticker(state["symbol"])
                    return {'id': ex_id, 'bid': t['bid'], 'ask': t['ask'], 'ok': True}
                
                with ThreadPoolExecutor(max_workers=len(exchange_objs)) as exe:
                    results = [r for r in exe.map(fetch, exchange_objs.keys()) if r['ok']]
                
                if len(results) > 1:
                    low = min(results, key=lambda x: x['ask'])
                    high = max(results, key=lambda x: x['bid'])
                    profit = ((high['bid'] - low['ask']) / low['ask']) * 100

                    if profit >= state["profit_threshold"]:
                        msg = (f"💰 *הזדמנות ארביטראז'!*\n\n"
                               f"🪙 מטבע: `{state['symbol']}`\n"
                               f"📊 פער: `{profit:.2f}%`\n"
                               f"🛒 קנה ב-{low['id'].upper()}: `{low['ask']}`\n"
                               f"💎 מכור ב-{high['id'].upper()}: `{high['bid']}`\n"
                               f"⏰ זמן: `{get_time()}`")
                        bot.send_message(state["chat_id"], msg, parse_mode='Markdown')
            except Exception as e:
                logger.error(f"Engine Loop Error: {e}")
        time.sleep(30) # סריקה כל 30 שניות ליציבות

# 5. Handlers אמיתיים לפקודות (לא תשובות סתמיות)
@bot.message_handler(commands=['status'])
def cmd_status(m):
    state["chat_id"] = m.chat.id
    msg = (f"📊 *סטטוס מערכת מבצעי*\n\n"
           f"🕒 זמן ישראל: `{get_time()}`\n"
           f"📈 סף רווח: `{state['profit_threshold']}%`\n"
           f"🏦 בורסות פעילות: `{', '.join(exchange_objs.keys())}`\n"
           f"✅ המנוע סורק ושולח התראות.")
    bot.reply_to(m, msg, parse_mode='Markdown')

@bot.message_handler(commands=['set_profit'])
def cmd_set_profit(m):
    try:
        val = float(m.text.split()[1])
        state['profit_threshold'] = val
        bot.reply_to(m, f"✅ סף הרווח עודכן ל-`{val}%`")
    except:
        bot.reply_to(m, "⚠️ פורמט שגוי. השתמש ב: `/set_profit 0.5`")

@bot.message_handler(commands=['help'])
def cmd_help(m):
    msg = ("📖 *מדריך פקודות:*\n"
           "/status - הפעלת המנוע וקבלת מצב\n"
           "/set_profit - שינוי אחוז הרווח\n"
           "/force_reload - רענון חיבורי בורסות")
    bot.reply_to(m, msg, parse_mode='Markdown')

# 6. הרצה חסינת תקלות
if __name__ == "__main__":
    # הפעלת שרת ה-Port עבור Render
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000))), daemon=True).start()
    # הפעלת מנוע הסריקה
    threading.Thread(target=arbitrage_engine, daemon=True).start()
    
    while True:
        try:
            bot.remove_webhook() # פותר Conflict 409
            bot.infinity_polling(timeout=25)
        except:
            time.sleep(5)
