import time, logging
from datetime import datetime,timezone
from telegram import Update
from telegram.ext import ContextTypes
from .config import S
from . import db
from .plans import PLANS
from .providers import ask,ProviderError
from .documents import extract
log=logging.getLogger(__name__)
def admin(uid): return uid in S.admins
async def need_admin(update):
    if not admin(update.effective_user.id):
        await update.message.reply_text("Admin only."); return False
    return True
def user(update): return db.upsert(update.effective_user.id,update.effective_user.username)
async def start(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    user(update); await update.message.reply_text(f"سلام! به {S.bot_name} خوش آمدید. /plans برای پلن‌ها، /status برای وضعیت، /help برای راهنما.")
async def help_cmd(update,ctx):
    await update.message.reply_text("/start /plans /buy day|week|month|quarter /status /provider openai|gemini /model <name> /analyze\nپیام متنی یا تصویر ارسال کنید. مدیر: /admin_stats /admin_users /pending /approve ID /reject ID /grant USER DAYS /setquota USER COUNT")
async def plans(update,ctx):
    user(update); await update.message.reply_text("پلن‌ها:\n"+"\n".join(f"{k}: {v['label']} — {S.prices[k]:.2f} {S.currency}" for k,v in PLANS.items())+"\nثبت درخواست: /buy month")
async def buy(update,ctx):
    user(update)
    if not ctx.args or ctx.args[0].lower() not in PLANS:
        await update.message.reply_text("استفاده: /buy day|week|month|quarter"); return
    p=ctx.args[0].lower(); pid=db.create_payment(update.effective_user.id,p)
    await update.message.reply_text(f"درخواست #{pid} ثبت شد. مبلغ {S.prices[p]:.2f} {S.currency}.\n{S.bank}\nپس از بررسی مدیر، اشتراک فعال می‌شود.")
    for aid in S.admins:
        try: await ctx.bot.send_message(aid,f"درخواست پرداخت #{pid}، کاربر {update.effective_user.id}، پلن {p}. /pending")
        except Exception: pass
async def status(update,ctx):
    u=user(update); active=False
    try: active=bool(u["until"] and datetime.fromisoformat(u["until"])>datetime.now(timezone.utc))
    except (ValueError,TypeError): pass
    await update.message.reply_text(f"اشتراک: {'فعال تا '+u['until'] if active else 'غیرفعال'}\nسهمیه امروز: {max(0,int(u['quota'] or 0)-int(u['used'] or 0))}")
async def provider(update,ctx):
    u=user(update)
    if not ctx.args: await update.message.reply_text(f"فعلی: {u['provider']}. انتخاب: /provider openai یا /provider gemini"); return
    p=ctx.args[0].lower()
    if p not in {"openai","gemini"}: await update.message.reply_text("فقط openai یا gemini."); return
    if (p=="openai" and not S.openai_key) or (p=="gemini" and not S.gemini_key): await update.message.reply_text("این سرویس توسط مدیر پیکربندی نشده است."); return
    db.set_provider(update.effective_user.id,p); await update.message.reply_text("سرویس تغییر کرد: "+p)
async def model(update,ctx):
    user(update)
    if not ctx.args: await update.message.reply_text("استفاده: /model <name>"); return
    m=ctx.args[0]
    if len(m)>100 or not all(c.isalnum() or c in "-_./:" for c in m): await update.message.reply_text("نام مدل نامعتبر است."); return
    db.set_model(update.effective_user.id,m); await update.message.reply_text("مدل انتخاب شد.")
async def run_ai(update,ctx,prompt,image=None,mime="image/jpeg"):
    u=user(update)
    if len(prompt)>S.max_chars: await update.message.reply_text(f"پیام خیلی طولانی است؛ حداکثر {S.max_chars} کاراکتر."); return
    if not db.rate_ok(update.effective_user.id,time.time()): await update.message.reply_text("کمی صبر کنید و دوباره تلاش کنید."); return
    if not db.consume(update.effective_user.id): await update.message.reply_text("سهمیه رایگان تمام شده؛ /plans"); return
    p=u["provider"] or S.default_provider; m=u["model"] or (S.openai_model if p=="openai" else S.gemini_model)
    await update.message.reply_text("در حال پردازش…")
    try:
        answer=str(await ask(p,m,prompt,image,mime) or "پاسخی دریافت نشد.")
        db.log_usage(update.effective_user.id,p,m,len(prompt),len(answer))
        for i in range(0,len(answer),3900): await update.message.reply_text(answer[i:i+3900])
    except ProviderError as e: await update.message.reply_text(str(e))
    except Exception:
        log.exception("AI handler failure"); await update.message.reply_text("خطای داخلی رخ داد؛ بعداً تلاش کنید.")
async def text_handler(update,ctx): await run_ai(update,ctx,update.message.text or "")
async def photo_handler(update,ctx):
    f=await ctx.bot.get_file(update.message.photo[-1].file_id); raw=bytes(await f.download_as_bytearray())
    await run_ai(update,ctx,update.message.caption or "این تصویر را تحلیل کن.",raw)
async def document_handler(update,ctx):
    d=update.message.document
    if not d: return
    f=await ctx.bot.get_file(d.file_id); raw=bytes(await f.download_as_bytearray())
    try: text=extract(d.file_name,raw)
    except ValueError as e: await update.message.reply_text(str(e)); return
    ctx.user_data["last_document"]=text
    if update.message.caption: await run_ai(update,ctx,"این سند را تحلیل کن:\n"+text+"\nدرخواست: "+update.message.caption)
    else: await update.message.reply_text("متن فایل استخراج شد. سؤال خود را بفرستید یا /analyze را بزنید.")
async def analyze(update,ctx):
    text=ctx.user_data.get("last_document")
    if not text: await update.message.reply_text("ابتدا یک PDF، DOCX یا فایل متنی ارسال کنید."); return
    await run_ai(update,ctx,"خلاصه و تحلیل کن و نکات کلیدی را فهرست کن:\n"+text)
async def admin_stats(update,ctx):
    if not await need_admin(update): return
    s=db.stats(); await update.message.reply_text(f"کاربران: {db.count_users()}\nدرخواست AI: {s['requests']}\nهزینه تخمینی: {s['cost']} (هزینه واقعی در این نسخه محاسبه نمی‌شود)")
async def admin_users(update,ctx):
    if not await need_admin(update): return
    rows=db.users()
    await update.message.reply_text(("کاربران:\n"+"\n".join(f"{x['id']} @{x['username'] or '-'} | req={x['requests']} | until={x['until'] or '-'}" for x in rows))[:3900] or "خالی")
async def pending(update,ctx):
    if not await need_admin(update): return
    rows=db.pending()
    await update.message.reply_text(("پرداخت‌های در انتظار:\n"+"\n".join(f"#{x['id']} user={x['user_id']} plan={x['plan']} amount={x['amount']} {x['currency']} | /approve {x['id']}" for x in rows))[:3900] if rows else "درخواستی وجود ندارد.")
async def approve(update,ctx):
    if not await need_admin(update): return
    if not ctx.args or not ctx.args[0].isdigit(): await update.message.reply_text("استفاده: /approve <id>"); return
    p=db.payment(int(ctx.args[0]))
    if not p or p["status"]!="pending": await update.message.reply_text("درخواست وجود ندارد یا قبلاً بررسی شده."); return
    try:
        until=db.approve_payment(p["id"], update.effective_user.id)
    except (ValueError, RuntimeError):
        await update.message.reply_text("تأیید انجام نشد؛ وضعیت پرداخت را بررسی کنید."); return
    if not until:
        await update.message.reply_text("قبلاً بررسی شده."); return
    await update.message.reply_text(f"تأیید شد؛ اشتراک تا {until}")
    try: await ctx.bot.send_message(p["user_id"],f"پرداخت تأیید شد؛ پلن {PLANS[p['plan']]['label']} فعال شد.")
    except Exception: pass
async def reject(update,ctx):
    if not await need_admin(update): return
    if not ctx.args or not ctx.args[0].isdigit(): await update.message.reply_text("استفاده: /reject <id> [reason]"); return
    pid=int(ctx.args[0]); p=db.payment(pid); reason=" ".join(ctx.args[1:])[:250] or "rejected"
    if not p or p["status"]!="pending" or not db.review(pid,"rejected",reason): await update.message.reply_text("درخواست وجود ندارد یا قبلاً بررسی شده."); return
    await update.message.reply_text("رد شد.")
    try: await ctx.bot.send_message(p["user_id"],"درخواست پرداخت رد شد: "+reason)
    except Exception: pass
async def grant(update,ctx):
    if not await need_admin(update): return
    if len(ctx.args)!=2 or not all(x.isdigit() for x in ctx.args): await update.message.reply_text("استفاده: /grant <user_id> <days>"); return
    uid,days=map(int,ctx.args)
    if days<1 or days>3650: await update.message.reply_text("روز باید بین 1 و 3650 باشد."); return
    db.upsert(uid); await update.message.reply_text("اشتراک تا "+str(db.extend(uid,days)))
async def setquota(update,ctx):
    if not await need_admin(update): return
    if len(ctx.args)!=2 or not all(x.isdigit() for x in ctx.args): await update.message.reply_text("استفاده: /setquota <user_id> <count>"); return
    uid,q=map(int,ctx.args); db.upsert(uid); db.set_quota(uid,min(q,100000)); await update.message.reply_text("سهمیه تنظیم شد.")
