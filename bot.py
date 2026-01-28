import os
import time
import json
import gspread
import telebot
import ccxt
import re
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask
from threading import Thread
from apscheduler.schedulers.background import BackgroundScheduler

# --- שרת יציבות ---
app = Flask('')
@app.route('/')
def home(): return "Arbit-Bot Logic Online"

def run_web():
    port_env = os.environ.get('PORT', '10000')
    clean_port = int(re.sub(r'\D', '', port_env))
    app.run(host='0.0.0.0', port=clean_port)

Thread(target=run_web).start()

# --- הגדרות בוט ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
SHEET_NAME = "arbit-bot-live_Control_Panel"
bot = telebot.TeleBot(TOKEN, parse_mode='Markdown')

def get_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_raw = os.environ.get('GSPREAD_CREDENTIALS')
    creds_json = json.loads(creds_raw)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
    return gspread.authorize(creds).open(SHEET_NAME)

last_settings = {}
last_keep_alive_time = 0

def update_from_excel(manual=False):
    global last_settings
    try:
        doc = get_sheet()
        s_sheet = doc.worksheet("Settings")
        p_sheet = doc.worksheet("pairs")
        
        current = {
            "interval": int(float(s_sheet.acell('B3').value or 60)),
            "profit": float(s_sheet.acell('B5').value or 0.6),
            "keep_alive": int(float(s_sheet.acell('B6').value or 60)),
            "exchanges": [ex.strip().lower() for ex in s_sheet.col_values(3)[1:] if ex.strip()],
            "pairs": [p.strip().upper() for p in p_sheet.col_values(1)[1:] if p.strip()]
        }

        if last_settings and not manual:
            changes = []
            if current['profit'] != last_settings.get('profit'):
                changes.append(f"📈 רווח יעד: {last_settings.get('profit')}% ➔ {current['profit']}%")
            if current['interval'] != last_settings.get('interval'):
                changes.append(f"⏱ זמן סריקה: {last_settings.get('interval')}s ➔ {current['interval']}s")
            
            if changes:
                bot.send_message(CHAT_ID, "⚙️ **שינוי זוהה באקסל:**\n" + "\n".join(changes))
        
        last_settings = current
        return True
    except Exception as e:
        print(f"Excel Error: {e}")
        return False

def run_arbitrage_scan():
    global last_keep_alive_time
    if not last_settings: return
    
    try:
        curr_t = time.time()
        if curr_t - last_keep_alive_time >= (last_settings['keep_alive'] * 60):
            bot.send_message(CHAT_ID, f"🔄 **דיווח סטטוס:** סורק {len(last_settings['pairs'])} צמדים.")
            last_keep_alive_time = curr_t

        active_ex = {name: getattr(ccxt, name)() for name in last_settings['exchanges'] if hasattr(ccxt, name)}
        for pair in last_settings['pairs']:
            prices = {}
            for name, ex in active_ex.items():
                try: prices[name] = ex.fetch_ticker(pair)['last']
                except: continue
            
            if len(prices) > 1:
                low_ex, high_ex = min(prices, key=prices.get), max(prices, key=prices.get)
                diff = ((prices[high_ex] - prices[low_ex]) / prices[low_ex]) * 100
                if diff >= last_settings['profit']:
                    bot.send_message(CHAT_ID, f"💰 **הזדמנות!** {pair}\n📊 פער: {diff:.2f}%\n⬇️ {low_ex} ➔ ⬆️ {high_ex}")
    except Exception as e: print(f"Scan Error: {e}")

# --- ניהול פקודות טלגרם ---

@bot.message_handler(commands=['start', 'help'])
def send_help(message):
    help_text = (
        "🤖 **מדריך פקודות - Arbit-Bot:**\n\n"
        "📊 `/status` \n"
        "→ *מציג את ההגדרות שטעונות בבוט כרגע (רווח, בורסות, מטבעות).*\n\n"
        "🔍 `/check` \n"
        "→ *מריץ סריקה מיידית של כל הבורסות ומוציא דוח הזדמנויות עכשיו.*\n\n"
        "💰 `/prices` \n"
        "→ *בודק ומציג את המחיר הנוכחי של כל המטבעות שלך בכל בורסה בנפרד.*\n\n"
        "❓ `/help` \n"
        "→ *מציג את תפריט העזרה הזה עם הסבר על כל פקודה.*"
    )
    bot.reply_to(message, help_text)

@bot.message_handler(commands=['status'])
def send_status(message):
    update_from_excel(manual=True)
    status_msg = (
        f"⚙️ **סטטוס הגדרות נוכחיות:**\n\n"
        f"📈 **רווח יעד:** `{last_settings['profit']}%` \n"
        f"⏱ **זמן סריקה:** `{last_settings['interval']}s` \n"
        f"🏦 **בורסות:** `{', '.join(last_settings['exchanges'])}` \n"
        f"🪙 **מטבעות:** `{', '.join(last_settings['pairs'])}` \n"
        f"📢 **דיווח כל:** `{last_settings['keep_alive']} דקות`"
    )
    bot.send_message(message.chat.id, status_msg)

@bot.message_handler(commands=['check'])
def manual_check(message):
    bot.send_message(message.chat.id, "🔎 מפעיל סריקה ידנית מקיפה... אנא המתן.")
    run_arbitrage_scan()

@bot.message_handler(commands=['prices'])
def show_prices(message):
    msg = "💰 **מחירי שוק בזמן אמת:**\n"
    active_ex = {name: getattr(ccxt, name)() for name in last_settings['exchanges'] if hasattr(ccxt, name)}
    for pair in last_settings['pairs']:
        msg += f"\n🪙 *{pair}:*\n"
        for name, ex in active_ex.items():
            try:
                p = ex.fetch_ticker(pair)['last']
                msg += f"• {name.capitalize()}: `{p}`\n"
            except: msg += f"• {name.capitalize()}: `לא זמין`\n"
    bot.send_message(message.chat.id, msg)

# --- ניהול תזמון (Scheduler) ---
scheduler = BackgroundScheduler()
scheduler.add_job(update_from_excel, 'interval', seconds=30)
scheduler.add_job(run_arbitrage_scan, 'interval', seconds=60)
scheduler.start()

if __name__ == "__main__":
    update_from_excel()
    # שליחת הודעת הפעלה עם הסבר קצר
    bot.send_message(CHAT_ID, "🚀 **הבוט עלה לאוויר!**\nשלח `/help` כדי לראות את רשימת הפקודות וההסברים.")
    bot.polling(none_stop=True)
