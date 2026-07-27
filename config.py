import os
from pathlib import Path

# The default configuration values (used to auto-generate the .env file)
DEFAULT_CONFIG = {
    "DISCORD_TOKEN": "YOUR_BOT_TOKEN_HERE",
    "PREFIX": "!",
    "OWNER_ID": "YOUR_DISCORD_USER_ID_HERE",
    "MOD_ROLES": "MOD_ROLE_ID_1,MOD_ROLE_ID_2",
    "BOT_STATUS": "In Progress...",
    "EMBED_COLOR": "0x3498db",
    "BAD_WORDS": [
        "badword1",
        "badword2",
        "badword3"
    ]
}

# Auto-generate .env if it doesn't exist
env_path = Path(".env")
if not env_path.exists():
    with open(env_path, "w", encoding="utf-8") as f:
        f.write("# Discord Bot Configuration\n")
        f.write("# Update these values to configure your bot\n\n")
        for key, value in DEFAULT_CONFIG.items():
            if isinstance(value, list):
                value = ",".join(value)
            f.write(f"{key}={value}\n")

# Load variables from .env natively
with open(env_path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#"):
            if "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip("'\"")

# ---------------------------------------------------------
# Exported Configuration Variables
# ---------------------------------------------------------

# Bot token (keep this private!)
TOKEN = os.environ.get("DISCORD_TOKEN", DEFAULT_CONFIG["DISCORD_TOKEN"])

# Command prefix
PREFIX = os.environ.get("PREFIX", DEFAULT_CONFIG["PREFIX"])

# Bot owner ID (this is your Discord user ID)
try:
    OWNER_ID = int(os.environ.get("OWNER_ID", DEFAULT_CONFIG["OWNER_ID"]))
except ValueError:
    OWNER_ID = 0  # Fallback if it's still the placeholder

# List of moderator role IDs
mod_roles_str = os.environ.get("MOD_ROLES", DEFAULT_CONFIG["MOD_ROLES"])
MOD_ROLES = []
for r in mod_roles_str.split(","):
    r = r.strip()
    if r:
        try:
            MOD_ROLES.append(int(r))
        except ValueError:
            pass # Skip placeholders

# Bot status
BOT_STATUS = os.environ.get("BOT_STATUS", DEFAULT_CONFIG["BOT_STATUS"])

# Color for embeds (in hex)
embed_color_str = os.environ.get("EMBED_COLOR", DEFAULT_CONFIG["EMBED_COLOR"])
EMBED_COLOR = int(embed_color_str, 16) if embed_color_str.startswith("0x") else int(embed_color_str)

# AutoMod Bad Words List
bad_words_str = os.environ.get("BAD_WORDS", ",".join(DEFAULT_CONFIG["BAD_WORDS"]))
BAD_WORDS = [w.strip() for w in bad_words_str.split(",") if w.strip()]
