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

ALPHA_VANTAGE_API_KEY = 'RFGIIVCI3VGEZ41Y'  # Tumhari API key
TELEGRAM_BOT_TOKEN = '7430804447:AAHWWJXODevJ5JuT-sCujdcxHMYUnFVSn_c'  # Apna Telegram bot token yahan daalo

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
    """Fetch latest 50 15-min candles for given forex pair from Alpha Vantage"""
    url = (
        'https://www.alphavantage.co/query?function=FX_INTRADAY'
        f'&from_symbol={symbol[:3]}&to_symbol={symbol[3:]}'
        '&interval=15min&outputsize=compact'
        f'&apikey={ALPHA_VANTAGE_API_KEY}'
    )
    response = requests.get(url)
    if response.status_code != 200:
        logger.error(f"Failed to fetch data for {symbol}, status code: {response.status_code}")
        return None
    data = response.json()
    if 'Time Series FX (15min)' not in data:
        logger.error(f"No candle data found for {symbol}: {data}")
        return None

    time_series = data['Time Series FX (15min)']
    df = pd.DataFrame.from_dict(time_series, orient='index')
    df = df.rename(columns={
        '1. open': 'open',
        '2. high': 'high',
        '3. low': 'low',
        '4. close': 'close'
    })
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    df = df.tail(50)
    for col in ['open', 'high', 'low', 'close']:
        df[col] = df[col].astype(float)
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

    last_time = df.index[-1]  # UTC time of last candle
    next_candle_time_utc = last_time + timedelta(minutes=15)

    # Convert UTC to IST timezone
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
