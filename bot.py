import os
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import telebot
import requests
import json
from flask import Flask
from threading import Thread

# --- חלק 1: שרת דמה לשמירה על הבוט דולק ב-Render ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is running"

def run_web():
    # Render מחפש תשובה בפורט שהגדרנו (10000)
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

# הפעלת השרת ברקע
Thread(target=run_web).start()

# --- חלק 2: הגדרות הבוט והאקסל ---
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
SHEET_NAME = "arbit-bot-live_Control_Panel"
bot = telebot.TeleBot(TOKEN)

# פונקציה להתחברות לאקסל
def get_gsheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_json = json.loads(os.environ.get('GSPREAD_CREDENTIALS'))
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME)

# משתנים למעקב אחרי שינויים
last_settings = {}

def check_for_settings_changes(sheet):
    global last_settings
    try:
        settings_sheet = sheet.worksheet("Settings")
        current_settings = {
            "interval": settings_sheet.acell('B3').value,
            "profit": settings_sheet.acell('B5').value
        }
        
        if last_settings and current_settings != last_settings:
            msg = f"⚙️ **זוהה שינוי בהגדרות:**\n"
            msg += f"⏱ זמן סריקה: {last_settings['interval']} -> {current_settings['interval']} שניות\n"
            msg += f"📈 רווח יעד: {last_settings['profit']}% -> {current_settings['profit']}%"
            bot.send_message(os.environ.get('TELEGRAM_CHAT_ID'), msg)
        
        last_settings = current_settings
        return current_settings
    except Exception as e:
        print(f"Error checking settings: {e}")
        return None

# --- חלק 3: הלולאה הראשית ---
def main():
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    bot.send_message(chat_id, "🚀 **arbit-bot-live הופעל!**\nהבוט מחובר ושומר על חיבור יציב.")
    
    while True:
        try:
            sheet = get_gsheet()
            settings = check_for_settings_changes(sheet)
            
            # כאן תבוא לוגיקת הסריקה של הבורסות (mexc, bingx וכו')
            print("Sensing markets...")
            
            # המתנה לפי האקסל (B3)
            wait_time = int(settings['interval']) if settings else 60
            time.sleep(wait_time)
            
        except Exception as e:
            print(f"Error in main loop: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()
