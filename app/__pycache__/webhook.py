import hashlib,hmac,json,logging,uvicorn
from fastapi import FastAPI,Request,HTTPException
from .config import S
from .db import init_db,webhook_apply
app=FastAPI(title="Payment Callback",docs_url=None,redoc_url=None)
@app.on_event("startup")
def startup(): init_db()
@app.get("/health")
def health(): return {"status":"ok"}
@app.post("/payment/callback")
async def callback(request:Request):
    if not S.webhook_secret: raise HTTPException(503,"Webhook secret is not configured")
    raw=await request.body()
    expected="sha256="+hmac.new(S.webhook_secret.encode(),raw,hashlib.sha256).hexdigest()
    if not hmac.compare_digest(request.headers.get("X-Signature",""),expected): raise HTTPException(401,"Invalid signature")
    try: data=json.loads(raw)
    except json.JSONDecodeError: raise HTTPException(400,"Invalid JSON")
    event=str(data.get("event_id","")).strip(); uid=data.get("telegram_user_id"); plan=data.get("plan")
    if not event or len(event)>200 or not isinstance(uid,int) or uid<=0: raise HTTPException(400,"Invalid event/user")
    if data.get("status")!="paid": return {"ok":True,"ignored":True}
    try: applied=webhook_apply(event,uid,plan)
    except ValueError: raise HTTPException(400,"Invalid plan")
    return {"ok":True,"applied":applied,"duplicate":not applied}
if __name__=="__main__":
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app,host=S.webhook_host,port=S.webhook_port)
