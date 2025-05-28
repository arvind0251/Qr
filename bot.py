import logging
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
from sklearn.linear_model import LinearRegression
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

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

# Prediction
def predict_next_close(df):
    close_prices = df['close'].values
    if len(close_prices) < 10:
        return None

    X = np.arange(len(close_prices)).reshape(-1, 1)
    y = close_prices

    model = LinearRegression()
    model.fit(X, y)
    next_index = len(close_prices)
    predicted_price = model.predict([[next_index]])[0]
    return predicted_price

# /predict command
async def predict_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        await update.message.reply_text("Use: /predict SYMBOL INTERVAL\nExample: /predict AUDUSD 15min")
        return

    symbol, interval = context.args[0].upper(), context.args[1]
    if symbol not in SUPPORTED_PAIRS or interval not in SUPPORTED_INTERVALS:
        await update.message.reply_text("Invalid symbol or interval.")
        return

    df = fetch_candles(symbol, interval)
    if df is None or df.empty:
        await update.message.reply_text("Failed to fetch data.")
        return

    prediction = predict_next_close(df)
    if prediction is None:
        await update.message.reply_text("Prediction failed (not enough data).")
        return

    last_close = df['close'].iloc[-1]
    direction = "UP" if prediction > last_close else "DOWN"
    next_time = df.index[-1] + timedelta(minutes=int(interval.replace("min", "")))
    ist_time = pytz.utc.localize(next_time).astimezone(pytz.timezone('Asia/Kolkata'))
    ist_str = ist_time.strftime('%Y-%m-%d %H:%M:%S')

    await update.message.reply_text(
        f"{SUPPORTED_PAIRS[symbol]} ({interval})\n"
        f"Last Close: {last_close:.5f}\n"
        f"Predicted Next: {prediction:.5f}\n"
        f"Direction: {direction}\n"
        f"Next Candle (IST): {ist_str}"
    )

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome! Use /predict SYMBOL INTERVAL\nExample: /predict AUDUSD 15min")

# Main function
def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("predict", predict_command))

    app.run_polling()

if __name__ == '__main__':
    main()
