import logging
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
from sklearn.linear_model import LinearRegression
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# API Keys
TWELVE_API_KEY = 'RFGIIVCI3VGEZ41Y'
TELEGRAM_BOT_TOKEN = '7430804447:AAHWWJXODevJ5JuT-sCujdcxHMYUnFVSn_c'

# Config
SUPPORTED_PAIRS = {
    'AUDCAD': 'AUD/CAD',
    'AUDUSD': 'AUD/USD',
    'CADJPY': 'CAD/JPY',
    'EURUSD': 'EUR/USD',
    'GBPAUD': 'GBP/AUD',
    'USDJPY': 'USD/JPY',
    'AUDJPY': 'AUD/JPY'
}
SUPPORTED_INTERVALS = ['1min', '5min', '15min']

WINDOW_SIZE = 10  # Sliding window size

# Fetch data
def fetch_candles(symbol: str, interval: str, limit=100):
    url = (
        f"https://api.twelvedata.com/time_series?symbol={SUPPORTED_PAIRS[symbol]}"
        f"&interval={interval}&outputsize={limit}&apikey={TWELVE_API_KEY}"
    )
    response = requests.get(url)
    data = response.json()
    if "values" not in data:
        logger.error(f"Fetch error: {data}")
        return None

    df = pd.DataFrame(data["values"])
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.sort_values('datetime')
    df['close'] = df['close'].astype(float)
    df.set_index('datetime', inplace=True)
    return df

# Prepare sliding window data
def prepare_data(close_prices, window=WINDOW_SIZE):
    X, y = [], []
    for i in range(len(close_prices) - window):
        X.append(close_prices[i:i+window])
        y.append(close_prices[i+window])
    return np.array(X), np.array(y)

# Predict next close price using Linear Regression on sliding window
def predict_next_close(df):
    close_prices = df['close'].values
    if len(close_prices) < WINDOW_SIZE + 1:
        return None

    X, y = prepare_data(close_prices)
    model = LinearRegression()
    model.fit(X, y)
    latest_window = close_prices[-WINDOW_SIZE:].reshape(1, -1)
    predicted_price = model.predict(latest_window)[0]
    return predicted_price

# Bot command handler
def predict_command(update: Update, context: CallbackContext):
    if len(context.args) != 2:
        update.message.reply_text("Use: /predict SYMBOL INTERVAL\nExample: /predict AUDUSD 15min")
        return

    symbol, interval = context.args[0].upper(), context.args[1]
    if symbol not in SUPPORTED_PAIRS or interval not in SUPPORTED_INTERVALS:
        update.message.reply_text("Invalid symbol or interval.")
        return

    df = fetch_candles(symbol, interval)
    if df is None or df.empty:
        update.message.reply_text("Failed to fetch data.")
        return

    prediction = predict_next_close(df)
    if prediction is None:
        update.message.reply_text("Prediction failed (not enough data).")
        return

    last_close = df['close'].iloc[-1]
    direction = "UP" if prediction > last_close else "DOWN"
    next_time = df.index[-1] + timedelta(minutes=int(interval.replace("min", "")))
    ist_time = pytz.utc.localize(next_time).astimezone(pytz.timezone('Asia/Kolkata'))
    ist_str = ist_time.strftime('%Y-%m-%d %H:%M:%S')

    update.message.reply_text(
        f"{SUPPORTED_PAIRS[symbol]} ({interval})\n"
        f"Last Close: {last_close:.5f}\n"
        f"Predicted Next: {prediction:.5f}\n"
        f"Direction: {direction}\n"
        f"Next Candle (IST): {ist_str}"
    )

# /start command
def start(update: Update, context: CallbackContext):
    update.message.reply_text("Welcome! Use /predict SYMBOL INTERVAL\nExample: /predict AUDUSD 15min")

# Main runner
def main():
    updater = Updater(TELEGRAM_BOT_TOKEN)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("predict", predict_command))

    updater.start_polling()
    logger.info("Bot started")
    updater.idle()

if __name__ == '__main__':
    main()
