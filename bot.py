from typing import Final
import logging
from datetime import datetime, timezone

import requests
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# 🔑 API kalitlar
OWM_API_KEY: Final = "48079323ef048b7d7b16eaa6a72dc54a"
TELEGRAM_TOKEN: Final = "8026735251:AAEBWe-StOeDNDFN4DwAfXqQY7xinpcsBEI"

# 🔧 Loglar
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# 🌄 Rasm katalogi
IMAGE_CATALOG = {
    "hot": "https://images.unsplash.com/photo-1501594907352-04cda38ebc29?auto=format&fit=crop&w=1200&q=80",
    "cold": "https://images.unsplash.com/photo-1478265409131-1f23f2b78f6b?auto=format&fit=crop&w=1200&q=80",
    "snow": "https://images.unsplash.com/photo-1482192596544-9eb780fc7f66?auto=format&fit=crop&w=1200&q=80",
    "rain": "https://images.unsplash.com/photo-1501592531935-1f90499378d6?auto=format&fit=crop&w=1200&q=80",
    "thunderstorm": "https://images.unsplash.com/photo-1504384308090-c894fdcc538d?auto=format&fit=crop&w=1200&q=80",
    "clouds": "https://images.unsplash.com/photo-1499346030926-9a72daac6c63?auto=format&fit=crop&w=1200&q=80",
    "mist": "https://images.unsplash.com/photo-1502082553048-f009c37129b9?auto=format&fit=crop&w=1200&q=80",
    "clear": "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1200&q=80",
}
COLD_THRESHOLD = 5
HOT_THRESHOLD = 30

# 🔧 Yordamchi funksiyalar
def _select_image(temp: float, main: str) -> str:
    main_l = main.lower()
    if "thunderstorm" in main_l:
        return IMAGE_CATALOG["thunderstorm"]
    if "snow" in main_l:
        return IMAGE_CATALOG["snow"]
    if "rain" in main_l or "drizzle" in main_l:
        return IMAGE_CATALOG["rain"]
    if "mist" in main_l or "fog" in main_l or "haze" in main_l:
        return IMAGE_CATALOG["mist"]
    if "cloud" in main_l:
        return IMAGE_CATALOG["clouds"]
    if temp <= COLD_THRESHOLD:
        return IMAGE_CATALOG["cold"]
    if temp >= HOT_THRESHOLD:
        return IMAGE_CATALOG["hot"]
    return IMAGE_CATALOG["clear"]

def _format_time(ts: int, offset: int) -> str:
    local = datetime.fromtimestamp(ts + offset, tz=timezone.utc)
    return local.strftime("%H:%M")

def _fetch_weather(city: str) -> tuple[bool, str | dict]:
    url = (
        "https://api.openweathermap.org/data/2.5/weather"
        f"?q={city}&appid={OWM_API_KEY}&units=metric&lang=uz"
    )
    try:
        resp = requests.get(url, timeout=10)
    except requests.RequestException:
        return False, "🌐 Serverga ulanishda xato. Keyinroq urinib ko‘ring."

    if resp.status_code != 200:
        return False, "🚫 Shahar topilmadi. Nomini tekshiring."

    data = resp.json()
    temp = data["main"]["temp"]
    main_weather = data["weather"][0]["main"]
    image_url = _select_image(temp, main_weather)

    tz_shift = data.get("timezone", 0)
    sunrise = _format_time(data["sys"]["sunrise"], tz_shift)
    sunset = _format_time(data["sys"]["sunset"], tz_shift)

    return True, {
        "city": data["name"],
        "temp": temp,
        "desc": data["weather"][0]["description"].capitalize(),
        "image_url": image_url,
        "sunrise": sunrise,
        "sunset": sunset,
    }

def _weather_caption(info: dict) -> str:
    return (
        f"<b>📍 {info['city']}</b>\n"
        f"🌡 <b>Harorat:</b> <code>{info['temp']}°C</code>\n"
        f"☁️ <i>{info['desc']}</i>\n"
        f"🌅 <b>Quyosh chiqadi:</b> {info['sunrise']}\n"
        f"🌇 <b>Quyosh botadi:</b> {info['sunset']}\n\n"
        f"📆 Bugun sizga ajoyib kun tilayman! ☀️🌈"
    )

def _weather_keyboard(city: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔄 Ob-havoni yangilash", callback_data=f"refresh:{city}")]]
    )

# 🤖 Bot handlerlar
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 <b>Assalomu alaykum!</b>\n"
        "Men sizga dunyoning istalgan shahridan <i>ob-havo</i> haqida chiroyli tarzda xabar beraman.\n\n"
        "✍️ Faqat shahar nomini yozing: masalan, <code>Toshkent</code>",
        parse_mode="HTML",
    )

async def city_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    city = update.message.text.strip()
    if not city or city.startswith("/"):
        return

    ok, result = _fetch_weather(city)
    if not ok:
        await update.message.reply_text(result)
        return

    await update.message.reply_photo(
        photo=result["image_url"],
        caption=_weather_caption(result),
        parse_mode="HTML",
        reply_markup=_weather_keyboard(result["city"]),
    )

async def refresh_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if not query.data.startswith("refresh:"):
        return

    city = query.data.split(":", 1)[1]
    ok, result = _fetch_weather(city)
    if not ok:
        await query.edit_message_caption(result)
        return

    await query.edit_message_media(
        media=InputMediaPhoto(
            media=result["image_url"],
            caption=_weather_caption(result),
            parse_mode="HTML",
        ),
        reply_markup=_weather_keyboard(result["city"]),
    )

async def unknown_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "❓ Bunday buyruq mavjud emas. Shunchaki shahar nomini yozing: masalan, <code>Andijon</code>",
        parse_mode="HTML",
    )

# 🚀 Botni ishga tushirish
def main() -> None:
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(refresh_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, city_query))
    app.add_handler(MessageHandler(filters.COMMAND, unknown_cmd))
    logger.info("✅ Bot ishga tushdi…")
    app.run_polling()

if __name__ == "__main__":
    main()
