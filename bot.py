import os
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import telebot
import ccxt
from flask import Flask
from threading import Thread
import json

# --- 1. שרת לשמירה על הבוט דולק ב-Render ---
app = Flask('')
@app.route('/')
def home(): return "Bot is Alive"

def run_web():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

Thread(target=run_web).start()

# --- 2. הגדרות וחיבורים ---
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
SHEET_NAME = "arbit-bot-live_Control_Panel"
bot = telebot.TeleBot(TOKEN)

def get_gsheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_json = json.loads(os.environ.get('GSPREAD_CREDENTIALS'))
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME)

# אתחול בורסות
exchanges = {
    'mexc': ccxt.mexc(),
    'bingx': ccxt.bingx(),
    'xt': ccxt.xt(),
    'bitmart': ccxt.bitmart(),
    'kucoin': ccxt.kucoin()
}

last_settings = {}

# --- 3. פונקציות עזר ---
def check_settings(sheet):
    global last_settings
    s_sheet = sheet.worksheet("Settings")
    current = {
        "interval": s_sheet.acell('B3').value,
        "profit": s_sheet.acell('B5').value
    }
    if last_settings and current != last_settings:
        msg = f"⚙️ **שינוי בהגדרות:**\n⏱ אינטרוול: {current['interval']}s\n📈 יעד: {current['profit']}%"
        bot.send_message(CHAT_ID, msg)
    last_settings = current
    return current

def main():
    bot.send_message(CHAT_ID, "🚀 **arbit-bot-live הופעל וסורק!**")
    while True:
        try:
            sheet = get_gsheet()
            settings = check_settings(sheet)
            pairs_sheet = sheet.worksheet("pairs")
            pairs = pairs_sheet.col_values(1)[1:] # מדלג על הכותרת
            
            target_profit = float(settings['profit'])
            
            for pair in pairs:
                prices = {}
                for name, ex in exchanges.items():
                    try:
                        ticker = ex.fetch_ticker(pair)
                        prices[name] = ticker['last']
                    except: continue
                
                if len(prices) > 1:
                    low_ex = min(prices, key=prices.get)
                    high_ex = max(prices, key=prices.get)
                    diff = ((prices[high_ex] - prices[low_ex]) / prices[low_ex]) * 100
                    
                    if diff >= target_profit:
                        msg = f"💰 **הזדמנות נמצאה!**\n💎 צמד: {pair}\n📉 קנייה ב-{low_ex}: {prices[low_ex]}\n📈 מכירה ב-{high_ex}: {prices[high_ex]}\n📊 פער: {diff:.2f}%"
                        bot.send_message(CHAT_ID, msg)
            
            time.sleep(int(settings['interval']))
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()
