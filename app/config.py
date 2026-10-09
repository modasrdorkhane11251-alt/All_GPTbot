import os
from dotenv import load_dotenv
load_dotenv()
def num(k, d):
    try: return int(os.getenv(k, d))
    except (ValueError, TypeError): return int(d)
def price(k, d):
    try: return float(os.getenv(k, d))
    except (ValueError, TypeError): return float(d)
class Settings:
    token=os.getenv("TELEGRAM_BOT_TOKEN","").strip()
    admins={int(x.strip()) for x in os.getenv("ADMIN_IDS","").split(",") if x.strip().isdigit()}
    bot_name=os.getenv("BOT_NAME","AI Assistant")
    mode=os.getenv("DEPLOYMENT_MODE","self_hosted")
    db_path=os.getenv("DATABASE_PATH","./data/bot.sqlite3")
    max_chars=num("MAX_MESSAGE_CHARS",12000)
    free_quota=num("FREE_DAILY_QUOTA",5)
    rate_seconds=num("RATE_LIMIT_SECONDS",2)
    default_provider=os.getenv("DEFAULT_PROVIDER","openai").lower()
    openai_key=os.getenv("OPENAI_API_KEY","").strip()
    openai_url=os.getenv("OPENAI_BASE_URL","https://api.openai.com/v1").rstrip("/")
    openai_model=os.getenv("OPENAI_MODEL","gpt-4o-mini")
    gemini_key=os.getenv("GEMINI_API_KEY","").strip()
    gemini_model=os.getenv("GEMINI_MODEL","gemini-2.0-flash")
    timeout=num("AI_TIMEOUT_SECONDS",60)
    bank=os.getenv("BANK_TRANSFER_INSTRUCTIONS","Contact administrator for payment instructions.")
    currency=os.getenv("CURRENCY","EUR")
    prices={"day":price("PRICE_DAY",2),"week":price("PRICE_WEEK",5),"month":price("PRICE_MONTH",12),"quarter":price("PRICE_QUARTER",30)}
    webhook_secret=os.getenv("PAYMENT_WEBHOOK_SECRET","").strip()
    webhook_host=os.getenv("WEBHOOK_HOST","0.0.0.0")
    webhook_port=num("WEBHOOK_PORT",8080)
S=Settings()
