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

# --- שרת יציבות למניעת קריסת Render ---
app = Flask('')
@app.route('/')
def home(): return "Arbit-Bot Control Panel Online"

def run_web():
    # חילוץ ספרות בלבד מהפורט למקרה שנותרו תווים טקסטואליים
    port_env = os.environ.get('PORT', '10000')
    clean_port = int(re.sub(r'\D', '', port_env))
    app.run(host='0.0.0.0', port=clean_port)

Thread(target=run_web).start()

# --- הגדרות בוט - סנכרון מלא עם ה-Environment שלך ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
SHEET_NAME = "arbit-bot-live_Control_Panel"
bot = telebot.TeleBot(TOKEN)

def get_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_raw = os.environ.get('GSPREAD_CREDENTIALS')
    creds_json = json.loads(creds_raw)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
    return gspread.authorize(creds).open(SHEET_NAME)

last_settings = {}
last_keep_alive_time = 0

def run_logic():
    global last_settings, last_keep_alive_time
    try:
        doc = get_sheet()
        s_sheet = doc.worksheet("Settings")
        p_sheet = doc.worksheet("pairs")
        
        # קריאת נתונים מהאקסל עם המרה בטוחה לערכים נומריים
        current = {
            "interval": int(float(s_sheet.acell('B3').value or 60)),
            "profit": float(s_sheet.acell('B5').value or 0.6),
            "keep_alive": int(float(s_sheet.acell('B6').value or 60)),
            "exchanges": [ex.strip().lower() for ex in s_sheet.col_values(3)[1:] if ex.strip()],
            "pairs": [p.strip().upper() for p in p_sheet.col_values(1)[1:] if p.strip()]
        }

        # זיהוי ועדכון בטלגרם על שינוי הגדרות באקסל
        if last_settings and (current['profit'] != last_settings.get('profit')):
            bot.send_message(CHAT_ID, f"⚙️ **עדכון מהאקסל:** יעד הרווח שונה ל-{current['profit']}%")
        
        last_settings = current

        # דיווח תקופתי (Keep Alive)
        curr_t = time.time()
        if curr_t - last_keep_alive_time >= (current['keep_alive'] * 60):
            bot.send_message(CHAT_ID, f"🔄 דיווח תקופתי: הבוט סורק {len(current['pairs'])} צמדים בבורסות: {', '.join(current['exchanges'])}")
            last_keep_alive_time = curr_t

        # לוגיקת סריקה מלאה (ארביטראז')
        active_ex = {name: getattr(ccxt, name)() for name in current['exchanges'] if hasattr(ccxt, name)}
        for pair in current['pairs']:
            prices = {}
            for name, ex in active_ex.items():
                try: 
                    ticker = ex.fetch_ticker(pair)
                    prices[name] = ticker['last']
                except: continue
            
            if len(prices) > 1:
                low_ex = min(prices, key=prices.get)
                high_ex = max(prices, key=prices.get)
                diff = ((prices[high_ex] - prices[low_ex]) / prices[low_ex]) * 100
                
                if diff >= current['profit']:
                    alert = f"💰 **הזדמנות!** {pair}\n📉 קנייה ({low_ex}): {prices[low_ex]}\n📈 מכירה ({high_ex}): {prices[high_ex]}\n📊 פער: {diff:.2f}%"
                    bot.send_message(CHAT_ID, alert)

    except Exception as e:
        print(f"Loop Error: {e}")

# הפעלה מתוזמנת לבדיקת האקסל וביצוע סריקה
scheduler = BackgroundScheduler()
scheduler.add_job(run_logic, 'interval', seconds=60)
scheduler.start()

if __name__ == "__main__":
    bot.send_message(CHAT_ID, "🚀 הבוט הופעל בהצלחה! השליטה כעת מנוהלת מהאקסל.")
    while True: time.sleep(1)
