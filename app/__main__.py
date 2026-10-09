import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from .config import S
from .db import init_db
from .handlers import *
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
def main():
    if not S.token:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN in .env")
    init_db()
    app = Application.builder().token(S.token).build()
    for name, fn in [
        ("start", start), ("help", help_cmd), ("plans", plans), ("buy", buy),
        ("status", status), ("provider", provider), ("model", model), ("analyze", analyze),
        ("admin_stats", admin_stats), ("admin_users", admin_users), ("pending", pending),
        ("approve", approve), ("reject", reject), ("grant", grant), ("setquota", setquota)
    ]:
        app.add_handler(CommandHandler(name, fn))
    app.add_handler(MessageHandler(filters.Document.ALL, document_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.run_polling(allowed_updates=["message"])
if __name__ == "__main__":
    main()
