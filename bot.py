import telebot
import time
import os
import ccxt
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# הגדרת לוגים קריטית לניטור מרחוק
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# הגדרות בוט ומשתני סביבה
TOKEN = os.getenv('TELEGRAM_TOKEN')
MY_CHAT_ID = os.getenv('MY_CHAT_ID') # מומלץ להוסיף ב-Render כדי לקבל התראות אוטומטיות
bot = telebot.TeleBot(TOKEN)

# אתחול בורסות - CCXT
EXCHANGES_CONFIG = {
    'binance': ccxt.binance({'enableRateLimit': True}),
    'bybit': ccxt.bybit({'enableRateLimit': True}),
    'kucoin': ccxt.kucoin({'enableRateLimit': True}),
    'okx': ccxt.okx({'enableRateLimit': True})
}

def fetch_exchange_data(ex_id, symbol="BTC/USDT"):
    """פונקציה לסריקת בורסה בודדת - מבודדת לחלוטין למניעת קריסת המערכת"""
    try:
        ex_instance = EXCHANGES_CONFIG[ex_id]
        ticker = ex_instance.fetch_ticker(symbol)
        return {
            'id': ex_id,
            'bid': ticker['bid'], # מחיר מכירה (הכי גבוה שקונה מוכן לשלם)
            'ask': ticker['ask'], # מחיר קנייה (הכי נמוך שמוכר מוכן לקבל)
            'last': ticker['last'],
            'status': 'success'
        }
    except Exception as e:
        logger.error(f"Failed to fetch {ex_id}: {str(e)}")
        return {'id': ex_id, 'status': 'failed'}

def arbitrage_engine(symbol="BTC/USDT", threshold=0.15):
    """מנוע הארביטראז' המרכזי - סריקה מקבילית וחישוב פערים"""
    logger.info(f"--- Arbitrage Engine Started for {symbol} ---")
    while True:
        try:
            # 1. סריקה במקביל של כל הבורסות
            with ThreadPoolExecutor(max_workers=len(EXCHANGES_CONFIG)) as executor:
                results = list(executor.map(lambda ex: fetch_exchange_data(ex, symbol), EXCHANGES_CONFIG.keys()))

            # 2. סינון תוצאות תקינות
            valid = [r for r in results if r['status'] == 'success']
            
            if len(valid) > 1:
                # מציאת הבורסה הזולה ביותר (לקנייה - Ask) והיקרה ביותר (למכירה - Bid)
                low_ex = min(valid, key=lambda x: x['ask'])
                high_ex = max(valid, key=lambda x: x['bid'])
                
                # חישוב פער באחוזים
                profit_margin = ((high_ex['bid'] - low_ex['ask']) / low_ex['ask']) * 100

                if profit_margin > threshold:
                    msg = (
                        f"⚠️ *הזדמנות ארביטראז' זוהתה!*\n\n"
                        f"💎 נכס: `{symbol}`\n"
                        f"📈 רווח פוטנציאלי: `{profit_margin:.3f}%`\n\n"
                        f"🛒 קנייה (Ask) ב-{low_ex['id'].upper()}: `{low_ex['ask']}`\n"
                        f"💰 מכירה (Bid) ב-{high_ex['id'].upper()}: `{high_ex['bid']}`\n\n"
                        f"⏰ זמן: `{datetime.now().strftime('%H:%M:%S')}`"
                    )
                    logger.info(f"ARBITRAGE FOUND: {profit_margin:.3f}%")
                    # שליחה לכל מי ששלח הודעה לבוט או ל-ID המוגדר
                    if MY_CHAT_ID:
                        bot.send_message(MY_CHAT_ID, msg, parse_mode='Markdown')

            time.sleep(15) # קצב סריקה מקצועי
        except Exception as e:
            logger.error(f"Critical error in engine: {e}")
            time.sleep(10)

@bot.message_handler(commands=['status'])
def status_handler(message):
    global MY_CHAT_ID
    MY_CHAT_ID = message.chat.id # מעדכן את ה-ID כדי שתקבל התראות
    bot.reply_to(message, "✅ *מערכת ה-Arbitrage Pro באוויר*\nסורק כעת: Binance, Bybit, KuCoin, OKX.\nהתראות יישלחו לכאן אוטומטית.", parse_mode='Markdown')

def start_bot():
    """הפעלת הבוט עם הגנות מלאות"""
    while True:
        try:
            logger.info("Initializing connection - Cleaning Webhooks...")
            bot.remove_webhook()
            logger.info("Bot is Live. Waiting for /status to identify user...")
            bot.infinity_polling(timeout=25, long_polling_timeout=20)
        except Exception as e:
            logger.error(f"Bot Polling Crash: {e}. Restarting in 5s...")
            time.sleep(5)

if __name__ == "__main__":
    # הפעלת המנוע ב-Thread נפרד
    threading.Thread(target=arbitrage_engine, daemon=True).start()
    # הפעלת הבוט
    start_bot()
