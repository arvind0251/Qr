import logging
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Configs
TWELVE_API_KEY = 'RFGIIVCI3VGEZ41Y'
TELEGRAM_BOT_TOKEN = '7430804447:AAHWWJXODevJ5JuT-sCujdcxHMYUnFVSn_c'

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

def fetch_candles(symbol: str, interval: str, limit=100):
    url = (
        f"https://api.twelvedata.com/time_series?symbol={SUPPORTED_PAIRS[symbol]}"
        f"&interval={interval}&outputsize={limit}&apikey={TWELVE_API_KEY}"
    )
    response = requests.get(url)
    data = response.json()

    if "values" not in data:
        logger.error(f"Failed to fetch candles: {data}")
        return None

    df = pd.DataFrame(data["values"])
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.sort_values('datetime')
    for col in ['open', 'high', 'low', 'close']:
        df[col] = df[col].astype(float)
    df.set_index('datetime', inplace=True)
    return df

def create_lstm_model():
    model = Sequential([
        LSTM(50, return_sequences=False, input_shape=(10, 1)),
        Dense(1)
    ])
    model.compile(optimizer='adam', loss='mse')
    return model

def prepare_data(df):
    close_prices = df['close'].values.reshape(-1, 1)
    X, y = [], []
    for i in range(len(close_prices) - 10):
        X.append(close_prices[i:i+10])
        y.append(close_prices[i+10])
    return np.array(X), np.array(y)

def predict_next_close(df):
    X, y = prepare_data(df)
    if len(X) == 0:
        return None
    model = create_lstm_model()
    model.fit(X, y, epochs=10, verbose=0)
    latest_sequence = df['close'].values[-10:].reshape(1, 10, 1)
    prediction = model.predict(latest_sequence, verbose=0)[0][0]
    return prediction

def predict_command(update: Update, context: CallbackContext):
    if len(context.args) != 2:
        update.message.reply_text("Use: /predict SYMBOL INTERVAL (e.g., /predict AUDUSD 15min)")
        return

    symbol, interval = context.args[0].upper(), context.args[1]
    if symbol not in SUPPORTED_PAIRS:
        update.message.reply_text(f"Invalid pair. Use one of: {', '.join(SUPPORTED_PAIRS.keys())}")
        return
    if interval not in SUPPORTED_INTERVALS:
        update.message.reply_text(f"Invalid interval. Use: {', '.join(SUPPORTED_INTERVALS)}")
        return

    df = fetch_candles(symbol, interval)
    if df is None or df.empty:
        update.message.reply_text("Failed to fetch data.")
        return

    prediction = predict_next_close(df)
    if prediction is None:
        update.message.reply_text("Prediction failed.")
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
        f"Next Candle Time (IST): {ist_str}"
    )

def start(update: Update, context: CallbackContext):
    update.message.reply_text("Welcome! Use /predict SYMBOL INTERVAL (e.g., /predict AUDUSD 15min)")

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
