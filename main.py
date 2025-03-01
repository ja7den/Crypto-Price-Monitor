import math
import ccxt
import json
import time
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

telegram_handle = '@CryptoPriceAlertMonitor'

def load_config(path='config.json'):
    with open(path, 'r') as f:
        return json.load(f)

def get_price(exchange, symbol):
    try:
        ticker = exchange.fetch_ticker(symbol)
        return ticker['last']
    except Exception as e:
        print(f"Error fetching ticker for {symbol}: {e}")
        return None

def round_to_threshold(current_price, threshold):
    factor = math.floor(current_price / threshold)
    return factor * threshold

def decimal_places_from_threshold(threshold):
    s = str(threshold)
    if '.' in s:
        return len(s.split('.')[1])
    return 0

def format_rounded_price(rounded_price, decimals):
    return f"${rounded_price:,.{decimals}f}"


def draw_text_with_outline(draw, position, text, font, fill, outline, outline_width=2):
    x, y = position

    for dx in range(-outline_width, outline_width+1):
        for dy in range(-outline_width, outline_width+1):
            if dx != 0 or dy != 0:
                draw.text((x+dx, y+dy), text, font=font, fill=outline)

    draw.text(position, text, font=font, fill=fill)


def load_font(font_size):

    try:
        return ImageFont.truetype("trebucbd.ttf", font_size)
    except IOError:
        try:
            return ImageFont.truetype("arialbd.ttf", font_size)
        except IOError:
            return ImageFont.load_default()

def create_banner_image(symbol, display_price, telegram_handle, decimals):

    background = Image.open("image.png").convert("RGBA")
    img = background.copy()
    draw = ImageDraw.Draw(img)


    price_font = load_font(60)       
    symbol_font = load_font(28)      


    dark_grey = (255, 255, 255)         
    outline_color = (50,50,50)  

    price_text = format_rounded_price(display_price, decimals)


    symbol_text = f"{symbol.upper()}/USDT | {telegram_handle}"


    center_x = background.width // 2
    center_y = background.height // 2

    bbox_price = draw.textbbox((0, 0), price_text, font=price_font)
    price_w = bbox_price[2] - bbox_price[0]
    price_h = bbox_price[3] - bbox_price[1]
    price_x = center_x - price_w // 2
    price_y = center_y - (price_h // 2) - 20  

    draw_text_with_outline(draw, (price_x, price_y), price_text, price_font, fill=dark_grey, outline=outline_color, outline_width=2)

    bbox_symbol = draw.textbbox((0, 0), symbol_text, font=symbol_font)
    symbol_w = bbox_symbol[2] - bbox_symbol[0]
    symbol_h = bbox_symbol[3] - bbox_symbol[1]
    symbol_x = center_x - symbol_w // 2
    symbol_y = price_y + price_h + 10  

    draw_text_with_outline(draw, (symbol_x, symbol_y), symbol_text, symbol_font, fill=dark_grey, outline=outline_color, outline_width=2)

    return img

def send_telegram_photo(bot_token, chat_id, image):

    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    bio = BytesIO()
    image.save(bio, format='PNG')
    bio.seek(0)
    files = {"photo": ("image.png", bio, "image/png")}
    data = {"chat_id": chat_id}
    try:
        response = requests.post(url, data=data, files=files)
        if response.status_code != 200:
            print("Failed to send Telegram photo:", response.text)
    except Exception as e:
        print("Error sending Telegram photo:", e)

def send_discord_photo(webhook_url, image):

    bio = BytesIO()
    image.save(bio, format='PNG')
    bio.seek(0)
    files = {"file": ("image.png", bio, "image/png")}
    try:
        response = requests.post(webhook_url, files=files)
        if response.status_code not in (200, 204):
            print("Failed to send Discord photo:", response.text)
    except Exception as e:
        print("Error sending Discord photo:", e)


def get_default_threshold(price):

    if price < 1:
        return 0.05
    elif price < 5:
        return 0.1
    elif price < 50:
        return 0.5
    elif price < 500:
        return 5
    elif price < 5000:
        return 50
    elif price < 50000:
        return 500
    else:
        return price * 0.005


def main():
    config = load_config("config.json")
    telegram_bot_token = config.get("telegram_bot_token")
    telegram_channel_id = config.get("telegram_channel_id")
    discord_webhook = config.get("discord_webhook")
    tokens_config = config.get("tokens", [])


    exchange = ccxt.binance()


    tokens = {}
    for token in tokens_config:
        symbol = token.get("symbol")
        symbol_pair = symbol if "/" in symbol else f"{symbol.upper()}/USDT"

        current_price = get_price(exchange, symbol_pair)
        if current_price is None:
            print(f"Skipping {symbol_pair} due to price fetch error.")
            continue

        threshold = token.get("threshold")
        if threshold is None:
            threshold = get_default_threshold(current_price)


        initial_rounded = round_to_threshold(current_price, threshold)
        tokens[symbol_pair] = {"last_price": initial_rounded, "threshold": threshold}

        decimals = decimal_places_from_threshold(threshold)


        banner = create_banner_image(symbol, initial_rounded, telegram_handle, decimals)
        print(f"Initial notification for {symbol_pair}: {initial_rounded} (actual: {current_price})")
        send_telegram_photo(telegram_bot_token, telegram_channel_id, banner)
        send_discord_photo(discord_webhook, banner)

    print("Started monitoring prices...")


    while True:
        for symbol_pair, data in tokens.items():
            current_price = get_price(exchange, symbol_pair)
            if current_price is None:
                continue

            last_price = data["last_price"]
            threshold = data["threshold"]
            decimals = decimal_places_from_threshold(threshold)
            new_rounded = round_to_threshold(current_price, threshold)

            if abs(new_rounded - last_price) >= threshold:
                token_symbol = symbol_pair.split('/')[0]
                banner = create_banner_image(token_symbol, new_rounded, telegram_handle, decimals)
                print(f"Notification for {symbol_pair}: {new_rounded} (was {last_price}, actual {current_price})")
                send_telegram_photo(telegram_bot_token, telegram_channel_id, banner)
                send_discord_photo(discord_webhook, banner)
                tokens[symbol_pair]["last_price"] = new_rounded

        time.sleep(60)  

if __name__ == '__main__':
    main()
