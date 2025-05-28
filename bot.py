import logging
import requests
import pandas as pd
from datetime import datetime, timedelta
import pytz
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Your API keys
TWELVE_DATA_API_KEY = '210fdbf5fb9a488e819654b9d51b7edf'
TELEGRAM_BOT_TOKEN = '7430804447:AAHWWJXODevJ5JuT-sCujdcxHMYUnFVSn_c'

SUPPORTED_PAIRS = {
    'EURUSD': 'EUR/USD',
    'USDJPY': 'USD/JPY',
    'GBPUSD': 'GBP/USD',
    'AUDUSD': 'AUD/USD',
    'USDCAD': 'USD/CAD',
    'USDCHF': 'USD/CHF',
    'NZDUSD': 'NZD/USD'
}

def fetch_1min_candle_data(symbol: str):
    """Fetch last 50 1-min candles using Twelve Data"""
    url = (
        f'https://api.twelvedata.com/time_series?symbol={symbol}'
        f'&interval=1min&outputsize=50&apikey={TWELVE_DATA_API_KEY}'
    )
    response = requests.get(url)
    if response.status_code != 200:
        logger.error(f"Failed to fetch data for {symbol}")
        return None

    data = response.json()
    if 'values' not in data:
        logger.error(f"No data found for {symbol}: {data}")
        return None

    df = pd.DataFrame(data['values'])
    df = df.rename(columns={
        'datetime': 'timestamp',
        'open': 'open',
        'high': 'high',
        'low': 'low',
        'close': 'close'
    })
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp')
    for col in ['open', 'high', 'low', 'close']:
        df[col] = df[col].astype(float)
    return df

def predict_next_candle(df: pd.DataFrame):
    """Simple heuristic: if close > open -> Bullish, else Bearish"""
    last = df.iloc[-1]
    return "Bullish (Green Candle)" if last['close'] > last['open'] else "Bearish (Red Candle)"

def price_command(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text("Usage: /price EURUSD")
        return

    symbol = context.args[0].upper()
    if symbol not in SUPPORTED_PAIRS:
        update.message.reply_text(f"Unsupported symbol. Try: {', '.join(SUPPORTED_PAIRS.keys())}")
        return

    df = fetch_1min_candle_data(symbol)
    if df is None or df.empty:
        update.message.reply_text("Failed to fetch price data.")
        return

    price = df.iloc[-1]['close']
    update.message.reply_text(f"Current price of {SUPPORTED_PAIRS[symbol]}: {price:.5f}")

def predict_command(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text("Usage: /predict EURUSD")
        return

    symbol = context.args[0].upper()
    if symbol not in SUPPORTED_PAIRS:
        update.message.reply_text(f"Unsupported symbol. Try: {', '.join(SUPPORTED_PAIRS.keys())}")
        return

    df = fetch_1min_candle_data(symbol)
    if df is None or df.empty:
        update.message.reply_text("Failed to fetch data.")
        return

    prediction = predict_next_candle(df)
    last_time = df.iloc[-1]['timestamp']
    next_time = last_time + timedelta(minutes=1)

    # Convert to IST
    utc = pytz.utc
    ist = pytz.timezone('Asia/Kolkata')
    next_ist = utc.localize(next_time).astimezone(ist)
    time_str = next_ist.strftime('%Y-%m-%d %H:%M:%S')

    update.message.reply_text(
        f"Next 1-min candle prediction for {SUPPORTED_PAIRS[symbol]}:\n"
        f"{prediction}\nExpected start time: {time_str} (IST)"
    )

def error_handler(update: object, context: CallbackContext) -> None:
    logger.error(msg="Exception while handling update:", exc_info=context.error)

def main():
    updater = Updater(TELEGRAM_BOT_TOKEN)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("price", price_command))
    dp.add_handler(CommandHandler("predict", predict_command))
    dp.add_error_handler(error_handler)

    updater.start_polling()
    logger.info("Bot started.")
    updater.idle()

if __name__ == '__main__':
    main()
