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

# --- ניטור ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask('')
@app.route('/')
def home(): return f"Bot Control Active | IST: {time.ctime(time.time() + 7200)}"

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
        
        state["last_settings"] = {
            "scan_interval": rows[2][1] if len(rows) > 2 else "60",
            "target_volume": rows[3][1] if len(rows) > 3 else "1000",
            "target_profit": rows[4][1] if len(rows) > 4 else "0.5",
            "keep_alive_interval": rows[5][1] if len(rows) > 5 else "15",
            "exchanges": [ex.strip().lower() for ex in s_sheet.col_values(3)[1:] if ex.strip()],
            "pairs": [p.strip().upper() for p in p_sheet.col_values(1)[1:] if p.strip()]
        }
    except Exception as e: logger.error(f"Cycle Error: {e}")

# --- ניהול בורסות (עמודה C) ומטבעות (Pairs) ---

@bot.message_handler(commands=['add_exchange'])
def add_ex(message):
    try:
        ex_name = message.text.split()[1].lower()
        if ex_name not in ccxt.exchanges:
            return bot.reply_to(message, "❌ בורסה לא נתמכת ב-CCXT.")
        doc = get_sheet_safe()
        doc.worksheet("Settings").append_row(["", "", ex_name], table_range="C1")
        bot.reply_to(message, f"✅ הבורסה `{ex_name}` נוספה בהצלחה.")
        master_cycle()
    except: bot.reply_to(message, "ℹ️ שימוש: `/add_exchange binance` ")

@bot.message_handler(commands=['del_exchange'])
def del_ex(message):
    try:
        ex_name = message.text.split()[1].lower()
        sheet = get_sheet_safe().worksheet("Settings")
        cells = sheet.findall(ex_name)
        for cell in cells:
            if cell.col == 3: # עמודה C
                sheet.update_cell(cell.row, cell.col, "")
                bot.reply_to(message, f"✅ הבורסה `{ex_name}` הוסרה.")
                return master_cycle()
        bot.reply_to(message, "❌ הבורסה לא נמצאה ברשימה.")
    except: bot.reply_to(message, "ℹ️ שימוש: `/del_exchange binance` ")

@bot.message_handler(commands=['add_pair'])
def add_p(message):
    try:
        pair = message.text.split()[1].upper()
        get_sheet_safe().worksheet("pairs").append_row([pair])
        bot.reply_to(message, f"✅ המטבע `{pair}` נוסף לסריקה.")
        master_cycle()
    except: bot.reply_to(message, "ℹ️ שימוש: `/add_pair ETH/USDT` ")

@bot.message_handler(commands=['del_pair'])
def del_p(message):
    try:
        pair = message.text.split()[1].upper()
        sheet = get_sheet_safe().worksheet("pairs")
        cell = sheet.find(pair)
        if cell:
            sheet.delete_rows(cell.row)
            bot.reply_to(message, f"✅ המטבע `{pair}` הוסר מהרשימה.")
            master_cycle()
        else: bot.reply_to(message, "❌ המטבע לא נמצא.")
    except: bot.reply_to(message, "ℹ️ שימוש: `/del_pair BTC/USDT` ")

# --- השוואה והגדרות (זהה לקוד הקודם) ---

@bot.message_handler(commands=['compare'])
def compare_menu(message):
    if not state["last_settings"].get("pairs"): return bot.reply_to(message, "⏳ אין מטבעות.")
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [types.InlineKeyboardButton(p, callback_data=f"c_{p}") for p in state["last_settings"]["pairs"]]
    markup.add(*buttons)
    bot.send_message(message.chat.id, "🪙 **בחר מטבע להשוואה:**", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('c_'))
def handle_comp(call):
    pair = call.data.split('_')[1]
    exchanges = state["last_settings"].get("exchanges", [])
    msg = [f"🔎 **השוואת {pair}:**\n"]
    prices = {}
    for name in exchanges:
        try:
            ex = getattr(ccxt, name)()
            price = ex.fetch_ticker(pair)['last']
            prices[name] = price
            msg.append(f"✅ `{name.upper()}`: {price}")
        except: msg.append(f"❌ `{name.upper()}`: שגיאה")
    if len(prices) > 1:
        diff = ((max(prices.values()) - min(prices.values())) / min(prices.values())) * 100
        msg.append(f"\n📊 פער: `{diff:.2f}%` ")
    bot.edit_message_text("\n".join(msg), call.message.chat.id, call.message.message_id)

@bot.message_handler(commands=['status'])
def cmd_status(message):
    ls = state["last_settings"]
    msg = (f"⚙️ **לוח בקרה:**\n"
           f"⏱ סריקה: `{ls.get('scan_interval')}s` | 📊 ווליום: `${ls.get('target_volume')}`\n"
           f"📈 רווח: `{ls.get('target_profit')}%` | 📢 דיווח: `{ls.get('keep_alive_interval')}m` \n\n"
           f"🏦 בורסות: `{', '.join(ls.get('exchanges', []))}`\n"
           f"🪙 מטבעות: `{', '.join(ls.get('pairs', []))}`")
    bot.reply_to(message, msg)

if __name__ == "__main__":
    master_cycle()
    scheduler = BackgroundScheduler()
    scheduler.add_job(master_cycle, 'interval', seconds=60)
    scheduler.start()
    bot.polling(none_stop=True)
