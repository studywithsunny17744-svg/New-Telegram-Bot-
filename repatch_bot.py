import os
import re

with open("bot.py", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Add API Base
if "EXPLOITS_API_BASE" not in text:
    text = text.replace('BASE_URL_BOMBER = "https://bomber-api-psi.vercel.app/send"',
                        'BASE_URL_BOMBER = "https://bomber-api-psi.vercel.app/send"\nEXPLOITS_API_BASE = "https://exploitsindia.site/api"')

# 2. Update the mobile lookup url
text = re.sub(
    r'url\s*=\s*f"\{BASE_URL_COSMO\}\?key=\{KEY_COSMO\}&type=mobile&term=\{mobile\}"',
    r'url = f"{EXPLOITS_API_BASE}/number.php?exploits={mobile}"',
    text
)

# 3. Replace the OSINT wrappers entirely
wrappers_pattern = r"# --- OSINT Wrappers ---.*?def format_ffinfo"
new_wrappers = """# --- OSINT Wrappers ---
async def handle_exploits_command(update, context, endpoint_name, search_emoji="🔍", title="Search", param_name="term"):
    if not await track_user(update): return
    await database.log_activity(update.effective_user.id, endpoint_name)
    
    if not context.args:
        usage_msg = (
            f"{HEADER}"
            f"{ERROR_ICON} *INVALID SYNTAX*\\n"
            f"{SUB_LINE}\\n\\n"
            f"📝 *Format:* `/{endpoint_name} <{param_name}>`\\n"
            f"{FOOTER}"
        )
        await update.message.reply_text(usage_msg, parse_mode="Markdown")
        return

    term = " ".join(context.args)
    loading = (
        f"{HEADER}"
        f"{LOADING_ICON} *SCANNING...*\\n"
        f"{SUB_LINE}\\n\\n"
        f"{search_emoji} {title}\\n"
        f"🎯 Target : `{term}`\\n\\n"
        f"_Fetching data..._\\n"
        f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰"
    )
    progress_msg = await update.message.reply_text(loading, parse_mode="Markdown")
    await update.message.chat.send_action("typing")

    url = f"{EXPLOITS_API_BASE}/{endpoint_name}.php?exploits={term}"
    response = await fetch_api_data(url)
    
    result_text = format_response(response, term, title)
    await progress_msg.edit_text(result_text, parse_mode="Markdown")

async def family_command(update, context):
    await handle_exploits_command(update, context, "family", "👪", "Family Lookup", "query")

async def aadhar_command(update, context):
    await handle_exploits_command(update, context, "aadhar", "🆔", "Aadhaar Lookup", "aadhaar_no")

async def pincode_command(update, context):
    await handle_exploits_command(update, context, "pincode", "📍", "Pincode Lookup", "pincode")

async def ifsc_command(update, context):
    await handle_exploits_command(update, context, "ifsc", "🏦", "IFSC Lookup", "ifsc_code")

async def telegram_command(update, context):
    await handle_exploits_command(update, context, "telegram", "✈️", "Telegram Lookup", "username_or_id")

async def instagram_command(update, context):
    await handle_exploits_command(update, context, "instagram", "📸", "Instagram Lookup", "username")

async def vehicle_command(update, context):
    await handle_exploits_command(update, context, "vehicle", "🚗", "Vehicle Lookup", "plate_number")

async def email_command(update, context):
    await handle_osint_command(update, context, BASE_URL_MOUKTIK, KEY_MOUKTIK, "email", "email", "📧", "Email Lookup")

async def pan_command(update, context):
    await handle_osint_command(update, context, BASE_URL_MOUKTIK, KEY_MOUKTIK, "pan", "pan_number", "💳", "PAN Lookup")

def format_ffinfo"""

text = re.sub(wrappers_pattern, new_wrappers, text, flags=re.DOTALL)

# 4. Update the handlers
handlers_pattern = r"# OSINT Handlers.*?app\.add_handler\(CommandHandler\(\"ffinfo\""
new_handlers = """# OSINT Handlers
    app.add_handler(CommandHandler("family", family_command))
    app.add_handler(CommandHandler("aadhar", aadhar_command))
    app.add_handler(CommandHandler("pincode", pincode_command))
    app.add_handler(CommandHandler("ifsc", ifsc_command))
    app.add_handler(CommandHandler("telegram", telegram_command))
    app.add_handler(CommandHandler("instagram", instagram_command))
    app.add_handler(CommandHandler("vehicle", vehicle_command))
    app.add_handler(CommandHandler("email", email_command))
    app.add_handler(CommandHandler("pan", pan_command))
    app.add_handler(CommandHandler("ffinfo\""""
text = re.sub(handlers_pattern, new_handlers, text, flags=re.DOTALL)

with open("bot.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Bot patched successfully.")
