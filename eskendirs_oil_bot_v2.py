"""
╔══════════════════════════════════════════════════════════╗
║        ESKENDIR'S GAS & OIL PRICE CHATBOT               ║
║        Stack: python-telegram-bot + aiohttp + aiosqlite ║
║        APIs: Yahoo Finance (no key) + open.er-api.com   ║
╚══════════════════════════════════════════════════════════╝
"""

import asyncio
import aiosqlite
import aiohttp
import logging
import os
import random
from datetime import datetime
from aiohttp import web

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIGURATION  (set as environment variables on Render)
# ─────────────────────────────────────────────────────────────────────────────
BOT_TOKEN    = os.environ.get("BOT_TOKEN",   "YOUR_BOT_TOKEN_HERE")
WEBHOOK_URL  = os.environ.get("WEBHOOK_URL", "https://YOUR-APP.onrender.com")
PORT         = int(os.environ.get("PORT",    8080))
DB_PATH      = "oil_bot.db"
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
AUTHOR       = "Eskendir"

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  DATABASE SEED DATA
# ─────────────────────────────────────────────────────────────────────────────

_SEED_FAQS = [
    ("opec",
     f"🌍 *OPEC* (Organization of the Petroleum Exporting Countries) was founded in 1960 "
     f"in Baghdad by Iran, Iraq, Kuwait, Saudi Arabia, and Venezuela.\n\n"
     f"Today it has 13 members and controls ~44% of global oil output.\n"
     f"_{AUTHOR} notes: OPEC+ — which includes Russia — is even more powerful!_"),

    ("brent",
     f"🌊 *Brent Crude* is extracted from the North Sea and is the world's leading oil "
     f"benchmark — about 2/3 of globally traded oil is priced against it.\n\n"
     f"API gravity ~38.3°, sulfur ~0.37% (low-sulfur = 'sweet').\n"
     f"_{AUTHOR} tracks Brent every single day!_"),

    ("wti",
     f"🏭 *WTI (West Texas Intermediate)* is a light, sweet crude from Cushing, Oklahoma. "
     f"It's the primary US oil benchmark.\n\n"
     f"API gravity ~39.6°, sulfur ~0.24%.\n"
     f"WTI usually trades $2–$3 below Brent. _{AUTHOR} explains the spread daily!_"),

    ("kazakhstan",
     f"🇰🇿 Kazakhstan is a top-20 global oil producer! _{AUTHOR}'s homeland is energy-rich!_\n\n"
     f"🏭 *Tengiz* — 26–29 billion bbl reserves\n"
     f"🌊 *Kashagan* — one of world's largest offshore fields\n"
     f"🔥 *Karachaganak* — giant gas-condensate field\n\n"
     f"Production: ~1.8M barrels/day. Oil = ~50% of export revenue."),

    ("natural gas",
     f"🔥 *Natural Gas* is a fossil fuel (mainly methane, CH₄) used for electricity, "
     f"heating, and industry. Prices quoted in $/MMBtu.\n\n"
     f"🇰🇿 Kazakhstan's Karachaganak field has massive gas reserves.\n"
     f"_{AUTHOR} notes: gas burns ~50% cleaner than coal!_"),

    ("barrel",
     f"📦 *1 Oil Barrel* = 42 US gallons = 158.99 liters\n\n"
     f"What one barrel produces:\n"
     f"• ~19.5 gal gasoline\n• ~10 gal diesel\n• ~4 gal jet fuel\n"
     f"• Remaining: asphalt, lubricants, petrochemicals\n\n"
     f"_{AUTHOR} trivia: the 42-gal standard was set in Pennsylvania in 1872!_"),

    ("refinery",
     f"⚙️ *Refineries* convert raw crude into usable products via:\n"
     f"🔬 Distillation → Cracking → Reforming → Treating\n\n"
     f"🌍 Largest: Jamnagar, India (1.24M bbl/day)\n"
     f"🇰🇿 Kazakhstan has refineries in Atyrau, Pavlodar & Shymkent!\n"
     f"_{AUTHOR} says: refining is where the real value is added!_"),

    ("gasoline",
     f"⛽ *Gasoline/Petrol* prices depend on: crude oil cost + refining + distribution + taxes.\n\n"
     f"🌍 Sample pump prices (per liter):\n"
     f"• Kazakhstan: ~$0.45 (subsidized)\n"
     f"• Russia: ~$0.70\n"
     f"• Germany: ~$1.80\n"
     f"• USA: ~$0.95\n\n"
     f"_{AUTHOR} appreciates Kazakhstan's affordable fuel!_ 🇰🇿"),

    ("crude",
     f"🛢️ *Crude oil* is unrefined petroleum extracted from the ground. "
     f"It's classified by density (light/heavy) and sulfur content (sweet/sour).\n\n"
     f"Light sweet crude → easier/cheaper to refine → higher price.\n"
     f"_{AUTHOR} explains: not all crude is equal — quality matters!_"),

    ("petrol",
     f"⛽ *Petrol* is the British/Commonwealth term for gasoline. "
     f"It's the main refined product from crude oil, used in internal combustion engines.\n\n"
     f"In Kazakhstan it's sold as AI-92, AI-95, AI-98 (octane ratings).\n"
     f"_{AUTHOR} fills up with AI-95!_ 😄"),

    ("diesel",
     f"🚛 *Diesel fuel* is a heavier distillate than gasoline, used in trucks, buses, ships, "
     f"and industrial engines. More energy-dense than petrol.\n\n"
     f"Kazakhstan exports significant diesel to CIS countries.\n"
     f"_{AUTHOR} notes: diesel is still the backbone of freight worldwide!_"),

    ("lng",
     f"❄️ *LNG (Liquefied Natural Gas)* is natural gas cooled to -162°C to become liquid "
     f"for shipping. Volume reduces by 600x!\n\n"
     f"Major exporters: Qatar, Australia, USA.\n"
     f"_{AUTHOR} insight: LNG is reshaping global energy trade faster than ever!_"),
]

_GREETINGS  = {"hello", "hi", "hey", "howdy", "sup", "greetings", "yo", "hiya",
               "good morning", "good evening", "good afternoon", "wassup", "what's up"}
_FAREWELLS  = {"bye", "goodbye", "farewell", "see you", "cya", "good night",
               "take care", "later", "see ya", "ttyl"}
_THANKS     = {"thank", "thanks", "thx", "ty", "appreciate", "cheers", "thnx"}
_PRICE_WORDS = {"price", "cost", "how much", "rate", "value", "worth", "expensive",
                "cheap", "dollar", "usd", "money", "market", "trading", "today"}

YAHOO_SYMBOLS: dict[str, str] = {
    "CL=F": "WTI Crude Oil",
    "BZ=F": "Brent Crude Oil",
    "NG=F": "Natural Gas",
    "RB=F": "RBOB Gasoline",
    "HO=F": "Heating Oil",
}

_UNIT_MAP = {
    "WTI Crude Oil":   "$/bbl",
    "Brent Crude Oil": "$/bbl",
    "Natural Gas":     "$/MMBtu",
    "RBOB Gasoline":   "$/gal",
    "Heating Oil":     "$/gal",
}


# ─────────────────────────────────────────────────────────────────────────────
#  DATABASE  (async via aiosqlite)
# ─────────────────────────────────────────────────────────────────────────────

async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS faqs (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword  TEXT NOT NULL UNIQUE,
                response TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS users (
                user_id    INTEGER PRIMARY KEY,
                username   TEXT,
                first_seen TEXT NOT NULL,
                msg_count  INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS chat_history (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   INTEGER NOT NULL,
                username  TEXT,
                message   TEXT,
                response  TEXT,
                timestamp TEXT NOT NULL
            );
        """)

        for keyword, response in _SEED_FAQS:
            await db.execute(
                "INSERT OR IGNORE INTO faqs (keyword, response) VALUES (?, ?)",
                (keyword, response),
            )

        await db.commit()
    logger.info("✅  Database initialised (%d FAQ entries)", len(_SEED_FAQS))


async def db_faq_lookup(text: str) -> str | None:
    lower = text.lower()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT response FROM faqs "
            "WHERE ? LIKE '%' || keyword || '%' LIMIT 1",
            (lower,),
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else None


async def db_log(user_id: int, username: str | None, message: str, response: str) -> None:
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO chat_history (user_id, username, message, response, timestamp) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, username, message[:500], response[:500], now),
        )
        await db.execute(
            """INSERT INTO users (user_id, username, first_seen, msg_count)
               VALUES (?, ?, ?, 1)
               ON CONFLICT(user_id) DO UPDATE
                 SET msg_count = msg_count + 1,
                     username  = excluded.username""",
            (user_id, username, now),
        )
        await db.commit()


async def db_get_history(user_id: int, limit: int = 6) -> list[tuple]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT message, timestamp FROM chat_history "
            "WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ) as cur:
            return await cur.fetchall()


async def db_user_stats(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT msg_count, first_seen FROM users WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return {"count": row[0], "since": row[1][:10]} if row else {"count": 0, "since": "just now"}


# ─────────────────────────────────────────────────────────────────────────────
#  EXTERNAL APIs
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_commodity_prices() -> dict[str, dict]:
    results: dict[str, dict] = {}
    timeout = aiohttp.ClientTimeout(total=12)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for symbol, name in YAHOO_SYMBOLS.items():
            url = (
                f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
                f"?interval=1d&range=1d"
            )
            try:
                async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}) as resp:
                    if resp.status != 200:
                        results[name] = {"error": True}
                        continue
                    data = await resp.json()
                    meta  = data["chart"]["result"][0]["meta"]
                    price = float(meta.get("regularMarketPrice") or meta.get("previousClose", 0))
                    prev  = float(meta.get("chartPreviousClose") or meta.get("previousClose", price))
                    change = price - prev
                    pct    = (change / prev * 100) if prev else 0.0
                    results[name] = {
                        "price": price, "change": change,
                        "pct": pct, "error": False,
                    }
            except Exception as exc:
                logger.warning("Yahoo Finance error (%s): %s", name, exc)
                results[name] = {"error": True}
    return results


async def fetch_usd_rates() -> dict[str, float]:
    url = "https://open.er-api.com/v6/latest/USD"
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url) as resp:
                data  = await resp.json()
                rates = data.get("rates", {})
                return {c: rates.get(c, 0.0) for c in ("KZT", "EUR", "RUB", "GBP", "CNY", "SAR")}
    except Exception as exc:
        logger.warning("Exchange rate API error: %s", exc)
        return {}


# ─────────────────────────────────────────────────────────────────────────────
#  FORMATTING
# ─────────────────────────────────────────────────────────────────────────────

def _arrow(change: float) -> str:
    return "📈" if change > 0 else ("📉" if change < 0 else "➡️")


def format_prices(prices: dict[str, dict]) -> str:
    if not prices:
        return f"❌ Could not retrieve prices. Please try again.\n\n_— {AUTHOR}_"
    lines = [f"🛢️ *Live Energy Prices*\n_Tracked by {AUTHOR}'s Bot_\n"]
    for name, d in prices.items():
        if d.get("error"):
            lines.append(f"• *{name}* — ❌ unavailable\n")
            continue
        arrow = _arrow(d["change"])
        sign  = "+" if d["change"] >= 0 else ""
        unit  = _UNIT_MAP.get(name, "USD")
        lines.append(
            f"{arrow} *{name}*\n"
            f"   `${d['price']:.3f}` {unit}\n"
            f"   Change: `{sign}{d['change']:.3f}` ({sign}{d['pct']:.2f}%)\n"
        )
    lines.append(f"🕒 `{datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC`")
    lines.append(f"_Source: Yahoo Finance — {AUTHOR}_")
    return "\n".join(lines)


def format_rates(rates: dict[str, float]) -> str:
    if not rates:
        return f"❌ Could not retrieve exchange rates.\n\n_— {AUTHOR}_"
    flags = {"KZT": "🇰🇿", "EUR": "🇪🇺", "RUB": "🇷🇺", "GBP": "🇬🇧", "CNY": "🇨🇳", "SAR": "🇸🇦"}
    lines = [f"💱 *USD Exchange Rates*\n_Relevant to oil trading — by {AUTHOR}_\n"]
    for code, val in rates.items():
        lines.append(f"{flags.get(code, '🌐')} `1 USD = {val:,.4f} {code}`")
    lines.append(
        f"\n💡 *Why it matters:* Oil is priced in USD globally. "
        f"A stronger USD typically pushes oil prices lower — _{AUTHOR} explains!_"
    )
    lines.append(f"\n🕒 `{datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC`")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
#  KEYBOARDS
# ─────────────────────────────────────────────────────────────────────────────

def kb_main() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("🛢️ Oil Prices"),    KeyboardButton("💱 Exchange Rates")],
            [KeyboardButton("📚 Oil Facts"),      KeyboardButton("🌍 About OPEC")],
            [KeyboardButton("📜 My History"),     KeyboardButton("📊 My Stats")],
            [KeyboardButton("👋 Goodbye"),        KeyboardButton("❓ Help")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Ask about oil, gas, or type a keyword...",
    )


def ikb_prices() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Refresh",    callback_data="prices:refresh"),
            InlineKeyboardButton("💱 USD Rates",  callback_data="rates:show"),
        ],
        [
            InlineKeyboardButton("📖 WTI Info",   callback_data="info:wti"),
            InlineKeyboardButton("🌊 Brent Info", callback_data="info:brent"),
        ],
        [
            InlineKeyboardButton("🔥 Gas Info",   callback_data="info:gas"),
            InlineKeyboardButton("⛽ Gasoline",   callback_data="info:gasoline"),
        ],
    ])


def ikb_rates() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Refresh",    callback_data="rates:show"),
            InlineKeyboardButton("🛢️ Oil Prices", callback_data="prices:refresh"),
        ],
    ])


def ikb_facts() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🌍 OPEC",        callback_data="fact:opec"),
            InlineKeyboardButton("🇰🇿 Kazakhstan", callback_data="fact:kz"),
        ],
        [
            InlineKeyboardButton("📦 Oil Barrel",  callback_data="fact:barrel"),
            InlineKeyboardButton("⚙️ Refinery",    callback_data="fact:refinery"),
        ],
        [
            InlineKeyboardButton("❄️ LNG",         callback_data="fact:lng"),
            InlineKeyboardButton("🔥 Natural Gas", callback_data="fact:natgas"),
        ],
        [InlineKeyboardButton("❌ Close",           callback_data="close")],
    ])


def ikb_back_to_facts() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("◀️ Back to Facts", callback_data="facts:menu"),
            InlineKeyboardButton("🛢️ Live Prices",   callback_data="prices:refresh"),
        ],
    ])


def ikb_back_to_prices() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("◀️ Back to Prices", callback_data="prices:refresh"),
            InlineKeyboardButton("📚 Oil Facts",      callback_data="facts:menu"),
        ],
    ])


# ─────────────────────────────────────────────────────────────────────────────
#  COMMAND HANDLERS
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    name = update.effective_user.first_name or "friend"
    text = (
        f"👋 Welcome, *{name}*!\n\n"
        f"I'm *{AUTHOR}'s Gas & Oil Bot* 🛢️\n\n"
        f"Here's what I can do:\n"
        f"• 📊 Live oil & gas prices (WTI, Brent, Natural Gas…)\n"
        f"• 💱 USD exchange rates (KZT, EUR, RUB…)\n"
        f"• 📚 Oil & gas industry facts & trivia\n"
        f"• 🌍 OPEC & Kazakhstan energy sector info\n"
        f"• 💬 Answer your questions about the energy market\n\n"
        f"Use the keyboard below or just type your question!\n\n"
        f"_— Built with ❤️ by {AUTHOR}_"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb_main())
    await db_log(update.effective_user.id, update.effective_user.username, "/start", text)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        f"🆘 *{AUTHOR}'s Bot — Help Guide*\n\n"
        f"*Commands:*\n"
        f"`/start` — Welcome & main menu\n"
        f"`/prices` — Live energy prices\n"
        f"`/rates` — USD exchange rates\n"
        f"`/facts` — Oil & gas knowledge base\n"
        f"`/history` — Your recent chat history\n"
        f"`/stats` — Your profile & rank\n"
        f"`/help` — This guide\n\n"
        f"*Or just type anything*, e.g.:\n"
        f"_'What is brent crude?'_\n"
        f"_'Tell me about Kazakhstan oil'_\n"
        f"_'What is LNG?'_\n\n"
        f"_{AUTHOR} hopes this helps!_ 🤝"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb_main())


async def cmd_prices(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text(
        f"⏳ _Fetching live prices… {AUTHOR} is on it!_", parse_mode=ParseMode.MARKDOWN
    )
    prices = await fetch_commodity_prices()
    text   = format_prices(prices)
    await msg.delete()
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=ikb_prices())
    await db_log(update.effective_user.id, update.effective_user.username, "/prices", text)


async def cmd_rates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text(
        f"⏳ _Loading exchange rates…_", parse_mode=ParseMode.MARKDOWN
    )
    rates = await fetch_usd_rates()
    text  = format_rates(rates)
    await msg.delete()
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=ikb_rates())
    await db_log(update.effective_user.id, update.effective_user.username, "/rates", text)


async def cmd_facts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        f"📚 *Oil & Gas Knowledge Base*\n"
        f"_Curated by {AUTHOR} — tap a topic!_\n\n"
        f"Choose what you'd like to learn:"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=ikb_facts())
    await db_log(update.effective_user.id, update.effective_user.username, "/facts", text)


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = await db_get_history(update.effective_user.id)
    if not rows:
        text = f"📭 No history yet! Start chatting and I'll remember.\n\n_— {AUTHOR}_"
    else:
        lines = [f"📜 *Your Last {len(rows)} Messages*\n_Logged by {AUTHOR}'s Bot_\n"]
        for msg, ts in rows:
            t = ts[:16].replace("T", " ") if ts else "?"
            lines.append(f"🕒 `{t}` — _{msg[:60]}_")
        lines.append(f"\n_— {AUTHOR} keeps your history safe!_ 🔒")
        text = "\n".join(lines)
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb_main())


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    stats = await db_user_stats(update.effective_user.id)
    count = stats["count"]
    since = stats["since"]

    if count < 5:
        rank, next_rank = "🌱 Rookie Analyst", "📊 Market Watcher (5 messages)"
    elif count < 20:
        rank, next_rank = "📊 Market Watcher", "🛢️ Oil Enthusiast (20 messages)"
    elif count < 50:
        rank, next_rank = "🛢️ Oil Enthusiast", "📈 Commodity Trader (50 messages)"
    elif count < 100:
        rank, next_rank = "📈 Commodity Trader", "🏭 Energy Expert (100 messages)"
    else:
        rank, next_rank = "🏭 Energy Expert", "You've reached the top! 💪"

    text = (
        f"📊 *Your Profile*\n\n"
        f"✉️ Messages sent: *{count}*\n"
        f"📅 Active since: *{since}*\n"
        f"🏅 Current rank: *{rank}*\n"
        f"⬆️ Next rank: *{next_rank}*\n\n"
        f"_Every question makes you a sharper analyst!_ 🛢️\n\n"
        f"_— {AUTHOR}_"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb_main())
    await db_log(update.effective_user.id, update.effective_user.username, "/stats", text)


# ─────────────────────────────────────────────────────────────────────────────
#  CALLBACK QUERY HANDLERS
# ─────────────────────────────────────────────────────────────────────────────

async def cb_prices_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer("🔄 Refreshing prices…")
    prices = await fetch_commodity_prices()
    text   = format_prices(prices)
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=ikb_prices())


async def cb_rates_show(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer("💱 Loading rates…")
    rates = await fetch_usd_rates()
    text  = format_rates(rates)
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=ikb_rates())


async def cb_facts_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    text = (
        f"📚 *Oil & Gas Knowledge Base*\n"
        f"_Curated by {AUTHOR} — tap a topic!_\n\n"
        f"Choose what you'd like to learn:"
    )
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=ikb_facts())


async def cb_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    key = query.data.split(":", 1)[1]

    texts = {
        "wti": (
            f"🏭 *WTI Crude Oil — Deep Dive*\n_by {AUTHOR}_\n\n"
            f"*Full name:* West Texas Intermediate\n"
            f"*Source:* Cushing, Oklahoma, USA\n"
            f"*API gravity:* ~39.6° (light)\n"
            f"*Sulfur:* ~0.24% (sweet)\n"
            f"*Benchmark for:* US oil market\n\n"
            f"WTI is stored and priced at the *Cushing hub* — "
            f"the 'Pipeline Crossroads of the World.'\n\n"
            f"It typically trades $2–$3 *below Brent* due to inland location "
            f"and transport costs to export terminals.\n\n"
            f"_{AUTHOR} tip: watch WTI for US energy policy signals!_"
        ),
        "brent": (
            f"🌊 *Brent Crude — Deep Dive*\n_by {AUTHOR}_\n\n"
            f"*Full name:* Brent Blend\n"
            f"*Source:* North Sea (UK & Norway)\n"
            f"*API gravity:* ~38.3° (light)\n"
            f"*Sulfur:* ~0.37% (sweet)\n"
            f"*Benchmark for:* ~2/3 of world's oil trade\n\n"
            f"Named after the *Brent Goose* — Shell used bird names for its oil fields.\n\n"
            f"Brent prices are especially sensitive to: Middle East tensions, "
            f"European energy demand, and OPEC+ decisions.\n\n"
            f"_{AUTHOR} follows Brent daily — it's the world's most important oil price!_"
        ),
        "gas": (
            f"🔥 *Natural Gas — Deep Dive*\n_by {AUTHOR}_\n\n"
            f"*Main component:* Methane (CH₄, ~90%)\n"
            f"*Unit:* MMBtu (Million British Thermal Units)\n"
            f"*US hub:* Henry Hub, Louisiana\n\n"
            f"*Uses:*\n"
            f"• ⚡ Electricity generation (~38% of US power)\n"
            f"• 🏠 Home heating & cooking\n"
            f"• 🏭 Industrial feedstock (fertilizers, plastics)\n"
            f"• 🚌 CNG vehicles\n\n"
            f"🇰🇿 *Kazakhstan:* The Karachaganak field (NW Kazakhstan) is one of "
            f"the world's largest gas-condensate deposits.\n\n"
            f"_{AUTHOR} note: gas is the transition fuel between coal and renewables!_"
        ),
        "gasoline": (
            f"⛽ *RBOB Gasoline Futures*\n_by {AUTHOR}_\n\n"
            f"*RBOB* = Reformulated Blendstock for Oxygenate Blending\n"
            f"*Unit:* USD per gallon (1 gal ≈ 3.785 L)\n"
            f"*Exchange:* NYMEX\n\n"
            f"*Pump price breakdown:*\n"
            f"• Crude oil cost: ~55%\n"
            f"• Refining margin: ~15%\n"
            f"• Distribution & retail: ~15%\n"
            f"• Taxes: ~15% (varies hugely by country)\n\n"
            f"*Global pump prices ($/liter):*\n"
            f"🇻🇪 Venezuela: ~$0.01 | 🇰🇿 Kazakhstan: ~$0.45\n"
            f"🇺🇸 USA: ~$0.95 | 🇩🇪 Germany: ~$1.80\n\n"
            f"_{AUTHOR} says: appreciate Kazakhstan's subsidized fuel!_ 🇰🇿"
        ),
    }

    text = texts.get(key, "❌ Info not found.")
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=ikb_back_to_prices())


async def cb_fact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    key = query.data.split(":", 1)[1]

    texts = {
        "opec": (
            f"🌍 *OPEC Fast Facts*\n_Curated by {AUTHOR}_\n\n"
            f"📅 Founded: September 14, 1960\n"
            f"🏛️ HQ: Vienna, Austria\n"
            f"👥 Members: 13 countries\n"
            f"🛢️ Controls: ~44% of world oil production\n"
            f"💰 Holds: ~80% of proven world reserves\n\n"
            f"*Top 3 OPEC producers:*\n"
            f"1. 🇸🇦 Saudi Arabia — ~10M bbl/day\n"
            f"2. 🇮🇶 Iraq — ~4.3M bbl/day\n"
            f"3. 🇦🇪 UAE — ~3.3M bbl/day\n\n"
            f"⚡ OPEC+ (includes Russia & Kazakhstan) has operated since 2016.\n"
            f"_{AUTHOR} calls it the most powerful energy alliance on Earth!_"
        ),
        "kz": (
            f"🇰🇿 *Kazakhstan Oil & Gas*\n_Pride of {AUTHOR}!_\n\n"
            f"Kazakhstan ranks among the world's top 20 oil producers.\n\n"
            f"*3 Giant Fields:*\n"
            f"🏭 *Tengiz* — 26–29 billion bbl reserves (TCO, Chevron-operated)\n"
            f"🌊 *Kashagan* — Caspian Sea, one of the 5 largest fields ever found\n"
            f"🔥 *Karachaganak* — 9 billion bbl oil-equiv. gas-condensate\n\n"
            f"📊 *Key stats:*\n"
            f"• Production: ~1.8 million bbl/day\n"
            f"• Exports via CPC Pipeline → Black Sea → World\n"
            f"• Oil & gas = ~50% of export revenue\n"
            f"• KazMunayGas is the national energy company\n\n"
            f"_{AUTHOR} says: Kazakhstan's energy sector will only grow stronger! 💪_"
        ),
        "barrel": (
            f"📦 *The Oil Barrel*\n_Fun facts by {AUTHOR}_\n\n"
            f"1 barrel = 42 US gallons = 158.99 liters\n\n"
            f"*From 1 barrel you get:*\n"
            f"⛽ ~19.5 gal gasoline\n"
            f"🚛 ~10 gal diesel/heating oil\n"
            f"✈️ ~4 gal jet fuel\n"
            f"🏗️ Remaining: asphalt, lubricants, petrochemicals\n\n"
            f"*History:* The 42-gallon barrel was standardized in *1872* "
            f"by Pennsylvania oil producers.\n\n"
            f"*Fun stat:* At $80/bbl, each liter of crude costs ~$0.50.\n"
            f"_{AUTHOR} trivia: oil is cheaper than most bottled water per liter!_ 💧"
        ),
        "refinery": (
            f"⚙️ *Oil Refining*\n_Technical deep-dive by {AUTHOR}_\n\n"
            f"*Refining steps:*\n"
            f"1. 🔬 *Distillation* — Separate fractions by boiling point\n"
            f"2. ⚗️ *Cracking* — Break heavy molecules into lighter, valuable ones\n"
            f"3. 🔄 *Reforming* — Boost octane rating for gasoline\n"
            f"4. 🧹 *Treating* — Remove sulfur, contaminants\n\n"
            f"*World's largest refineries:*\n"
            f"1. 🇮🇳 Jamnagar, India — 1.24M bbl/day\n"
            f"2. 🇻🇪 Paraguana, Venezuela — 940K bbl/day\n"
            f"3. 🇰🇷 Ulsan, South Korea — 840K bbl/day\n\n"
            f"🇰🇿 Kazakhstan refineries: *Atyrau, Pavlodar, Shymkent*\n"
            f"_{AUTHOR}: refining is where crude becomes cash!_ 💰"
        ),
        "lng": (
            f"❄️ *LNG — Liquefied Natural Gas*\n_by {AUTHOR}_\n\n"
            f"Natural gas cooled to *−162°C* becomes liquid, shrinking its "
            f"volume by *~600 times* — making it shippable globally.\n\n"
            f"*Process:*\n"
            f"🔵 Extraction → 🏭 Liquefaction → 🚢 Shipping → 🔴 Regasification → 🏠 End use\n\n"
            f"*Top LNG exporters:*\n"
            f"1. 🇦🇺 Australia\n"
            f"2. 🇶🇦 Qatar\n"
            f"3. 🇺🇸 USA\n\n"
            f"LNG is reshaping global energy markets, breaking Russia's "
            f"pipeline monopoly on European gas supply.\n"
            f"_{AUTHOR} insight: LNG is the future of gas trade!_ 🌍"
        ),
        "natgas": (
            f"🔥 *Natural Gas Quick Facts*\n_by {AUTHOR}_\n\n"
            f"• Main component: Methane CH₄ (~85–95%)\n"
            f"• Measured in: MMBtu, mcf, or cubic meters\n"
            f"• Burns ~50% cleaner than coal for electricity\n"
            f"• Used by ~3 billion people for cooking/heating\n\n"
            f"*Top producers:*\n"
            f"1. 🇺🇸 USA — ~1,000 bcm/year\n"
            f"2. 🇷🇺 Russia — ~638 bcm/year\n"
            f"3. 🇮🇷 Iran — ~257 bcm/year\n\n"
            f"🇰🇿 Kazakhstan gas mainly exported to Russia & China.\n"
            f"_{AUTHOR} note: gas prices spiked 10x in Europe in 2022 — energy security matters!_"
        ),
    }

    text = texts.get(key, "❌ Fact not found.")
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=ikb_back_to_facts())


async def cb_close(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer("Closed.")
    await query.message.delete()


# ─────────────────────────────────────────────────────────────────────────────
#  MESSAGE HANDLER  (keyboard buttons + free text)
# ─────────────────────────────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text  = update.message.text.strip()
    lower = text.lower()
    uid   = update.effective_user.id
    uname = update.effective_user.username
    name  = update.effective_user.first_name or "friend"

    # ── Keyboard button routing ───────────────────────────────────────────────
    if text == "🛢️ Oil Prices":
        await cmd_prices(update, context)
        return

    if text == "💱 Exchange Rates":
        await cmd_rates(update, context)
        return

    if text == "📚 Oil Facts":
        await cmd_facts(update, context)
        return

    if text == "📜 My History":
        await cmd_history(update, context)
        return

    if text == "📊 My Stats":
        await cmd_stats(update, context)
        return

    if text == "❓ Help":
        await cmd_help(update, context)
        return

    if text == "🌍 About OPEC":
        resp = (
            f"🌍 *About OPEC*\n_A deep dive by {AUTHOR}_\n\n"
            f"*Full name:* Organization of the Petroleum Exporting Countries\n"
            f"*Founded:* September 14, 1960, Baghdad\n"
            f"*HQ:* Vienna, Austria 🇦🇹\n"
            f"*Members:* 13 countries\n\n"
            f"📊 *Market power:*\n"
            f"• Controls ~44% of global oil production\n"
            f"• Holds ~80% of world proven reserves\n"
            f"• Sets production quotas to influence prices\n\n"
            f"⚡ *OPEC+* (since 2016) adds Russia, Kazakhstan & 8 others — "
            f"making it even more dominant today!\n\n"
            f"🇰🇿 _{AUTHOR} is proud Kazakhstan participates in OPEC+ agreements!_"
        )
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🇰🇿 Kazakhstan Oil", callback_data="fact:kz"),
                InlineKeyboardButton("🛢️ Live Prices",    callback_data="prices:refresh"),
            ],
        ])
        await update.message.reply_text(resp, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
        await db_log(uid, uname, text, resp)
        return

    if text == "👋 Goodbye":
        resp = (
            f"👋 Goodbye, *{name}*!\n\n"
            f"It was great chatting about energy markets with you!\n"
            f"Come back anytime — prices change every second! 📊\n\n"
            f"🛢️ *{AUTHOR}* says: _may the oil always flow in your favor!_ 💪"
        )
        await update.message.reply_text(resp, parse_mode=ParseMode.MARKDOWN, reply_markup=kb_main())
        await db_log(uid, uname, text, resp)
        return

    # ── 1. Greeting ───────────────────────────────────────────────────────────
    if any(g in lower for g in _GREETINGS):
        resp = (
            f"👋 Hello, *{name}*!\n\n"
            f"Great to see you at *{AUTHOR}'s Oil & Gas Bot!* 🛢️\n\n"
            f"Ask me anything about oil prices, OPEC, Kazakhstan energy, "
            f"natural gas, or use the buttons below!\n\n"
            f"_— {AUTHOR} welcomes you!_"
        )
        await update.message.reply_text(resp, parse_mode=ParseMode.MARKDOWN, reply_markup=kb_main())
        await db_log(uid, uname, text, resp)
        return

    # ── 2. Farewell ───────────────────────────────────────────────────────────
    if any(f in lower for f in _FAREWELLS):
        resp = (
            f"👋 Goodbye, *{name}*! Safe travels!\n\n"
            f"Thanks for chatting with *{AUTHOR}'s Bot* 🛢️\n"
            f"Come back when you want the latest prices — markets never sleep!\n\n"
            f"_— {AUTHOR} waves goodbye! 🤝_"
        )
        await update.message.reply_text(resp, parse_mode=ParseMode.MARKDOWN, reply_markup=kb_main())
        await db_log(uid, uname, text, resp)
        return

    # ── 3. Thanks ─────────────────────────────────────────────────────────────
    if any(t in lower for t in _THANKS):
        resp = (
            f"😊 You're very welcome, *{name}*!\n\n"
            f"*{AUTHOR}* is always happy to share oil & gas knowledge!\n"
            f"Feel free to ask anything else. 🛢️"
        )
        await update.message.reply_text(resp, parse_mode=ParseMode.MARKDOWN, reply_markup=kb_main())
        await db_log(uid, uname, text, resp)
        return

    # ── 4. Live price request ─────────────────────────────────────────────────
    if any(w in lower for w in _PRICE_WORDS):
        msg = await update.message.reply_text(
            f"⏳ _Pulling live data… {AUTHOR} is checking the markets!_",
            parse_mode=ParseMode.MARKDOWN,
        )
        prices = await fetch_commodity_prices()
        resp   = format_prices(prices)
        await msg.delete()
        await update.message.reply_text(resp, parse_mode=ParseMode.MARKDOWN, reply_markup=ikb_prices())
        await db_log(uid, uname, text, resp)
        return

    # ── 5. FAQ keyword lookup ─────────────────────────────────────────────────
    faq = await db_faq_lookup(text)
    if faq:
        await update.message.reply_text(faq, parse_mode=ParseMode.MARKDOWN, reply_markup=kb_main())
        await db_log(uid, uname, text, faq)
        return

    # ── 6. Fallback ───────────────────────────────────────────────────────────
    resp = (
        f"🤔 *{AUTHOR}* doesn't have a specific answer for that yet.\n\n"
        f"Try asking about:\n"
        f"• *Brent, WTI, crude, barrel, refinery*\n"
        f"• *OPEC, natural gas, LNG, diesel, petrol*\n"
        f"• *Kazakhstan, gasoline, oil price*\n\n"
        f"Or use the keyboard buttons below for live data! 👇"
    )
    await update.message.reply_text(resp, parse_mode=ParseMode.MARKDOWN, reply_markup=kb_main())
    await db_log(uid, uname, text, resp)


# ─────────────────────────────────────────────────────────────────────────────
#  WEBHOOK SERVER  (aiohttp — same as bot_5 architecture)
# ─────────────────────────────────────────────────────────────────────────────

async def main() -> None:
    await init_db()

    application = Application.builder().token(BOT_TOKEN).build()

    # Commands
    application.add_handler(CommandHandler("start",   cmd_start))
    application.add_handler(CommandHandler("help",    cmd_help))
    application.add_handler(CommandHandler("prices",  cmd_prices))
    application.add_handler(CommandHandler("rates",   cmd_rates))
    application.add_handler(CommandHandler("facts",   cmd_facts))
    application.add_handler(CommandHandler("history", cmd_history))
    application.add_handler(CommandHandler("stats",   cmd_stats))

    # Inline button callbacks
    application.add_handler(CallbackQueryHandler(cb_prices_refresh, pattern=r"^prices:refresh$"))
    application.add_handler(CallbackQueryHandler(cb_rates_show,     pattern=r"^rates:show$"))
    application.add_handler(CallbackQueryHandler(cb_facts_menu,     pattern=r"^facts:menu$"))
    application.add_handler(CallbackQueryHandler(cb_info,           pattern=r"^info:"))
    application.add_handler(CallbackQueryHandler(cb_fact,           pattern=r"^fact:"))
    application.add_handler(CallbackQueryHandler(cb_close,          pattern=r"^close$"))

    # Free text + keyboard buttons
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Register webhook with Telegram
    webhook_full_url = f"{WEBHOOK_URL}{WEBHOOK_PATH}"
    await application.bot.set_webhook(
        url=webhook_full_url,
        allowed_updates=Update.ALL_TYPES,
    )
    logger.info("🔗  Webhook registered: %s", webhook_full_url)

    async def telegram_webhook(request: web.Request) -> web.Response:
        try:
            body   = await request.json()
            upd    = Update.de_json(body, application.bot)
            await application.process_update(upd)
        except Exception as exc:
            logger.error("Webhook processing error: %s", exc)
        return web.Response(text="OK")

    async def health_check(request: web.Request) -> web.Response:
        return web.Response(text=f"🛢️ {AUTHOR}'s Oil & Gas Bot is ONLINE! 📊")

    web_app = web.Application()
    web_app.router.add_post(WEBHOOK_PATH, telegram_webhook)
    web_app.router.add_get("/",       health_check)
    web_app.router.add_get("/health", health_check)

    async with application:
        await application.start()
        runner = web.AppRunner(web_app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()

        logger.info("🚀  %s's Oil Bot running on port %d", AUTHOR, PORT)
        logger.info("🛢️  Markets are open. Bot is live!")

        try:
            await asyncio.Event().wait()
        finally:
            logger.info("📉  Shutting down gracefully…")
            await runner.cleanup()
            await application.stop()


if __name__ == "__main__":
    asyncio.run(main())
