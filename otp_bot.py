from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import pyotp
import logging
import asyncio
import re  # For Base32 validation
import sqlite3

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Rate limiting delay (in seconds)
REQUEST_DELAY = 1  # 1 second delay between requests

# Base32 validation regex
BASE32_REGEX = re.compile(r'^[A-Z2-7]+=*$')

# Database connection
conn = sqlite3.connect('otp_bot.db', check_same_thread=False)
cursor = conn.cursor()

# Create table if it doesn't exist
cursor.execute('''
CREATE TABLE IF NOT EXISTS otp_secrets (
    name TEXT PRIMARY KEY,
    secret_key TEXT NOT NULL
)
''')
conn.commit()

def is_valid_base32(secret_key: str) -> bool:
    """Check if the secret_key is a valid Base32 string."""
    return bool(BASE32_REGEX.match(secret_key))

async def send_with_delay(update: Update, text: str):
    """Send a message with a delay to avoid rate limits and reply to the previous message."""
    await asyncio.sleep(REQUEST_DELAY)
    await update.message.reply_text(
        text,
        reply_to_message_id=update.message.message_id  # Reply to the user's message
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when the /start command is issued."""
    await send_with_delay(update,
        "Welcome to the Real-Time OTP Bot!\n\n"
        "Available commands:\n"
        "/start - Show this message\n"
        "/getotp <name> - Get OTP code for a service\n"
        "/addcode <name> <secret_key> - Add a new OTP code\n"
        "/deletecode <name> - Delete an OTP code\n"
        "/listcodes - List all stored OTP codes"
    )

async def getotp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /getotp command."""
    if not context.args:
        await send_with_delay(update, "Usage: /getotp <name>")
        return

    name = context.args[0].lower()
    cursor.execute('SELECT secret_key FROM otp_secrets WHERE name = ?', (name,))
    result = cursor.fetchone()

    if not result:
        await send_with_delay(update, f"Service '{name}' not found. Use /listcodes to see available services.")
        return

    # Generate the current TOTP code
    totp = pyotp.TOTP(result[0])
    otp_code = totp.now()
    await send_with_delay(update, f"Your real-time OTP code for {name} is: {otp_code}")

async def addcode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /addcode command."""
    if len(context.args) < 2:
        await send_with_delay(update, "Usage: /addcode <name> <secret_key>")
        return

    name = context.args[0].lower()
    secret_key = context.args[1].upper()  # Convert to uppercase for Base32 validation

    # Validate the secret_key
    if not is_valid_base32(secret_key):
        await send_with_delay(update, "Invalid secret_key. It must be a valid Base32 string (A-Z, 2-7, and = only).")
        return

    # Add the new OTP code to the database
    try:
        cursor.execute('INSERT INTO otp_secrets (name, secret_key) VALUES (?, ?)', (name, secret_key))
        conn.commit()
        await send_with_delay(update, f"OTP code for '{name}' added successfully.")
    except sqlite3.IntegrityError:
        await send_with_delay(update, f"Service '{name}' already exists. Use /deletecode to remove it first.")

async def deletecode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /deletecode command."""
    if not context.args:
        await send_with_delay(update, "Usage: /deletecode <name>")
        return

    name = context.args[0].lower()
    cursor.execute('DELETE FROM otp_secrets WHERE name = ?', (name,))
    conn.commit()

    if cursor.rowcount == 0:
        await send_with_delay(update, f"Service '{name}' not found. Use /listcodes to see available services.")
    else:
        await send_with_delay(update, f"OTP code for '{name}' deleted successfully.")

async def listcodes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /listcodes command."""
    cursor.execute('SELECT name FROM otp_secrets')
    results = cursor.fetchall()

    if not results:
        await send_with_delay(update, "No OTP codes stored. Use /addcode to add one.")
        return

    # List all stored OTP codes
    codes_list = "\n".join([f"- {row[0]}" for row in results])
    await send_with_delay(update, f"Stored OTP codes:\n{codes_list}")

def main() -> None:
    """Start the bot."""
    # Replace 'YOUR_TOKEN' with your bot's token
    application = Application.builder().token("7836596322:AAFAzXSGEIwejCCTpEM68p6_lMu8W163pjw").build()

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("getotp", getotp))
    application.add_handler(CommandHandler("addcode", addcode))
    application.add_handler(CommandHandler("deletecode", deletecode))
    application.add_handler(CommandHandler("listcodes", listcodes))

    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main()