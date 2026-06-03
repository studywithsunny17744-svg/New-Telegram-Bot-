# -*- coding: utf-8 -*-
import logging
import json
import datetime
import re
import os
from urllib.parse import quote
from telegram import Update, constants, InlineKeyboardButton, InlineKeyboardMarkup, MessageEntity
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler, ApplicationHandlerStop
from telegram.request import HTTPXRequest
import httpx
import database

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Configuration
BOT_TOKEN = "8365030445:AAHIxmsjadhJsGo1MGCHujfg4V0JEw8L334"
BOT_OWNER = "@Mani272yt"
BOT_TITLE = "MANI 272"
ADMIN_IDS = [8190259025]  # REPLACE THIS with the ID from @userinfobot
WELCOME_PHOTO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "welcome.png")

# --- Ad Reward System Configuration ---
AD_LINK = "https://gplinks.co/dwEidy"  # REPLACE THIS with your shortlink URL

# --- UI Theme Constants ---
HEADER = "\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
SUB_LINE = "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬"
FOOTER = (
    f"\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
    f"⚡ *Powered by* {BOT_OWNER}\n"
    f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰"
)
ERROR_ICON = "🔻"
SUCCESS_ICON = "🔰"
LOADING_ICON = "⏳"
COIN_ICON = "🪙"

NO_COIN_MSG = (
    f"{HEADER}"
    f"{ERROR_ICON} *NO COINS FOUND*\n"
    f"{SUB_LINE}\n\n"
    f"This is a premium command.\n"
    f"Current Balance: `0` {COIN_ICON}\n\n"
    f"👉 Use `/earn` to get coins for free!\n"
    f"{FOOTER}"
)

# ExploitsIndia OSINT APIs (plain-text responses)
NUMBER_API_ENDPOINT = "https://api.subhxcosmo.in/api?key=MANI&type=mobile&term={term}"
AADHAAR_API_ENDPOINT = "https://api.subhxcosmo.in/api?key=MANI&type=id_family&term={term}"
FAMILY_API_ENDPOINT = "https://exploitsindia.site/api/family.php?exploits={term}"
PINCODE_API_ENDPOINT = "https://exploitsindia.site/api/pincode.php?exploits={term}"
IFSC_API_ENDPOINT = "https://exploitsindia.site/api/ifsc.php?exploits={term}"
TELEGRAM_API_ENDPOINT = "https://exploitsindia.site/api/telegram.php?exploits={term}"
INSTAGRAM_API_ENDPOINT = "https://exploitsindia.site/api/instagram.php?exploits={term}"
VEHICLE_API_ENDPOINT = "https://exploitsindia.site/api/vehicle.php?exploits={term}"

EXPLOITS_APIS = {
    "number": ("Mobile Lookup", NUMBER_API_ENDPOINT, "📱"),
    "aadhaar": ("Aadhaar Lookup", AADHAAR_API_ENDPOINT, "🪪"),
    "family": ("Family Lookup", FAMILY_API_ENDPOINT, "👪"),
    "pincode": ("Pincode Lookup", PINCODE_API_ENDPOINT, "📮"),
    "ifsc": ("IFSC Lookup", IFSC_API_ENDPOINT, "🏦"),
    "telegram": ("Telegram Lookup", TELEGRAM_API_ENDPOINT, "✈️"),
    "instagram": ("Instagram Lookup", INSTAGRAM_API_ENDPOINT, "📸"),
    "vehicle": ("Vehicle Lookup", VEHICLE_API_ENDPOINT, "🚗"),
}

BASE_URL_VISITS = "http://sspam.thug4ff.com/visits"
BASE_URL_BOMBER = "https://bomber-api-psi.vercel.app/send"
LIKE_API_URL = "https://like.sukhdaku.qzz.io/like"
LIKE_API_HEADERS = {
    "X-API-KEY": "redefine_kavach_9d3b7f1c2a4e6f8b0c3d5e7a9f1c2b4d",
    "X-CLIENT-ID": "cli_aimguard_6Z9XK3P4Q7R8S2T1",
    "User-Agent": "Aimguard/1.0.0",
    "X-REQUEST-TYPE": "redefine-like",
}
LIKE_VALID_REGIONS = ("IND", "NX", "AG")
LIKE_REGION_ALIASES = {"IN": "IND", "IND": "IND", "NX": "NX", "AG": "AG"}
LINK_REGEX = re.compile(
    r"(https?://\S+|www\.\S+|t\.me/\S+|telegram\.me/\S+|telegram\.dog/\S+|"
    r"discord\.gg/\S+|bit\.ly/\S+|goo\.gl/\S+|youtu\.be/\S+)",
    re.IGNORECASE
)

def parse_mobile_number(text: str):
    """Extract 10-digit Indian mobile from plain text (+91, spaces, etc.)."""
    if not text:
        return None
    text = text.strip()
    # Full message is only a number
    digits = re.sub(r"\D", "", text)
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    if digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    if len(digits) == 10 and digits[0] in "6789":
        return digits
    # Number buried in longer text
    match = re.search(r"(?<!\d)(?:\+?91[\s-]?)?([6-9]\d{9})(?!\d)", text)
    if match:
        return match.group(1)
    return None

def extract_mobile_from_message(message, bot_username: str = None):
    """Get mobile from text, caption, contact, or @bot mention message."""
    if not message:
        return None

    if message.contact and message.contact.phone_number:
        mobile = parse_mobile_number(message.contact.phone_number)
        if mobile:
            return mobile

    text = message.text or message.caption or ""
    if bot_username:
        text = re.sub(rf"@?{re.escape(bot_username)}\b", "", text, flags=re.IGNORECASE).strip()
    return parse_mobile_number(text)

async def send_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, parse_mode=constants.ParseMode.MARKDOWN):
    """Send reply in chat; always reply to user's message in groups."""
    chat_id = update.effective_chat.id
    reply_id = update.message.message_id if update.message else None
    chunks = [text[i:i + 4000] for i in range(0, len(text), 4000)] or [text]
    last_msg = None
    for idx, chunk in enumerate(chunks):
        kwargs = {"chat_id": chat_id, "text": chunk, "parse_mode": parse_mode}
        if idx == 0 and reply_id:
            kwargs["reply_to_message_id"] = reply_id
        last_msg = await context.bot.send_message(**kwargs)
    return last_msg

# --- Helper Function for API Requests ---
async def fetch_api_data(url):
    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.get(url)
        return response
    except Exception as e:
        logging.error(f"API Request Error: {e}")
        return None

def build_exploits_url(endpoint_template: str, term: str) -> str:
    return endpoint_template.format(term=quote(str(term).strip()))

def format_number_lookup_response(response, mobile: str) -> str:
    """Custom formatter for the subhxcosmo number lookup API — matches screenshot style."""
    if not response:
        return (
            f"{HEADER}{ERROR_ICON} *CONNECTION FAILED*\n{SUB_LINE}\n\n"
            f"Server did not respond. Try again later.\n{FOOTER}"
        )
    if response.status_code not in (200, 201, 202):
        return (
            f"{HEADER}{ERROR_ICON} *API ERROR*\n{SUB_LINE}\n\n"
            f"HTTP Status: `{response.status_code}`\n{FOOTER}"
        )

    # Try JSON first
    try:
        data = response.json()
    except Exception:
        data = None

    if data and isinstance(data, dict):
        # Handle error responses
        if not data.get("success"):
            return (
                f"{HEADER}{ERROR_ICON} *NO DATA FOUND*\n{SUB_LINE}\n\n"
                f"🎯 Query: `{mobile}`\n\nNo records found for this search.\n{FOOTER}"
            )

        # Extract results array from nested structure: data["result"]["results"]
        result_obj = data.get("result", {})
        results = []
        if isinstance(result_obj, dict):
            results = result_obj.get("results", [])
        elif isinstance(result_obj, list):
            results = result_obj

        if not results:
            return (
                f"{HEADER}{ERROR_ICON} *NO DATA FOUND*\n{SUB_LINE}\n\n"
                f"🎯 Query: `{mobile}`\n\nNo records found.\n{FOOTER}"
            )

        # Take first result record
        rec = results[0] if results else {}

        name = rec.get("NAME") or rec.get("name") or "N/A"
        father = rec.get("fname") or rec.get("father_name") or "N/A"
        addr_raw = rec.get("ADDRESS") or rec.get("address") or "N/A"
        # Clean address: replace ! with comma
        address = addr_raw.replace("!", ", ").replace(",  ", ", ").strip(", ")
        circle = rec.get("circle") or rec.get("Circle") or "N/A"
        mob = rec.get("MOBILE") or rec.get("mobile") or mobile
        aadhaar = rec.get("aadhaar") or rec.get("id") or ""
        email = rec.get("email") or ""
        alt = rec.get("alt") or ""

        result = (
            f"{HEADER}"
            f"📱 *MOBILE LOOKUP*\n"
            f"{SUB_LINE}\n\n"
            f"🎯 *Query:* `{mobile}`\n\n"
            f"🔍 *NUMBER LOOKUP RESULT*\n"
            f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\n"
            f"Lookup Result for: `{mobile}`\n"
            f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\n"
            f"👤 Name: {name}\n"
            f"👨 Father Name: {father}\n"
            f"📱 Mobile: `{mob}`\n"
            f"🏠 Address: {address}\n"
            f"📡 Circle: {circle}\n"
        )
        if aadhaar:
            result += f"🪪 Aadhaar: `{aadhaar}`\n"
        if email:
            result += f"📧 Email: {email}\n"
        if alt:
            result += f"📞 Alt Number: `{alt}`\n"

        result += (
            f"\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
            f"{FOOTER}"
        )
        return result

    # Fallback: plain text response
    body = clean_exploits_api_text(response.text)
    if not body:
        return (
            f"{HEADER}{ERROR_ICON} *NO DATA*\n{SUB_LINE}\n\n"
            f"No response from server for `{mobile}`.\n{FOOTER}"
        )

    # Plain text — display as-is in the formatted box
    return (
        f"{HEADER}"
        f"📱 *MOBILE LOOKUP*\n"
        f"{SUB_LINE}\n\n"
        f"🎯 *Query:* `{mobile}`\n\n"
        f"🔍 *NUMBER LOOKUP RESULT*\n"
        f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\n"
        f"{body}\n\n"
        f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
        f"{FOOTER}"
    )

def format_aadhaar_lookup_response(response, term: str) -> str:
    """Custom formatter for the subhxcosmo Aadhaar/family API."""
    if not response:
        return (
            f"{HEADER}{ERROR_ICON} *CONNECTION FAILED*\n{SUB_LINE}\n\n"
            f"Server did not respond. Try again later.\n{FOOTER}"
        )
    if response.status_code not in (200, 201, 202):
        return (
            f"{HEADER}{ERROR_ICON} *API ERROR*\n{SUB_LINE}\n\n"
            f"HTTP Status: `{response.status_code}`\n{FOOTER}"
        )

    try:
        data = response.json()
    except Exception:
        data = None

    if data and isinstance(data, dict):
        if not data.get("success"):
            return (
                f"{HEADER}{ERROR_ICON} *NO DATA FOUND*\n{SUB_LINE}\n\n"
                f"🎯 Query: `{term}`\n\nNo records found for this Aadhaar.\n{FOOTER}"
            )

        result_obj = data.get("result", {})
        results = []
        if isinstance(result_obj, dict):
            results = result_obj.get("results", [])
        elif isinstance(result_obj, list):
            results = result_obj

        if not results:
            return (
                f"{HEADER}{ERROR_ICON} *NO DATA FOUND*\n{SUB_LINE}\n\n"
                f"🎯 Query: `{term}`\n\nNo records found.\n{FOOTER}"
            )

        rec = results[0] if results else {}

        # Ration card details
        ration = rec.get("ration_card_details", {})
        state = ration.get("state_name", "N/A")
        district = ration.get("district_name", "N/A")
        ration_no = ration.get("ration_card_no", "N/A")
        scheme = ration.get("scheme_name", "N/A")

        # Members
        members = rec.get("members", [])

        # Additional info
        add_info = rec.get("additional_info", {})
        fps_cat = add_info.get("fps_category", "N/A")

        result = (
            f"{HEADER}"
            f"🪪 *AADHAAR LOOKUP*\n"
            f"{SUB_LINE}\n\n"
            f"🎯 *Query:* `{term}`\n\n"
            f"🔍 *AADHAAR LOOKUP RESULT*\n"
            f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\n"
            f"📋 *RATION CARD DETAILS*\n"
            f"  ┣ State: {state}\n"
            f"  ┣ District: {district}\n"
            f"  ┣ Ration Card No: `{ration_no}`\n"
            f"  ┣ Scheme: {scheme}\n"
            f"  ┗ FPS Category: {fps_cat}\n\n"
        )

        if members:
            result += f"👪 *FAMILY MEMBERS* ({len(members)})\n"
            for m in members:
                sno = m.get("s_no", "")
                name = m.get("member_name", "N/A")
                mid = m.get("member_id", "")
                result += f"  {sno}. {name}"
                if mid:
                    result += f" (ID: `{mid}`)"
                result += "\n"
            result += "\n"

        result += (
            f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
            f"{FOOTER}"
        )
        return result

    # Fallback: plain text
    body = clean_exploits_api_text(response.text)
    if not body:
        return (
            f"{HEADER}{ERROR_ICON} *NO DATA*\n{SUB_LINE}\n\n"
            f"No response from server for `{term}`.\n{FOOTER}"
        )
    return (
        f"{HEADER}"
        f"🪪 *AADHAAR LOOKUP*\n"
        f"{SUB_LINE}\n\n"
        f"🎯 *Query:* `{term}`\n\n"
        f"{body}\n\n"
        f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
        f"{FOOTER}"
    )

def clean_exploits_api_text(text: str) -> str:
    if not text:
        return ""
    skip = ("BUY API", "SUPPORT :", "@Cyb3rS0ldier", "@cyb3rs0ldier")
    lines = [ln.rstrip() for ln in text.splitlines() if not any(s in ln for s in skip)]
    return "\n".join(lines).strip()

def format_exploits_response(response, term: str, title: str) -> str:
    if not response:
        return (
            f"{HEADER}{ERROR_ICON} *CONNECTION FAILED*\n{SUB_LINE}\n\n"
            f"Server did not respond. Try again later.\n{FOOTER}"
        )

    if response.status_code not in (200, 201, 202):
        return (
            f"{HEADER}{ERROR_ICON} *API ERROR*\n{SUB_LINE}\n\n"
            f"HTTP Status: `{response.status_code}`\n{FOOTER}"
        )

    body = clean_exploits_api_text(response.text)
    if not body:
        return (
            f"{HEADER}{ERROR_ICON} *NO DATA*\n{SUB_LINE}\n\n"
            f"No response from server for `{term}`.\n{FOOTER}"
        )

    upper = body.upper()
    if "PROTECTED" in upper and "❌" not in body:
        return (
            f"{HEADER}🛡️ *PROTECTED*\n{SUB_LINE}\n\n"
            f"This record is protected and cannot be displayed.\n{FOOTER}"
        )
    if "❌ NO DATA FOUND" in upper or "NO DATA FOUND" in upper:
        return (
            f"{HEADER}{ERROR_ICON} *NO DATA FOUND*\n{SUB_LINE}\n\n"
            f"🎯 Query: `{term}`\n\nNo records found for this search.\n{FOOTER}"
        )
    if "❌ API ERROR" in upper or "❌ API Error" in body:
        hint = ""
        if "FAMILY" in upper:
            hint = "\n\n💡 _Try `/aadhaar` for single Aadhaar holder details._"
        return (
            f"{HEADER}{ERROR_ICON} *LOOKUP FAILED*\n{SUB_LINE}\n\n"
            f"🎯 Query: `{term}`\n\nAPI returned an error. Try again later.{hint}\n{FOOTER}"
        )

    return (
        f"{HEADER}{SUCCESS_ICON} *{title.upper()}*\n{SUB_LINE}\n\n"
        f"🎯 *Query:* `{term}`\n\n"
        f"{body}\n"
        f"{FOOTER}"
    )

async def fetch_like_api(uid: str, region: str):
    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.get(
                LIKE_API_URL,
                params={"uid": uid, "region": region},
                headers=LIKE_API_HEADERS,
            )
        return response
    except Exception as e:
        logging.error(f"Like API Request Error: {e}")
        return None

# --- Permission Checks & Tracking ---

async def track_user(update: Update):
    if not update.effective_user:
        return True
    
    user = update.effective_user
    await database.add_or_update_user(
        user.id,
        user.username,
        user.first_name,
        user.last_name
    )
    
    if await database.is_banned(user.id):
        if update.message:
            ban_msg = (
                f"{HEADER}"
                f"🔻 *ACCESS DENIED*\n"
                f"{SUB_LINE}\n\n"
                f"🚫 Your account has been *suspended*.\n"
                f"Contact the admin for appeal.\n"
                f"{FOOTER}"
            )
            await update.message.reply_text(ban_msg, parse_mode=constants.ParseMode.MARKDOWN)
        return False
        
    # Check Daily Limit (Admins bypass)
    if user.id not in ADMIN_IDS:
        can_use, used, limit = await database.check_daily_limit(user.id)
        if not can_use:
            if update.message:
                limit_msg = (
                    f"{HEADER}"
                    f"⚠️ *DAILY LIMIT REACHED*\n"
                    f"{SUB_LINE}\n\n"
                    f"📊 Usage: `{used}` / `{limit}` commands\n"
                    f"🔄 Resets in: *24 hours*\n\n"
                    f"💡 _Come back tomorrow or contact admin_\n"
                    f"_for a limit upgrade._\n"
                    f"{FOOTER}"
                )
                await update.message.reply_text(limit_msg, parse_mode=constants.ParseMode.MARKDOWN)
            return False
            
    return True

def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in ADMIN_IDS:
            deny_msg = (
                f"{HEADER}"
                f"🔒 *ADMIN ONLY*\n"
                f"{SUB_LINE}\n\n"
                f"This command requires *admin privileges*.\n"
                f"{FOOTER}"
            )
            await update.message.reply_text(deny_msg, parse_mode=constants.ParseMode.MARKDOWN)
            return
        return await func(update, context)
    return wrapper

def message_contains_link(message) -> bool:
    if not message:
        return False

    text = message.text or message.caption or ""
    if text and LINK_REGEX.search(text):
        return True

    entities = []
    if message.entities:
        entities.extend(message.entities)
    if message.caption_entities:
        entities.extend(message.caption_entities)

    link_types = {MessageEntity.URL, MessageEntity.TEXT_LINK, "url", "text_link"}
    for ent in entities:
        ent_type = ent.type.value if hasattr(ent.type, "value") else ent.type
        if ent.type in link_types or ent_type in ("url", "text_link"):
            return True
    return False

def can_send_links(user_id: int) -> bool:
    """Only bot admins (ADMIN_IDS) or whitelisted users may post links."""
    return user_id in ADMIN_IDS

# --- COIN EARN SYSTEM ---

async def earn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await track_user(update): return
    user_id = update.effective_user.id
    
    earn_msg = (
        f"{HEADER}"
        f"💰 *EARN FREE COINS*\n"
        f"{SUB_LINE}\n\n"
        f"1️⃣ Click the ad link below.\n"
        f"2️⃣ Wait for *20 seconds* on the page.\n"
        f"3️⃣ Come back and type `/claim`.\n\n"
        f"🔗 [CLICK HERE TO EARN]({AD_LINK})\n\n"
        f"🎁 Reward: `1` {COIN_ICON}\n"
        f"{FOOTER}"
    )
    
    # Store the exact time they generated the link
    await database.set_earn_timestamp(user_id)
    await update.message.reply_text(earn_msg, parse_mode=constants.ParseMode.MARKDOWN, disable_web_page_preview=True)

async def claim_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await track_user(update): return
    user_id = update.effective_user.id
    
    last_earn = await database.get_last_earn_time(user_id)
    if not last_earn:
        msg = f"{HEADER}{ERROR_ICON} *NO ACTIVE TASK*\n{SUB_LINE}\n\nUse `/earn` first to generate an ad link.\n{FOOTER}"
        await update.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)
        return
        
    start_time = datetime.datetime.fromisoformat(last_earn)
    elapsed = (datetime.datetime.now() - start_time).total_seconds()
    
    if elapsed < 20:
        wait_msg = (
            f"{HEADER}"
            f"{ERROR_ICON} *TOO FAST*\n"
            f"{SUB_LINE}\n\n"
            f"You must wait at least 20 seconds!\n"
            f"⏳ Remaining: `{int(20 - elapsed)}s`\n"
            f"{FOOTER}"
        )
        await update.message.reply_text(wait_msg, parse_mode=constants.ParseMode.MARKDOWN)
        return

    # Success - Add Coin & Clear Timestamp to prevent double claiming
    await database.add_coin(user_id, 1)
    await database.clear_earn_timestamp(user_id)
        
    new_bal = await database.get_coins(user_id)
    success_msg = (
        f"{HEADER}"
        f"{SUCCESS_ICON} *COIN CLAIMED!*\n"
        f"{SUB_LINE}\n\n"
        f"✅ You received `1` {COIN_ICON}\n"
        f"💰 Total Balance: `{new_bal}` {COIN_ICON}\n\n"
        f"You can now use premium commands.\n"
        f"{FOOTER}"
    )
    await update.message.reply_text(success_msg, parse_mode=constants.ParseMode.MARKDOWN)


# --- Command Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await track_user(update): return
    await database.log_activity(update.effective_user.id, "start")

    user_name = update.effective_user.first_name
    coins = await database.get_coins(update.effective_user.id)
    
    welcome_msg = (
        f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
        f"      🎮 *{BOT_TITLE}* 🎮\n"
        f"    ⚔️ *MULTI-TOOL BOT* ⚔️\n"
        f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n\n"
        f"Hey *{user_name}*! Welcome to the\n"
        f"ultimate gaming toolkit. 🕹️\n\n"
        f"💰 *Your Balance:* `{coins}` {COIN_ICON}\n\n"
        f"▬▬▬ 🛠️ *ARSENAL* 🛠️ ▬▬▬\n\n"
        f"📱 Send 10-digit number directly ({COIN_ICON})\n"
        f"🪪 `/aadhaar` ➜ _Aadhaar card info_\n"
        f"👪 `/family` ➜ _Family members lookup_\n"
        f"📮 `/pincode` ➜ _Pincode lookup_\n"
        f"🏦 `/ifsc` ➜ _IFSC bank lookup_\n"
        f"✈️ `/telegram` ➜ _Telegram OSINT_\n"
        f"📸 `/instagram` ➜ _Instagram OSINT_\n"
        f"🚗 `/vehicle` ➜ _Vehicle plate lookup_\n"
        f"🎯 `/visits` ➜ _FF profile visits_ ({COIN_ICON})\n"
        f"🔫 `/ffinfo` ➜ _Free Fire player info_ ({COIN_ICON})\n"
        f"❤️ `/like` ➜ _Send like_ 🔒 _Admin only_\n"
        f"💣 `/bomb` ➜ _SMS bomber_ ({COIN_ICON})\n\n"
        f"▬▬▬ 💰 *ECONOMY* 💰 ▬▬▬\n\n"
        f"🔗 `/earn` ➜ _Watch ad to earn coins_\n"
        f"🎁 `/claim` ➜ _Claim your earned coins_\n\n"
        f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
        f"💡 Use `/help` for detailed usage.\n"
        f"{FOOTER}"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔗 Support Channel", url="https://t.me/maniuf76")],
        [InlineKeyboardButton("📖 Help & Commands", callback_data="help_btn")]
    ]
    if update.effective_user.id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")])
        
    await update.message.reply_text(
        welcome_msg,
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await track_user(update): return
    await database.log_activity(update.effective_user.id, "help")
    
    help_text = (
        f"{HEADER}"
        f"📖 *COMMAND MANUAL*\n"
        f"{SUB_LINE}\n\n"
        f"🔹 *OSINT TOOLS*\n"
        f"  📱 Send 10-digit number directly ({COIN_ICON})\n"
        f"  🪪 `/aadhaar <aadhaar_number>` — Aadhaar holder info\n"
        f"  👪 `/family <aadhaar_number>` — Family members list\n"
        f"  📮 `/pincode <pincode>`\n"
        f"  🏦 `/ifsc <ifsc_code>`\n"
        f"  ✈️ `/telegram <username>`\n"
        f"  📸 `/instagram <username>`\n"
        f"  🚗 `/vehicle <plate_number>`\n\n"
        f"🔹 *GAMING TOOLS*\n"
        f"  🔫 `/ffinfo <uid>` — Player info ({COIN_ICON})\n"
        f"  🎯 `/visits <uid> <region>` — Visits ({COIN_ICON})\n"
        f"  ❤️ `/like <uid> <region>` — Send like 🔒 _Admin only_\n"
        f"  💣 `/bomb <number>` — SMS bomber ({COIN_ICON})\n\n"
        f"🔹 *ECONOMY*\n"
        f"  🔗 `/earn` — Generate ad link\n"
        f"  🎁 `/claim` — Claim your coins\n\n"
        f"  💎 `/balance` — Check coins\n"
        f"  🏆 `/leaderboard` — View top users\n"
        f"  🎫 `/redeem <code>` — Use redeem code\n\n"
        f"🔹 *ADMIN ECONOMY*\n"
        f"  `/give <user_id> <coins>` — add coins\n"
        f"  `/gencode <code> <coins> <max_uses>` — create redeem code\n"
        f"  `/delcode <code>` — delete redeem code\n"
        f"  `/resetallcoins` — reset all user coins\n\n"
        f"🔹 *GROUP LINK GUARD* (Admin)\n"
        f"  `/wladd <user_id>` — allow links\n"
        f"  `/wlremove <user_id>` — remove allow\n"
        f"  `/wllist` — view whitelist\n\n"
        f"🔹 *LIKE REGIONS:* `IND` `NX` `AG`\n\n"
        f"💡 _Like command is admin-only._\n"
        f"{FOOTER}"
    )
    await update.message.reply_text(help_text, parse_mode=constants.ParseMode.MARKDOWN)

# --- LIKE COMMAND (ADMIN ONLY) ---
@admin_only
async def like_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await track_user(update):
        return

    user_id = update.effective_user.id

    if len(context.args) < 2:
        usage_msg = (
            f"{HEADER}"
            f"{ERROR_ICON} *INVALID SYNTAX*\n"
            f"{SUB_LINE}\n\n"
            f"📝 *Format:* `/like <uid> <region>`\n"
            f"📌 *Example:* `/like 1234567890 IND`\n\n"
            f"🌍 *Regions:* `IND` `NX` `AG`\n"
            f"{FOOTER}"
        )
        await update.message.reply_text(usage_msg, parse_mode=constants.ParseMode.MARKDOWN)
        return

    uid, region = context.args[0], context.args[1].upper()

    if not uid.isdigit():
        await update.message.reply_text(
            f"{HEADER}{ERROR_ICON} *INVALID UID*\n{SUB_LINE}\n\nUID must be a numeric value.{FOOTER}",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return

    region = LIKE_REGION_ALIASES.get(region, region)
    if region not in LIKE_VALID_REGIONS:
        regions_str = "` `".join(LIKE_VALID_REGIONS)
        await update.message.reply_text(
            f"{HEADER}{ERROR_ICON} *INVALID REGION*\n{SUB_LINE}\n\nUse one of: `{regions_str}`{FOOTER}",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return

    loading_msg = (
        f"{HEADER}"
        f"{LOADING_ICON} *SENDING LIKE...*\n"
        f"{SUB_LINE}\n\n"
        f"🎯 UID    : `{uid}`\n"
        f"🌍 Region : `{region}`\n\n"
        f"_Please wait..._\n"
        f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰"
    )
    msg = await update.message.reply_text(loading_msg, parse_mode=constants.ParseMode.MARKDOWN)

    response = await fetch_like_api(uid, region)

    if response and response.status_code == 200:
        try:
            data = response.json()

            if isinstance(data, dict) and data.get("error"):
                result_text = (
                    f"{HEADER}{ERROR_ICON} *LIKE FAILED*\n{SUB_LINE}\n\n"
                    f"⚠️ {data.get('error')}\n{FOOTER}"
                )
            else:
                await database.record_user_like(user_id, uid, region)
                await database.log_activity(user_id, "like", f"{uid} {region}")

                player_info = data.get("player") or data.get("Player") or {}
                likes_info = data.get("likes") or data.get("Likes") or {}

                if player_info or likes_info:
                    result_text = (
                        f"{HEADER}"
                        f"{SUCCESS_ICON} *LIKE DELIVERED!*\n"
                        f"{SUB_LINE}\n\n"
                        f"👤 *PLAYER*\n"
                        f"  ┣ Nickname : `{player_info.get('nickname', player_info.get('name', 'N/A'))}`\n"
                        f"  ┣ UID      : `{player_info.get('uid', uid)}`\n"
                        f"  ┗ Region   : `{player_info.get('region', region)}`\n\n"
                        f"❤️ *LIKE STATS*\n"
                        f"  ┣ Before : `{likes_info.get('before', likes_info.get('before_likes', 0))}`\n"
                        f"  ┣ After  : `{likes_info.get('after', likes_info.get('after_likes', 0))}`\n"
                        f"  ┗ Added  : `+{likes_info.get('added_by_api', likes_info.get('added', 0))}`\n"
                        f"{FOOTER}"
                    )
                else:
                    result_text = format_response(response, f"{uid} {region}", "Like")
        except Exception as e:
            logging.error(f"Like API parsing error: {e}")
            result_text = f"{HEADER}{ERROR_ICON} *PARSE ERROR*\n{SUB_LINE}\n\n`{response.text[:200]}`{FOOTER}"
    else:
        error_msg = "Connection failed"
        if response:
            error_msg = f"Status {response.status_code}"
            try:
                error_data = response.json()
                error_msg = error_data.get("error") or error_data.get("message", error_msg)
            except Exception:
                if response.text:
                    error_msg = response.text[:200]
        result_text = f"{HEADER}{ERROR_ICON} *LIKE FAILED*\n{SUB_LINE}\n\n{error_msg}{FOOTER}"

    await msg.edit_text(result_text, parse_mode=constants.ParseMode.MARKDOWN)

# --- ExploitsIndia OSINT Handler ---
async def handle_exploits_lookup(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    api_key: str,
    cmd_name: str,
    param_hint: str,
    requires_coin: bool = False,
):
    if not await track_user(update):
        return

    user_id = update.effective_user.id

    if not context.args:
        usage_msg = (
            f"{HEADER}{ERROR_ICON} *INVALID SYNTAX*\n{SUB_LINE}\n\n"
            f"Format: `/{cmd_name} <{param_hint}>`\n{FOOTER}"
        )
        await update.message.reply_text(usage_msg, parse_mode=constants.ParseMode.MARKDOWN)
        return

    if requires_coin and user_id not in ADMIN_IDS:
        coins = await database.get_coins(user_id)
        if coins < 1:
            await update.message.reply_text(NO_COIN_MSG, parse_mode=constants.ParseMode.MARKDOWN)
            return
        await database.deduct_coin(user_id, 1)

    term = " ".join(context.args)
    title, endpoint, emoji = EXPLOITS_APIS[api_key]
    await database.log_activity(user_id, cmd_name, term)

    loading = (
        f"{HEADER}{LOADING_ICON} *SCANNING...*\n{SUB_LINE}\n\n"
        f"{emoji} {title}\nTarget: `{term}`\n\n_Fetching data..._\n"
        f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰"
    )
    progress_msg = await update.message.reply_text(loading, parse_mode=constants.ParseMode.MARKDOWN)
    await update.message.chat.send_action(constants.ChatAction.TYPING)

    url = build_exploits_url(endpoint, term)
    response = await fetch_api_data(url)
    result_text = format_exploits_response(response, term, title)

    try:
        if len(result_text) <= 4096:
            await progress_msg.edit_text(result_text, parse_mode=constants.ParseMode.MARKDOWN)
        else:
            await progress_msg.delete()
            await send_reply(update, context, result_text)
    except Exception as e:
        logging.error(f"Failed to send exploits result: {e}")
        try:
            await send_reply(update, context, result_text)
        except Exception as e2:
            logging.error(f"Fallback send failed: {e2}")

def format_response(response, term, title):
    if not response:
        return (
            f"{HEADER}"
            f"{ERROR_ICON} *CONNECTION FAILED*\n"
            f"{SUB_LINE}\n\n"
            f"Server did not respond. Try again later.\n"
            f"{FOOTER}"
        )
    
    try:
        json_data = response.json()
    except:
        json_data = None

    if response.status_code not in [200, 201, 202]:
        err = ""
        if json_data and (json_data.get("message") or json_data.get("error")):
            err = json_data.get('message') or json_data.get('error')
        else:
            err = f"HTTP {response.status_code}"
        return (
            f"{HEADER}"
            f"{ERROR_ICON} *API ERROR*\n"
            f"{SUB_LINE}\n\n"
            f"⚠️ {err}\n"
            f"{FOOTER}"
        )
    
    try:
        if isinstance(json_data, dict):
            if json_data.get("status") == "error" or json_data.get("error") is True:
                return (
                    f"{HEADER}"
                    f"{ERROR_ICON} *LOOKUP FAILED*\n"
                    f"{SUB_LINE}\n\n"
                    f"⚠️ {json_data.get('message', 'Unknown error')}\n"
                    f"{FOOTER}"
                )

            # Remove unwanted fields from API response
            json_data.pop("owner", None)
            json_data.pop("success", None)
            json_data.pop("cached", None)
            json_data.pop("proxyUsed", None)
            json_data.pop("attempt", None)
            json_data.pop("developer", None)
            json_data.pop("developerinfo", None)
            json_data.pop("Developerinfo", None)
            json_data.pop("developerInfo", None)
            json_data.pop("DeveloperInfo", None)
            
            results = json_data.get("result", {}).get("results", []) if isinstance(json_data.get("result"), dict) else json_data.get("result", [])
            
            if results and isinstance(results, list):
                result_text = (
                    f"{HEADER}"
                    f"{SUCCESS_ICON} *{title.upper()}*\n"
                    f"{SUB_LINE}\n\n"
                    f"🎯 *Query:* `{term}`\n\n"
                )
                for idx, record in enumerate(results[:5], 1):
                    result_text += f"╔══ 📄 *Record {idx}* ══╗\n"
                    for k, v in record.items():
                        if v:
                            key = k.replace('_', ' ').title()
                            result_text += f"┃ ▸ *{key}:* `{v}`\n"
                    result_text += f"╚{'═' * 20}╝\n\n"
                result_text += FOOTER
                return result_text
            
            result_text = (
                f"{HEADER}"
                f"{SUCCESS_ICON} *{title.upper()}*\n"
                f"{SUB_LINE}\n\n"
            )
            for k, v in json_data.items():
                # Filter out developer-related fields (case insensitive)
                if v and "developer" not in k.lower():
                    key = k.replace('_', ' ').title()
                    result_text += f"▸ *{key}:* `{v}`\n"
            result_text += f"\n{FOOTER}"
            return result_text
            
        return f"{HEADER}{SUCCESS_ICON} *{title.upper()}*\n{SUB_LINE}\n\n{response.text[:1000]}\n{FOOTER}"
    except Exception as e:
        logging.error(f"Formatting error: {e}")
        return f"{HEADER}{SUCCESS_ICON} *{title.upper()}*\n{SUB_LINE}\n\n{response.text[:1000]}\n{FOOTER}"

# --- OSINT Wrappers ---
async def aadhaar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Aadhaar family lookup via subhxcosmo API."""
    if not await track_user(update):
        return

    if not context.args:
        await update.message.reply_text(
            f"{HEADER}{ERROR_ICON} *USAGE*\n{SUB_LINE}\n\n"
            f"`/aadhaar <12_digit_aadhaar>`\n"
            f"Example: `/aadhaar 905863437154`\n{FOOTER}",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return
    term = context.args[0].strip()
    if not term.isdigit() or len(term) != 12:
        await update.message.reply_text(
            f"{HEADER}{ERROR_ICON} *INVALID AADHAAR*\n{SUB_LINE}\n\n"
            f"Aadhaar must be exactly 12 digits.\n{FOOTER}",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return

    user_id = update.effective_user.id
    await database.log_activity(user_id, "aadhaar", term)

    loading = (
        f"{HEADER}"
        f"{LOADING_ICON} *SCANNING...*\n"
        f"{SUB_LINE}\n\n"
        f"🪪 Aadhaar Lookup\nTarget: `{term}`\n\n_Fetching data..._\n"
        f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰"
    )
    progress_msg = await update.message.reply_text(loading, parse_mode=constants.ParseMode.MARKDOWN)
    await update.message.chat.send_action(constants.ChatAction.TYPING)

    url = build_exploits_url(AADHAAR_API_ENDPOINT, term)
    response = await fetch_api_data(url)
    result_text = format_aadhaar_lookup_response(response, term)

    try:
        if len(result_text) <= 4096:
            await progress_msg.edit_text(result_text, parse_mode=constants.ParseMode.MARKDOWN)
        else:
            await progress_msg.delete()
            await send_reply(update, context, result_text)
    except Exception as e:
        logging.error(f"Failed to send aadhaar result: {e}")
        try:
            await progress_msg.edit_text(result_text)
        except Exception:
            await send_reply(update, context, result_text)

async def family_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Family members list — family.php API (separate from /aadhaar)."""
    if not context.args:
        await update.message.reply_text(
            f"{HEADER}{ERROR_ICON} *USAGE*\n{SUB_LINE}\n\n"
            f"`/family <12_digit_aadhaar>`\n"
            f"Example: `/family 905863437154`\n\n"
            f"_For single person details use_ `/aadhaar`\n{FOOTER}",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return
    term = context.args[0].strip()
    if not term.isdigit() or len(term) != 12:
        await update.message.reply_text(
            f"{HEADER}{ERROR_ICON} *INVALID AADHAAR*\n{SUB_LINE}\n\n"
            f"Enter 12-digit Aadhaar number for family lookup.\n{FOOTER}",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return
    await handle_exploits_lookup(update, context, "family", "family", "aadhaar_number")

async def pincode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_exploits_lookup(update, context, "pincode", "pincode", "pincode")

async def ifsc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_exploits_lookup(update, context, "ifsc", "ifsc", "ifsc_code")

async def telegram_osint_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_exploits_lookup(update, context, "telegram", "telegram", "username")

async def instagram_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_exploits_lookup(update, context, "instagram", "instagram", "username")

async def vehicle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_exploits_lookup(update, context, "vehicle", "vehicle", "plate_number")

def format_ffinfo(data):
    if not isinstance(data, dict):
        return f"{HEADER}{ERROR_ICON} *API ERROR*\n{SUB_LINE}\n\nInvalid response from API.{FOOTER}"
        
    p = data.get("playerData", {})
    prof = data.get("profileInfo", {})
    soc = data.get("socialInfo", {})
    pet = data.get("petInfo", {})
    cred = data.get("creditScoreInfo", {})
    dia = data.get("diamondCostRes", {})
    dev = data.get("developerInfo", {})

    def ts_to_date(ts):
        if not ts: return "N/A"
        try: return datetime.datetime.fromtimestamp(int(ts)).strftime("%d %b %Y, %I:%M %p").lower()
        except: return "N/A"
        
    def br_rank_name(pts):
        return "Ranked" if pts else "Unranked"

    equipped_items = prof.get("equippedItems", [])
    weapon_skins = p.get("weaponSkinShows", [])
    skills = prof.get("EquippedSkills", [])
    prime = p.get("primeLevel", {}).get("primeLevel", "N/A")
    if "<:" in prime:
        prime = prime.split("<")[0].strip()

    msg = f"┌ 👤 ACCOUNT BASIC INFO\n"
    msg += f"├─ Name: {p.get('nickname', 'N/A')}\n"
    msg += f"├─ UID: {p.get('accountId', 'N/A')}\n"
    msg += f"├─ Level: {p.get('level', 'N/A')} (EXP: {p.get('exp', 'N/A'):,})\n"
    msg += f"├─ Region: {p.get('region', 'N/A')}\n"
    msg += f"├─ Likes: {p.get('liked', 'N/A'):,}\n"
    msg += f"├─ Prime Level: {prime}\n"
    msg += f"├─ Account Type: {p.get('accountType', 'N/A')}\n"
    msg += f"├─ Release Version: {p.get('releaseVersion', 'N/A')}\n"
    msg += f"├─ Season ID: {p.get('seasonId', 'N/A')}\n"
    msg += f"├─ Badge Count: {p.get('badgeCnt', 'N/A')} (ID: {p.get('badgeId', 'N/A')})\n"
    msg += f"├─ Title ID: {p.get('title', 'N/A')}\n"
    msg += f"├─ Banner ID: {p.get('bannerId', 'N/A')}\n"
    msg += f"├─ Head Pic ID: {p.get('headPic', 'N/A')}\n"
    msg += f"├─ Created At: {ts_to_date(p.get('createAt'))}\n"
    msg += f"└─ Last Login: {ts_to_date(p.get('lastLoginAt'))}\n\n"

    msg += f"┌ 🏆 RANKS & ACTIVITY\n"
    msg += f"├─ BR Rank: {br_rank_name(p.get('rankingPoints'))} ({p.get('rankingPoints', 'N/A'):,} Pts) — Pos: {p.get('rank', 'N/A')}\n"
    msg += f"├─ BR Max Rank: {p.get('maxRank', 'N/A')}\n"
    msg += f"├─ Show BR Rank: {'Yes' if p.get('showBrRank') else 'No'}\n"
    msg += f"├─ CS Rank: {br_rank_name(p.get('csRankingPoints'))} ({p.get('csRankingPoints', 'N/A')} Pts) — Pos: {p.get('csRank', 'N/A')}\n"
    msg += f"├─ CS Max Rank: {p.get('csMaxRank', 'N/A')}\n"
    msg += f"└─ Show CS Rank: {'Yes' if p.get('showCsRank') else 'No'}\n\n"

    msg += f"┌ 💬 SOCIAL INFO\n"
    msg += f"├─ Language: {soc.get('language', 'N/A')}\n"
    msg += f"├─ Active Time: {soc.get('activeTime', 'N/A')}\n"
    msg += f"├─ Rank Show: {soc.get('rankShow', 'N/A')}\n"
    msg += f"└─ Signature:\n{soc.get('signature', 'N/A')}\n\n"

    msg += f"┌ 👕 COSMETICS & EQUIPMENT\n"
    msg += f"├─ Avatar ID: {prof.get('avatarId', 'N/A')}\n"
    msg += f"├─ Clothes: {prof.get('clothes', ['N/A'])[0]}\n"
    msg += f"├─ Equipped Items: {len(equipped_items)} Items\n"
    msg += f"│ {', '.join(map(str, equipped_items))}\n"
    msg += f"├─ Weapon Skins: {len(weapon_skins)} Equipped\n"
    msg += f"│ {', '.join(map(str, weapon_skins))}\n"
    msg += f"└─ Skills: {', '.join(map(str, skills))}\n\n"

    msg += f"┌ 🐾 PET DETAILS\n"
    msg += f"├─ Name: {pet.get('name', 'N/A')}\n"
    msg += f"├─ ID: {pet.get('id', 'N/A')}\n"
    msg += f"├─ Level: {pet.get('level', 'N/A')} (EXP: {pet.get('exp', 'N/A')})\n"
    msg += f"├─ Skin ID: {pet.get('skinId', 'N/A')}\n"
    msg += f"├─ Skill ID: {pet.get('selectedSkillId', 'N/A')}\n"
    msg += f"└─ Selected: {'Yes' if pet.get('isSelected') else 'No'}\n\n"

    msg += f"┌ 💎 CREDIT & DIAMONDS\n"
    msg += f"├─ Credit Score: {cred.get('creditScore', 'N/A')}/100\n"
    msg += f"├─ Reward State: {cred.get('rewardState', 'N/A').replace('_', ' ')}\n"
    msg += f"├─ Summary End: {ts_to_date(cred.get('periodicSummaryEndTime'))}\n"
    msg += f"└─ Diamond Cost: 💎 {dia.get('diamondCost', 'N/A')}\n\n"

    msg += f"┌ ⚡ DEVELOPER INFO\n"
    msg += f"├─ Developer: ! Ｍａｎｉ２７２\n"
    msg += f"└─ Signature: ! Ｍａｎｉ２７２ — Always learning 💻 Full-stack Developer\n\n"
    msg += f"! Ｍａｎｉ２７２ Intelligence • ! Ｍａｎｉ２７２ | UID: {p.get('accountId', 'N/A')}•\n"

    return f"```\n{msg}\n```"

async def ffinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await track_user(update): return
    
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        coins = await database.get_coins(user_id)
        if coins < 1:
            await update.message.reply_text(NO_COIN_MSG, parse_mode=constants.ParseMode.MARKDOWN)
            return
            
    if not context.args:
        usage_msg = (
            f"{HEADER}"
            f"{ERROR_ICON} *INVALID SYNTAX*\n"
            f"{SUB_LINE}\n\n"
            f"📝 *Format:* `/ffinfo <uid>`\n"
            f"📌 *Example:* `/ffinfo 1234567890`\n"
            f"{FOOTER}"
        )
        await update.message.reply_text(usage_msg, parse_mode=constants.ParseMode.MARKDOWN)
        return

    if user_id not in ADMIN_IDS:
        await database.deduct_coin(user_id, 1)

    uid = context.args[0]
    await database.log_activity(user_id, "ffinfo", uid)
    
    loading = (
        f"{HEADER}"
        f"{LOADING_ICON} *SCANNING PLAYER...*\n"
        f"{SUB_LINE}\n\n"
        f"🔫 Free Fire INFO\n"
        f"🎯 UID : `{uid}`\n\n"
        f"_Fetching data..._\n"
        f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰"
    )
    msg = await update.message.reply_text(loading, parse_mode=constants.ParseMode.MARKDOWN)
    
    url = f"http://node1.quaxly.com:25357/info?uid={uid}"
    response = await fetch_api_data(url)
    
    if response and response.status_code == 200:
        try:
            data = response.json()
            if data.get("error"):
                result_text = f"{HEADER}{ERROR_ICON} *API ERROR*\n{SUB_LINE}\n\n{data.get('error')}\n{FOOTER}"
            else:
                result_text = format_ffinfo(data)
        except Exception as e:
            result_text = f"{HEADER}{ERROR_ICON} *PARSE ERROR*\n{SUB_LINE}\n\nCould not parse response.\n{FOOTER}"
    else:
        result_text = f"{HEADER}{ERROR_ICON} *CONNECTION FAILED*\n{SUB_LINE}\n\nServer did not respond.\n{FOOTER}"
        
    await msg.edit_text(result_text, parse_mode=constants.ParseMode.MARKDOWN)

async def run_mobile_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE, mobile: str):
    if not await track_user(update):
        return

    user_id = update.effective_user.id

    if user_id not in ADMIN_IDS:
        if await database.is_protected(mobile):
            protect_msg = (
                f"{HEADER}"
                f"🛡️ *PROTECTED NUMBER*\n"
                f"{SUB_LINE}\n\n"
                f"This number is shielded by the admin.\n"
                f"{FOOTER}"
            )
            await send_reply(update, context, protect_msg)
            return

        coins = await database.get_coins(user_id)
        if coins < 1:
            await send_reply(update, context, NO_COIN_MSG)
            return
        await database.deduct_coin(user_id, 1)

    await database.log_activity(user_id, "mobile")

    loading = (
        f"{HEADER}"
        f"{LOADING_ICON} *SCANNING NUMBER...*\n"
        f"{SUB_LINE}\n\n"
        f"📱 Target : `{mobile}`\n\n"
        f"_Fetching data..._\n"
        f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰"
    )
    try:
        progress_msg = await send_reply(update, context, loading)
    except Exception as e:
        logging.error(f"Failed to send loading message: {e}")
        return

    url = build_exploits_url(NUMBER_API_ENDPOINT, mobile)
    response = await fetch_api_data(url)
    result_text = format_number_lookup_response(response, mobile)

    try:
        if len(result_text) <= 4096:
            await progress_msg.edit_text(result_text, parse_mode=constants.ParseMode.MARKDOWN)
        else:
            await progress_msg.delete()
            await send_reply(update, context, result_text)
    except Exception as e:
        logging.error(f"Failed to send mobile result (edit): {e}")
        try:
            await progress_msg.edit_text(result_text)
        except Exception:
            pass
        try:
            await send_reply(update, context, result_text)
        except Exception as e2:
            logging.error(f"Fallback send also failed: {e2}")

async def mobile_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    bot_username = context.bot.username if context.bot else None
    mobile = extract_mobile_from_message(update.message, bot_username)
    if not mobile:
        return

    await run_mobile_lookup(update, context, mobile)

# --- Visits Command ---
async def visits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await track_user(update): return
    
    user_id = update.effective_user.id
    
    # PREMIUM COIN CHECK
    if user_id not in ADMIN_IDS:
        coins = await database.get_coins(user_id)
        if coins < 1:
            await update.message.reply_text(NO_COIN_MSG, parse_mode=constants.ParseMode.MARKDOWN)
            return
            
    if len(context.args) < 2:
        usage_msg = (
            f"{HEADER}"
            f"{ERROR_ICON} *INVALID SYNTAX*\n"
            f"{SUB_LINE}\n\n"
            f"📝 *Format:* `/visits <uid> <region>`\n"
            f"📌 *Example:* `/visits 1234567890 IN`\n"
            f"{FOOTER}"
        )
        await update.message.reply_text(usage_msg, parse_mode=constants.ParseMode.MARKDOWN)
        return

    # Deduct coin
    if user_id not in ADMIN_IDS:
        await database.deduct_coin(user_id, 1)

    uid, region = context.args[0], context.args[1]
    await database.log_activity(user_id, "visits", f"{uid} {region}")
    
    loading = (
        f"{HEADER}"
        f"{LOADING_ICON} *FETCHING VISITS...*\n"
        f"{SUB_LINE}\n\n"
        f"🎯 UID    : `{uid}`\n"
        f"🌍 Region : `{region}`\n\n"
        f"_Please wait..._\n"
        f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰"
    )
    msg = await update.message.reply_text(loading, parse_mode=constants.ParseMode.MARKDOWN)
    url = f"{BASE_URL_VISITS}?uid={uid}&region={region}"
    resp = await fetch_api_data(url)
    result_text = format_response(resp, f"{uid} {region}", "Visits")
    await msg.edit_text(result_text, parse_mode=constants.ParseMode.MARKDOWN)

# --- Bomber Command ---
async def bomber_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await track_user(update): return
    
    user_id = update.effective_user.id
    
    # PREMIUM COIN CHECK
    if user_id not in ADMIN_IDS:
        coins = await database.get_coins(user_id)
        if coins < 1:
            await update.message.reply_text(NO_COIN_MSG, parse_mode=constants.ParseMode.MARKDOWN)
            return
            
    if not context.args:
        usage_msg = (
            f"{HEADER}"
            f"{ERROR_ICON} *INVALID SYNTAX*\n"
            f"{SUB_LINE}\n\n"
            f"📝 *Format:* `/bomb <number>`\n"
            f"📌 *Example:* `/bomb 9876543210`\n"
            f"{FOOTER}"
        )
        await update.message.reply_text(usage_msg, parse_mode=constants.ParseMode.MARKDOWN)
        return

    number = context.args[0]
    
    if user_id not in ADMIN_IDS:
        if await database.is_protected(number):
            protect_msg = (
                f"{HEADER}"
                f"🛡️ *PROTECTED NUMBER*\n"
                f"{SUB_LINE}\n\n"
                f"This number is shielded by the admin.\n"
                f"{FOOTER}"
            )
            await update.message.reply_text(protect_msg, parse_mode=constants.ParseMode.MARKDOWN)
            return
            
        # Deduct coin
        await database.deduct_coin(user_id, 1)

    await database.log_activity(user_id, "bomb", number)
    loading = (
        f"{HEADER}"
        f"💣 *BOMBING INITIATED...*\n"
        f"{SUB_LINE}\n\n"
        f"📱 Target : `{number}`\n"
        f"📊 Amount : `100`\n\n"
        f"_Deploying SMS strikes..._\n"
        f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰"
    )
    msg = await update.message.reply_text(loading, parse_mode=constants.ParseMode.MARKDOWN)
    
    url = f"{BASE_URL_BOMBER}?phone={number}&amount=100"
    resp = await fetch_api_data(url)
    result_text = format_response(resp, number, "SMS Bomber")
    await msg.edit_text(result_text, parse_mode=constants.ParseMode.MARKDOWN)

# --- Admin Panel & Commands ---

@admin_only
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = await database.get_stats()
    msg = (
        f"{HEADER}"
        f"📊 *DASHBOARD*\n"
        f"{SUB_LINE}\n\n"
        f"👥 Total Users  : `{stats['total_users']}`\n"
        f"✨ New Today    : `{stats['new_users_today']}`\n"
        f"🔥 Active Today : `{stats['active_today']}`\n\n"
        f"▬▬▬ 🏆 *TOP COMMANDS* ▬▬▬\n\n"
    )
    for cmd, count in stats['top_commands']:
        msg += f"  ▸ `{cmd}` — {count} uses\n"
    
    msg += f"\n▬▬▬ ❤️ *LIKE STATS* ▬▬▬\n\n"
    for vtype, count in stats['bot_stats']:
        msg += f"  ▸ `{vtype}` — {count}\n"
        
    msg += f"\n{FOOTER}"
    await update.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)

@admin_only
async def ban_user_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(f"{HEADER}{ERROR_ICON} *USAGE*\n{SUB_LINE}\n\n`/banuser <user_id>`{FOOTER}", parse_mode=constants.ParseMode.MARKDOWN)
        return
    user_id = int(context.args[0])
    await database.ban_user(user_id)
    await update.message.reply_text(f"{HEADER}🔨 *USER BANNED*\n{SUB_LINE}\n\n🆔 `{user_id}` has been suspended.{FOOTER}", parse_mode=constants.ParseMode.MARKDOWN)

@admin_only
async def unban_user_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(f"{HEADER}{ERROR_ICON} *USAGE*\n{SUB_LINE}\n\n`/unbanuser <user_id>`{FOOTER}", parse_mode=constants.ParseMode.MARKDOWN)
        return
    user_id = int(context.args[0])
    await database.unban_user(user_id)
    await update.message.reply_text(f"{HEADER}{SUCCESS_ICON} *USER UNBANNED*\n{SUB_LINE}\n\n🆔 `{user_id}` has been restored.{FOOTER}", parse_mode=constants.ParseMode.MARKDOWN)

@admin_only
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(f"{HEADER}{ERROR_ICON} *USAGE*\n{SUB_LINE}\n\n`/broadcast <message>`{FOOTER}", parse_mode=constants.ParseMode.MARKDOWN)
        return
    
    msg_text = " ".join(context.args)
    users = await database.get_all_users()
    
    broadcast_msg = (
        f"{HEADER}"
        f"📣 *ANNOUNCEMENT*\n"
        f"{SUB_LINE}\n\n"
        f"{msg_text}\n"
        f"{FOOTER}"
    )
    
    count = 0
    for user_id in users:
        try:
            await context.bot.send_message(user_id, broadcast_msg, parse_mode=constants.ParseMode.MARKDOWN)
            count += 1
        except:
            pass
    await update.message.reply_text(f"{HEADER}{SUCCESS_ICON} *BROADCAST SENT*\n{SUB_LINE}\n\n📨 Delivered to `{count}` users.{FOOTER}", parse_mode=constants.ParseMode.MARKDOWN)

@admin_only
async def user_info_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(f"{HEADER}{ERROR_ICON} *USAGE*\n{SUB_LINE}\n\n`/userinfo <user_id>`{FOOTER}", parse_mode=constants.ParseMode.MARKDOWN)
        return
    user_id = int(context.args[0])
    user = await database.get_user_info(user_id)
    if not user:
        await update.message.reply_text(f"{HEADER}{ERROR_ICON} *NOT FOUND*\n{SUB_LINE}\n\nUser not found in database.{FOOTER}", parse_mode=constants.ParseMode.MARKDOWN)
        return
    
    ban_status = "🔴 BANNED" if user['is_banned'] else "🟢 ACTIVE"
    info = (
        f"{HEADER}"
        f"👤 *PLAYER DOSSIER*\n"
        f"{SUB_LINE}\n\n"
        f"  ┣ ID       : `{user['user_id']}`\n"
        f"  ┣ Username : @{user['username']}\n"
        f"  ┣ Name     : {user['first_name']} {user['last_name'] or ''}\n"
        f"  ┣ Joined   : `{user['join_date']}`\n"
        f"  ┣ Active   : `{user['last_active']}`\n"
        f"  ┣ Commands : `{user['commands_count']}`\n"
        f"  ┣ Coins    : `{user.get('coins', 0)}` {COIN_ICON}\n"
        f"  ┣ Likes    : `{user.get('likes_count', 0)}`\n"
        f"  ┗ Status   : {ban_status}\n"
        f"{FOOTER}"
    )
    await update.message.reply_text(info, parse_mode=constants.ParseMode.MARKDOWN)

@admin_only
async def set_limit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(f"{HEADER}{ERROR_ICON} *USAGE*\n{SUB_LINE}\n\n`/setlimit <user_id> <limit>`{FOOTER}", parse_mode=constants.ParseMode.MARKDOWN)
        return
    user_id = int(context.args[0])
    limit = int(context.args[1])
    await database.set_user_limit(user_id, limit)
    await update.message.reply_text(f"{HEADER}{SUCCESS_ICON} *LIMIT UPDATED*\n{SUB_LINE}\n\n🆔 User : `{user_id}`\n📊 Limit : `{limit}` / day{FOOTER}", parse_mode=constants.ParseMode.MARKDOWN)

@admin_only
async def reset_likes_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await database.reset_likes_cooldown()
    await update.message.reply_text(f"{HEADER}{SUCCESS_ICON} *COOLDOWNS RESET*\n{SUB_LINE}\n\nAll like cooldowns cleared.\nUsers can like again immediately.{FOOTER}", parse_mode=constants.ParseMode.MARKDOWN)

@admin_only
async def protect_number_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(f"{HEADER}{ERROR_ICON} *USAGE*\n{SUB_LINE}\n\n`/protect <number>`{FOOTER}", parse_mode=constants.ParseMode.MARKDOWN)
        return
    number = context.args[0]
    await database.protect_number(number, update.effective_user.id)
    await update.message.reply_text(f"{HEADER}🛡️ *NUMBER PROTECTED*\n{SUB_LINE}\n\n`{number}` is now shielded.{FOOTER}", parse_mode=constants.ParseMode.MARKDOWN)

@admin_only
async def unprotect_number_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(f"{HEADER}{ERROR_ICON} *USAGE*\n{SUB_LINE}\n\n`/unprotect <number>`{FOOTER}", parse_mode=constants.ParseMode.MARKDOWN)
        return
    number = context.args[0]
    await database.unprotect_number(number)
    await update.message.reply_text(f"{HEADER}{SUCCESS_ICON} *SHIELD REMOVED*\n{SUB_LINE}\n\n`{number}` is no longer protected.{FOOTER}", parse_mode=constants.ParseMode.MARKDOWN)

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await track_user(update): return
    user_id = update.effective_user.id
    coins = await database.get_coins(user_id)
    msg = (
        f"{HEADER}"
        f"💰 *WALLET BALANCE*\n"
        f"{SUB_LINE}\n\n"
        f"🆔 User : `{user_id}`\n"
        f"💰 Coins: `{coins}` {COIN_ICON}\n"
        f"{FOOTER}"
    )
    await update.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)

@admin_only
async def give_coins_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            f"{HEADER}{ERROR_ICON} *USAGE*\n{SUB_LINE}\n\n`/give <user_id> <coins>`{FOOTER}",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return
    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text(
            f"{HEADER}{ERROR_ICON} *INVALID INPUT*\n{SUB_LINE}\n\nUser ID and coins must be numeric.{FOOTER}",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return
    if amount == 0:
        await update.message.reply_text(
            f"{HEADER}{ERROR_ICON} *ZERO COINS?*\n{SUB_LINE}\n\nAmount must be non-zero.{FOOTER}",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return

    if amount > 0:
        await database.add_coin(target_id, amount)
    else:
        await database.deduct_coin(target_id, -amount)

    new_bal = await database.get_coins(target_id)
    msg = (
        f"{HEADER}{SUCCESS_ICON} *COINS UPDATED*\n"
        f"{SUB_LINE}\n\n"
        f"🆔 User : `{target_id}`\n"
        f"➕ Change : `{amount}` {COIN_ICON}\n"
        f"💰 New Balance : `{new_bal}` {COIN_ICON}\n"
        f"{FOOTER}"
    )
    await update.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)

@admin_only
async def generate_code_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text(
            f"{HEADER}{ERROR_ICON} *USAGE*\n{SUB_LINE}\n\n`/gencode <code> <coins> <max_uses>`{FOOTER}",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return
    code = context.args[0].upper()
    try:
        coins = int(context.args[1])
        max_uses = int(context.args[2])
    except ValueError:
        await update.message.reply_text(
            f"{HEADER}{ERROR_ICON} *INVALID INPUT*\n{SUB_LINE}\n\nCoins and max_uses must be numeric.{FOOTER}",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return
    if coins <= 0 or max_uses <= 0:
        await update.message.reply_text(
            f"{HEADER}{ERROR_ICON} *INVALID VALUES*\n{SUB_LINE}\n\nCoins and max_uses must be > 0.{FOOTER}",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return

    await database.create_redeem_code(code, coins, max_uses, update.effective_user.id)

    msg = (
        f"{HEADER}{SUCCESS_ICON} *REDEEM CODE CREATED*\n"
        f"{SUB_LINE}\n\n"
        f"🎫 Code  : `{code}`\n"
        f"💰 Coins : `{coins}`\n"
        f"👥 Uses  : `{max_uses}`\n\n"
        f"Share this code with users. They can use:\n"
        f"`/redeem {code}`\n"
        f"{FOOTER}"
    )
    await update.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)

async def redeem_code_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await track_user(update): return
    if not context.args:
        await update.message.reply_text(
            f"{HEADER}{ERROR_ICON} *NO CODE*\n{SUB_LINE}\n\nUse `/redeem <code>`.{FOOTER}",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return

    code = context.args[0].upper()
    row = await database.get_redeem_code(code)
    if not row:
        await update.message.reply_text(
            f"{HEADER}{ERROR_ICON} *INVALID CODE*\n{SUB_LINE}\n\nThis redeem code does not exist.{FOOTER}",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return

    _, coins, max_uses, used_count, created_by, created_at = row
    if used_count >= max_uses:
        await update.message.reply_text(
            f"{HEADER}{ERROR_ICON} *CODE EXPIRED*\n{SUB_LINE}\n\nThis code has reached its max uses.{FOOTER}",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return

    user_id = update.effective_user.id
    
    if await database.has_user_redeemed(code, user_id):
        await update.message.reply_text(
            f"{HEADER}{ERROR_ICON} *ALREADY REDEEMED*\n{SUB_LINE}\n\nYou have already used this code.{FOOTER}",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return

    await database.add_coin(user_id, coins)
    await database.increment_redeem_use(code)
    await database.mark_code_redeemed(code, user_id)

    new_bal = await database.get_coins(user_id)
    msg = (
        f"{HEADER}{SUCCESS_ICON} *REDEEM SUCCESSFUL*\n"
        f"{SUB_LINE}\n\n"
        f"🎫 Code  : `{code}`\n"
        f"💰 Earned: `{coins}` {COIN_ICON}\n"
        f"💰 Balance: `{new_bal}` {COIN_ICON}\n"
        f"{FOOTER}"
    )
    await update.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)

@admin_only
async def delete_code_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            f"{HEADER}{ERROR_ICON} *USAGE*\n{SUB_LINE}\n\n`/delcode <code>`{FOOTER}",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return
    code = context.args[0].upper()
    await database.delete_redeem_code(code)
    await update.message.reply_text(
        f"{HEADER}{SUCCESS_ICON} *CODE DELETED*\n{SUB_LINE}\n\n🎫 Code `{code}` has been removed.{FOOTER}",
        parse_mode=constants.ParseMode.MARKDOWN,
    )

async def leaderboard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await track_user(update): return
    users = await database.get_top_users_by_coins(10)
    msg = f"{HEADER}🏆 *COIN LEADERBOARD* 🏆\n{SUB_LINE}\n\n"
    if not users:
        msg += "No users found.\n"
    else:
        for idx, (uid, first_name, username, coins) in enumerate(users, 1):
            name = first_name or username or str(uid)
            msg += f"*{idx}.* {name} - `{coins}` {COIN_ICON}\n"
    msg += FOOTER
    await update.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)

@admin_only
async def reset_all_coins_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await database.reset_all_coins()
    await update.message.reply_text(
        f"{HEADER}{SUCCESS_ICON} *COINS RESET*\n{SUB_LINE}\n\nAll user coins have been reset to 0.{FOOTER}",
        parse_mode=constants.ParseMode.MARKDOWN,
    )

@admin_only
async def whitelist_link_user_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            f"{HEADER}{ERROR_ICON} *USAGE*\n{SUB_LINE}\n\n`/wladd <user_id>`{FOOTER}",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            f"{HEADER}{ERROR_ICON} *INVALID USER ID*\n{SUB_LINE}\n\nUser ID must be numeric.{FOOTER}",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return

    await database.add_link_whitelist(target_id, update.effective_user.id)
    await update.message.reply_text(
        f"{HEADER}{SUCCESS_ICON} *LINK WHITELISTED*\n{SUB_LINE}\n\n🆔 `{target_id}` can now send links in groups.{FOOTER}",
        parse_mode=constants.ParseMode.MARKDOWN,
    )

@admin_only
async def unwhitelist_link_user_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            f"{HEADER}{ERROR_ICON} *USAGE*\n{SUB_LINE}\n\n`/wlremove <user_id>`{FOOTER}",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            f"{HEADER}{ERROR_ICON} *INVALID USER ID*\n{SUB_LINE}\n\nUser ID must be numeric.{FOOTER}",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return

    removed = await database.remove_link_whitelist(target_id)
    if removed:
        msg = f"{HEADER}{SUCCESS_ICON} *REMOVED FROM WHITELIST*\n{SUB_LINE}\n\n🆔 `{target_id}` can no longer send links.{FOOTER}"
    else:
        msg = f"{HEADER}{ERROR_ICON} *NOT IN WHITELIST*\n{SUB_LINE}\n\n🆔 `{target_id}` was not whitelisted.{FOOTER}"
    await update.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)

@admin_only
async def list_link_whitelist_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = await database.get_link_whitelist()
    if not rows:
        await update.message.reply_text(
            f"{HEADER}📭 *WHITELIST EMPTY*\n{SUB_LINE}\n\nNo user is allowed to send links yet.{FOOTER}",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return

    msg = (
        f"{HEADER}"
        f"✅ *LINK WHITELIST*\n"
        f"{SUB_LINE}\n\n"
    )
    for uid, added_by, added_at in rows[:30]:
        msg += f"• User: `{uid}` | By: `{added_by}`\n"
    msg += f"\n{FOOTER}"
    await update.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.new_chat_members:
        return

    if update.effective_chat.type not in ("group", "supergroup"):
        return

    for member in update.message.new_chat_members:
        if member.is_bot:
            continue

        await database.add_or_update_user(
            member.id,
            member.username,
            member.first_name,
            member.last_name,
        )

        user_name = member.first_name or "Friend"
        welcome_msg = (
            f"{HEADER}"
            f"👋 *Welcome {user_name}!*\n"
            f"{SUB_LINE}\n\n"
            f"Glad to have you here in our group.\n"
            f"Enjoy *{BOT_TITLE}* 🎮\n"
            f"{FOOTER}"
        )
        try:
            if os.path.isfile(WELCOME_PHOTO):
                with open(WELCOME_PHOTO, "rb") as photo:
                    await update.message.reply_photo(
                        photo=photo,
                        caption=welcome_msg,
                        parse_mode=constants.ParseMode.MARKDOWN,
                    )
            else:
                await update.message.reply_text(
                    welcome_msg,
                    parse_mode=constants.ParseMode.MARKDOWN,
                )
        except Exception as e:
            logging.error(f"Failed to send welcome message: {e}")

async def group_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Group: number lookup first, then link guard."""
    if not update.message or not update.effective_chat or not update.effective_user:
        return

    if update.effective_chat.type not in ("group", "supergroup"):
        return

    if update.effective_user.is_bot:
        return

    if update.message.new_chat_members:
        return

    bot_username = context.bot.username if context.bot else None
    mobile = extract_mobile_from_message(update.message, bot_username)
    if mobile:
        logging.info(f"Mobile lookup in group {update.effective_chat.id}: {mobile}")
        await run_mobile_lookup(update, context, mobile)
        raise ApplicationHandlerStop

    if not message_contains_link(update.message):
        return

    user_id = update.effective_user.id
    if can_send_links(user_id):
        return
    if await database.is_link_whitelisted(user_id):
        return

    deleted = False
    try:
        await update.message.delete()
        deleted = True
    except Exception as e:
        logging.error(f"Failed to delete link message: {e}")

    user = update.effective_user
    name = user.first_name or "User"
    warn_msg = (
        f"⚠️ <b>Warning</b> <a href=\"tg://user?id={user.id}\">{name}</a>\n"
        f"Links are not allowed in this group.\n"
        f"Only bot admin or whitelisted users can send links."
    )
    if not deleted:
        warn_msg += "\n\n<i>(Bot could not delete — give bot admin + Delete Messages permission)</i>"

    try:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=warn_msg,
            parse_mode=constants.ParseMode.HTML,
            reply_to_message_id=update.message.message_id,
        )
    except Exception as e:
        logging.error(f"Failed to send link warning: {e}")

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Help button is available to all users
    if query.data == "help_btn":
        help_text = (
            f"{HEADER}"
            f"📖 *COMMAND MANUAL*\n"
            f"{SUB_LINE}\n\n"
            f"🔹 *OSINT TOOLS*\n"
            f"  📱 Send 10-digit number directly ({COIN_ICON})\n"
            f"  🪪 `/aadhaar <aadhaar_number>` — Aadhaar holder info\n"
            f"  👪 `/family <aadhaar_number>` — Family members list\n"
            f"  📮 `/pincode <pincode>`\n"
            f"  🏦 `/ifsc <ifsc_code>`\n"
            f"  ✈️ `/telegram <username>`\n"
            f"  📸 `/instagram <username>`\n"
            f"  🚗 `/vehicle <plate_number>`\n\n"
            f"🔹 *GAMING TOOLS*\n"
            f"  🔫 `/ffinfo <uid>` — Player info ({COIN_ICON})\n"
            f"  🎯 `/visits <uid> <region>` — Visits ({COIN_ICON})\n"
            f"  ❤️ `/like <uid> <region>` — Send like 🔒 _Admin only_\n"
            f"  💣 `/bomb <number>` — SMS bomber ({COIN_ICON})\n\n"
            f"🔹 *ECONOMY*\n"
            f"  🔗 `/earn` — Generate ad link\n"
            f"  🎁 `/claim` — Claim your coins\n"
            f"  💎 `/balance` — Check coins\n"
            f"  🏆 `/leaderboard` — View top users\n"
            f"  🎫 `/redeem <code>` — Use redeem code\n\n"
            f"🔹 *ADMIN ECONOMY*\n"
            f"  `/give <user_id> <coins>` — add coins\n"
            f"  `/gencode <code> <coins> <max_uses>` — create redeem code\n"
            f"  `/delcode <code>` — delete redeem code\n"
            f"  `/resetallcoins` — reset all user coins\n\n"
            f"🔹 *GROUP LINK GUARD* (Admin)\n"
            f"  `/wladd <user_id>` — allow links\n"
            f"  `/wlremove <user_id>` — remove allow\n"
            f"  `/wllist` — view whitelist\n\n"
            f"🔹 *LIKE REGIONS:* `IND` `NX` `AG`\n\n"
            f"💡 _Like command is admin-only._\n"
            f"{FOOTER}"
        )
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_start")]]
        await query.edit_message_text(help_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=constants.ParseMode.MARKDOWN)
        return

    if query.data == "back_to_start":
        user_name = query.from_user.first_name
        coins = await database.get_coins(query.from_user.id)
        
        welcome_msg = (
            f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
            f"      🎮 *{BOT_TITLE}* 🎮\n"
            f"    ⚔️ *MULTI-TOOL BOT* ⚔️\n"
            f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n\n"
            f"Hey *{user_name}*! Welcome to the\n"
            f"ultimate gaming toolkit. 🕹️\n\n"
            f"💰 *Your Balance:* `{coins}` {COIN_ICON}\n\n"
            f"▬▬▬ 🛠️ *ARSENAL* 🛠️ ▬▬▬\n\n"
            f"📱 Send 10-digit number directly ({COIN_ICON})\n"
            f"🪪 `/aadhaar` ➜ _Aadhaar card info_\n"
            f"👪 `/family` ➜ _Family members lookup_\n"
            f"📮 `/pincode` ➜ _Pincode lookup_\n"
            f"🏦 `/ifsc` ➜ _IFSC bank lookup_\n"
            f"✈️ `/telegram` ➜ _Telegram OSINT_\n"
            f"📸 `/instagram` ➜ _Instagram OSINT_\n"
            f"🚗 `/vehicle` ➜ _Vehicle plate lookup_\n"
            f"🎯 `/visits` ➜ _FF profile visits_ ({COIN_ICON})\n"
            f"🔫 `/ffinfo` ➜ _Free Fire player info_ ({COIN_ICON})\n"
            f"❤️ `/like` ➜ _Send like_ 🔒 _Admin only_\n"
            f"💣 `/bomb` ➜ _SMS bomber_ ({COIN_ICON})\n\n"
            f"▬▬▬ 💰 *ECONOMY* 💰 ▬▬▬\n\n"
            f"🔗 `/earn` ➜ _Watch ad to earn coins_\n"
            f"🎁 `/claim` ➜ _Claim your earned coins_\n\n"
            f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
            f"💡 Use `/help` for detailed usage.\n"
            f"{FOOTER}"
        )
        keyboard = [
            [InlineKeyboardButton("🔗 Support Channel", url="https://t.me/maniuf76")],
            [InlineKeyboardButton("📖 Help & Commands", callback_data="help_btn")]
        ]
        if query.from_user.id in ADMIN_IDS:
            keyboard.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")])
        await query.edit_message_text(welcome_msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=constants.ParseMode.MARKDOWN)
        return

    # Everything below requires admin
    if query.from_user.id not in ADMIN_IDS:
        await query.edit_message_text(f"{HEADER}🔒 *UNAUTHORIZED*\n{SUB_LINE}\n\nAdmin access required.{FOOTER}", parse_mode=constants.ParseMode.MARKDOWN)
        return

    if query.data == "admin_panel":
        keyboard = [
            [InlineKeyboardButton("📊 Dashboard", callback_data="stats_btn"), InlineKeyboardButton("📣 Broadcast", callback_data="broadcast_btn")],
            [InlineKeyboardButton("❤️ Reset Likes", callback_data="reset_likes_btn")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_start"), InlineKeyboardButton("✖️ Close", callback_data="close_admin")]
        ]
        admin_msg = (
            f"{HEADER}"
            f"⚙️ *ADMIN CONTROL PANEL*\n"
            f"{SUB_LINE}\n\n"
            f"Select an option below:\n"
            f"{FOOTER}"
        )
        await query.edit_message_text(admin_msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=constants.ParseMode.MARKDOWN)

    elif query.data == "stats_btn":
        stats = await database.get_stats()
        msg = (
            f"{HEADER}"
            f"📊 *DASHBOARD*\n"
            f"{SUB_LINE}\n\n"
            f"👥 Total Users  : `{stats['total_users']}`\n"
            f"✨ New Today    : `{stats['new_users_today']}`\n"
            f"🔥 Active Today : `{stats['active_today']}`\n\n"
            f"▬▬▬ 🏆 *TOP COMMANDS* ▬▬▬\n\n"
        )
        for cmd, count in stats['top_commands']:
            msg += f"  ▸ `{cmd}` — {count} uses\n"
        
        msg += f"\n▬▬▬ ❤️ *LIKE STATS* ▬▬▬\n\n"
        for vtype, count in stats['bot_stats']:
            msg += f"  ▸ `{vtype}` — {count}\n"
            
        msg += f"\n{FOOTER}"
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=constants.ParseMode.MARKDOWN)

    elif query.data == "broadcast_btn":
        bc_msg = (
            f"{HEADER}"
            f"📣 *BROADCAST MODE*\n"
            f"{SUB_LINE}\n\n"
            f"Send a message to all users:\n\n"
            f"`/broadcast <your message>`\n"
            f"{FOOTER}"
        )
        await query.edit_message_text(
            bc_msg,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]),
            parse_mode=constants.ParseMode.MARKDOWN
        )
    
    elif query.data == "reset_likes_btn":
        await database.reset_likes_cooldown()
        reset_msg = (
            f"{HEADER}"
            f"{SUCCESS_ICON} *COOLDOWNS RESET*\n"
            f"{SUB_LINE}\n\n"
            f"All like cooldowns cleared.\n"
            f"Users can like again immediately.\n"
            f"{FOOTER}"
        )
        await query.edit_message_text(
            reset_msg,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]),
            parse_mode=constants.ParseMode.MARKDOWN
        )
    
    elif query.data == "close_admin":
        await query.delete_message()

async def post_init(application: ApplicationBuilder):
    await database.init_db()
    print(f"Database initialized with Ad Rewards & Coin System.")

# Main Setup
def main():
    print(f"Starting {BOT_TITLE} with Coin Economy System...")
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    
    # Base Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    
    # Ad Reward Economy
    app.add_handler(CommandHandler("earn", earn_command))
    app.add_handler(CommandHandler("claim", claim_command))
    app.add_handler(CommandHandler("balance", balance_command))
    
    # OSINT Handlers
    app.add_handler(CommandHandler("family", family_command))
    app.add_handler(CommandHandler("aadhaar", aadhaar_command))
    app.add_handler(CommandHandler("aadhar", aadhaar_command))
    app.add_handler(CommandHandler("pincode", pincode_command))
    app.add_handler(CommandHandler("ifsc", ifsc_command))
    app.add_handler(CommandHandler("telegram", telegram_osint_command))
    app.add_handler(CommandHandler("instagram", instagram_command))
    app.add_handler(CommandHandler("vehicle", vehicle_command))
    app.add_handler(CommandHandler("ffinfo", ffinfo_command))
    app.add_handler(CommandHandler("visits", visits_command))
    app.add_handler(CommandHandler("bomb", bomber_command))
    
    # Like Command (admin only)
    app.add_handler(CommandHandler("like", like_command))
    
    # Admin Commands
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("banuser", ban_user_cmd))
    app.add_handler(CommandHandler("unbanuser", unban_user_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("userinfo", user_info_cmd))
    app.add_handler(CommandHandler("resetlikes", reset_likes_cmd))
    app.add_handler(CommandHandler("setlimit", set_limit_cmd))
    app.add_handler(CommandHandler("protect", protect_number_cmd))
    app.add_handler(CommandHandler("unprotect", unprotect_number_cmd))
    app.add_handler(CommandHandler("give", give_coins_cmd))
    app.add_handler(CommandHandler("gencode", generate_code_cmd))
    app.add_handler(CommandHandler("redeem", redeem_code_cmd))
    app.add_handler(CommandHandler("delcode", delete_code_cmd))
    app.add_handler(CommandHandler("leaderboard", leaderboard_cmd))
    app.add_handler(CommandHandler("resetallcoins", reset_all_coins_cmd))
    app.add_handler(CommandHandler("wladd", whitelist_link_user_cmd))
    app.add_handler(CommandHandler("wlremove", unwhitelist_link_user_cmd))
    app.add_handler(CommandHandler("wllist", list_link_whitelist_cmd))
    
    # Callback Handlers
    app.add_handler(CallbackQueryHandler(admin_callback_handler))

    # Group Welcome
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & filters.StatusUpdate.NEW_CHAT_MEMBERS,
            welcome_new_member,
        )
    )

    # Group: mobile lookup + link guard
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & ~filters.COMMAND
            & ~filters.StatusUpdate.NEW_CHAT_MEMBERS
            & (filters.TEXT | filters.CONTACT | filters.CAPTION),
            group_message_handler,
        )
    )

    # Private chat: direct number lookup
    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND,
            mobile_lookup,
        )
    )
    
    print("Polling...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
