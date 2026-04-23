"""
============================================================
  Eskendir's Oil & Gas Price Tracker Bot
  Author  : Eskendir
  Stack   : Python 3.11+, Aiogram 3.x, SQLite, aiohttp
  Hosting : Render.com (webhook mode)
============================================================
"""

import asyncio
import logging
import os
import sqlite3
from datetime import datetime

import aiohttp
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

# ──────────────────────────────────────────────
#  CONFIGURATION  (set these as env vars on Render)
# ──────────────────────────────────────────────
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
WEBHOOK_HOST: str = os.getenv("WEBHOOK_HOST", "")          # e.g. https://my-bot.onrender.com
WEBHOOK_PATH: str = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL: str = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
WEB_SERVER_HOST: str = "0.0.0.0"
WEB_SERVER_PORT: int = int(os.getenv("PORT", "8080"))

DB_PATH: str = "eskendir_bot.db"

# ──────────────────────────────────────────────
#  LOGGING
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════
#  DATABASE  (SQLite)
# ══════════════════════════════════════════════

def init_db() -> None:
    """Create tables and seed default responses."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # ── Responses table ──────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS responses (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            trigger  TEXT    UNIQUE NOT NULL,
            response TEXT    NOT NULL,
            category TEXT    DEFAULT 'general'
        )
    """)

    # ── Chat history table ───────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_history (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            username     TEXT,
            user_message TEXT    NOT NULL,
            bot_response TEXT    NOT NULL,
            timestamp    DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── Seed responses ───────────────────────
    seeds = [
        # Greetings
        ("hello", "👋 Hello! Eskendir's Oil & Gas Bot is ready! Type /help to see all commands. 🛢️", "greeting"),
        ("hi",    "Hi there! 🛢️ Welcome to Eskendir's energy market tracker!", "greeting"),
        ("hey",   "Hey! Eskendir's bot here — your real-time oil & gas companion. 🔥", "greeting"),
        # Farewells
        ("bye",      "👋 Goodbye! Eskendir's bot will miss you. Stay updated on oil markets! 🛢️", "farewell"),
        ("goodbye",  "See you later! ⛽ Eskendir's bot is always here for your energy needs.", "farewell"),
        ("cya",      "Catch you later! 🔥 Built by Eskendir — come back anytime.", "farewell"),
        # Thanks
        ("thanks",     "You're welcome! 😊 Eskendir built this bot just for you.", "general"),
        ("thank you",  "Happy to help! 🌟 Eskendir put a lot of work into making this useful.", "general"),
        # Info
        ("what is oil",
         "🛢️ Crude oil is a naturally occurring fossil fuel traded globally as WTI and Brent crude. "
         "Eskendir's bot tracks both benchmarks in real-time!", "info"),
        ("what is natural gas",
         "🔥 Natural gas (mostly methane) is used for heating, electricity, and industry. "
         "Eskendir's bot monitors NG futures so you don't have to!", "info"),
        ("what is brent",
         "🌍 Brent Crude is the global oil pricing benchmark extracted from the North Sea. "
         "Eskendir's bot tracks it live — use /prices!", "info"),
        ("what is wti",
         "🛢️ WTI (West Texas Intermediate) is the US oil benchmark. "
         "Eskendir's bot monitors it 24/7 via Yahoo Finance!", "info"),
        # Meta
        ("who made you",
         "🎓 I was created by Eskendir as a school AI chatbot project! "
         "Built with Python, Aiogram 3 and real market data APIs.", "general"),
        ("who is eskendir",
         "Eskendir is the talented developer behind this bot! 🚀 "
         "A student passionate about coding and energy markets.", "general"),
        ("help",
         "📋 Commands: /start /prices /market /trends /about /history\n"
         "Use the keyboard buttons for quick access! — Eskendir's bot", "general"),
    ]
    cur.executemany(
        "INSERT OR IGNORE INTO responses (trigger, response, category) VALUES (?,?,?)",
        seeds,
    )

    conn.commit()
    conn.close()
    logger.info("Database initialised ✔")


def db_lookup(text: str) -> str | None:
    """Search the responses table for the best match."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # Exact match first
    cur.execute("SELECT response FROM responses WHERE LOWER(trigger)=LOWER(?)", (text,))
    row = cur.fetchone()
    if not row:
        # Partial: any trigger is a substring of the message
        cur.execute(
            "SELECT response FROM responses "
            "WHERE LOWER(?) LIKE '%'||LOWER(trigger)||'%' "
            "ORDER BY LENGTH(trigger) DESC LIMIT 1",
            (text,),
        )
        row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def db_save_history(user_id: int, username: str | None, user_msg: str, bot_msg: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO user_history (user_id,username,user_message,bot_response) VALUES (?,?,?,?)",
        (user_id, username or "unknown", user_msg[:512], bot_msg[:512]),
    )
    conn.commit()
    conn.close()


def db_get_history(user_id: int, limit: int = 5) -> list[tuple]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "SELECT user_message,bot_response,timestamp FROM user_history "
        "WHERE user_id=? ORDER BY timestamp DESC LIMIT ?",
        (user_id, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


# ══════════════════════════════════════════════
#  YAHOO FINANCE API  (free, no key required)
# ══════════════════════════════════════════════

SYMBOLS: dict[str, str] = {
    "CL=F":  "🛢️ WTI Crude Oil",
    "BZ=F":  "🌍 Brent Crude Oil",
    "NG=F":  "🔥 Natural Gas",
    "RB=F":  "⛽ RBOB Gasoline",
    "HO=F":  "🔥 Heating Oil",
}

async def yf_fetch(symbol: str) -> dict | None:
    """Fetch latest price from Yahoo Finance (no API key needed)."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; EskendirBot/1.0)"}
    params  = {"interval": "1d", "range": "1d"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, headers=headers, params=params,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                meta = data["chart"]["result"][0]["meta"]
                return {
                    "symbol":     symbol,
                    "price":      meta.get("regularMarketPrice", 0.0),
                    "prev_close": meta.get("chartPreviousClose", 0.0),
                    "currency":   meta.get("currency", "USD"),
                }
    except Exception as exc:
        logger.warning("YFinance fetch error for %s: %s", symbol, exc)
        return None


async def yf_fetch_all() -> dict[str, dict]:
    tasks  = {sym: asyncio.create_task(yf_fetch(sym)) for sym in SYMBOLS}
    result = {}
    for sym, task in tasks.items():
        data = await task
        if data:
            result[sym] = data
    return result


def price_change_str(current: float, prev: float) -> str:
    if prev == 0:
        return ""
    diff = current - prev
    pct  = diff / prev * 100
    icon = "📈" if diff >= 0 else "📉"
    sign = "+" if diff >= 0 else ""
    return f"{icon} {sign}{diff:.2f} ({sign}{pct:.2f}%)"


# ══════════════════════════════════════════════
#  KEYBOARDS
# ══════════════════════════════════════════════

def kb_main() -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text="🛢️ Live Prices"),   KeyboardButton(text="📊 Market Overview"))
    b.row(KeyboardButton(text="📈 Price Trends"),   KeyboardButton(text="ℹ️ About"))
    b.row(KeyboardButton(text="💬 My History"),     KeyboardButton(text="❓ Help"))
    return b.as_markup(resize_keyboard=True)


def ikb_prices() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🛢️ WTI",       callback_data="price:CL=F"),
          InlineKeyboardButton(text="🌍 Brent",      callback_data="price:BZ=F"))
    b.row(InlineKeyboardButton(text="🔥 Nat. Gas",  callback_data="price:NG=F"),
          InlineKeyboardButton(text="⛽ Gasoline",   callback_data="price:RB=F"))
    b.row(InlineKeyboardButton(text="🔥 Heating Oil", callback_data="price:HO=F"),
          InlineKeyboardButton(text="📊 All Prices", callback_data="price:all"))
    b.row(InlineKeyboardButton(text="🔄 Refresh All", callback_data="price:all"))
    return b.as_markup()


def ikb_market() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="📈 Bullish Factors", callback_data="mkt:bullish"),
          InlineKeyboardButton(text="📉 Bearish Factors",  callback_data="mkt:bearish"))
    b.row(InlineKeyboardButton(text="🌍 OPEC+ Info",       callback_data="mkt:opec"),
          InlineKeyboardButton(text="💡 Fun Facts",         callback_data="mkt:facts"))
    b.row(InlineKeyboardButton(text="🔙 Back",             callback_data="mkt:back"))
    return b.as_markup()


def ikb_single(symbol: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🔄 Refresh",        callback_data=f"price:{symbol}"),
          InlineKeyboardButton(text="◀️ All Prices",     callback_data="price:all"))
    return b.as_markup()


# ══════════════════════════════════════════════
#  ROUTER  &  HANDLERS
# ══════════════════════════════════════════════

router = Router()

# ── /start ────────────────────────────────────
@router.message(CommandStart())
async def cmd_start(msg: Message) -> None:
    name = msg.from_user.first_name or "friend"
    text = (
        f"👋 Welcome, <b>{name}</b>!\n\n"
        f"🛢️ <b>Eskendir's Oil & Gas Price Bot</b>\n\n"
        f"I'm your personal energy-market assistant, crafted by <b>Eskendir</b> "
        f"to deliver real-time commodity prices straight to Telegram!\n\n"
        f"<b>What I track:</b>\n"
        f"  🛢️ WTI &amp; Brent Crude Oil\n"
        f"  🔥 Natural Gas futures\n"
        f"  ⛽ Gasoline &amp; Heating Oil\n\n"
        f"Use the menu buttons below or type any message to chat! 💬"
    )
    await msg.answer(text, reply_markup=kb_main(), parse_mode="HTML")
    db_save_history(msg.from_user.id, msg.from_user.username, "/start", text)


# ── /help ─────────────────────────────────────
@router.message(Command("help"))
@router.message(F.text == "❓ Help")
async def cmd_help(msg: Message) -> None:
    text = (
        "🆘 <b>Help — Eskendir's Oil &amp; Gas Bot</b>\n\n"
        "<b>Commands:</b>\n"
        "  /start    — Welcome screen\n"
        "  /prices   — Live commodity prices\n"
        "  /market   — Full market overview\n"
        "  /trends   — What moves prices\n"
        "  /about    — About this project\n"
        "  /history  — Your last conversations\n\n"
        "<b>Chat keywords:</b>\n"
        "  • Greetings → hello, hi, hey\n"
        "  • Farewells → bye, goodbye, cya\n"
        "  • Info      → what is oil, what is WTI, …\n"
        "  • Prices    → price, cost, how much, …\n\n"
        "Built with ❤️ by <b>Eskendir</b> as a school AI chatbot project."
    )
    await msg.answer(text, reply_markup=kb_main(), parse_mode="HTML")
    db_save_history(msg.from_user.id, msg.from_user.username, msg.text or "/help", text)


# ── /prices ───────────────────────────────────
@router.message(Command("prices"))
@router.message(F.text == "🛢️ Live Prices")
async def cmd_prices(msg: Message) -> None:
    text = (
        "🛢️ <b>Select a commodity</b>\n\n"
        "Eskendir's bot fetches live data from Yahoo Finance — no delays, no cost! 📡"
    )
    await msg.answer(text, reply_markup=ikb_prices(), parse_mode="HTML")


# ── /market ───────────────────────────────────
@router.message(Command("market"))
@router.message(F.text == "📊 Market Overview")
async def cmd_market(msg: Message) -> None:
    wait = await msg.answer("⏳ Fetching market data… Eskendir's bot is working!")
    prices = await yf_fetch_all()

    if not prices:
        await wait.edit_text("❌ Could not reach Yahoo Finance. Please try again in a moment.")
        return

    lines = [
        "📊 <b>Market Overview</b>",
        f"<i>by Eskendir's Oil &amp; Gas Bot</i>\n",
    ]
    for sym, d in prices.items():
        chg = price_change_str(d["price"], d["prev_close"])
        label = SYMBOLS.get(sym, sym)
        lines.append(f"{label}\n   💵 <b>${d['price']:.2f}</b>  {chg}\n")

    lines.append(f"🕐 {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("📡 Source: Yahoo Finance | <b>Eskendir</b>")
    text = "\n".join(lines)

    await wait.edit_text(text, reply_markup=ikb_market(), parse_mode="HTML")
    db_save_history(msg.from_user.id, msg.from_user.username, msg.text or "/market", text)


# ── /trends ───────────────────────────────────
@router.message(Command("trends"))
@router.message(F.text == "📈 Price Trends")
async def cmd_trends(msg: Message) -> None:
    text = (
        "📈 <b>What Moves Oil &amp; Gas Prices?</b>\n"
        "<i>Eskendir's market explainer</i>\n\n"
        "🔴 <b>Price RISES when:</b>\n"
        "  • OPEC+ cuts production quotas\n"
        "  • Geopolitical crises (wars, sanctions)\n"
        "  • Cold winter → high heating demand\n"
        "  • Strong Chinese industrial demand\n"
        "  • Shipping disruptions (Suez, Hormuz)\n\n"
        "🟢 <b>Price FALLS when:</b>\n"
        "  • US shale ramps up output\n"
        "  • Strong US Dollar (USD ↑ → oil ↓)\n"
        "  • Weak global GDP / recession fears\n"
        "  • Rising US crude inventory (EIA)\n"
        "  • Warm weather / mild winter\n\n"
        "💡 <b>Pro Tip from Eskendir:</b>\n"
        "Watch the <b>EIA Petroleum Status Report</b> every Wednesday — it's the #1 weekly price catalyst!"
    )
    await msg.answer(text, reply_markup=kb_main(), parse_mode="HTML")
    db_save_history(msg.from_user.id, msg.from_user.username, msg.text or "/trends", text)


# ── /about ────────────────────────────────────
@router.message(Command("about"))
@router.message(F.text == "ℹ️ About")
async def cmd_about(msg: Message) -> None:
    text = (
        "ℹ️ <b>About Eskendir's Oil &amp; Gas Bot</b>\n\n"
        "🤖 <b>Name:</b> Oil &amp; Gas Price Tracker\n"
        "👨‍💻 <b>Developer:</b> Eskendir\n"
        "🎓 <b>Purpose:</b> School AI Chatbot Project\n\n"
        "🔧 <b>Tech Stack:</b>\n"
        "  • Python 3.11+\n"
        "  • Aiogram 3.x (async webhook)\n"
        "  • SQLite (response &amp; history DB)\n"
        "  • Yahoo Finance API (free, no key)\n"
        "  • Render.com (deployment)\n\n"
        "✅ <b>Features:</b>\n"
        "  • Real-time commodity prices\n"
        "  • NLP keyword detection\n"
        "  • SQLite seeded response database\n"
        "  • Inline + reply keyboard buttons\n"
        "  • Full chat history logging\n"
        "  • Async webhook architecture\n\n"
        "Built with ❤️ by <b>Eskendir</b>"
    )
    await msg.answer(text, reply_markup=kb_main(), parse_mode="HTML")


# ── /history ──────────────────────────────────
@router.message(Command("history"))
@router.message(F.text == "💬 My History")
async def cmd_history(msg: Message) -> None:
    rows = db_get_history(msg.from_user.id)
    if not rows:
        await msg.answer(
            "📭 No history yet!\n\nEskendir's bot hasn't recorded any of your messages. "
            "Start chatting! 😊",
            reply_markup=kb_main(),
        )
        return

    lines = ["💬 <b>Your Recent Chats</b>\n<i>(Eskendir's bot remembers you!)</i>\n"]
    for i, (umsg, bresp, ts) in enumerate(rows, 1):
        lines.append(
            f"<b>#{i}</b> [{ts[:16]}]\n"
            f"You: {umsg[:60]}{'…' if len(umsg) > 60 else ''}\n"
            f"Bot: {bresp[:80]}{'…' if len(bresp) > 80 else ''}\n"
        )
    await msg.answer("\n".join(lines), reply_markup=kb_main(), parse_mode="HTML")


# ══════════════════════════════════════════════
#  CALLBACK QUERY HANDLERS
# ══════════════════════════════════════════════

@router.callback_query(F.data.startswith("price:"))
async def cb_price(cb: CallbackQuery) -> None:
    await cb.answer("⏳ Fetching…")
    sym = cb.data.split(":", 1)[1]

    if sym == "all":
        prices = await yf_fetch_all()
        if not prices:
            await cb.message.edit_text("❌ Yahoo Finance unavailable. Try again.")
            return
        lines = ["🛢️ <b>All Commodity Prices</b>\n<i>Eskendir's live tracker</i>\n"]
        for s, d in prices.items():
            chg = price_change_str(d["price"], d["prev_close"])
            lines.append(f"{SYMBOLS.get(s, s)}\n   💵 <b>${d['price']:.2f}</b>  {chg}\n")
        lines.append(f"🕐 {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
        await cb.message.edit_text(
            "\n".join(lines), reply_markup=ikb_prices(), parse_mode="HTML"
        )

    else:
        data = await yf_fetch(sym)
        if not data:
            await cb.message.edit_text("❌ Could not fetch that price. Try again.")
            return
        label = SYMBOLS.get(sym, sym)
        chg   = price_change_str(data["price"], data["prev_close"])
        text  = (
            f"{label}\n\n"
            f"💵 <b>Price:</b>      ${data['price']:.2f}\n"
            f"📊 <b>Change:</b>     {chg}\n"
            f"📉 <b>Prev Close:</b> ${data['prev_close']:.2f}\n"
            f"💱 <b>Currency:</b>   {data['currency']}\n\n"
            f"🕐 {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"📡 Yahoo Finance  |  🤖 <i>Eskendir's Bot</i>"
        )
        await cb.message.edit_text(text, reply_markup=ikb_single(sym), parse_mode="HTML")


@router.callback_query(F.data.startswith("mkt:"))
async def cb_market(cb: CallbackQuery) -> None:
    await cb.answer()
    action = cb.data.split(":", 1)[1]

    if action == "back":
        await cb.message.edit_text(
            "🏠 Use the keyboard menu or /prices to continue!\n<i>Eskendir's bot</i>",
            parse_mode="HTML",
        )
        return

    content: dict[str, str] = {
        "bullish": (
            "📈 <b>Bullish Factors</b>\n<i>Price-raising forces — Eskendir's analysis</i>\n\n"
            "1. 🇸🇦 OPEC+ production cuts\n"
            "2. ⚔️ Middle East geopolitical tensions\n"
            "3. ❄️ Harsh winter / high heating demand\n"
            "4. 🏭 Strong Chinese industrial output\n"
            "5. 🚢 Hormuz / Suez shipping disruptions\n"
            "6. 📉 Low US crude inventory levels\n\n"
            "💡 When these align, brace for price surges!"
        ),
        "bearish": (
            "📉 <b>Bearish Factors</b>\n<i>Price-dropping forces — Eskendir's analysis</i>\n\n"
            "1. 🇺🇸 Record US shale oil production\n"
            "2. 💹 Strong US Dollar (DXY)\n"
            "3. 😔 Weak global GDP / recession fears\n"
            "4. ☀️ Mild winter / low heating demand\n"
            "5. 🔋 EV adoption reducing gasoline use\n"
            "6. 📈 Rising EIA weekly inventory builds\n\n"
            "💡 When these align, expect prolonged weakness!"
        ),
        "opec": (
            "🌍 <b>OPEC+ Explained</b>\n<i>by Eskendir's bot</i>\n\n"
            "🏢 <b>Full name:</b> Organization of Petroleum Exporting Countries + allies\n"
            "👥 <b>Members:</b> 23 nations\n"
            "🛢️ <b>Market share:</b> ~40 % of global supply\n"
            "📅 <b>Meets:</b> Several times per year (Ministerial Conference)\n\n"
            "<b>Key members:</b>\n"
            "  🇸🇦 Saudi Arabia (de-facto leader)\n"
            "  🇷🇺 Russia\n"
            "  🇦🇪 UAE  •  🇮🇶 Iraq  •  🇰🇼 Kuwait\n\n"
            "💡 A single OPEC+ announcement can swing prices by 5–10 % overnight!"
        ),
        "facts": (
            "💡 <b>Oil &amp; Gas Fun Facts</b>\n<i>Eskendir's favourite trivia</i>\n\n"
            "🛢️ 1 barrel = 42 US gallons = 159 litres\n"
            "🌍 World consumes ~102 M barrels/day\n"
            "⛽ Oil was first commercially drilled in 1859 (PA, USA)\n"
            "🔥 Natural Gas is 70–90 % methane (CH₄)\n"
            "🏆 Venezuela has the world's largest proven reserves\n"
            "🇺🇸 USA is the world's #1 oil producer\n"
            "💰 Oil is priced in USD globally — the 'petrodollar'\n"
            "🌡️ Gas prices spike hard in winter months\n\n"
            "🎓 <b>From Eskendir:</b> 'Petroleum' comes from Latin\n"
            "   <i>petra</i> (rock) + <i>oleum</i> (oil) = 'rock oil'!"
        ),
    }

    text = content.get(action, "❓ Unknown option")
    await cb.message.edit_text(text, reply_markup=ikb_market(), parse_mode="HTML")


# ══════════════════════════════════════════════
#  CATCH-ALL TEXT HANDLER  (NLP + DB lookup)
# ══════════════════════════════════════════════

GREETINGS = {"hello", "hi", "hey", "howdy", "sup", "what's up", "greetings",
              "good morning", "good afternoon", "good evening", "morning", "evening"}
FAREWELLS = {"bye", "goodbye", "see you", "cya", "farewell", "later",
              "take care", "see ya", "toodles"}
OIL_KW    = {"oil", "crude", "brent", "wti", "barrel", "petroleum", "opec"}
GAS_KW    = {"gas", "natural gas", "fuel", "gasoline", "petrol", "lng",
              "heating oil", "diesel"}
PRICE_KW  = {"price", "cost", "how much", "rate", "value", "worth", "dollar",
              "usd", "market"}


@router.message(F.text)
async def handle_text(msg: Message) -> None:
    raw  = msg.text or ""
    text = raw.strip().lower()

    # 1. SQLite lookup
    db_resp = db_lookup(text)
    if db_resp:
        await msg.answer(db_resp, reply_markup=kb_main(), parse_mode="HTML")
        db_save_history(msg.from_user.id, msg.from_user.username, raw, db_resp)
        return

    words = set(text.split())

    # 2. Greeting detection
    if words & GREETINGS or any(g in text for g in GREETINGS):
        resp = (
            "👋 Hello! Eskendir's Oil &amp; Gas Bot is at your service!\n\n"
            "Tap <b>🛢️ Live Prices</b> to see real-time commodity data, "
            "or /help for all commands. 🔥"
        )
        await msg.answer(resp, reply_markup=kb_main(), parse_mode="HTML")
        db_save_history(msg.from_user.id, msg.from_user.username, raw, resp)
        return

    # 3. Farewell detection
    if words & FAREWELLS or any(f in text for f in FAREWELLS):
        resp = (
            "👋 Goodbye! Thanks for using Eskendir's Oil &amp; Gas Bot.\n"
            "Come back anytime to check live energy prices! 🛢️⛽"
        )
        await msg.answer(resp, reply_markup=kb_main(), parse_mode="HTML")
        db_save_history(msg.from_user.id, msg.from_user.username, raw, resp)
        return

    # 4. Oil keyword → show price picker
    if words & OIL_KW or any(k in text for k in OIL_KW):
        resp = "🛢️ Interested in oil prices? Eskendir's bot has you covered! Pick a market:"
        await msg.answer(resp, reply_markup=ikb_prices(), parse_mode="HTML")
        db_save_history(msg.from_user.id, msg.from_user.username, raw, resp)
        return

    # 5. Gas keyword → show price picker
    if words & GAS_KW or any(k in text for k in GAS_KW):
        resp = "⛽ Gas prices? Eskendir's bot tracks Natural Gas and Gasoline futures live! Select:"
        await msg.answer(resp, reply_markup=ikb_prices(), parse_mode="HTML")
        db_save_history(msg.from_user.id, msg.from_user.username, raw, resp)
        return

    # 6. Generic price enquiry
    if words & PRICE_KW or any(k in text for k in PRICE_KW):
        resp = "💰 Looking for prices? Eskendir's bot fetches real-time commodity data. Choose:"
        await msg.answer(resp, reply_markup=ikb_prices(), parse_mode="HTML")
        db_save_history(msg.from_user.id, msg.from_user.username, raw, resp)
        return

    # 7. Fallback
    fallback = (
        "🤔 I didn't quite catch that, but Eskendir's bot specialises in oil &amp; gas markets!\n\n"
        "Try asking about:\n"
        "  • 🛢️ Oil / crude prices\n"
        "  • ⛽ Gas / gasoline prices\n"
        "  • 📊 Market overview\n\n"
        "Or use /help to explore all commands!"
    )
    await msg.answer(fallback, reply_markup=kb_main(), parse_mode="HTML")
    db_save_history(msg.from_user.id, msg.from_user.username, raw, fallback)


# ══════════════════════════════════════════════
#  WEBHOOK SERVER  (aiohttp)
# ══════════════════════════════════════════════

async def on_startup(bot: Bot) -> None:
    await bot.set_webhook(WEBHOOK_URL)
    logger.info("Webhook registered → %s", WEBHOOK_URL)


async def on_shutdown(bot: Bot) -> None:
    await bot.delete_webhook()
    logger.info("Webhook removed.")


async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is not set!")
    if not WEBHOOK_HOST:
        raise RuntimeError("WEBHOOK_HOST environment variable is not set!")

    init_db()

    bot = Bot(token=BOT_TOKEN)
    dp  = Dispatcher()
    dp.include_router(router)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, WEB_SERVER_HOST, WEB_SERVER_PORT).start()

    logger.info("Server running on %s:%s", WEB_SERVER_HOST, WEB_SERVER_PORT)
    await asyncio.Event().wait()          # run forever


if __name__ == "__main__":
    asyncio.run(main())
