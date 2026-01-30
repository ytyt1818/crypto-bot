import telebot, time, os, ccxt, threading, logging, gspread, json
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
from flask import Flask
from concurrent.futures import ThreadPoolExecutor

# הגדרת לוגים בסיסית ונקייה
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# שרת Flask למניעת קריסת Render
app = Flask(__name__)
@app.route('/')
def health(): return "LIVE", 200

# משיכת פרמטרים מה-Environment
TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
G_CREDS = os.getenv('GSPREAD_CREDENTIALS')
bot = telebot.TeleBot(TOKEN)

# מצב מערכת
state = {
    "interval": 60,
    "profit": 0.3,
    "exchanges": [],
    "pairs": [],
    "is_running": True
}

def get_israel_time():
    return (datetime.utcnow() + timedelta(hours=2)).strftime('%H:%M:%S')

# פונקציית סנכרון מותאמת בדיוק לטבלה שלך (C2, C4, E, G, H)
def sync_logic():
    try:
        if not G_CREDS: return
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(G_CREDS), scope)
        client = gspread.authorize(creds)
        sheet = client.open("CryptoBot_Config").worksheet("settings")
        data = sheet.get_all_values()

        # עדכון תדירות ורווח (C2 ו-C4)
        new_int = int(data[1][2])
        new_prof = float(data[3][2])
        
        # דיווח על שינוי ברווח אם קרה
        if new_prof != state["profit"]:
            bot.send_message(CHAT_ID, f"🔄 *עדכון רווח:* `{new_prof}%`", parse_mode='Markdown')
            state["profit"] = new_prof
        
        state["interval"] = max(10, new_int)
        
        # עדכון בורסות (עמודה E) ומטבעות (עמודה G/H)
        state["exchanges"] = [row[4].lower().strip() for row in data[1:] if len(row) > 4 and row[4]]
        state["pairs"] = [row[6] for row in data[1:] if len(row) > 7 and row[7] == 'V']
        
        logger.info(f"Synced: {len(state['pairs'])} pairs")
    except Exception as e:
        logger.error(f"Sync error: {e}")

# מנוע הארביטראז' - שולח הודעות על רווחים
def arbitrage_engine():
    while True:
        sync_logic()
        if state["pairs"] and state["exchanges"] and CHAT_ID:
            try:
                # אתחול בורסות
                instances = {ex: getattr(ccxt, ex)({'enableRateLimit': True}) for ex in state["exchanges"] if hasattr(ccxt, ex)}
                
                for symbol in state["pairs"]:
                    def fetch(ex_id):
                        try:
                            t = instances[ex_id].fetch_ticker(symbol)
                            return {'id': ex_id, 'bid': t['bid'], 'ask': t['ask']}
                        except: return None

                    with ThreadPoolExecutor(max_workers=len(instances)) as exe:
                        res = [r for r in exe.map(fetch, instances.keys()) if r]

                    if len(res) > 1:
                        low = min(res, key=lambda x: x['ask'])
                        high = max(res, key=lambda x: x['bid'])
                        profit = ((high['bid'] - low['ask']) / low['ask']) * 100
                        
                        if profit >= state["profit"]:
                            msg = (f"💰 *הזדמנות רווח! {profit:.2f}%*\n"
                                   f"🪙 מטבע: `{symbol}`\n"
                                   f"🛒 קנה ב-{low['id'].upper()}: `{low['ask']}`\n"
                                   f"💎 מכור ב-{high['id'].upper()}: `{high['bid']}`")
                            bot.send_message(CHAT_ID, msg, parse_mode='Markdown')
            except Exception as e:
                logger.error(f"Engine error: {e}")
        
        time.sleep(state["interval"])

if __name__ == "__main__":
    # 1. שרת בריאות
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()
    
    # 2. ניקוי חיבורים קודמים (פותר שגיאת 409)
    bot.remove_webhook()
    time.sleep(2)
    
    # 3. הודעת הפעלה מיידית
    if CHAT_ID:
        bot.send_message(CHAT_ID, f"🚀 *המערכת פעילה! סורקת ומנטרת שינויים.*\nזמן: `{get_israel_time()}`", parse_mode='Markdown')
    
    # 4. הפעלת המנוע
    threading.Thread(target=arbitrage_engine, daemon=True).start()
    
    # 5. פולינג לבוט
    bot.infinity_polling(timeout=25)
