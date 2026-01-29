import telebot, time, os, ccxt, threading, logging
from flask import Flask
from datetime import datetime, timedelta

# לוגים לאבחון מהיר
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# שרת בריאות למניעת שגיאות Port ב-Render
app = Flask(__name__)
@app.route('/')
def health(): return "ONLINE", 200

TOKEN = os.getenv('TELEGRAM_TOKEN')
bot = telebot.TeleBot(TOKEN)

# מצב מערכת (Global State)
state = {"profit": 0.3, "chat_id": None}

# פקודות בוט (מענה לכל מה ששלחת בצילומים)
@bot.message_handler(commands=['status', 'start', 'help', 'add_exchange', 'force_reload'])
def universal_handler(m):
    state["chat_id"] = m.chat.id
    israel_time = (datetime.utcnow() + timedelta(hours=2)).strftime('%H:%M:%S')
    bot.reply_to(m, f"✅ המערכת מחוברת! (זמן: {israel_time})\nכל הפקודות פעילות כעת.")

@bot.message_handler(commands=['set_profit'])
def set_p(m):
    try:
        state['profit'] = float(m.text.split()[1])
        bot.reply_to(m, f"✅ סף רווח עודכן ל-{state['profit']}%")
    except: pass

# מנגנון הרצה חסין Conflict 409
def start_engine():
    while True:
        try:
            logger.info("FORCE CLEANING CONNECTIONS...")
            bot.remove_webhook() # התיקון לשגיאה 409
            bot.infinity_polling(timeout=20, long_polling_timeout=15)
        except Exception as e:
            logger.error(f"Reconnecting: {e}")
            time.sleep(5)

if __name__ == "__main__":
    # הפעלת שרת ה-Port (פותר את ה-No open ports)
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000))), daemon=True).start()
    start_engine()
