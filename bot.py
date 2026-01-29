import os
import time
import json
import gspread
import telebot
import ccxt
import re
import logging
import sys
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask
from threading import Thread
from apscheduler.schedulers.background import BackgroundScheduler

# --- הגדרת ניטור מקצועי (Logging) ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# --- שרת Flask ליציבות (Keep-Alive) ---
app = Flask('')
@app.route('/')
def home():
    return f"Bot Status: ACTIVE | System Time: {time.ctime()}"

def run_web():
    port_env = os.environ.get('PORT', '10000')
    clean_port = int(re.sub(r'\D', '', port_env))
    app.run(host='0.0.0.0', port=clean_port)

Thread(target=run_web, daemon=True).start()

# --- הגדרות ליבה ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
SHEET_NAME = "arbit-bot-live_Control_Panel"
bot = telebot.TeleBot(TOKEN, parse_mode='Markdown')

def get_sheet_safe():
    """חיבור חסין עם ניקוי תווים לא חוקיים מה-JSON"""
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_raw = os.environ.get('GSPREAD_CREDENTIALS', '').strip()
        
        if not creds_raw:
            logger.error("GSPREAD_CREDENTIALS is empty in Render settings!")
            return None
            
        # ניקוי JSON במקרה של העתקה לא נקייה
        if not creds_raw.startswith('{'):
            creds_raw = creds_raw[creds_raw.find('{'):creds_raw.rfind('}')+1]

        creds_json = json.loads(creds_raw)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
        return gspread.authorize(creds).open(SHEET_NAME)
    except Exception as e:
        logger.error(f"Google Sheets Auth Error: {e}")
        return None

last_settings = {}
last_keep_alive_time = 0

def master_cycle():
    global last_settings, last_keep_alive_time
    logger.info("--- Starting Master Cycle ---")
    
    doc = get_sheet_safe()
    if not doc:
        logger.warning("Cycle skipped due to connection error.")
        return 

    try:
        s_sheet = doc.worksheet("Settings")
        p_sheet = doc.worksheet("pairs")
        
        current = {
            "interval": int(float(s_sheet.acell('B3').value or 60)),
            "profit": float(s_sheet.acell('B5').value or 0.6),
            "keep_alive": int(float(s_sheet.acell('B6').value or 60)),
            "exchanges": [ex.strip().lower() for ex in s_sheet.col_values(3)[1:] if ex.strip()],
            "pairs": [p.strip().upper() for p in p_sheet.col_values(1)[1:] if p.strip()]
        }

        # ביצוע סריקה
        active_ex = {name: getattr(ccxt, name)() for name in current['exchanges'] if hasattr(ccxt, name)}
        for pair in current['pairs']:
            prices = {}
            for name, ex in active_ex.items():
                try: prices[name] = ex.fetch_ticker(pair)['last']
                except: continue
            
            if len(prices) > 1:
                low_ex, high_ex = min(prices, key=prices.get), max(prices, key=prices.get)
                diff = ((prices[high_ex] - prices[low_ex]) / prices[low_ex]) * 100
                if diff >= current['profit']:
                    bot.send_message(CHAT_ID, f"💰 **הזדמנות!** {pair}\n📊 פער: `{diff:.2f}%` \n{low_ex} ➔ {high_ex}")

        # Keep-Alive
        if (time.time() - last_keep_alive_time) >= (current['keep_alive'] * 60):
            bot.send_message(CHAT_ID, "🔄 **דיווח בוט:** המערכת פועלת וסורקת.")
            last_keep_alive_time = time.time()
            
        last_settings = current
    except Exception as e:
        logger.error(f"Execution Error: {e}")

# --- הפעלה ---
if __name__ == "__main__":
    master_cycle()
    scheduler = BackgroundScheduler()
    scheduler.add_job(master_cycle, 'interval', seconds=60)
    scheduler.start()

    while True:
        try:
            bot.polling(none_stop=True, timeout=40)
        except Exception as e:
            logger.error(f"Telegram Polling restart: {e}")
            time.sleep(10)
