import logging
import requests
import pandas as pd
from datetime import timedelta
import pytz
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

TWELVE_API_KEY = '210fdbf5fb9a488e819654b9d51b7edf'  # Tumhari Twelve Data API key
TELEGRAM_BOT_TOKEN = '7430804447:AAHWWJXODevJ5JuT-sCujdcxHMYUnFVSn_c'  # Telegram bot token

SUPPORTED_PAIRS = {
    'AUDCAD': 'AUD/CAD',
    'AUDUSD': 'AUD/USD',
    'CADJPY': 'CAD/JPY',
    'EURUSD': 'EUR/USD',
    'GBPAUD': 'GBP/AUD',
    'USDJPY': 'USD/JPY',
    'AUDJPY': 'AUD/JPY'
}

def fetch_candle_data(symbol: str):
    """Fetch latest 50 15-min candles for given forex pair from Twelve Data"""
    twelve_symbol = SUPPORTED_PAIRS[symbol]
    url = (
        f"https://api.twelvedata.com/time_series?symbol={twelve_symbol}"
        f"&interval=15min&outputsize=50&apikey={TWELVE_API_KEY}"
    )
    response = requests.get(url)
    if response.status_code != 200:
        logger.error(f"Failed to fetch data for {symbol}, status code: {response.status_code}")
        return None
    data = response.json()
    if "values" not in data:
        logger.error(f"No candle data found for {symbol}: {data}")
        return None

    df = pd.DataFrame(data["values"])
    df = df.rename(columns={
        'open': 'open',
        'high': 'high',
        'low': 'low',
        'close': 'close',
        'datetime': 'datetime'
    })
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.sort_values('datetime')
    for col in ['open', 'high', 'low', 'close']:
        df[col] = df[col].astype(float)
    df = df.set_index('datetime')
    return df

def simple_candle_prediction(df: pd.DataFrame):
    """Predict next candle bullish or bearish using simple heuristic"""
    last_candle = df.iloc[-1]
    if last_candle['close'] > last_candle['open']:
        return "Bullish (Green Candle)"
    else:
        return "Bearish (Red Candle)"

def price_command(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text("Please provide a symbol, e.g., /price AUDUSD")
        return
    symbol = context.args[0].upper()
    if symbol not in SUPPORTED_PAIRS:
        update.message.reply_text(f"Unsupported symbol. Supported: {', '.join(SUPPORTED_PAIRS.keys())}")
        return

    df = fetch_candle_data(symbol)
    if df is None or df.empty:
        update.message.reply_text("Failed to fetch price data. Try again later.")
        return

    last_candle = df.iloc[-1]
    price = last_candle['close']
    update.message.reply_text(f"Current price of {SUPPORTED_PAIRS[symbol]} is {price:.5f}")

def predict_command(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text("Please provide a symbol, e.g., /predict AUDUSD")
        return
    symbol = context.args[0].upper()
    if symbol not in SUPPORTED_PAIRS:
        update.message.reply_text(f"Unsupported symbol. Supported: {', '.join(SUPPORTED_PAIRS.keys())}")
        return

    df = fetch_candle_data(symbol)
    if df is None or df.empty:
        update.message.reply_text("Failed to fetch candle data. Try again later.")
        return

    prediction = simple_candle_prediction(df)
    last_time = df.index[-1]
    next_candle_time_utc = last_time + timedelta(minutes=15)

    utc_zone = pytz.utc
    ist_zone = pytz.timezone('Asia/Kolkata')
    next_candle_time_utc = utc_zone.localize(next_candle_time_utc)
    next_candle_time_ist = next_candle_time_utc.astimezone(ist_zone)

    next_candle_time_str = next_candle_time_ist.strftime('%Y-%m-%d %H:%M:%S')

    update.message.reply_text(
        f"Next 15-min candle prediction for {SUPPORTED_PAIRS[symbol]}:\n"
        f"{prediction}\n"
        f"Expected start time: {next_candle_time_str} (IST)"
    )

def error_handler(update: object, context: CallbackContext) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

def main():
    updater = Updater(TELEGRAM_BOT_TOKEN)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("price", price_command))
    dispatcher.add_handler(CommandHandler("predict", predict_command))
    dispatcher.add_error_handler(error_handler)

    updater.start_polling()
    logger.info("Bot started. Listening for commands...")
    updater.idle()

if __name__ == '__main__':
    main()
