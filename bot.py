import telebot
import time
import os
import ccxt
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# הגדרת לוגים מקצועית למניעת ניחושים בתקלות
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- הגדרות בוט וחיבורים ---
TOKEN = os.getenv('TELEGRAM_TOKEN')
bot = telebot.TeleBot(TOKEN)

# מצב מערכת מרכזי - מוגדר מראש עבורך
state = {
    "is_running": True,
    "profit_threshold": 0.3,
    "symbol": "BTC/USDT",
    "target_chat_id": None, 
    "active_exchanges": ['binance', 'bybit', 'kucoin', 'okx', 'mexc', 'bingx']
}

# אתחול אוטומטי של בורסות - ללא צורך במגע יד אדם
exchanges = {}
for ex_id in state["active_exchanges"]:
    try:
        ex_class = getattr(ccxt, ex_id)
        exchanges[ex_id] = ex_class({'enableRateLimit': True})
        logger.info(f"✅ Connection established: {ex_id}")
    except Exception as e:
        logger.error(f"❌ Connection failed: {ex_id} | {e}")

# --- מנוע סריקה מקבילי (High-Performance Architecture) ---

def fetch_single_ticker(ex_id):
    try:
        ticker = exchanges[ex_id].fetch_ticker(state["symbol"])
        return {'id': ex_id, 'bid': ticker['bid'], 'ask': ticker['ask'], 'status': 'success'}
    except:
        return {'id': ex_id, 'status': 'failed'}

def arbitrage_monitor():
    """סורק את כל הבורסות במקביל כל 20 שניות"""
    while True:
        if state["is_running"] and state["target_chat_id"]:
            try:
                with ThreadPoolExecutor(max_workers=len(exchanges)) as executor:
                    results = list(executor.map(fetch_single_ticker, exchanges.keys()))

                valid = [r for r in results if r['status'] == 'success']
                if len(valid) > 1:
                    low = min(valid, key=lambda x: x['ask'])
                    high = max(valid, key=lambda x: x['bid'])
                    profit = ((high['bid'] - low['ask']) / low['ask']) * 100

                    if profit >= state["profit_threshold"]:
                        msg = (f"🚀 *ארביטראז' נמצא!*\n\n"
                               f"💎 נכס: `{state['symbol']}`\n"
                               f"📈 רווח: `{profit:.3f}%` (יעד: {state['profit_threshold']}%)\n\n"
                               f"🛒 קנה (Ask) ב-{low['id'].upper()}: `{low['ask']}`\n"
                               f"💰 מכור (Bid) ב-{high['id'].upper()}: `{high['bid']}`\n\n"
                               f"⏰ זמן: `{datetime.now().strftime('%H:%M:%S')}`")
                        bot.send_message(state["target_chat_id"], msg, parse_mode='Markdown')
            except Exception as e:
                logger.error(f"Engine Error: {e}")
        time.sleep(20)

# --- פקודות שליטה (אין צורך לשנות קוד) ---

@bot.message_handler(commands=['status'])
def cmd_status(message):
    state["target_chat_id"] = message.chat.id
    msg = (f"📊 *מצב בוט ארביטראז'*\n\n"
           f"• סף רווח: `{state['profit_threshold']}%`\n"
           f"• בורסות סרוקות: `{', '.join(exchanges.keys())}`\n"
           f"• סטטוס: `סורק במקביל` ✅\n\n"
           f"התראות יישלחו לכאן באופן אוטומטי.")
    bot.reply_to(message, msg, parse_mode='Markdown')

@bot.message_handler(commands=['set_profit'])
def cmd_set_profit(message):
    try:
        new_val = float(message.text.split()[1])
        state['profit_threshold'] = new_val
        bot.reply_to(message, f"✅ סף הרווח עודכן ל-`{new_val}%`")
    except:
        bot.reply_to(message, "⚠️ פורמט: `/set_profit 0.5`")

# --- הפעלה יציבה ---
if __name__ == "__main__":
    threading.Thread(target=arbitrage_monitor, daemon=True).start()
    while True:
        try:
            bot.remove_webhook()
            bot.infinity_polling(timeout=25)
        except Exception as e:
            logger.error(f"Bot Crash: {e}")
            time.sleep(5)
