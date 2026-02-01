import os
import time
import json
import logging
import telebot
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# הגדרת לוגים למניעת ניחושים
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# משיכת משתני סביבה מה-Render שלך
TOKEN = os.getenv('TELEGRAM_TOKEN')
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
JSON_CREDS = os.getenv('GSPREAD_CREDENTIALS')

bot = telebot.TeleBot(TOKEN)

class ArbitrageArchitect:
    def __init__(self):
        self.client = None
        self.sheet = None

    def connect(self):
        """חיבור מבוסס Credentials עם מנגנון אימות מחדש"""
        try:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds_dict = json.loads(JSON_CREDS)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            self.client = gspread.authorize(creds)
            # פתיחת הלשונית Settings בדיוק כפי שהיא מופיעה באקסל
            self.sheet = self.client.open_by_key(SPREADSHEET_ID).worksheet("Settings")
            return True
        except Exception as e:
            logger.error(f"Critical Connection Error: {e}")
            return False

    def get_data(self):
        """קריאת הנתונים לפי המבנה המדויק: Setting Name (A), Value (B) וכו'"""
        try:
            if not self.sheet: self.connect()
            records = self.sheet.get_all_records()
            
            summary = {
                "params": {},
                "exchanges": [],
                "pairs": []
            }
            
            for row in records:
                # מיפוי עמודה A ו-B
                key = row.get('Setting Name (A)')
                val = row.get('Value (B)')
                if key and val:
                    summary["params"][key] = val
                
                # מיפוי עמודה C (בורסות)
                exch = row.get('Active_Exchanges (C)')
                if exch:
                    summary["exchanges"].append(exch)
                
                # מיפוי עמודה D (צמדים)
                pair = row.get('Pairs (D)')
                if pair:
                    summary["pairs"].append(pair)
            
            return summary
        except Exception as e:
            logger.error(f"Data Fetch Error: {e}")
            return None

# אתחול המערכת
system = ArbitrageArchitect()

@bot.message_handler(commands=['status'])
def handle_status(message):
    data = system.get_data()
    if data:
        msg = "📊 **מצב בוט ארביטראז' - סנכרון מלא**\n\n"
        msg += f"⏱ **אינטרוול:** `{data['params'].get('Scan_Interval_Seconds', 'N/A')}` שניות\n"
        msg += f"💰 **רווח מטרה:** `{data['params'].get('Target_Profit_Percent', 'N/A')}`%\n"
        msg += f"🏛 **בורסות:** {', '.join(data['exchanges']) if data['exchanges'] else 'אין'}\n"
        msg += f"📈 **צמדים:** {', '.join(data['pairs']) if data['pairs'] else 'אין'}\n"
        bot.reply_to(message, msg, parse_mode='Markdown')
    else:
        bot.reply_to(message, "❌ שגיאה: לא ניתן למשוך נתונים מהאקסל. בדוק את ה-Logs ב-Render.")

if __name__ == "__main__":
    logger.info("System Starting...")
    # מנגנון Watchdog למניעת קריסות
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            logger.error(f"Polling Restarting due to: {e}")
            time.sleep(5)
