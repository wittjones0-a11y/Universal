"""Configuration module for the Universal Bot."""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Bot Token
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "your_token_here")

# SQLite path (use DATABASE_PATH — Railway sets DATABASE_URL for Postgres addons)
DATABASE_PATH = os.getenv(
    "DATABASE_PATH",
    str(BASE_DIR / "data" / "bot_data.db"),
)

# Moderation Settings
MODERATION_CONFIG = {
    "spam_threshold": 5,  # messages per 5 seconds
    "spam_cooldown": 5,
    "warn_limit": 3,  # warns before auto-mute
    "mute_duration": 300,  # seconds
    "log_channel": None,  # Will be set per guild
}

# Profanity filter
BANNED_WORDS = [
    # Add banned words here
]

# Auto-moderation rules
AUTO_MODERATION_ENABLED = True
AUTO_MUTE_ENABLED = True
AUTO_BAN_ENABLED = False

# Verification
VERIFICATION_TIMEOUT = 300  # seconds
VERIFICATION_REQUIRED = True

# Role IDs for Verification System
UNVERIFIED_ROLE_ID = 1454892709939773554
VERIFIED_ROLE_ID = 1371012886884782222

# Logging
LOG_LEVEL = "INFO"
LOG_TO_FILE = True
LOG_FILE = "data/bot.log"
