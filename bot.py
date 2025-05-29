import logging
import requests
import pandas as pd
from datetime import datetime, timedelta
import pytz
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# API keys
POLYGON_API_KEY = 'ZTppfs8VAEPg6EPEhB0_8xtbzC0mjT0m'
TELEGRAM_BOT_TOKEN = '7430804447:AAHWWJXODevJ5JuT-sCujdcxHMYUnFVSn_c'  # Replace with your real bot token

SUPPORTED_PAIRS = {
    'AUDCAD': 'C:AUDCAD',
    'AUDCHF': 'C:AUDCHF',
    'AUDJPY': 'C:AUDJPY',
    'AUDNZD': 'C:AUDNZD',
    'AUDUSD': 'C:AUDUSD',
    'CADCHF': 'C:CADCHF',
    'CHFJPY': 'C:CHFJPY',
    'EURAUD': 'C:EURAUD',
    'EURCAD': 'C:EURCAD',
    'EURCHF': 'C:EURCHF',
    'EURGBP': 'C:EURGBP',
    'EURJPY': 'C:EURJPY',
    'EURUSD': 'C:EURUSD',
    'GBPAUD': 'C:GBPAUD',
    'GBPCAD': 'C:GBPCAD',
    'GBPCHF': 'C:GBPCHF',
    'GBPJPY': 'C:GBPJPY',
    'GBPUSD': 'C:GBPUSD',
    'NZDCAD': 'C:NZDCAD',
    'NZDCHF': 'C:NZDCHF',
    'NZDJPY': 'C:NZDJPY',
    'NZDUSD': 'C:NZDUSD',
    'USDCAD': 'C:USDCAD',
    'USDCHF': 'C:USDCHF',
    'USDJPY': 'C:USDJPY',
}

def fetch_1min_candle_data(pair: str):
    url = f"https://api.polygon.io/v2/aggs/ticker/{pair}/range/1/minute/50/2023-12-01/2023-12-01?adjusted=true&sort=desc&limit=50&apiKey={POLYGON_API_KEY}"
    response = requests.get(url)
    if response.status_code != 200:
        logger.error("Failed to fetch data")
        return None
    data = response.json()
    if 'results' not in data:
        logger.error("No results in data")
        return None

    df = pd.DataFrame(data['results'])
    df['timestamp'] = pd.to_datetime(df['t'], unit='ms')
    df = df.rename(columns={
        'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close'
    })
    df = df[['timestamp', 'open', 'high', 'low', 'close']]
    df = df.sort_values('timestamp')
    return df

def predict_next_candle(df: pd.DataFrame):
    last = df.iloc[-1]
    return "Bullish (Green Candle)" if last['close'] > last['open'] else "Bearish (Red Candle)"

def price_command(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text("Usage: /price AUDCAD")
        return

    symbol = context.args[0].upper()
    if symbol not in SUPPORTED_PAIRS:
        update.message.reply_text(f"Supported pairs: {', '.join(SUPPORTED_PAIRS.keys())}")
        return

    df = fetch_1min_candle_data(SUPPORTED_PAIRS[symbol])
    if df is None:
        update.message.reply_text("Failed to fetch price.")
        return

    price = df.iloc[-1]['close']
    update.message.reply_text(f"Current price for {symbol}: {price:.5f}")

def predict_command(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text("Usage: /predict AUDCAD")
        return

    symbol = context.args[0].upper()
    if symbol not in SUPPORTED_PAIRS:
        update.message.reply_text(f"Supported pairs: {', '.join(SUPPORTED_PAIRS.keys())}")
        return

    df = fetch_1min_candle_data(SUPPORTED_PAIRS[symbol])
    if df is None:
        update.message.reply_text("Failed to fetch data.")
        return

    prediction = predict_next_candle(df)
    last_time = df.iloc[-1]['timestamp']
    next_time = last_time + timedelta(minutes=1)

    ist = pytz.timezone('Asia/Kolkata')
    next_ist = next_time.astimezone(ist)
    time_str = next_ist.strftime('%Y-%m-%d %H:%M:%S')

    update.message.reply_text(
        f"Next 1-min candle prediction for {symbol}:\n"
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
