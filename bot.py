import os
import time
import json
import gspread
import telebot
from telebot import types
import ccxt
import re
import logging
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask
from threading import Thread
from apscheduler.schedulers.background import BackgroundScheduler

# --- ניהול לוגים לניפוי שגיאות ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask('')
@app.route('/')
def home(): return f"Arbit-Bot Live | IST: {time.ctime(time.time() + 7200)}"

def run_web():
    port = int(re.sub(r'\D', '', os.environ.get('PORT', '10000')))
    app.run(host='0.0.0.0', port=port)

Thread(target=run_web, daemon=True).start()

# --- הגדרות ליבה ---
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
        
        # טעינת הגדרות בצורה בטוחה
        state["last_settings"] = {
            "target_profit": s_sheet.acell('B5').value or "0.5",
            "exchanges": [ex.strip().lower() for ex in s_sheet.col_values(3)[1:] if ex.strip()],
            "pairs": [p.strip().upper() for p in p_sheet.col_values(1)[1:] if p.strip()]
        }
        
        # לוגיקת סריקה (מושמטת כאן לקיצור, זהה לגרסה הקודמת)
        pass
    except Exception as e:
        logger.error(f"Cycle Error: {e}")

# --- טיפול בפקודת ההשוואה (Keyboard) ---

@bot.message_handler(commands=['compare'])
def compare_menu(message):
    logger.info("Compare command triggered")
    if not state["last_settings"] or not state.get("last_settings", {}).get("pairs"):
        # ניסיון טעינה מהיר אם הזיכרון ריק
        master_cycle()
        if not state["last_settings"].get("pairs"):
            return bot.reply_to(message, "❌ לא נמצאו מטבעות בלשונית 'pairs' באקסל.")

    markup = types.InlineKeyboardMarkup(row_width=2)
    pairs = state["last_settings"]["pairs"]
    
    # יצירת כפתורים לכל מטבע
    buttons = []
    for p in pairs:
        buttons.append(types.InlineKeyboardButton(text=f"🪙 {p}", callback_data=f"c_{p}"))
    
    markup.add(*buttons)
    bot.send_message(message.chat.id, "📊 **בחר מטבע להשוואה מהירה:**", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('c_'))
def handle_compare_choice(call):
    pair = call.data.split('_')[1]
    exchanges = state["last_settings"].get("exchanges", [])
    
    bot.answer_callback_query(call.id, f"שואב נתונים עבור {pair}...")
    
    results = [f"🔎 **השוואת מחירים עבור {pair}:**\n"]
    prices = {}
    
    for name in exchanges:
        try:
            ex = getattr(ccxt, name)()
            price = ex.fetch_ticker(pair)['last']
            prices[name] = price
            results.append(f"✅ `{name.upper()}`: {price}")
        except:
            results.append(f"❌ `{name.upper()}`: שגיאה")
            
    if len(prices) > 1:
        diff = ((max(prices.values()) - min(prices.values())) / min(prices.values())) * 100
        results.append(f"\n📊 פער נוכחי: `{diff:.2f}%`")
        
    bot.edit_message_text("\n".join(results), call.message.chat.id, call.message.message_id)

@bot.message_handler(commands=['force_reload'])
def force_reload(message):
    bot.reply_to(message, "🔄 מרענן את כל הנתונים מהאקסל...")
    master_cycle()
    bot.send_message(message.chat.id, "✅ הנתונים סונכרנו בהצלחה.")

if __name__ == "__main__":
    master_cycle()
    scheduler = BackgroundScheduler()
    scheduler.add_job(master_cycle, 'interval', seconds=60)
    scheduler.start()
    bot.polling(none_stop=True)
