"""
============================================================
  Eskendir's Oil & Gas Price Tracker Bot
  Author  : Eskendir
  Stack   : python-telegram-bot 21.x, aiosqlite, aiohttp
  Hosting : Render.com (webhook mode)
  Pattern : Identical to the working Alisher/Aruzhan bot
============================================================
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
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIGURATION  (set these as environment variables on Render)
# ─────────────────────────────────────────────────────────────────────────────
BOT_TOKEN    = os.environ.get("BOT_TOKEN",   "YOUR_BOT_TOKEN_HERE")
WEBHOOK_URL  = os.environ.get("WEBHOOK_URL", "https://YOUR-APP.onrender.com")
PORT         = int(os.environ.get("PORT",    8080))
DB_PATH      = "eskendir_bot.db"
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  ESKENDIR'S VOICE  — prepended to every reply
# ─────────────────────────────────────────────────────────────────────────────
_ESKENDIR_INTROS = [
    "🛢️ *Eskendir says:*",
    "⛽ *Eskendir, keeper of the markets, reports:*",
    "📊 *Eskendir shares:*",
    "💹 *Eskendir's market insight:*",
    "🔥 *Eskendir replies:*",
    "🌍 *Eskendir, born of petrodollars, tells you:*",
    "📡 *Eskendir reports live:*",
    "🧠 *Eskendir intercepts your signal:*",
]

def eskendir(msg: str) -> str:
    """Wrap every outgoing message in Eskendir's voice."""
    return f"{random.choice(_ESKENDIR_INTROS)}\n\n{msg}"


# ─────────────────────────────────────────────────────────────────────────────
#  DATABASE  (aiosqlite — same pattern as bot_5.py)
# ─────────────────────────────────────────────────────────────────────────────

_SEED_RESPONSES = [
    # (category, keyword, response)
    # ── Greetings ─────────────────────────────────────────────────────────────
    ("greeting", "hello",
     "Greetings, energy enthusiast! 🛢️ The oil markets have been waiting for you.\n"
     "Ask me about crude oil or gas prices, or type /help to explore!"),
    ("greeting", "hi",
     "Hi there! ⛽ Ready to dive into energy markets?\n"
     "Eskendir's bot tracks WTI, Brent, Natural Gas and more — live!"),
    ("greeting", "hey",
     "Hey! The markets are moving — and so are you! 📊\n"
     "Try /prices for live data or /quiz to test your energy market IQ!"),
    ("greeting", "good morning",
     "Good morning! ☀️ The pre-market session is underway.\n"
     "Eskendir suggests checking /prices before the day session opens! 🛢️"),
    ("greeting", "good evening",
     "Good evening! 🌙 Asian markets are opening and oil is on the move.\n"
     "Perfect time to check /market for an overview! ⛽"),
    ("greeting", "good night",
     "Good night! 🌟 Futures markets never sleep, but you should.\n"
     "Eskendir will keep watching the charts until you return! 🛢️"),
    # ── Farewells ─────────────────────────────────────────────────────────────
    ("farewell", "bye",
     "Farewell, market watcher! 📈 May the price always move your way.\n"
     "Eskendir will keep monitoring the barrels until your return! 🛢️"),
    ("farewell", "goodbye",
     "Goodbye! 💫 Remember — you are now an energy market expert.\n"
     "Go out there and talk about oil like Eskendir would! ⛽"),
    ("farewell", "see you",
     "See you on the next trading session! 🌍 The markets will miss you.\n"
     "Eskendir will be here, watching crude oil futures! 📊"),
    ("farewell", "later",
     "Later, trader! 🚀 Brent and WTI will keep moving while you're gone.\n"
     "Eskendir's bot is always here for your energy market updates!"),
    ("farewell", "cya",
     "Cya! ✨ Safe travels through the volatile commodity markets.\n"
     "Eskendir sends you off with a barrel of good vibes! 🛢️"),
    # ── Questions / Topics ────────────────────────────────────────────────────
    ("question", "who are you",
     "I am Eskendir's Oil & Gas Price Bot, your guide to energy markets! 🛢️\n"
     "I fetch live prices, explain market forces, and quiz you on commodities.\n"
     "Type /help to see everything I can do!"),
    ("question", "what can you do",
     "Here is what Eskendir's bot does:\n\n"
     "• /prices — Live commodity prices (Yahoo Finance)\n"
     "• /market — Full market overview with analysis\n"
     "• /trends — What drives oil & gas prices\n"
     "• /quiz — Energy market trivia challenge\n"
     "• /stats — Your engagement profile\n"
     "• /about — About this school project\n"
     "• /help — Full help menu\n\n"
     "Or just chat — Eskendir understands greetings, farewells, and market questions!"),
    ("question", "how are you",
     "I am as stable as Brent Crude on a calm trading day — doing great! 📊\n"
     "The spreads are tight, the API is responding, and Eskendir is pleased.\n"
     "How are YOUR positions doing today, trader?"),
    ("question", "what is oil",
     "Crude oil is a naturally occurring fossil fuel — the lifeblood of the global economy! 🛢️\n"
     "It's traded as WTI (US benchmark) and Brent (global benchmark).\n"
     "Eskendir reminds you: the world consumes ~102 million barrels every single day!"),
    ("question", "what is natural gas",
     "Natural gas (mostly methane, CH4) is used for heating, electricity, and industry! 🔥\n"
     "It trades as Henry Hub futures in the US and TTF in Europe.\n"
     "Eskendir's bot tracks NG=F futures via Yahoo Finance in real time!"),
    ("question", "what is brent",
     "Brent Crude is the global oil pricing benchmark, extracted from the North Sea. 🌍\n"
     "About 65-70% of global oil is priced against Brent.\n"
     "Eskendir's favourite benchmark — use /prices to see it live!"),
    ("question", "what is wti",
     "WTI (West Texas Intermediate) is the US oil benchmark, stored in Cushing, Oklahoma. 🛢️\n"
     "WTI typically trades at a small discount to Brent.\n"
     "Eskendir's bot fetches both — use /prices to compare them!"),
    ("question", "what is opec",
     "OPEC+ is the cartel of 23 oil-producing nations controlling ~40% of global supply. 🌍\n"
     "Led by Saudi Arabia, its production decisions move markets by 5-10% overnight!\n"
     "Eskendir watches every OPEC+ meeting announcement closely. 📊"),
    # ── Fun ───────────────────────────────────────────────────────────────────
    ("fun", "joke",
     "Why did the oil trader break up? 😄\n"
     "Because the relationship was too CRUDE!\n"
     "Eskendir approved this joke — even commodities traders need to laugh! 🛢️"),
    ("fun", "fact",
     "Did you know? 🌟 One barrel of oil = 42 US gallons = 159 litres!\n"
     "It's a measurement from the 1860s when oil was stored in wooden whiskey barrels.\n"
     "Eskendir considers this history's most consequential barrel! 🛢️"),
    ("fun", "bored",
     "Bored?! 😱 With oil hitting new highs and OPEC+ in session?!\n"
     "Eskendir insists you try /quiz, /prices, or /market immediately.\n"
     "The energy markets have infinite drama — boredom is simply not permitted! 📊"),
    ("fun", "love",
     "Ah, love! 💕 Eskendir says: find someone who looks at you\n"
     "the way Saudi Arabia looks at oil revenue. 🛢️"),
]


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS responses (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                category  TEXT NOT NULL,
                keyword   TEXT NOT NULL,
                response  TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id    INTEGER PRIMARY KEY,
                username   TEXT,
                first_seen TEXT NOT NULL,
                msg_count  INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS conversation_log (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   INTEGER NOT NULL,
                message   TEXT,
                response  TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        await db.execute("DELETE FROM responses")
        await db.executemany(
            "INSERT INTO responses (category, keyword, response) VALUES (?, ?, ?)",
            _SEED_RESPONSES,
        )
        await db.commit()
    logger.info("✅  Database initialised with %d seeded responses", len(_SEED_RESPONSES))


async def db_keyword_lookup(text: str) -> str | None:
    lower = text.lower()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT response FROM responses "
            "WHERE ? LIKE '%' || keyword || '%' "
            "ORDER BY RANDOM() LIMIT 1",
            (lower,),
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else None


async def db_log(user_id: int, username: str | None, message: str, response: str) -> None:
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO conversation_log (user_id, message, response, timestamp) "
            "VALUES (?, ?, ?, ?)",
            (user_id, message[:512], response[:512], now),
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


async def db_user_stats(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT msg_count, first_seen FROM users WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return {"count": row[0], "since": row[1][:10]} if row else {"count": 0, "since": "just now"}


# ─────────────────────────────────────────────────────────────────────────────
#  EXTERNAL API  — Yahoo Finance (free, no key, no registration needed)
# ─────────────────────────────────────────────────────────────────────────────

SYMBOLS = {
    "CL=F": "WTI Crude Oil",
    "BZ=F": "Brent Crude Oil",
    "NG=F": "Natural Gas",
    "RB=F": "RBOB Gasoline",
    "HO=F": "Heating Oil",
}

SYMBOL_ICONS = {
    "CL=F": "🛢️",
    "BZ=F": "🌍",
    "NG=F": "🔥",
    "RB=F": "⛽",
    "HO=F": "🔥",
}


async def yf_fetch(symbol: str) -> dict | None:
    url     = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
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
        logger.warning("YFinance error for %s: %s", symbol, exc)
        return None


async def yf_fetch_all() -> dict:
    results = {}
    for sym in SYMBOLS:
        data = await yf_fetch(sym)
        if data:
            results[sym] = data
    return results


def price_change_str(current: float, prev: float) -> str:
    if prev == 0:
        return ""
    diff = current - prev
    pct  = diff / prev * 100
    icon = "📈" if diff >= 0 else "📉"
    sign = "+" if diff >= 0 else ""
    return f"{icon} {sign}{diff:.2f} ({sign}{pct:.2f}%)"


# ─────────────────────────────────────────────────────────────────────────────
#  BOT DATA  — quiz, ranks, market blurbs
# ─────────────────────────────────────────────────────────────────────────────

_QUIZ = [
    {"q": "How many gallons are in one barrel of oil? 🛢️", "a": "42",
     "hint": "It comes from the size of old wooden whiskey barrels!"},
    {"q": "What is the global oil price benchmark called? 🌍", "a": "brent",
     "hint": "Extracted from the North Sea — think UK/Norway!"},
    {"q": "Which country is the world's #1 oil producer? 🇺🇸", "a": "usa",
     "hint": "Shale revolution! Think Texas and North Dakota."},
    {"q": "Approximately how many million barrels does the world use per day? 📊", "a": "102",
     "hint": "It's about 100 million — try the exact figure!"},
    {"q": "Which planet is the US oil benchmark named after? 🛢️", "a": "wti",
     "hint": "West Texas... Intermediate! Stored in Cushing, Oklahoma."},
    {"q": "What gas makes up most of natural gas? 🔥", "a": "methane",
     "hint": "Chemical formula CH4 — the lightest hydrocarbon!"},
    {"q": "In what year was oil first commercially drilled? ⛽", "a": "1859",
     "hint": "Pennsylvania, USA — mid 19th century!"},
    {"q": "What does EIA stand for? 📋", "a": "energy information administration",
     "hint": "It's a US government agency that publishes weekly oil inventory reports!"},
]

_RANKS = [
    (0,   4,  "🌍 Rookie Trader"),
    (5,   14, "📊 Market Watcher"),
    (15,  29, "⛽ Futures Analyst"),
    (30,  49, "🛢️ Commodity Expert"),
    (50,  99, "💹 Senior Energy Trader"),
    (100, 9999, "🏆 Eskendir-Level Pro"),
]

def _rank(count: int) -> str:
    for lo, hi, label in _RANKS:
        if lo <= count <= hi:
            return label
    return "🏆 Eskendir-Level Pro"

_MARKET_INFO = {
    "bullish": (
        "📈 Bullish Factors — What pushes prices UP\n"
        "Eskendir's analysis:\n\n"
        "1. 🇸🇦 OPEC+ production cuts\n"
        "2. ⚔️ Middle East geopolitical tensions\n"
        "3. ❄️ Cold winter / high heating demand\n"
        "4. 🏭 Strong Chinese industrial output\n"
        "5. 🚢 Hormuz / Suez shipping disruptions\n"
        "6. 📉 Low US crude inventory builds\n\n"
        "💡 When these align, brace for price surges!"
    ),
    "bearish": (
        "📉 Bearish Factors — What pushes prices DOWN\n"
        "Eskendir's analysis:\n\n"
        "1. 🇺🇸 Record US shale oil production\n"
        "2. 💹 Strong US Dollar (DXY index rises)\n"
        "3. 😔 Weak global GDP / recession fears\n"
        "4. ☀️ Mild winter / low heating demand\n"
        "5. 🔋 EV adoption reducing gasoline demand\n"
        "6. 📈 Rising EIA weekly inventory builds\n\n"
        "💡 When these align, expect prolonged weakness!"
    ),
    "opec": (
        "🌍 OPEC+ Explained\n"
        "by Eskendir's bot\n\n"
        "Full name: Organization of Petroleum Exporting Countries + allies\n"
        "Members: 23 nations\n"
        "Market share: ~40% of global supply\n"
        "Meets: Several times per year\n\n"
        "Key members:\n"
        "  🇸🇦 Saudi Arabia (de-facto leader)\n"
        "  🇷🇺 Russia\n"
        "  🇦🇪 UAE  |  🇮🇶 Iraq  |  🇰🇼 Kuwait\n\n"
        "💡 A single OPEC+ announcement can swing prices by 5-10% overnight!"
    ),
    "facts": (
        "💡 Oil & Gas Fun Facts\n"
        "Eskendir's favourite trivia:\n\n"
        "🛢️ 1 barrel = 42 US gallons = 159 litres\n"
        "🌍 World uses ~102 million barrels/day\n"
        "⛽ Oil first drilled commercially in 1859 (Pennsylvania)\n"
        "🔥 Natural Gas is 70-90% methane (CH4)\n"
        "🏆 Venezuela has the world's largest proven reserves\n"
        "🇺🇸 USA is world's #1 oil producer (shale revolution)\n"
        "💰 Oil is priced in USD globally — the 'petrodollar'\n"
        "🌡️ Gas prices spike hard in winter months\n\n"
        "From Eskendir: 'Petroleum' comes from Latin\n"
        "   petra (rock) + oleum (oil) = 'rock oil'!"
    ),
}

_FALLBACKS = [
    "🤔 Hmm, even the oil markets are pondering that one!\n"
    "Try /help to see what Eskendir's bot can do, or ask me about crude oil! ⛽",

    "📊 Interesting message — Eskendir is still decoding your signal.\n"
    "Meanwhile, grab live /prices or check the /market overview! 🛢️",

    "🛢️ Eskendir is expanding his vocabulary!\n"
    "Try /quiz for instant energy market knowledge! 💹",

    "⭐ That's a thought worthy of an OPEC boardroom!\n"
    "Challenge yourself with a /quiz or check /trends! 📈",

    "📡 Signal partially received from the trading floor!\n"
    "Try asking about oil, gas, prices, or markets! 🔥",
]


# ─────────────────────────────────────────────────────────────────────────────
#  KEYBOARDS
# ─────────────────────────────────────────────────────────────────────────────

def kb_main() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["🛢️ Live Prices",    "📊 Market Overview"],
            ["📈 Price Trends",   "ℹ️ About"],
            ["💬 My Stats",       "❓ Help"],
        ],
        resize_keyboard=True,
    )


def ikb_prices() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛢️ WTI Crude",   callback_data="price:CL=F"),
         InlineKeyboardButton("🌍 Brent Crude",  callback_data="price:BZ=F")],
        [InlineKeyboardButton("🔥 Natural Gas",  callback_data="price:NG=F"),
         InlineKeyboardButton("⛽ Gasoline",      callback_data="price:RB=F")],
        [InlineKeyboardButton("🔥 Heating Oil",  callback_data="price:HO=F"),
         InlineKeyboardButton("📊 All Prices",   callback_data="price:all")],
        [InlineKeyboardButton("🔄 Refresh All",  callback_data="price:all")],
    ])


def ikb_market() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📈 Bullish Factors",  callback_data="mkt:bullish"),
         InlineKeyboardButton("📉 Bearish Factors",  callback_data="mkt:bearish")],
        [InlineKeyboardButton("🌍 OPEC+ Info",       callback_data="mkt:opec"),
         InlineKeyboardButton("💡 Fun Facts",         callback_data="mkt:facts")],
        [InlineKeyboardButton("🔙 Close",             callback_data="mkt:close")],
    ])


def ikb_single(symbol: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh",       callback_data=f"price:{symbol}"),
         InlineKeyboardButton("◀️ All Prices",    callback_data="price:all")],
    ])


# ─────────────────────────────────────────────────────────────────────────────
#  COMMAND HANDLERS
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    name = update.effective_user.first_name or "energy enthusiast"
    text = (
        f"🌍 Welcome to Eskendir's Oil & Gas Bot, {name}!\n\n"
        "Your personal energy market assistant, tracking real-time commodity prices!\n\n"
        "✨ Commands available:\n"
        "• /prices — Live commodity prices (Yahoo Finance)\n"
        "• /market — Full market overview\n"
        "• /trends — What drives oil & gas prices\n"
        "• /quiz — Energy market trivia challenge\n"
        "• /stats — Your engagement profile\n"
        "• /about — About this school project\n"
        "• /help — Full help menu\n\n"
        "Or simply chat — say hello, ask about oil, gas, prices! 🛢️"
    )
    await update.message.reply_text(
        eskendir(text), parse_mode=ParseMode.MARKDOWN, reply_markup=kb_main()
    )
    await db_log(update.effective_user.id, update.effective_user.username, "/start", text)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "🆘 *Eskendir's Oil & Gas Bot — Help Menu*\n\n"
        "📡 *Live Market Data:*\n"
        "• /prices — Real-time commodity prices\n"
        "• /market — Full market overview with analysis\n\n"
        "📈 *Market Education:*\n"
        "• /trends — What moves oil & gas prices\n"
        "• /quiz — Test your energy market knowledge!\n"
        "• /hint — Hint for the current quiz question\n\n"
        "📊 *Your Profile:*\n"
        "• /stats — Message count, rank, and journey\n"
        "• /about — About this school project\n\n"
        "💬 *Just Chat:*\n"
        "Try: hello / bye / what is oil / what is WTI /\n"
        "what is OPEC / tell me a joke / bored ...\n\n"
        "Eskendir hears everything! ✨"
    )
    await update.message.reply_text(
        eskendir(text), parse_mode=ParseMode.MARKDOWN, reply_markup=kb_main()
    )


async def cmd_prices(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "🛢️ *Select a commodity to check its live price:*\n\n"
        "Eskendir's bot fetches real-time data from Yahoo Finance!\n"
        "No API key, no cost, fully live. 📡"
    )
    await update.message.reply_text(
        eskendir(text), parse_mode=ParseMode.MARKDOWN, reply_markup=ikb_prices()
    )


async def cmd_market(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    wait_msg = await update.message.reply_text(
        eskendir("⏳ _Fetching live market data... Eskendir's bot is working!_"),
        parse_mode=ParseMode.MARKDOWN,
    )
    prices = await yf_fetch_all()

    if not prices:
        await wait_msg.edit_text(
            eskendir("❌ Yahoo Finance is unavailable right now. Please try again in a moment."),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    lines = ["📊 *Market Overview*", "_by Eskendir's Oil & Gas Bot_\n"]
    for sym, d in prices.items():
        chg   = price_change_str(d["price"], d["prev_close"])
        icon  = SYMBOL_ICONS.get(sym, "")
        name  = SYMBOLS.get(sym, sym)
        lines.append(f"{icon} *{name}*\n   💵 ${d['price']:.2f}  {chg}\n")

    lines.append(f"🕐 {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("📡 Source: Yahoo Finance | Built by *Eskendir*")
    text = "\n".join(lines)

    await wait_msg.edit_text(
        eskendir(text), parse_mode=ParseMode.MARKDOWN, reply_markup=ikb_market()
    )
    await db_log(update.effective_user.id, update.effective_user.username, "/market", text)


async def cmd_trends(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "📈 *What Moves Oil & Gas Prices?*\n"
        "_Eskendir's market explainer_\n\n"
        "🔴 *Price RISES when:*\n"
        "• OPEC+ cuts production quotas\n"
        "• Geopolitical crises (wars, sanctions)\n"
        "• Cold winter → high heating demand\n"
        "• Strong Chinese industrial demand\n"
        "• Shipping disruptions (Suez, Hormuz)\n\n"
        "🟢 *Price FALLS when:*\n"
        "• US shale ramps up output\n"
        "• Strong US Dollar (USD rises → oil drops)\n"
        "• Weak global GDP / recession fears\n"
        "• Rising US crude inventory (EIA)\n"
        "• Warm weather / mild winter\n\n"
        "💡 *Pro Tip from Eskendir:*\n"
        "Watch the *EIA Petroleum Status Report* every Wednesday!\n"
        "It's the #1 weekly price catalyst. 📊"
    )
    await update.message.reply_text(
        eskendir(text), parse_mode=ParseMode.MARKDOWN, reply_markup=kb_main()
    )
    await db_log(update.effective_user.id, update.effective_user.username, "/trends", text)


async def cmd_about(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "ℹ️ *About Eskendir's Oil & Gas Bot*\n\n"
        "🤖 *Name:* Oil & Gas Price Tracker\n"
        "👨‍💻 *Developer:* Eskendir\n"
        "🎓 *Purpose:* School AI Chatbot Project\n\n"
        "🔧 *Tech Stack:*\n"
        "  • Python 3.11+\n"
        "  • python-telegram-bot 21.x (async webhook)\n"
        "  • aiosqlite (async SQLite database)\n"
        "  • Yahoo Finance API (free, no key needed)\n"
        "  • Render.com (deployment)\n\n"
        "✅ *Features:*\n"
        "  • Real-time commodity prices\n"
        "  • NLP keyword detection\n"
        "  • SQLite seeded response database\n"
        "  • Inline + reply keyboard buttons\n"
        "  • Full chat history logging\n"
        "  • Async webhook architecture\n\n"
        "Built with ❤️ by *Eskendir* for a school assignment"
    )
    await update.message.reply_text(
        eskendir(text), parse_mode=ParseMode.MARKDOWN, reply_markup=kb_main()
    )


async def cmd_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = random.choice(_QUIZ)
    context.user_data["quiz_answer"] = q["a"].lower()
    context.user_data["quiz_hint"]   = q["hint"]
    text = (
        f"🧠 *Energy Market Trivia Challenge!*\n\n"
        f"❓ {q['q']}\n\n"
        f"_Type your answer below! Stuck? Use /hint_ ✨"
    )
    await update.message.reply_text(eskendir(text), parse_mode=ParseMode.MARKDOWN)
    await db_log(update.effective_user.id, update.effective_user.username, "/quiz", q["q"])


async def cmd_hint(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    hint = context.user_data.get("quiz_hint")
    if hint:
        text = f"💡 *Hint:* _{hint}_\n\nYou've got this! 🧠✨"
    else:
        text = "🤔 No active quiz question right now! Start one with /quiz 😄"
    await update.message.reply_text(eskendir(text), parse_mode=ParseMode.MARKDOWN)


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    stats = await db_user_stats(update.effective_user.id)
    count = stats["count"]
    since = stats["since"]
    rank  = _rank(count)
    next_rank = next(
        (label for lo, hi, label in _RANKS if lo > count), "You've reached the peak! 🏆"
    )
    text = (
        f"📊 *Your Trading Journey*\n\n"
        f"✉️ Messages sent: *{count}*\n"
        f"📅 Trading since: *{since}*\n"
        f"🏅 Current rank: *{rank}*\n"
        f"⬆️ Next rank: *{next_rank}*\n\n"
        f"_Every question makes you a better energy trader!_ 🛢️"
    )
    await update.message.reply_text(
        eskendir(text), parse_mode=ParseMode.MARKDOWN, reply_markup=kb_main()
    )
    await db_log(update.effective_user.id, update.effective_user.username, "/stats", text)


# ─────────────────────────────────────────────────────────────────────────────
#  CALLBACK QUERY HANDLER  (inline buttons)
# ─────────────────────────────────────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data  = query.data

    # ── Price buttons ─────────────────────────────────────────────────────────
    if data.startswith("price:"):
        sym = data.split(":", 1)[1]

        if sym == "all":
            await query.edit_message_text(
                eskendir("⏳ _Fetching all commodity prices..._"),
                parse_mode=ParseMode.MARKDOWN,
            )
            prices = await yf_fetch_all()
            if not prices:
                await query.edit_message_text(
                    eskendir("❌ Yahoo Finance unavailable. Try again shortly."),
                    parse_mode=ParseMode.MARKDOWN,
                )
                return
            lines = ["🛢️ *All Commodity Prices*\n_Eskendir's live tracker_\n"]
            for s, d in prices.items():
                chg  = price_change_str(d["price"], d["prev_close"])
                icon = SYMBOL_ICONS.get(s, "")
                name = SYMBOLS.get(s, s)
                lines.append(f"{icon} *{name}*\n   💵 ${d['price']:.2f}  {chg}\n")
            lines.append(f"🕐 {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
            await query.edit_message_text(
                eskendir("\n".join(lines)),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=ikb_prices(),
            )
        else:
            await query.edit_message_text(
                eskendir(f"⏳ _Fetching {SYMBOLS.get(sym, sym)}..._"),
                parse_mode=ParseMode.MARKDOWN,
            )
            d = await yf_fetch(sym)
            if not d:
                await query.edit_message_text(
                    eskendir("❌ Could not fetch that price. Please try again."),
                    parse_mode=ParseMode.MARKDOWN,
                )
                return
            icon  = SYMBOL_ICONS.get(sym, "")
            name  = SYMBOLS.get(sym, sym)
            chg   = price_change_str(d["price"], d["prev_close"])
            ts    = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
            text  = (
                f"{icon} *{name}*\n\n"
                f"💵 *Price:*      ${d['price']:.2f}\n"
                f"📊 *Change:*     {chg}\n"
                f"📉 *Prev Close:* ${d['prev_close']:.2f}\n"
                f"💱 *Currency:*   {d['currency']}\n\n"
                f"🕐 {ts}\n"
                f"📡 Yahoo Finance  |  🤖 _Eskendir's Bot_"
            )
            await query.edit_message_text(
                eskendir(text),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=ikb_single(sym),
            )

    # ── Market info buttons ───────────────────────────────────────────────────
    elif data.startswith("mkt:"):
        action = data.split(":", 1)[1]
        if action == "close":
            await query.edit_message_text(
                eskendir("🏠 Use the keyboard menu or /prices to continue!\nEskendir's bot"),
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        text = _MARKET_INFO.get(action, "Unknown option")
        await query.edit_message_text(
            eskendir(text),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ikb_market(),
        )


# ─────────────────────────────────────────────────────────────────────────────
#  MESSAGE HANDLER  — free-text conversations
# ─────────────────────────────────────────────────────────────────────────────

_BUTTON_MAP = {
    "🛢️ live prices":     "prices",
    "📊 market overview":  "market",
    "📈 price trends":     "trends",
    "ℹ️ about":            "about",
    "💬 my stats":         "stats",
    "❓ help":             "help",
}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text  = update.message.text.strip()
    lower = text.lower()
    uid   = update.effective_user.id
    uname = update.effective_user.username

    # ── Keyboard button shortcuts ─────────────────────────────────────────────
    shortcut = _BUTTON_MAP.get(lower)
    if shortcut == "prices":
        await cmd_prices(update, context); return
    elif shortcut == "market":
        await cmd_market(update, context); return
    elif shortcut == "trends":
        await cmd_trends(update, context); return
    elif shortcut == "about":
        await cmd_about(update, context); return
    elif shortcut == "stats":
        await cmd_stats(update, context); return
    elif shortcut == "help":
        await cmd_help(update, context); return

    response: str | None = None

    # ── 1. Active quiz answer check ───────────────────────────────────────────
    quiz_ans = context.user_data.get("quiz_answer")
    if quiz_ans and quiz_ans in lower:
        response = (
            f"🎉 *Correct! Absolutely brilliant!*\n\n"
            f"_The answer was:_ *{quiz_ans.capitalize()}*\n\n"
            f"Ready for another challenge? Type /quiz! 🚀"
        )
        context.user_data.pop("quiz_answer", None)
        context.user_data.pop("quiz_hint",   None)
        await update.message.reply_text(eskendir(response), parse_mode=ParseMode.MARKDOWN)
        await db_log(uid, uname, text, response)
        return

    if quiz_ans:
        wrongs = [
            "🤔 Not quite! The markets are fickle — try again, or use /hint! ✨",
            "❌ Hmm, not this time! Give it another shot or ask for a /hint! 📊",
            "🌍 Close, but no! Eskendir believes in you though! Try once more or /hint! ⭐",
        ]
        response = random.choice(wrongs)
        await update.message.reply_text(eskendir(response), parse_mode=ParseMode.MARKDOWN)
        await db_log(uid, uname, text, response)
        return

    # ── 2. Database keyword match ─────────────────────────────────────────────
    response = await db_keyword_lookup(text)

    # ── 3. Oil / gas / price keyword detection ────────────────────────────────
    if not response:
        oil_kw   = {"oil", "crude", "brent", "wti", "barrel", "petroleum", "opec"}
        gas_kw   = {"gas", "gasoline", "petrol", "lng", "diesel", "fuel"}
        price_kw = {"price", "cost", "how much", "rate", "value", "worth", "market", "usd"}
        words    = set(lower.split())

        if words & oil_kw or any(k in lower for k in oil_kw):
            await update.message.reply_text(
                eskendir("🛢️ Interested in oil prices? Eskendir's bot has you covered! Pick a market:"),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=ikb_prices(),
            )
            await db_log(uid, uname, text, "→ prices keyboard shown")
            return

        if words & gas_kw or any(k in lower for k in gas_kw):
            await update.message.reply_text(
                eskendir("⛽ Gas prices? Eskendir's bot tracks Natural Gas and Gasoline futures live! Select:"),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=ikb_prices(),
            )
            await db_log(uid, uname, text, "→ prices keyboard shown")
            return

        if words & price_kw or any(k in lower for k in price_kw):
            await update.message.reply_text(
                eskendir("💰 Looking for prices? Eskendir fetches real-time commodity data. Choose:"),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=ikb_prices(),
            )
            await db_log(uid, uname, text, "→ prices keyboard shown")
            return

    # ── 4. Fallback ───────────────────────────────────────────────────────────
    if not response:
        response = random.choice(_FALLBACKS)

    await update.message.reply_text(
        eskendir(response), parse_mode=ParseMode.MARKDOWN, reply_markup=kb_main()
    )
    await db_log(uid, uname, text, response)


# ─────────────────────────────────────────────────────────────────────────────
#  WEBHOOK SERVER  — exact same pattern as bot_5.py (Alisher bot)
# ─────────────────────────────────────────────────────────────────────────────

async def main() -> None:
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        raise RuntimeError("Set the BOT_TOKEN environment variable!")

    await init_db()

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start",     cmd_start))
    application.add_handler(CommandHandler("help",      cmd_help))
    application.add_handler(CommandHandler("prices",    cmd_prices))
    application.add_handler(CommandHandler("market",    cmd_market))
    application.add_handler(CommandHandler("trends",    cmd_trends))
    application.add_handler(CommandHandler("about",     cmd_about))
    application.add_handler(CommandHandler("quiz",      cmd_quiz))
    application.add_handler(CommandHandler("hint",      cmd_hint))
    application.add_handler(CommandHandler("stats",     cmd_stats))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    webhook_full_url = f"{WEBHOOK_URL}{WEBHOOK_PATH}"
    await application.bot.set_webhook(
        url=webhook_full_url,
        allowed_updates=Update.ALL_TYPES,
    )
    logger.info("🔗  Webhook registered: %s", webhook_full_url)

    async def telegram_webhook(request: web.Request) -> web.Response:
        try:
            body   = await request.json()
            update = Update.de_json(body, application.bot)
            await application.process_update(update)
        except Exception as exc:
            logger.error("Webhook processing error: %s", exc)
        return web.Response(text="OK")

    async def health_check(request: web.Request) -> web.Response:
        return web.Response(text="🛢️ Eskendir's Oil & Gas Bot is ONLINE and tracking markets! ✨")

    web_app = web.Application()
    web_app.router.add_post(WEBHOOK_PATH,  telegram_webhook)
    web_app.router.add_get("/",            health_check)
    web_app.router.add_get("/health",      health_check)

    async with application:
        await application.start()
        runner = web.AppRunner(web_app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()

        logger.info("🚀  Eskendir's Oil & Gas Bot running on port %d", PORT)
        logger.info("🛢️  Live and tracking commodities!")

        try:
            await asyncio.Event().wait()
        finally:
            logger.info("🌠  Shutting down gracefully…")
            await runner.cleanup()
            await application.stop()


if __name__ == "__main__":
    asyncio.run(main())
