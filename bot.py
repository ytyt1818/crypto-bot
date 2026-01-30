import telebot, time, os, ccxt, threading, logging, gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
from flask import Flask
from concurrent.futures import ThreadPoolExecutor

# הגדרת לוגים מקצועית
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# שרת Flask עבור Render (Port 10000)
app = Flask(__name__)
@app.route('/')
def health(): return "SYSTEM_STABLE_V3", 200

TOKEN = os.getenv('TELEGRAM_TOKEN')
bot = telebot.TeleBot(TOKEN)

# מצב מערכת גלובלי (Global State)
state = {
    "interval": 60,
    "profit": 0.3,
    "exchanges": [],
    "pairs": [],
    "chat_id": os.getenv('MY_CHAT_ID'),
    "is_running": True
}

def get_israel_time():
    return (datetime.utcnow() + timedelta(hours=2)).strftime('%H:%M:%S')

def send_audit_msg(param, old, new, source):
    """שולח דיווח מפורט על כל שינוי פרמטר במערכת"""
    if str(old) != str(new):
        msg = (f"🔄 *עדכון מערכת זוהה!*\n\n"
               f"⚙️ פרמטר: `{param}`\n"
               f"➖ מ-: `{old}`\n"
               f"➕ ל-: `{new}`\n"
               f"🌐 מקור: `{source}`\n"
               f"⏰ זמן: `{get_israel_time()}`")
        if state["chat_id"]:
            try:
                bot.send_message(state["chat_id"], msg, parse_mode='Markdown')
            except Exception as e:
                logger.error(f"Audit send error: {e}")

# --- סנכרון מקיף מול Google Sheets (image_8e633a.png) ---
def sync_all_settings():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name('service_account.json', scope)
        client = gspread.authorize(creds)
        sheet = client.open("CryptoBot_Config").worksheet("settings")
        
        # בדיקת שינוי תדירות (C2)
        new_int = int(sheet.acell('C2').value)
        send_audit_msg("תדירות סריקה", state["interval"], new_int, "Google Sheets")
        state["interval"] = new_int
        
        # בדיקת שינוי רווח (C4)
        new_prof = float(sheet.acell('C4').value)
        send_audit_msg("סף רווח", state["profit"], new_prof, "Google Sheets")
        state["profit"] = new_prof
        
        # בדיקת שינוי בורסות (עמודה E)
        new_exs = [ex.lower().strip() for ex in sheet.col_values(5)[1:] if ex]
        if set(state["exchanges"]) != set(new_exs):
            send_audit_msg("רשימת בורסות", state["exchanges"], new_exs, "Google Sheets")
            state["exchanges"] = new_exs
            
        # עדכון מטבעות פעילים (G/H)
        p_list, s_list = sheet.col_values(7)[1:], sheet.col_values(8)[1:]
        state["pairs"] = [p for p, s in zip(p_list, s_list) if s == 'V']
        
    except Exception as e:
        logger.error(f"Google Sync error: {e}")

# --- מנוע הארביטראז' המקבילי ---
def arbitrage_engine():
    logger.info("Arbitrage Engine Live")
    while True:
        sync_all_settings() # סנכרון ודיווח שינויים בכל סבב
        if state["is_running"] and state["chat_id"] and state["pairs"]:
            try:
                # אתחול בורסות דינמי
                instances = {ex: getattr(ccxt, ex)({'enableRateLimit': True}) for ex in state["exchanges"]}
                
                for symbol in state["pairs"]:
                    def fetch(ex_id):
                        try:
                            t = instances[ex_id].fetch_ticker(symbol)
                            return {'id': ex_id, 'bid': t['bid'], 'ask': t['ask']}
                        except: return None

                    with ThreadPoolExecutor(max_workers=len(instances)) as exe:
                        res = [r for r in exe.map(fetch, instances.keys()) if r]

                    if len(res) > 1:
                        low, high = min(res, key=lambda x: x['ask']), max(res, key=lambda x: x['bid'])
                        profit = ((high['bid'] - low['ask']) / low['ask']) * 100
                        if profit >= state["profit"]:
                            bot.send_message(state["chat_id"], 
                                f"💰 *רווח זוהה! {profit:.2f}%*\n🪙 `{symbol}`\n🛒 {low['id']}: {low['ask']}\n💎 {high['id']}: {high['bid']}", 
                                parse_mode='Markdown')
            except Exception as e: logger.error(f"Engine loop error: {e}")
        time.sleep(state["interval"])

# --- פקודות בוט ---
@bot.message_handler(commands=['set_profit'])
def cmd_set_profit(m):
    args = m.text.split()
    if len(args) > 1:
        try:
            new_val = float(args[1])
            send_audit_msg("סף רווח", state['profit'], new_val, f"User: {m.from_user.first_name}")
            state['profit'] = new_val
            bot.reply_to(m, f"✅ סף הרווח עודכן ל-`{new_val}%` ודווח לקבוצה.")
        except: bot.reply_to(m, "⚠️ הזן מספר תקין.")
    else:
        bot.send_message(m.chat.id, "הקלד ערך חדש, למשל: `/set_profit 0.5`", parse_mode='Markdown')

@bot.message_handler(commands=['status'])
def cmd_status(m):
    state["chat_id"] = m.chat.id
    sync_all_settings()
    msg = (f"📊 *מערכת Arbi-Bot Live*\n\n"
           f"📈 רווח יעד: `{state['profit']}%`\n"
           f"⏱ סריקה כל: `{state['interval']}s`\n"
           f"🏦 בורסות: `{len(state['exchanges'])}` | 🪙 מטבעות: `{len(state['pairs'])}`\n"
           f"✅ המערכת פעילה ומדווחת שינויים.")
    bot.reply_to(m, msg, parse_mode='Markdown')

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000))), daemon=True).start()
    threading.Thread(target=arbitrage_engine, daemon=True).start()
    while True:
        try:
            bot.remove_webhook()
            bot.infinity_polling(timeout=25)
        except: time.sleep(5)
