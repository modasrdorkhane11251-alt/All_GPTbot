"""Small owner panel. Bind to localhost behind an HTTPS reverse proxy."""
import hashlib
import hmac
import html
import os
import time
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from .config import S
from . import db
from .plans import PLANS

app = FastAPI(title="All GPTbot Admin", docs_url=None, redoc_url=None)
COOKIE = "allgpt_admin"
SESSION_SECONDS = 8 * 60 * 60


def _secret():
    return os.getenv("ADMIN_PANEL_SECRET", "").strip()


def _password():
    return os.getenv("ADMIN_PANEL_PASSWORD", "").strip()


def _sign(value: str) -> str:
    return hmac.new(_secret().encode(), value.encode(), hashlib.sha256).hexdigest()


def _valid_cookie(value: str) -> bool:
    if not value or "." not in value or not _secret():
        return False
    ts, sig = value.split(".", 1)
    if not ts.isdigit() or time.time() - int(ts) > SESSION_SECONDS or int(ts) > time.time() + 60:
        return False
    return hmac.compare_digest(sig, _sign(ts))


def _page(title: str, body: str, code: int = 200) -> HTMLResponse:
    page = f'''<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>
<style>
body{{font-family:system-ui,sans-serif;background:#f3f5f9;color:#202638;margin:0}}
header{{background:#17233b;color:white;padding:18px 5vw;display:flex;justify-content:space-between;align-items:center}}
main{{max-width:1100px;margin:24px auto;padding:0 16px}}.card{{background:white;border-radius:12px;padding:18px;margin:14px 0;box-shadow:0 2px 12px #16223b12}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}}
input,button{{font:inherit;padding:9px;border:1px solid #cbd2df;border-radius:7px;margin:4px;max-width:100%}}
button{{background:#2359c4;color:white;border:0;cursor:pointer}}table{{width:100%;border-collapse:collapse;overflow-wrap:anywhere}}td,th{{padding:8px;border-bottom:1px solid #e5e8ef;text-align:right}}
small,.muted{{color:#697386}}a{{color:#2359c4}}.danger{{background:#b83232}}form.inline{{display:inline-block}}
</style><header><strong>MODASR · All GPTbot</strong><span><a style="color:white" href="/logout">خروج</a></span></header>
<main>{body}<p class="muted">پنل مالک — از HTTPS و رمز قوی استفاده کنید.</p></main></html>'''
    return HTMLResponse(page, status_code=code)


async def _body_form(request: Request) -> dict:
    raw = await request.body()
    return {k: v[-1] for k, v in parse_qs(raw.decode("utf-8", "replace")).items()}


def _logged(request: Request) -> bool:
    return _valid_cookie(request.cookies.get(COOKIE, ""))


@app.on_event("startup")
def startup():
    db.init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    if not _logged(request):
        return _page("ورود مدیر", '''<div class="card"><h2>ورود به پنل مدیریت</h2>
        <form method="post" action="/login"><label>رمز مدیر</label>
        <input name="password" type="password" required autocomplete="current-password"><button>ورود</button></form></div>''')
    s = db.stats()
    users = db.users(50)
    payments = db.pending()
    user_rows = "".join(
        '<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'.format(
            int(u["id"]), html.escape("@" + (u.get("username") or "-")),
            int(u.get("requests") or 0), html.escape(u.get("until") or "ندارد"),
            f'<form class="inline" method="post" action="/user/quota"><input type="hidden" name="uid" value="{int(u["id"])}"><input name="quota" type="number" min="0" max="100000" value="{int(u.get("quota") or 0)}" style="width:78px"><button>سهمیه</button></form>'
            f'<form class="inline" method="post" action="/user/grant"><input type="hidden" name="uid" value="{int(u["id"])}"><input name="days" type="number" min="1" max="3650" value="30" style="width:65px"><button>تمدید روز</button></form>'
        ) for u in users)
    if not user_rows:
        user_rows = '<tr><td colspan="5">هنوز کاربری وجود ندارد.</td></tr>'
    payment_rows = "".join(
        f'<tr><td>#{int(p["id"])}</td><td>{int(p["user_id"])}</td><td>{html.escape(p["plan"])}</td><td>{float(p["amount"]):g} {html.escape(p["currency"])}</td><td>'
        f'<form class="inline" method="post" action="/payment/approve"><input type="hidden" name="pid" value="{int(p["id"])}"><button>تأیید دستی</button></form>'
        f'<form class="inline" method="post" action="/payment/reject"><input type="hidden" name="pid" value="{int(p["id"])}"><button class="danger">رد</button></form></td></tr>'
        for p in payments)
    if not payment_rows:
        payment_rows = '<tr><td colspan="5">پرداخت در انتظار وجود ندارد.</td></tr>'
    prices = "".join(
        f'<label>{html.escape(PLANS[k]["label"])} ({k})<br><input type="number" step="0.01" min="0" name="{k}" value="{S.prices[k]}" required></label>'
        for k in PLANS)
    body = f'''
    <h2>داشبورد</h2><div class="grid">
    <div class="card"><small>کاربران</small><h2>{db.count_users()}</h2></div>
    <div class="card"><small>درخواست‌های AI</small><h2>{int(s["requests"])}</h2></div>
    <div class="card"><small>درخواست پرداخت باز</small><h2>{len(payments)}</h2></div></div>
    <div class="card"><h3>قیمت پلن‌ها</h3><p class="muted">قیمت‌ها در فایل .env ذخیره می‌شوند و بعد از راه‌اندازی مجدد باقی می‌مانند.</p>
    <form method="post" action="/prices"><div class="grid">{prices}</div><p>واحد پول: <input name="currency" value="{html.escape(S.currency)}" maxlength="8" required></p><button>ذخیره قیمت‌ها</button></form></div>
    <div class="card"><h3>پرداخت‌های دستی در انتظار</h3><p class="muted">این تأیید دستی است؛ پرداخت آنلاین خودکار تا زمان اتصال رسمی درگاه فعال نیست.</p><table><tr><th>شناسه</th><th>کاربر</th><th>پلن</th><th>مبلغ</th><th>عملیات</th></tr>{payment_rows}</table></div>
    <div class="card"><h3>کاربران (۵۰ مورد اخیر)</h3><table><tr><th>شناسه</th><th>نام</th><th>درخواست</th><th>انقضا</th><th>مدیریت</th></tr>{user_rows}</table></div>
    '''
    return _page("داشبورد مدیر", body)


@app.post("/login")
async def login(request: Request):
    form = await _body_form(request)
    password = _password()
    if not password or not _secret():
        return _page("تنظیم نشده", "<div class='card'>ADMIN_PANEL_PASSWORD و ADMIN_PANEL_SECRET را در .env تنظیم کنید.</div>", 503)
    if not hmac.compare_digest(str(form.get("password", "")), password):
        return _page("خطای ورود", "<div class='card'>رمز اشتباه است. <a href='/'>تلاش دوباره</a></div>", 401)
    ts = str(int(time.time()))
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(COOKIE, ts + "." + _sign(ts), httponly=True, secure=True,
                        samesite="strict", max_age=SESSION_SECONDS, path="/")
    return response


@app.get("/logout")
def logout():
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(COOKIE, path="/")
    return response


@app.post("/prices")
async def prices(request: Request):
    if not _logged(request): return RedirectResponse("/", status_code=303)
    form = await _body_form(request)
    try:
        values = {k: float(form[k]) for k in PLANS}
        currency = str(form["currency"]).strip().upper()
        if any(v < 0 or v > 1_000_000_000 for v in values.values()) or not currency or len(currency) > 8: raise ValueError()
    except (KeyError, ValueError):
        return _page("خطا", "<div class='card'>قیمت یا واحد پول معتبر نیست. <a href='/'>بازگشت</a></div>", 400)
    env_path = os.getenv("ENV_FILE_PATH", ".env")
    try:
        with open(env_path, encoding="utf-8") as f: existing = f.read().splitlines()
    except OSError: existing = []
    updates = {f"PRICE_{k.upper()}": str(values[k]) for k in PLANS}
    updates["CURRENCY"] = currency
    keys, seen, lines = set(updates), set(), []
    for line in existing:
        key = line.split("=", 1)[0].strip() if "=" in line else ""
        if key in keys:
            if key not in seen:
                lines.append(f"{key}={updates[key]}"); seen.add(key)
        else: lines.append(line)
    for key, val in updates.items():
        if key not in seen: lines.append(f"{key}={val}")
    tmp = env_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: f.write("\n".join(lines) + "\n")
    os.chmod(tmp, 0o600); os.replace(tmp, env_path)
    S.prices.update(values); S.currency = currency
    return RedirectResponse("/", status_code=303)


@app.post("/payment/approve")
async def approve(request: Request):
    if not _logged(request): return RedirectResponse("/", status_code=303)
    form = await _body_form(request)
    try:
        pid = int(form["pid"]); payment = db.payment(pid)
        if payment and payment["status"] == "pending": db.approve_payment(pid, next(iter(S.admins), 0))
    except (ValueError, KeyError, RuntimeError): pass
    return RedirectResponse("/", status_code=303)


@app.post("/payment/reject")
async def reject(request: Request):
    if not _logged(request): return RedirectResponse("/", status_code=303)
    form = await _body_form(request)
    try: db.review(int(form["pid"]), "rejected", "rejected from web panel")
    except (ValueError, KeyError): pass
    return RedirectResponse("/", status_code=303)


@app.post("/user/quota")
async def set_quota(request: Request):
    if not _logged(request): return RedirectResponse("/", status_code=303)
    form = await _body_form(request)
    try:
        uid, quota = int(form["uid"]), int(form["quota"])
        if uid > 0 and 0 <= quota <= 100000 and db.get_user(uid): db.set_quota(uid, quota)
    except (ValueError, KeyError): pass
    return RedirectResponse("/", status_code=303)


@app.post("/user/grant")
async def grant(request: Request):
    if not _logged(request): return RedirectResponse("/", status_code=303)
    form = await _body_form(request)
    try:
        uid, days = int(form["uid"]), int(form["days"])
        if uid > 0 and 1 <= days <= 3650 and db.get_user(uid): db.extend(uid, days)
    except (ValueError, KeyError): pass
    return RedirectResponse("/", status_code=303)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.admin_panel:app", host=os.getenv("ADMIN_PANEL_HOST", "127.0.0.1"),
                port=int(os.getenv("ADMIN_PANEL_PORT", "8091")), log_level="info")
