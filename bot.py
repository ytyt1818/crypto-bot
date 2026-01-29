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

# --- הגדרות ניטור ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# --- שרת Flask ליציבות ---
app = Flask('')
@app.route('/')
def home(): return f"Bot Active | IST: {time.ctime(time.time() + 7200)}"

def run_web():
    port = int(re.sub(r'\D', '', os.environ.get('PORT', '10000')))
    app.run(host='0.0.0.0', port=port)

Thread(target=run_web, daemon=True).start()

# --- ליבה ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
SHEET_NAME = "arbit-bot-live_Control_Panel"
bot = telebot.TeleBot(TOKEN, parse_mode='Markdown')

def get_sheet_safe():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_raw = os.environ.get('GSPREAD_CREDENTIALS', '').strip()
        creds_json = json.loads(creds_raw)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
        return gspread.authorize(creds).open(SHEET_NAME)
    except Exception as e:
        logger.error(f"Sheet Auth Error: {e}")
        return None

state = {"last_settings": {}, "last_keep_alive": 0}

def master_cycle():
    global state
    doc = get_sheet_safe()
    if not doc: return 

    try:
        s_sheet = doc.worksheet("Settings")
        p_sheet = doc.worksheet("pairs")
        rows = s_sheet.get_all_values()
        if len(rows) < 6: return 
        
        current = {
            "target_profit": rows[4][1],
            "keep_alive_interval": rows[5][1],
            "exchanges": sorted(list(set([ex.strip().lower() for ex in s_sheet.col_values(3)[1:] if ex.strip()]))),
            "pairs": sorted(list(set([p.strip().upper() for p in p_sheet.col_values(1)[1:] if p.strip()])))
        }

        # דיווח שינויים
        if state["last_settings"] and current["target_profit"]:
            changes = []
            ls = state["last_settings"]
            if str(current["target_profit"]) != str(ls.get("target_profit")):
                changes.append(f"📈 אחוז רווח: השתנה מ-`{ls.get('target_profit')}%` ל-`{current['target_profit']}%` ")
            if changes:
                bot.send_message(CHAT_ID, "⚙️ **עדכון מערכת:**\n\n" + "\n".join(changes))

        state["last_settings"] = current

        # סריקת ארביטראז' בפועל
        profit_threshold = float(current['target_profit'])
        active_ex = {name: getattr(ccxt, name)() for name in current['exchanges'] if hasattr(ccxt, name)}
        
        for pair in current['pairs']:
            prices = {}
            for name, ex in active_ex.items():
                try:
                    prices[name] = ex.fetch_ticker(pair)['last']
                except: continue
            
            if len(prices) > 1:
                low_ex, high_ex = min(prices, key=prices.get), max(prices, key=prices.get)
                diff = ((prices[high_ex] - prices[low_ex]) / prices[low_ex]) * 100
                if diff >= profit_threshold:
                    bot.send_message(CHAT_ID, f"💰 **הזדמנות!** *{pair}*\n📊 פער: `{diff:.2f}%` \nקנייה ב-{low_ex} ➔ מכירה ב-{high_ex}")

        # דיווח סטטוס
        ka_val = int(float(current['keep_alive_interval']))
        if (time.time() - state["last_keep_alive"]) >= (ka_val * 60):
            bot.send_message(CHAT_ID, f"🔄 **סטטוס:** סורק {len(current['pairs'])} מטבעות ב-{len(current['exchanges'])} בורסות.")
            state["last_keep_alive"] = time.time()

    except Exception as e: logger.error(f"Cycle Error: {e}")

# --- פקודות בדיקה ושליטה ---

@bot.message_handler(commands=['test_prices'])
def test_prices(message):
    """בדיקה ידנית שהחיבור לבורסות מושך מחירים"""
    if not state["last_settings"]:
        return bot.reply_to(message, "⏳ המתן לסיום סבב סריקה ראשון...")
    
    msg = "🔎 **בדיקת חיבור לבורסות:**\n\n"
    pair = state["last_settings"]["pairs"][0]
    exchanges = state["last_settings"]["exchanges"]
    
    for name in exchanges:
        try:
            ex = getattr(ccxt, name)()
            price = ex.fetch_ticker(pair)['last']
            msg += f"✅ {name}: `{price}`\n"
        except Exception as e:
            msg += f"❌ {name}: שגיאה במשיכת מחיר\n"
    
    bot.reply_to(message, msg)

@bot.message_handler(commands=['set_profit'])
def set_profit(message):
    try:
        val = message.text.split()[1]
        get_sheet_safe().worksheet("Settings").update_acell('B5', val)
        bot.reply_to(message, f"⏳ מעדכן רווח ל-`{val}%`...")
        time.sleep(2)
        master_cycle()
    except: bot.reply_to(message, "ℹ️ שימוש: `/set_profit 0.5` ")

@bot.message_handler(commands=['status'])
def cmd_status(message):
    if state["last_settings"]:
        ls = state["last_settings"]
        msg = (f"⚙️ **מצב נוכחי:**\n"
               f"📈 רווח יעד: `{ls['target_profit']}%` \n"
               f"🏦 בורסות: `{', '.join(ls['exchanges'])}` \n"
               f"🪙 מטבעות: `{len(ls['pairs'])}` ")
        bot.reply_to(message, msg)

if __name__ == "__main__":
    master_cycle()
    scheduler = BackgroundScheduler()
    scheduler.add_job(master_cycle, 'interval', seconds=60)
    scheduler.start()
    while True:
        try: bot.polling(none_stop=True, timeout=40)
        except: time.sleep(10)
