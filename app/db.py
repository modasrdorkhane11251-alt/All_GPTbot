import os, sqlite3, threading
from datetime import datetime, timezone, timedelta
from .config import S
lock=threading.RLock()
def now(): return datetime.now(timezone.utc).isoformat()
def conn():
    folder=os.path.dirname(S.db_path)
    if folder: os.makedirs(folder,exist_ok=True)
    c=sqlite3.connect(S.db_path,timeout=20); c.row_factory=sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON"); c.execute("PRAGMA journal_mode=WAL")
    return c
def init_db():
    with lock, conn() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT, provider TEXT, model TEXT, until TEXT, quota INTEGER DEFAULT 0, quota_day TEXT, used INTEGER DEFAULT 0, requests INTEGER DEFAULT 0, last_req REAL DEFAULT 0, created TEXT);
        CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, plan TEXT, amount REAL, currency TEXT, status TEXT DEFAULT 'pending', created TEXT, reviewed TEXT, note TEXT);
        CREATE TABLE IF NOT EXISTS usage(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,provider TEXT,model TEXT,input_chars INTEGER,output_chars INTEGER,cost REAL DEFAULT 0,created TEXT);
        CREATE TABLE IF NOT EXISTS events(event_id TEXT PRIMARY KEY,created TEXT);
        ''')
def get_user(uid):
    with conn() as c:
        r=c.execute("SELECT * FROM users WHERE id=?",(int(uid),)).fetchone()
        return dict(r) if r else None
def upsert(uid, username=None):
    today=datetime.now(timezone.utc).date().isoformat()
    with lock, conn() as c:
        c.execute("INSERT INTO users(id,username,provider,quota,quota_day,created) VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET username=excluded.username",
        (int(uid),username,S.default_provider,S.free_quota,today,now()))
    return get_user(uid)
def set_provider(uid,p):
    with lock, conn() as c: c.execute("UPDATE users SET provider=? WHERE id=?",(p,int(uid)))
def set_model(uid,m):
    with lock, conn() as c: c.execute("UPDATE users SET model=? WHERE id=?",(m,int(uid)))
def set_quota(uid,q):
    with lock, conn() as c: c.execute("UPDATE users SET quota=? WHERE id=?",(int(q),int(uid)))
def create_payment(uid,plan):
    with lock, conn() as c:
        cur=c.execute("INSERT INTO payments(user_id,plan,amount,currency,created) VALUES(?,?,?,?,?)",(int(uid),plan,S.prices[plan],S.currency,now()))
        return cur.lastrowid
def payment(pid):
    with conn() as c:
        r=c.execute("SELECT * FROM payments WHERE id=?",(int(pid),)).fetchone()
        return dict(r) if r else None
def pending():
    with conn() as c: return [dict(r) for r in c.execute("SELECT * FROM payments WHERE status='pending' ORDER BY id LIMIT 100")]
def review(pid,status,note):
    with lock, conn() as c:
        cur=c.execute("UPDATE payments SET status=?,reviewed=?,note=? WHERE id=? AND status='pending'",(status,now(),note,int(pid)))
        return cur.rowcount==1
def extend(uid,days):
    with lock, conn() as c:
        r=c.execute("SELECT until FROM users WHERE id=?",(int(uid),)).fetchone()
        if not r: return None
        current=None
        try: current=datetime.fromisoformat(r["until"]) if r["until"] else None
        except ValueError: pass
        start=current if current and current>datetime.now(timezone.utc) else datetime.now(timezone.utc)
        until=(start+timedelta(days=int(days))).isoformat()
        c.execute("UPDATE users SET until=? WHERE id=?",(until,int(uid)))
        return until
def consume(uid):
    today=datetime.now(timezone.utc).date().isoformat()
    with lock, conn() as c:
        r=c.execute("SELECT * FROM users WHERE id=?",(int(uid),)).fetchone()
        if not r: return False
        if r["quota_day"]!=today:
            c.execute("UPDATE users SET quota_day=?,used=0 WHERE id=?",(today,int(uid)))
            r=c.execute("SELECT * FROM users WHERE id=?",(int(uid),)).fetchone()
        try: active=bool(r["until"] and datetime.fromisoformat(r["until"])>datetime.now(timezone.utc))
        except ValueError: active=False
        if active: return True
        if int(r["used"] or 0)>=int(r["quota"] or 0): return False
        c.execute("UPDATE users SET used=used+1 WHERE id=?",(int(uid),)); return True
def rate_ok(uid,ts):
    with lock, conn() as c:
        r=c.execute("SELECT last_req FROM users WHERE id=?",(int(uid),)).fetchone()
        if not r or ts-float(r["last_req"] or 0)<S.rate_seconds: return False
        c.execute("UPDATE users SET last_req=? WHERE id=?",(ts,int(uid))); return True
def log_usage(uid,p,m,ic,oc):
    with lock, conn() as c:
        c.execute("INSERT INTO usage(user_id,provider,model,input_chars,output_chars,created) VALUES(?,?,?,?,?,?)",(int(uid),p,m,ic,oc,now()))
        c.execute("UPDATE users SET requests=requests+1 WHERE id=?",(int(uid),))
def stats():
    with conn() as c:
        return dict(c.execute("SELECT COUNT(*) requests,COALESCE(SUM(cost),0) cost FROM usage").fetchone())
def users(limit=30):
    with conn() as c: return [dict(r) for r in c.execute("SELECT * FROM users ORDER BY created DESC LIMIT ?",(limit,))]
def count_users():
    with conn() as c: return c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
def webhook_apply(event_id,uid,plan):
    from .plans import PLANS
    if plan not in PLANS: raise ValueError("plan")
    with lock, conn() as c:
        try: c.execute("INSERT INTO events(event_id,created) VALUES(?,?)",(event_id,now()))
        except sqlite3.IntegrityError: return False
        r=c.execute("SELECT until FROM users WHERE id=?",(int(uid),)).fetchone()
        if not r:
            c.execute("INSERT INTO users(id,provider,quota,quota_day,created) VALUES(?,?,?,?,?)",(int(uid),S.default_provider,S.free_quota,datetime.now(timezone.utc).date().isoformat(),now()))
            old=None
        else: old=r["until"]
        try: current=datetime.fromisoformat(old) if old else None
        except ValueError: current=None
        start=current if current and current>datetime.now(timezone.utc) else datetime.now(timezone.utc)
        until=(start+timedelta(days=PLANS[plan]["days"])).isoformat()
        c.execute("UPDATE users SET until=? WHERE id=?",(until,int(uid)))
        return True
