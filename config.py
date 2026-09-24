from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Config:
    bot_token: str
    db_path: str = "engineering_bot.db"

def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is not set. Copy .env.example to .env and add the token.")
    return Config(bot_token=token, db_path=os.getenv("DB_PATH", "engineering_bot.db"))
