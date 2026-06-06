import os
import json
import random
import asyncio
import logging
from datetime import datetime, time
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

ADS = [
    {
        "text": "📚 *[SPONSOR]* Locul reclamei tale aici! Contactează-ne pentru colaborare.",
        "url": "https://exemplu.ro",
        "button": "🎓 Află mai mult"
    },
]

CATEGORIES = {
    "motivatie": ("🔥", "Motivație"),
    "curaj": ("⚡", "Curaj"),
    "bucurie": ("☀️", "Bucurie"),
    "succes": ("🏆", "Succes"),
}

SYSTEM_PROMPT = """Ești un coach motivațional cald și autentic care vorbește în română.
Generezi mesaje scurte de încurajare și motivație zilnică.
Fiecare mesaj trebuie să fie scurt (2-4 propoziții), personal și cald, 
inspirat din filozofie sau înțelepciune românească, 
și să se termine cu un îndemn concret la acțiune.
Răspunde DOAR cu mesajul, fără introducere."""

subscribers_file = "subscribers.json"

def load_subscribers():
    try:
        with open(subscribers_file) as f:
            return set(json.load(f))
    except:
        return set()

def save_subscribers(subs):
    with open(subscribers_file, "w") as f:
        json.dump(list(subs), f)

subscribers = load_subscribers()

async def get_motivational_message(category):
    emoji, name = CATEGORIES.get(category, ("✨", "Generală"))
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 300,
                    "system": SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": f"Generează un mesaj din categoria: {name}"}]
                }
            )
            data = resp.json()
            return data["content"][0]["text"]
    except Exception as e:
        logger.error(f"AI error: {e}")
        return "Astăzi e o nouă șansă. Fă un pas mic, dar fă-l. 💪"

async def send_message_with_ad(context, chat_id, category="motivatie"):
    emoji, name = CATEGORIES.get(category, ("✨", "Generală"))
    msg = await get_motivational_message(category)
    ad = random.choice(ADS) if ADS else None
    text = f"{emoji} *Mesajul zilei — {name}*\n\n_{msg}_"
    keyboard = []
    if ad:
        text += f"\n\n━━━━━━━━━━━━━━\n{ad['text']}"
        keyboard.append([InlineKeyboardButton(ad["button"], url=ad["url"])])
    keyboard.append([
        InlineKeyboardButton("🔥 Motivație", callback_data="cat_motivatie"),
        InlineKeyboardButton("⚡ Curaj", callback_data="cat_curaj"),
    ])
    keyboard.append([
        InlineKeyboardButton("☀️ Bucurie", callback_data="cat_bucurie"),
        InlineKeyboardButton("🏆 Succes", callback_data="cat_succes"),
    ])
    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True,
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    subscribers.add(chat_id)
    save_subscribers(subscribers)
    welcome = (
        f"✨ *Bun venit, {user.first_name}!*\n\n"
        "Sunt *Lumina Zilei* — botul care îți trimite în fiecare dimineață "
        "un mesaj de încurajare.\n\n"
        "📬 Vei primi mesajul zilei automat la *ora 08:00*.\n\n"
        "Sau alege o categorie acum 👇"
    )
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔥 Motivație", callback_data="cat_motivatie"),
            InlineKeyboardButton("⚡ Curaj", callback_data="cat_curaj"),
        ],
        [
            InlineKeyboardButton("☀️ Bucurie", callback_data="cat_bucurie"),
            InlineKeyboardButton("🏆 Succes", callback_data="cat_succes"),
        ],
        [InlineKeyboardButton("✨ Surprinde-mă!", callback_data="cat_random")]
    ])
    await update.message.reply_text(welcome, parse_mode="Markdown", reply_markup=keyboard)

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subscribers.discard(chat_id)
    save_subscribers(subscribers)
    await update.message.reply_text("😔 Te-ai dezabonat. Oricând poți reveni cu /start.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"📊 Abonați activi: *{len(subscribers)}*", parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat = query.data[4:]
    if cat == "random":
        cat = random.choice(list(CATEGORIES.keys()))
    await query.message.reply_text("⏳ Generez mesajul tău...")
    await send_message_with_ad(context, query.message.chat_id, cat)

async def daily_broadcast(context: ContextTypes.DEFAULT_TYPE):
    day = datetime.now().timetuple().tm_yday
    cats = list(CATEGORIES.keys())
    cat = cats[day % len(cats)]
    failed = set()
    for chat_id in list(subscribers):
        try:
            await send_message_with_ad(context, chat_id, cat)
            await asyncio.sleep(0.05)
        except:
            failed.add(chat_id)
    subscribers.difference_update(failed)
    save_subscribers(subscribers)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.job_queue.run_daily(
        daily_broadcast,
        time=time(hour=8, minute=0, second=0),
        name="daily_motivational"
    )
    logger.info("🚀 Botul Lumina Zilei a pornit!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
