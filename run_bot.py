#!/usr/bin/env python3
"""Run the Discord text feed bot with test configuration."""

import os
from pathlib import Path
import yaml

# Load DISCORD_TOKEN and DISCORD_CHANNEL_ID from .env file before importing anything else
dotenv_path = Path(".env")
if dotenv_path.exists():
    env_content = dotenv_path.read_text()
    for line in env_content.strip().split("\n"):
        if "=" in line and not line.startswith("#"):
            key, _, value = line.partition("=")
            os.environ[key.strip()] = value.strip()

# Load channel ID from config file
config_path = Path("config.test.yaml")
if config_path.exists():
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
        if "discord" in config and "channel_id" in config["discord"]:
            os.environ["DISCORD_CHANNEL_ID"] = str(config["discord"]["channel_id"])

# Now import the bot module
from src.bot import run_bot

if __name__ == "__main__":
    print("Starting Discord Text Feed Bot...")
    print(f"Using config: config.test.yaml")
    print(f"Discord token loaded from .env")
    run_bot(config_path="config.test.yaml")
