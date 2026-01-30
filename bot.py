import telebot, time, os, ccxt, threading, logging, gspread, json
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
from flask import Flask
from concurrent.futures import ThreadPoolExecutor

# --- 1. הגדרות וניטור (ז) ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
@app.route('/')
def health(): return "SYSTEM_OPERATIONAL", 200

TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
G_CREDS = os.getenv('GSPREAD_CREDENTIALS')
bot = telebot.TeleBot(TOKEN)

# --- 2. מצב מערכת (State) ---
state = {
    "interval": 60, "volume_min": 100, "profit_target": 0.3, "fees": 0.1,
    "exchanges": [], "pairs": [], "last_heartbeat": None,
    "active_instances": {}, "last_sync_time": 0
}

def get_is_time(): return (datetime.utcnow() + timedelta(hours=2))

# --- 3. סנכרון גוגל שיטס (התאמה לתאים C2-C5, E, G, H) ---
def sync_data():
    if time.time() - state["last_sync_time"] < 10: return # הגנת מכסה (ז)
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(G_CREDS), scope)
        client = gspread.authorize(creds)
        sheet = client.open("CryptoBot_Config").worksheet("settings")
        data = sheet.get_all_values()

        # עדכון פרמטרים (C2-C5)
        state["interval"] = max(10, int(data[1][2])) # C2
        state["volume_min"] = float(data[2][2])      # C3 (ד)
        new_profit = float(data[3][2])               # C4
        state["fees"] = float(data[4][2])            # C5 (ה)

        if new_profit != state["profit_target"]:
            bot.send_message(CHAT_ID, f"📝 *עדכון מדיניות:* רווח יעד נטו שונה ל-`{new_profit}%`", parse_mode='Markdown')
            state["profit_target"] = new_profit

        # בורסות ומטבעות (E, G, H)
        state["exchanges"] = [row[4].lower().strip() for row in data[1:] if len(row) > 4 and row[4]]
        state["pairs"] = [row[6] for row in data[1:] if len(row) > 7 and row[7] == 'V']
        
        # אתחול בורסות (ג)
        for ex in state["exchanges"]:
            if ex not in state["active_instances"]:
                try:
                    state["active_instances"][ex] = getattr(ccxt, ex)({'enableRateLimit': True})
                except:
                    bot.send_message(CHAT_ID, f"⚠️ *שגיאת חיבור:* בורסת `{ex}` לא מגיבה.", parse_mode='Markdown')

        state["last_sync_time"] = time.time()
    except Exception as e:
        logger.error(f"Sync error: {e}")

# --- 4. מנוע סריקה וחישוב עמלות (ה) ---
def scan_markets():
    while True:
        try:
            sync_data()
            now = get_is_time()

            # א. דו"ח בוקר (א)
            if now.hour == 8 and now.minute == 0:
                bot.send_message(CHAT_ID, f"☀️ *דו\"ח בוקר אוטומטי:*\nהמערכת סורקת `{len(state['pairs'])}` צמדים ב-`{len(state['exchanges'])}` בורסות.\nרווח יעד נטו: `{state['profit_target']}%`", parse_mode='Markdown')
                time.sleep(60)

            # ב. הודעת דופק (ב)
            heartbeat_interval = state["interval"] * 10 # דוגמה לחישוב לפי C5/תדירות
            if not state["last_heartbeat"] or (now - state["last_heartbeat"]).seconds > 3600:
                bot.send_message(CHAT_ID, f"💓 *Heartbeat:* המערכת פעילה.\nסנכרון אחרון: `{now.strftime('%H:%M')}`", parse_mode='Markdown')
                state["last_heartbeat"] = now

            # ג. לוגיקת הארביטראז'
            if state["pairs"] and state["active_instances"]:
                for symbol in state["pairs"]:
                    def fetch_data(ex_id):
                        try:
                            t = state["active_instances"][ex_id].fetch_ticker(symbol)
                            if t['bidVolume'] * t['bid'] < state["volume_min"]: return None # (ד)
                            return {'id': ex_id, 'bid': t['bid'], 'ask': t['ask']}
                        except: return None

                    with ThreadPoolExecutor(max_workers=5) as executor:
                        results = [r for r in executor.map(fetch_data, state["active_instances"].keys()) if r]

                    if len(results) > 1:
                        low = min(results, key=lambda x: x['ask'])
                        high = max(results, key=lambda x: x['bid'])
                        raw_profit = ((high['bid'] - low['ask']) / low['ask']) * 100
                        net_profit = raw_profit - state["fees"] # (ה)

                        if net_profit >= state["profit_target"]:
                            msg = (f"💰 *הזדמנות רווח נטו! {net_profit:.2f}%*\n"
                                   f"🪙 מטבע: `{symbol}`\n"
                                   f"🛒 קנייה ב-{low['id'].upper()}: `{low['ask']}`\n"
                                   f"💎 מכירה ב-{high['id'].upper()}: `{high['bid']}`\n"
                                   f"📊 (רווח ברוטו: {raw_profit:.2f}% | עמלות: {state['fees']}%)")
                            bot.send_message(CHAT_ID, msg, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Scanner Error: {e}")
            time.sleep(10) # (ו) מניעת לולאת קריסה
        
        time.sleep(state["interval"])

# --- 5. הרצה חסינה (ו) ---
if __name__ == "__main__":
    # שרת בריאות
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()
    
    # ניקוי Webhook (מניעת Conflict 409)
    bot.remove_webhook()
    time.sleep(2)
    
    bot.send_message(CHAT_ID, "🚀 *Master Build V1.0 עלה לאוויר!*\nהמערכת פועלת במצב אוטונומי מלא לפי הגדרות האקסל.", parse_mode='Markdown')
    
    # הפעלת המנוע
    scan_markets()
