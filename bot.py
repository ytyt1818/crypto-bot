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

# --- שרת Flask ליציבות (Keep-Alive) למניעת שינה ב-Render/Heroku ---
app = Flask('')
@app.route('/')
def home():
    return f"Bot Status: ACTIVE | IST Time: {time.ctime(time.time() + 7200)}"

def run_web():
    port_env = os.environ.get('PORT', '10000')
    clean_port = int(re.sub(r'\D', '', port_env))
    app.run(host='0.0.0.0', port=clean_port)

Thread(target=run_web, daemon=True).start()

# --- הגדרות ליבה וחיבורים ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
SHEET_NAME = "arbit-bot-live_Control_Panel"
bot = telebot.TeleBot(TOKEN, parse_mode='Markdown')

def get_sheet_safe():
    """חיבור מאובטח לגוגל שיטס עם טיפול בשגיאות"""
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_raw = os.environ.get('GSPREAD_CREDENTIALS', '').strip()
        if not creds_raw: return None
        if not creds_raw.startswith('{'):
            creds_raw = creds_raw[creds_raw.find('{'):creds_raw.rfind('}')+1]
        creds_json = json.loads(creds_raw)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
        return gspread.authorize(creds).open(SHEET_NAME)
    except Exception as e:
        logger.error(f"Google Sheets Connection Error: {e}")
        return None

# משתני מצב גלובליים לשימור זיכרון בין מחזורים
state = {
    "last_settings": {},
    "last_keep_alive": 0
}

def master_cycle():
    """המחזור הראשי של הבוט - בדיקת שינויים וביצוע סריקה"""
    global state
    logger.info("--- Starting Master Cycle ---")
    
    doc = get_sheet_safe()
    if not doc: return 

    try:
        s_sheet = doc.worksheet("Settings")
        p_sheet = doc.worksheet("pairs")
        
        # קריאת כל הפרמטרים מהאקסל (כולל אלו שנוספו)
        current = {
            "keep_alive_minutes": s_sheet.acell('B2').value or "0",
            "scan_interval": s_sheet.acell('B3').value or "60",
            "target_volume": s_sheet.acell('B4').value or "0",
            "target_profit": s_sheet.acell('B5').value or "0.5",
            "keep_alive_interval": s_sheet.acell('B6').value or "60",
            "exchanges": sorted([ex.strip().lower() for ex in s_sheet.col_values(3)[1:] if ex.strip()]),
            "pairs": sorted([p.strip().upper() for p in p_sheet.col_values(1)[1:] if p.strip()])
        }

        # מנגנון דיווח "היה ➔ השתנה"
        if state["last_settings"]:
            changes = []
            ls = state["last_settings"]
            
            # מיפוי תאים בודדים
            checks = [
                ("target_profit", "📈 אחוז רווח", "%"),
                ("keep_alive_interval", "📢 תדירות דיווח", " דקות"),
                ("scan_interval", "⏱ תדר סריקה", " שניות"),
                ("target_volume", "💰 נפח מסחר", "$")
            ]
            
            for key, label, unit in checks:
                if str(current[key]) != str(ls.get(key)):
                    changes.append(f"{label}: השתנה מ-`{ls.get(key)}{unit}` ל-`{current[key]}{unit}`")
            
            # בדיקת שינויים ברשימות (בורסות ומטבעות)
            if current['exchanges'] != ls.get('exchanges'):
                added = set(current['exchanges']) - set(ls.get('exchanges', []))
                removed = set(ls.get('exchanges', [])) - set(current['exchanges'])
                if added: changes.append(f"🏦 בורסות שנוספו: `{', '.join(added)}`")
                if removed: changes.append(f"🏦 בורסות שהוסרו: `{', '.join(removed)}`")

            if current['pairs'] != ls.get('pairs'):
                added_p = set(current['pairs']) - set(ls.get('pairs', []))
                removed_p = set(ls.get('pairs', [])) - set(current['pairs'])
                if added_p: changes.append(f"🪙 מטבעות שנוספו: `{', '.join(added_p)}`")
                if removed_p: changes.append(f"🪙 מטבעות שהוסרו: `{', '.join(removed_p)}`")

            if changes:
                bot.send_message(CHAT_ID, "⚙️ **עדכון הגדרות זוהה:**\n\n" + "\n".join(changes))

        state["last_settings"] = current

        # ביצוע סריקת ארביטראז'
        profit_threshold = float(current['target_profit'])
        active_ex = {name: getattr(ccxt, name)() for name in current['exchanges'] if hasattr(ccxt, name)}
        
        for pair in current['pairs']:
            prices = {}
            for name, ex in active_ex.items():
                try:
                    prices[name] = ex.fetch_ticker(pair)['last']
                except:
                    continue
            
            if len(prices) > 1:
                low_ex, high_ex = min(prices, key=prices.get), max(prices, key=prices.get)
                diff = ((prices[high_ex] - prices[low_ex]) / prices[low_ex]) * 100
                if diff >= profit_threshold:
                    bot.send_message(CHAT_ID, f"💰 **הזדמנות!** *{pair}*\n📊 פער: `{diff:.2f}%` \nקנייה ב-{low_ex} ➔ מכירה ב-{high_ex}")

        # דיווח סטטוס (Keep-Alive) לפי הערך ב-B6
        ka_val = int(float(current['keep_alive_interval']))
        if (time.time() - state["last_keep_alive"]) >= (ka_val * 60):
            bot.send_message(CHAT_ID, f"🔄 **סטטוס מערכת:** סורק {len(current['pairs'])} מטבעות ב-{len(current['exchanges'])} בורסות.")
            state["last_keep_alive"] = time.time()

    except Exception as e:
        logger.error(f"Cycle Execution Error: {e}")

# --- ממשק פקודות טלגרם עם הדרכה (UX) ---

@bot.message_handler(commands=['start', 'help'])
def cmd_help(message):
    help_text = (
        "🤖 **תפריט שליטה Arbit-Bot:**\n\n"
        "📊 `/status` - צפייה בהגדרות הנוכחיות\n"
        "🔍 `/check` - הרצת סריקה ידנית מיידית\n"
        "📈 `/set_profit` <מספר> - עדכון רווח יעד (B5)\n"
        "📢 `/set_report` <דקות> - עדכון תדירות דיווח (B6)\n"
        "🏦 `/add_exchange` <שם> - הוספת בורסה חדשה\n"
        "🪙 `/add_pair` <צמד> - הוספת מטבע למעקב\n\n"
        "💡 **הנחיה:** כדי לדעת איך להשתמש בפקודה, שלח רק את שמה (למשל `/add_pair`) ותקבל הסבר."
    )
    bot.reply_to(message, help_text)

@bot.message_handler(commands=['set_profit'])
def set_profit(message):
    args = message.text.split()
    if len(args) < 2:
        return bot.reply_to(message, "ℹ️ **איך לשנות רווח?**\nשלח את הפקודה ואחריה את המספר.\nדוגמה: `/set_profit 0.7` ")
    try:
        val = args[1]
        get_sheet_safe().worksheet("Settings").update('B5', val)
        bot.reply_to(message, f"✅ בקשה לעדכון רווח ל-`{val}%` נשלחה לאקסל.")
    except Exception as e: bot.reply_to(message, f"⚠️ שגיאה: {e}")

@bot.message_handler(commands=['add_exchange'])
def add_exchange(message):
    args = message.text.split()
    if len(args) < 2:
        return bot.reply_to(message, "ℹ️ **איך להוסיף בורסה?**\nשלח את הפקודה ואחריה את שם הבורסה.\nדוגמה: `/add_exchange binance` ")
    try:
        new_ex = args[1].lower()
        s_sheet = get_sheet_safe().worksheet("Settings")
        s_sheet.append_row(["", "", new_ex], table_range="C1")
        bot.reply_to(message, f"✅ הבורסה `{new_ex}` נוספה לרשימה באקסל.")
    except Exception as e: bot.reply_to(message, f"⚠️ שגיאה: {e}")

@bot.message_handler(commands=['add_pair'])
def add_pair(message):
    args = message.text.split()
    if len(args) < 2:
        return bot.reply_to(message, "ℹ️ **איך להוסיף מטבע?**\nשלח את הפקודה ואחריה את הצמד (גדולות).\nדוגמה: `/add_pair BTC/USDT` ")
    try:
        new_p = args[1].upper()
        p_sheet = get_sheet_safe().worksheet("pairs")
        p_sheet.append_row([new_p])
        bot.reply_to(message, f"✅ המטבע `{new_p}` נוסף לרשימה באקסל.")
    except Exception as e: bot.reply_to(message, f"⚠️ שגיאה: {e}")

@bot.message_handler(commands=['status'])
def cmd_status(message):
    if state["last_settings"]:
        ls = state["last_settings"]
        msg = (f"⚙️ **מצב נוכחי:**\n"
               f"📈 רווח יעד: `{ls['target_profit']}%` \n"
               f"📢 דיווח כל: `{ls['keep_alive_interval']} דק'` \n"
               f"🏦 בורסות: `{', '.join(ls['exchanges'])}` \n"
               f"🪙 מטבעות: `{len(ls['pairs'])}` פעילים.")
        bot.reply_to(message, msg)

@bot.message_handler(commands=['check'])
def manual_check(message):
    bot.send_message(message.chat.id, "🔎 מריץ סריקה ידנית...")
    master_cycle()

# --- הפעלה וניהול לוחות זמנים ---
if __name__ == "__main__":
    master_cycle() # הרצה ראשונית
    
    scheduler = BackgroundScheduler()
    # בדיקת שינויים וביצוע סריקה כל 60 שניות
    scheduler.add_job(master_cycle, 'interval', seconds=60)
    scheduler.start()

    logger.info("Bot is polling...")
    while True:
        try:
            bot.polling(none_stop=True, timeout=40)
        except Exception as e:
            logger.error(f"Polling restarted due to error: {e}")
            time.sleep(10)
