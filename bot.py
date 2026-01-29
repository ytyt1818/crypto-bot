import os
import time
import json
import gspread
import telebot
from telebot import types # לייבוא כפתורים
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
        
        current = {
            "target_profit": rows[4][1] if len(rows) > 4 else "0.5",
            "keep_alive_interval": rows[5][1] if len(rows) > 5 else "15",
            "exchanges": [ex.strip().lower() for ex in s_sheet.col_values(3)[1:] if ex.strip()],
            "pairs": [p.strip().upper() for p in p_sheet.col_values(1)[1:] if p.strip()]
        }
        state["last_settings"] = current

        # סריקה אוטומטית להזדמנויות
        profit_threshold = float(current['target_profit'])
        for pair in current['pairs']:
            prices = {}
            for ex_name in current['exchanges']:
                try:
                    exchange = getattr(ccxt, ex_name)()
                    prices[ex_name] = exchange.fetch_ticker(pair)['last']
                except: continue
            
            if len(prices) > 1:
                low_ex, high_ex = min(prices, key=prices.get), max(prices, key=prices.get)
                diff = ((prices[high_ex] - prices[low_ex]) / prices[low_ex]) * 100
                if diff >= profit_threshold:
                    bot.send_message(CHAT_ID, f"💰 **הזדמנות!**\n\n🪙 מטבע: `{pair}`\n📊 פער: `{diff:.2f}%` \n🛒 {low_ex.upper()} ➔ 💎 {high_ex.upper()}")

    except Exception as e:
        logger.error(f"Cycle Error: {e}")

# --- פקודות תפריט דינמיות ---

@bot.message_handler(commands=['compare'])
def compare_menu(message):
    """פותח תפריט כפתורים לבחירת מטבע מהאקסל"""
    if not state["last_settings"] or not state["last_settings"]["pairs"]:
        return bot.reply_to(message, "⏳ טוען נתונים, נסה שוב בעוד דקה.")
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    pairs = state["last_settings"]["pairs"]
    
    buttons = [types.InlineKeyboardButton(p, callback_data=f"comp_{p}") for p in pairs]
    markup.add(*buttons)
    
    bot.send_message(message.chat.id, "🪙 **בחר מטבע להשוואת מחירים:**", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('comp_'))
def handle_compare_choice(call):
    """מטפל בלחיצה על כפתור המטבע"""
    pair = call.data.replace('comp_', '')
    exchanges = state["last_settings"]["exchanges"]
    
    bot.answer_callback_query(call.id, f"בודק את {pair}...")
    msg = f"🔎 **השוואת מחירים עבור {pair}:**\n\n"
    
    prices = {}
    for name in exchanges:
        try:
            ex = getattr(ccxt, name)()
            price = ex.fetch_ticker(pair)['last']
            prices[name] = price
            msg += f"✅ `{name.upper()}`: {price}\n"
        except:
            msg += f"❌ `{name.upper()}`: אין נתונים\n"
            
    if len(prices) > 1:
        low_ex, high_ex = min(prices, key=prices.get), max(prices, key=prices.get)
        diff = ((prices[high_ex] - prices[low_ex]) / prices[low_ex]) * 100
        msg += f"\n📊 פער נוכחי: `{diff:.2f}%`"
        
    bot.edit_message_text(msg, call.message.chat.id, call.message.message_id)

@bot.message_handler(commands=['status'])
def cmd_status(message):
    if state["last_settings"]:
        ls = state["last_settings"]
        msg = (f"⚙️ **מצב נוכחי:**\n"
               f"📈 רווח יעד: `{ls['target_profit']}%` \n"
               f"🏦 בורסות: `{', '.join(ls['exchanges'])}` \n"
               f"🪙 מטבעות: `{', '.join(ls['pairs'])}` ")
        bot.reply_to(message, msg)

if __name__ == "__main__":
    master_cycle()
    scheduler = BackgroundScheduler()
    scheduler.add_job(master_cycle, 'interval', seconds=60)
    scheduler.start()
    bot.polling(none_stop=True)
