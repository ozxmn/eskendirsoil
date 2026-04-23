"""
╔══════════════════════════════════════════════════════════╗
║        ESKENDIR'S GAS & OIL PRICE CHATBOT               ║
║        Built with aiogram 3.x + asyncio                 ║
║        APIs: Yahoo Finance (no key) + ExchangeRate API  ║
╚══════════════════════════════════════════════════════════╝
"""

import asyncio
import aiohttp
import sqlite3
import logging
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

# ─── CONFIG ──────────────────────────────────────────────────────────────────

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
AUTHOR: str = "Eskendir"
DB_PATH: str = "chatbot.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ─── DATABASE LAYER ───────────────────────────────────────────────────────────


def init_db() -> None:
    """Initialize SQLite database and seed FAQ data."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Table: keyword-based FAQ responses
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS faqs (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword  TEXT NOT NULL UNIQUE,
            response TEXT NOT NULL
        )
        """
    )

    # Table: per-user chat history
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_history (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   INTEGER NOT NULL,
            username  TEXT,
            message   TEXT,
            response  TEXT,
            timestamp TEXT
        )
        """
    )

    # Seed FAQ rows (only if table is empty)
    faqs = [
        (
            "opec",
            f"🌍 *OPEC* (Organization of the Petroleum Exporting Countries) was founded in 1960 "
            f"in Baghdad by Iran, Iraq, Kuwait, Saudi Arabia, and Venezuela.\n\n"
            f"Today it has 13 members and controls ~44% of global oil output.\n"
            f"_{AUTHOR} notes: OPEC+ — which includes Russia — is even more powerful!_",
        ),
        (
            "brent",
            f"🌊 *Brent Crude* is extracted from the North Sea and is the world's leading oil "
            f"benchmark — about 2/3 of globally traded oil is priced against it.\n\n"
            f"API gravity ~38.3°, sulfur ~0.37% (low-sulfur = 'sweet').\n"
            f"_{AUTHOR} tracks Brent every single day!_",
        ),
        (
            "wti",
            f"🏭 *WTI (West Texas Intermediate)* is a light, sweet crude from Cushing, Oklahoma. "
            f"It's the primary US oil benchmark.\n\n"
            f"API gravity ~39.6°, sulfur ~0.24%.\n"
            f"WTI usually trades $2–$3 below Brent. _{AUTHOR} explains the spread daily!_",
        ),
        (
            "kazakhstan",
            f"🇰🇿 Kazakhstan is a top-20 global oil producer! _{AUTHOR}'s homeland is energy-rich!_\n\n"
            f"🏭 *Tengiz* — 26–29 billion bbl reserves\n"
            f"🌊 *Kashagan* — one of world's largest offshore fields\n"
            f"🔥 *Karachaganak* — giant gas-condensate field\n\n"
            f"Production: ~1.8M barrels/day. Oil = ~50% of export revenue.",
        ),
        (
            "natural gas",
            f"🔥 *Natural Gas* is a fossil fuel (mainly methane, CH₄) used for electricity, "
            f"heating, and industry. Prices quoted in $/MMBtu.\n\n"
            f"🇰🇿 Kazakhstan's Karachaganak field has massive gas reserves.\n"
            f"_{AUTHOR} notes: gas burns ~50% cleaner than coal!_",
        ),
        (
            "barrel",
            f"📦 *1 Oil Barrel* = 42 US gallons = 158.99 liters\n\n"
            f"What one barrel produces:\n"
            f"• ~19.5 gal gasoline\n• ~10 gal diesel\n• ~4 gal jet fuel\n"
            f"• Remaining: asphalt, lubricants, petrochemicals\n\n"
            f"_{AUTHOR} trivia: the 42-gal standard was set in Pennsylvania in 1872!_",
        ),
        (
            "refinery",
            f"⚙️ *Refineries* convert raw crude into usable products via:\n"
            f"🔬 Distillation → Cracking → Reforming → Treating\n\n"
            f"🌍 Largest: Jamnagar, India (1.24M bbl/day)\n"
            f"🇰🇿 Kazakhstan has refineries in Atyrau, Pavlodar & Shymkent!\n"
            f"_{AUTHOR} says: refining is where the real value is added!_",
        ),
        (
            "gasoline",
            f"⛽ *Gasoline/Petrol* prices depend on: crude oil cost + refining + distribution + taxes.\n\n"
            f"🌍 Sample pump prices (per liter):\n"
            f"• Kazakhstan: ~$0.45 (subsidized)\n"
            f"• Russia: ~$0.70\n"
            f"• Germany: ~$1.80\n"
            f"• USA: ~$0.95\n\n"
            f"_{AUTHOR} appreciates Kazakhstan's affordable fuel!_ 🇰🇿",
        ),
        (
            "crude",
            f"🛢️ *Crude oil* is unrefined petroleum extracted from the ground. "
            f"It's classified by density (light/heavy) and sulfur content (sweet/sour).\n\n"
            f"Light sweet crude → easier/cheaper to refine → higher price.\n"
            f"_{AUTHOR} explains: not all crude is equal — quality matters!_",
        ),
        (
            "petrol",
            f"⛽ *Petrol* is the British/Commonwealth term for gasoline. "
            f"It's the main refined product from crude oil, used in internal combustion engines.\n\n"
            f"In Kazakhstan it's sold as AI-92, AI-95, AI-98 (octane ratings).\n"
            f"_{AUTHOR} fills up with AI-95!_ 😄",
        ),
        (
            "diesel",
            f"🚛 *Diesel fuel* is a heavier distillate than gasoline, used in trucks, buses, ships, "
            f"and industrial engines. More energy-dense than petrol.\n\n"
            f"Kazakhstan exports significant diesel to CIS countries.\n"
            f"_{AUTHOR} notes: diesel is still the backbone of freight worldwide!_",
        ),
        (
            "lng",
            f"❄️ *LNG (Liquefied Natural Gas)* is natural gas cooled to -162°C to become liquid "
            f"for shipping. Volume reduces by 600x!\n\n"
            f"Major exporters: Qatar, Australia, USA.\n"
            f"_{AUTHOR} insight: LNG is reshaping global energy trade faster than ever!_",
        ),
    ]

    c.executemany(
        "INSERT OR IGNORE INTO faqs (keyword, response) VALUES (?, ?)",
        faqs,
    )

    conn.commit()
    conn.close()
    logger.info("✅ Database initialized.")


def get_faq_response(text: str) -> str | None:
    """Search FAQ table for a keyword match in user text."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT response FROM faqs WHERE ? LIKE '%' || keyword || '%'",
        (text.lower(),),
    )
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def save_history(user_id: int, username: str, message: str, response: str) -> None:
    """Persist a message/response pair to chat_history."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO chat_history (user_id, username, message, response, timestamp) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, username, message[:500], response[:500], datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def get_user_history(user_id: int, limit: int = 6) -> list[tuple]:
    """Retrieve last N messages for a user."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT message, timestamp FROM chat_history "
        "WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    )
    rows = c.fetchall()
    conn.close()
    return rows


# ─── API LAYER ────────────────────────────────────────────────────────────────

YAHOO_SYMBOLS: dict[str, str] = {
    "CL=F": "WTI Crude Oil",
    "BZ=F": "Brent Crude Oil",
    "NG=F": "Natural Gas",
    "RB=F": "RBOB Gasoline",
    "HO=F": "Heating Oil",
}


async def fetch_commodity_prices() -> dict[str, dict]:
    """
    Fetch live energy prices from Yahoo Finance (no API key needed).
    Returns dict: { commodity_name: {price, currency, change, pct_change} }
    """
    results: dict[str, dict] = {}
    timeout = aiohttp.ClientTimeout(total=12)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        tasks = []
        for symbol, name in YAHOO_SYMBOLS.items():
            url = (
                f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
                f"?interval=1d&range=1d"
            )
            tasks.append((name, session.get(url, headers={"User-Agent": "Mozilla/5.0"})))

        for name, coro in tasks:
            try:
                async with coro as resp:
                    if resp.status != 200:
                        results[name] = {"error": True}
                        continue
                    data = await resp.json()
                    meta = data["chart"]["result"][0]["meta"]
                    price: float = meta.get("regularMarketPrice") or meta.get("previousClose", 0.0)
                    prev: float = meta.get("chartPreviousClose") or meta.get("previousClose", price)
                    change = price - prev
                    pct = (change / prev * 100) if prev else 0.0
                    currency = meta.get("currency", "USD")
                    results[name] = {
                        "price": price,
                        "currency": currency,
                        "change": change,
                        "pct": pct,
                        "error": False,
                    }
            except Exception as exc:
                logger.warning(f"Yahoo Finance error ({name}): {exc}")
                results[name] = {"error": True}

    return results


async def fetch_usd_rates() -> dict[str, float]:
    """
    Fetch USD exchange rates from open.er-api.com (completely free, no key).
    Returns { currency_code: rate }
    """
    url = "https://open.er-api.com/v6/latest/USD"
    timeout = aiohttp.ClientTimeout(total=10)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                data = await resp.json()
                rates = data.get("rates", {})
                return {
                    "KZT": rates.get("KZT", 0.0),
                    "EUR": rates.get("EUR", 0.0),
                    "RUB": rates.get("RUB", 0.0),
                    "GBP": rates.get("GBP", 0.0),
                    "CNY": rates.get("CNY", 0.0),
                    "SAR": rates.get("SAR", 0.0),
                }
    except Exception as exc:
        logger.warning(f"Exchange rate API error: {exc}")
        return {}


# ─── FORMATTING HELPERS ───────────────────────────────────────────────────────


def _arrow(change: float) -> str:
    return "📈" if change > 0 else ("📉" if change < 0 else "➡️")


def format_prices(prices: dict[str, dict]) -> str:
    if not prices:
        return f"❌ Could not retrieve prices. Please try again.\n\n_— {AUTHOR}_"

    unit_map = {
        "WTI Crude Oil": "$/bbl",
        "Brent Crude Oil": "$/bbl",
        "Natural Gas": "$/MMBtu",
        "RBOB Gasoline": "$/gal",
        "Heating Oil": "$/gal",
    }

    lines = [f"🛢️ *Live Energy Prices*\n_Tracked by {AUTHOR}'s Bot_\n"]
    for name, d in prices.items():
        if d.get("error"):
            lines.append(f"• *{name}* — ❌ unavailable\n")
            continue
        arrow = _arrow(d["change"])
        sign = "+" if d["change"] >= 0 else ""
        unit = unit_map.get(name, d["currency"])
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
        flag = flags.get(code, "🌐")
        lines.append(f"{flag} `1 USD = {val:,.4f} {code}`")

    lines.append(
        f"\n💡 *Why it matters:* Oil is priced in USD globally. "
        f"A stronger USD typically pushes oil prices lower — _{AUTHOR} explains!_"
    )
    lines.append(f"\n🕒 `{datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC`")
    return "\n".join(lines)


# ─── KEYBOARDS ────────────────────────────────────────────────────────────────


def main_kb() -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text="🛢️ Oil Prices"), KeyboardButton(text="💱 Exchange Rates"))
    b.row(KeyboardButton(text="📚 Oil Facts"), KeyboardButton(text="🌍 About OPEC"))
    b.row(KeyboardButton(text="📜 My History"), KeyboardButton(text="❓ Help"))
    b.row(KeyboardButton(text="👋 Goodbye"))
    return b.as_markup(resize_keyboard=True)


def prices_ikb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="🔄 Refresh", callback_data="cb_prices"),
        InlineKeyboardButton(text="💱 USD Rates", callback_data="cb_rates"),
    )
    b.row(
        InlineKeyboardButton(text="📖 WTI Info", callback_data="cb_info_wti"),
        InlineKeyboardButton(text="🌊 Brent Info", callback_data="cb_info_brent"),
    )
    b.row(
        InlineKeyboardButton(text="🔥 Gas Info", callback_data="cb_info_gas"),
        InlineKeyboardButton(text="⛽ Gasoline", callback_data="cb_info_gasoline"),
    )
    return b.as_markup()


def facts_ikb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🌍 OPEC", callback_data="cb_fact_opec")
    b.button(text="🇰🇿 Kazakhstan", callback_data="cb_fact_kz")
    b.button(text="📦 Oil Barrel", callback_data="cb_fact_barrel")
    b.button(text="⚙️ Refinery", callback_data="cb_fact_refinery")
    b.button(text="❄️ LNG", callback_data="cb_fact_lng")
    b.button(text="🔥 Natural Gas", callback_data="cb_fact_natgas")
    b.adjust(2)
    return b.as_markup()


def back_to_facts_ikb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="◀️ Back to Facts", callback_data="cb_back_facts")
    b.button(text="🛢️ Live Prices", callback_data="cb_prices")
    b.adjust(2)
    return b.as_markup()


def back_to_prices_ikb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="◀️ Back to Prices", callback_data="cb_prices")
    b.button(text="📚 Oil Facts", callback_data="cb_back_facts")
    b.adjust(2)
    return b.as_markup()


# ─── BOT & DISPATCHER ─────────────────────────────────────────────────────────

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
)
dp = Dispatcher(storage=MemoryStorage())

# ─── COMMAND & KEYBOARD HANDLERS ──────────────────────────────────────────────


@dp.message(CommandStart())
async def cmd_start(message: types.Message) -> None:
    name = message.from_user.first_name or "friend"
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
    await message.answer(text, reply_markup=main_kb())
    save_history(message.from_user.id, message.from_user.username or "", "/start", text)


@dp.message(Command("help"))
@dp.message(F.text == "❓ Help")
async def cmd_help(message: types.Message) -> None:
    text = (
        f"🆘 *{AUTHOR}'s Bot — Help Guide*\n\n"
        f"*Commands:*\n"
        f"`/start` — Welcome & main menu\n"
        f"`/prices` — Live energy prices\n"
        f"`/rates` — USD exchange rates\n"
        f"`/facts` — Oil & gas knowledge base\n"
        f"`/history` — Your recent chat history\n"
        f"`/help` — This guide\n\n"
        f"*Keyboard Shortcuts:*\n"
        f"🛢️ `Oil Prices` — Live commodity feed\n"
        f"💱 `Exchange Rates` — USD vs KZT, EUR, RUB…\n"
        f"📚 `Oil Facts` — Tap topics to learn more\n"
        f"🌍 `About OPEC` — Energy cartel overview\n"
        f"📜 `My History` — Your last 6 messages\n"
        f"👋 `Goodbye` — Farewell message\n\n"
        f"*Or just ask anything*, e.g.:\n"
        f"_'What is brent crude?'_\n"
        f"_'Tell me about Kazakhstan oil'_\n"
        f"_'What is LNG?'_\n\n"
        f"_{AUTHOR} hopes this helps!_ 🤝"
    )
    await message.answer(text, reply_markup=main_kb())


@dp.message(Command("prices"))
@dp.message(F.text == "🛢️ Oil Prices")
async def cmd_prices(message: types.Message) -> None:
    wait = await message.answer(f"⏳ Fetching live prices… _{AUTHOR} is on it!_")
    prices = await fetch_commodity_prices()
    text = format_prices(prices)
    await wait.delete()
    await message.answer(text, reply_markup=prices_ikb())
    save_history(message.from_user.id, message.from_user.username or "", "Oil Prices", text[:400])


@dp.message(Command("rates"))
@dp.message(F.text == "💱 Exchange Rates")
async def cmd_rates(message: types.Message) -> None:
    wait = await message.answer(f"⏳ Loading exchange rates… _{AUTHOR} fetching data!_")
    rates = await fetch_usd_rates()
    text = format_rates(rates)
    await wait.delete()

    b = InlineKeyboardBuilder()
    b.button(text="🔄 Refresh Rates", callback_data="cb_rates")
    b.button(text="🛢️ Oil Prices", callback_data="cb_prices")
    b.adjust(2)

    await message.answer(text, reply_markup=b.as_markup())
    save_history(message.from_user.id, message.from_user.username or "", "Exchange Rates", text[:400])


@dp.message(Command("facts"))
@dp.message(F.text == "📚 Oil Facts")
async def cmd_facts(message: types.Message) -> None:
    text = (
        f"📚 *Oil & Gas Knowledge Base*\n"
        f"_Curated by {AUTHOR} — tap a topic!_\n\n"
        f"Choose what you'd like to learn:"
    )
    await message.answer(text, reply_markup=facts_ikb())


@dp.message(F.text == "🌍 About OPEC")
async def cmd_opec(message: types.Message) -> None:
    text = (
        f"🌍 *About OPEC*\n_A deep dive by {AUTHOR}_\n\n"
        f"*Full name:* Organization of the Petroleum Exporting Countries\n"
        f"*Founded:* September 14, 1960, Baghdad\n"
        f"*HQ:* Vienna, Austria 🇦🇹\n"
        f"*Members:* 13 countries\n\n"
        f"🏭 *Current members:*\n"
        f"Algeria, Congo, Equatorial Guinea, Gabon, Iran, Iraq, Kuwait, "
        f"Libya, Nigeria, Saudi Arabia, UAE, Venezuela\n\n"
        f"📊 *Market power:*\n"
        f"• Controls ~44% of global oil production\n"
        f"• Holds ~80% of world proven reserves\n"
        f"• Sets production quotas to influence prices\n\n"
        f"⚡ *OPEC+* (since 2016) adds Russia, Kazakhstan & 8 others — "
        f"making it even more dominant today!\n\n"
        f"🇰🇿 _{AUTHOR} is proud Kazakhstan participates in OPEC+ agreements!_"
    )

    b = InlineKeyboardBuilder()
    b.button(text="🇰🇿 Kazakhstan Oil", callback_data="cb_fact_kz")
    b.button(text="🛢️ Live Prices", callback_data="cb_prices")
    b.adjust(2)

    await message.answer(text, reply_markup=b.as_markup())
    save_history(message.from_user.id, message.from_user.username or "", "About OPEC", text[:400])


@dp.message(Command("history"))
@dp.message(F.text == "📜 My History")
async def cmd_history(message: types.Message) -> None:
    rows = get_user_history(message.from_user.id)
    if not rows:
        await message.answer(
            f"📭 No history yet! Start chatting and I'll remember.\n\n_— {AUTHOR}_"
        )
        return

    lines = [f"📜 *Your Last {len(rows)} Messages*\n_Logged by {AUTHOR}'s Bot_\n"]
    for msg, ts in rows:
        t = ts[:16].replace("T", " ") if ts else "?"
        lines.append(f"🕒 `{t}` — _{msg[:60]}_")
    lines.append(f"\n_— {AUTHOR} keeps your history safe!_ 🔒")

    await message.answer("\n".join(lines))


@dp.message(F.text == "👋 Goodbye")
async def cmd_bye(message: types.Message) -> None:
    name = message.from_user.first_name or "friend"
    text = (
        f"👋 Goodbye, *{name}*!\n\n"
        f"It was great chatting about energy markets with you!\n"
        f"Come back anytime — prices change every second! 📊\n\n"
        f"🛢️ *{AUTHOR}* says: _may the oil always flow in your favor!_ 💪\n\n"
        f"_See you soon!_"
    )
    await message.answer(text, reply_markup=main_kb())
    save_history(message.from_user.id, message.from_user.username or "", "Goodbye", text)


# ─── INLINE CALLBACK HANDLERS ─────────────────────────────────────────────────


@dp.callback_query(F.data == "cb_prices")
async def cb_prices(callback: types.CallbackQuery) -> None:
    await callback.answer("🔄 Refreshing prices…")
    prices = await fetch_commodity_prices()
    text = format_prices(prices)
    try:
        await callback.message.edit_text(text, reply_markup=prices_ikb())
    except Exception:
        await callback.message.answer(text, reply_markup=prices_ikb())


@dp.callback_query(F.data == "cb_rates")
async def cb_rates(callback: types.CallbackQuery) -> None:
    await callback.answer("💱 Loading rates…")
    rates = await fetch_usd_rates()
    text = format_rates(rates)

    b = InlineKeyboardBuilder()
    b.button(text="🔄 Refresh", callback_data="cb_rates")
    b.button(text="🛢️ Oil Prices", callback_data="cb_prices")
    b.adjust(2)

    try:
        await callback.message.edit_text(text, reply_markup=b.as_markup())
    except Exception:
        await callback.message.answer(text, reply_markup=b.as_markup())


@dp.callback_query(F.data == "cb_info_wti")
async def cb_info_wti(callback: types.CallbackQuery) -> None:
    await callback.answer()
    text = (
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
    )
    await callback.message.edit_text(text, reply_markup=back_to_prices_ikb())


@dp.callback_query(F.data == "cb_info_brent")
async def cb_info_brent(callback: types.CallbackQuery) -> None:
    await callback.answer()
    text = (
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
    )
    await callback.message.edit_text(text, reply_markup=back_to_prices_ikb())


@dp.callback_query(F.data == "cb_info_gas")
async def cb_info_gas(callback: types.CallbackQuery) -> None:
    await callback.answer()
    text = (
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
    )
    await callback.message.edit_text(text, reply_markup=back_to_prices_ikb())


@dp.callback_query(F.data == "cb_info_gasoline")
async def cb_info_gasoline(callback: types.CallbackQuery) -> None:
    await callback.answer()
    text = (
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
    )
    await callback.message.edit_text(text, reply_markup=back_to_prices_ikb())


@dp.callback_query(F.data == "cb_back_facts")
async def cb_back_facts(callback: types.CallbackQuery) -> None:
    await callback.answer()
    text = (
        f"📚 *Oil & Gas Knowledge Base*\n"
        f"_Curated by {AUTHOR} — tap a topic!_\n\n"
        f"Choose what you'd like to learn:"
    )
    await callback.message.edit_text(text, reply_markup=facts_ikb())


@dp.callback_query(F.data == "cb_fact_opec")
async def cb_fact_opec(callback: types.CallbackQuery) -> None:
    await callback.answer()
    text = (
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
    )
    await callback.message.edit_text(text, reply_markup=back_to_facts_ikb())


@dp.callback_query(F.data == "cb_fact_kz")
async def cb_fact_kz(callback: types.CallbackQuery) -> None:
    await callback.answer()
    text = (
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
    )
    await callback.message.edit_text(text, reply_markup=back_to_facts_ikb())


@dp.callback_query(F.data == "cb_fact_barrel")
async def cb_fact_barrel(callback: types.CallbackQuery) -> None:
    await callback.answer()
    text = (
        f"📦 *The Oil Barrel*\n_Fun facts by {AUTHOR}_\n\n"
        f"1 barrel = 42 US gallons = 158.99 liters\n\n"
        f"*From 1 barrel you get:*\n"
        f"⛽ ~19.5 gal gasoline\n"
        f"🚛 ~10 gal diesel/heating oil\n"
        f"✈️ ~4 gal jet fuel\n"
        f"🏗️ Remaining: asphalt, lubricants, petrochemicals\n\n"
        f"*History:* The 42-gallon barrel was standardized in *1872* "
        f"by Pennsylvania oil producers to avoid confusion in shipments.\n\n"
        f"*Fun stat:* At $80/bbl, each liter of crude costs ~$0.50.\n"
        f"_{AUTHOR} trivia: oil is cheaper than most bottled water per liter!_ 💧"
    )
    await callback.message.edit_text(text, reply_markup=back_to_facts_ikb())


@dp.callback_query(F.data == "cb_fact_refinery")
async def cb_fact_refinery(callback: types.CallbackQuery) -> None:
    await callback.answer()
    text = (
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
    )
    await callback.message.edit_text(text, reply_markup=back_to_facts_ikb())


@dp.callback_query(F.data == "cb_fact_lng")
async def cb_fact_lng(callback: types.CallbackQuery) -> None:
    await callback.answer()
    text = (
        f"❄️ *LNG — Liquefied Natural Gas*\n_by {AUTHOR}_\n\n"
        f"Natural gas cooled to *−162°C* becomes liquid, shrinking its "
        f"volume by *~600 times* — making it shippable globally.\n\n"
        f"*Process:*\n"
        f"🔵 Extraction → 🏭 Liquefaction → 🚢 Shipping → 🔴 Regasification → 🏠 End use\n\n"
        f"*Top LNG exporters (2024):*\n"
        f"1. 🇦🇺 Australia\n"
        f"2. 🇶🇦 Qatar\n"
        f"3. 🇺🇸 USA\n\n"
        f"LNG is reshaping global energy markets, breaking Russia's "
        f"pipeline monopoly on European gas supply.\n"
        f"_{AUTHOR} insight: LNG is the future of gas trade!_ 🌍"
    )
    await callback.message.edit_text(text, reply_markup=back_to_facts_ikb())


@dp.callback_query(F.data == "cb_fact_natgas")
async def cb_fact_natgas(callback: types.CallbackQuery) -> None:
    await callback.answer()
    text = (
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
    )
    await callback.message.edit_text(text, reply_markup=back_to_facts_ikb())


# ─── SMART TEXT HANDLER ───────────────────────────────────────────────────────

_GREETINGS = {"hello", "hi", "hey", "howdy", "sup", "greetings", "yo", "hiya", "good morning",
               "good evening", "good afternoon", "wassup", "what's up", "whats up"}
_FAREWELLS = {"bye", "goodbye", "farewell", "see you", "cya", "good night", "take care",
               "later", "see ya", "ttyl", "gotta go", "gtg"}
_THANKS = {"thank", "thanks", "thx", "ty", "appreciate", "cheers", "thnx"}
_PRICE_WORDS = {"price", "cost", "how much", "rate", "value", "worth", "expensive", "cheap",
                "dollar", "usd", "money", "market", "trading", "today"}


@dp.message(F.text)
async def handle_text(message: types.Message) -> None:
    raw = message.text.strip()
    low = raw.lower()
    name = message.from_user.first_name or "friend"
    response_text: str

    # ── Greeting ──
    if any(g in low for g in _GREETINGS):
        response_text = (
            f"👋 Hello, *{name}*!\n\n"
            f"Great to see you at *{AUTHOR}'s Oil & Gas Bot!* 🛢️\n\n"
            f"Ask me anything about oil prices, OPEC, Kazakhstan energy, "
            f"natural gas, or use the buttons below!\n\n"
            f"_— {AUTHOR} welcomes you!_"
        )
        await message.answer(response_text, reply_markup=main_kb())

    # ── Farewell ──
    elif any(f in low for f in _FAREWELLS):
        response_text = (
            f"👋 Goodbye, *{name}*! Safe travels!\n\n"
            f"Thanks for chatting with *{AUTHOR}'s Bot* 🛢️\n"
            f"Come back when you want the latest prices — markets never sleep!\n\n"
            f"_— {AUTHOR} waves goodbye! 🤝_"
        )
        await message.answer(response_text, reply_markup=main_kb())

    # ── Thanks ──
    elif any(t in low for t in _THANKS):
        response_text = (
            f"😊 You're very welcome, *{name}*!\n\n"
            f"*{AUTHOR}* is always happy to share oil & gas knowledge!\n"
            f"Feel free to ask anything else. 🛢️"
        )
        await message.answer(response_text, reply_markup=main_kb())

    # ── Live prices request ──
    elif any(w in low for w in _PRICE_WORDS):
        wait = await message.answer(f"⏳ Pulling live data… _{AUTHOR} is checking the markets!_")
        prices = await fetch_commodity_prices()
        response_text = format_prices(prices)
        await wait.delete()
        await message.answer(response_text, reply_markup=prices_ikb())

    # ── FAQ database lookup ──
    else:
        faq = get_faq_response(raw)
        if faq:
            response_text = faq
            await message.answer(response_text, reply_markup=main_kb())
        else:
            response_text = (
                f"🤔 *{AUTHOR}* doesn't have a specific answer for that yet.\n\n"
                f"Try asking about:\n"
                f"• *Brent, WTI, crude, barrel, refinery*\n"
                f"• *OPEC, natural gas, LNG, diesel, petrol*\n"
                f"• *Kazakhstan, gasoline, oil price*\n\n"
                f"Or use the keyboard buttons below for live data! 👇"
            )
            await message.answer(response_text, reply_markup=main_kb())

    save_history(
        message.from_user.id,
        message.from_user.username or "",
        raw,
        response_text[:400],
    )


# ─── ENTRY POINT ──────────────────────────────────────────────────────────────


async def main() -> None:
    init_db()
    logger.info(f"🛢️  {AUTHOR}'s Oil & Gas Bot is starting up...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
