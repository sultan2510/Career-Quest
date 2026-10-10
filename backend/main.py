import asyncio, base64, hashlib, json, os, re, secrets, smtplib
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import asyncpg, bcrypt, jwt
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field, field_validator

try:
    from backend.progress import ProgressSnapshot
except ModuleNotFoundError:
    from progress import ProgressSnapshot
try:
    from backend.rag_service import RagService
except ModuleNotFoundError:
    from rag_service import RagService

def load_env():  # backend/.env at startup, for shells that can't source it (Windows); real env vars win
    p = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            k, _, v = line.strip().partition("=")
            if k and not k.startswith("#"): os.environ.setdefault(k, v)


load_env()
E = os.environ.get
FRONT, SECRET, COOKIE, DAYS = E("FRONTEND_URL", "http://localhost:3000"), E("JWT_SECRET", ""), "cq_session", 7
PASSWORD_SCHEME = "sha256-bcrypt$"
DUMMY = bcrypt.hashpw(b"dummy", bcrypt.gensalt()).decode()  # keeps login timing similar for unknown emails


@asynccontextmanager
async def lifespan(app):
    assert len(SECRET) >= 32, "Set JWT_SECRET (32+ chars)"
    app.state.db = await asyncpg.create_pool(E("DATABASE_URL"), statement_cache_size=0, min_size=1, max_size=5)
    app.state.rag = RagService(generation_config={"model": "llama-4-17b-128e-instruct", "provider": None})
    yield
    await app.state.db.close()


app = FastAPI(title="CareerQuest API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[FRONT], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


def err(status, code, msg):
    raise HTTPException(status, {"code": code, "message": msg})


pool = lambda req: req.app.state.db
sha = lambda s: hashlib.sha256(s.encode()).hexdigest()
now = lambda: datetime.now(timezone.utc)
_pre = lambda p: base64.b64encode(hashlib.sha256(p.encode()).digest())  # bcrypt rejects >72 bytes, so hash first
hash_pw = lambda p: asyncio.to_thread(lambda: PASSWORD_SCHEME + bcrypt.hashpw(_pre(p), bcrypt.gensalt()).decode())


async def check_pw(password: str, stored: str) -> bool:
    marked = stored.startswith(PASSWORD_SCHEME)
    encoded = stored[len(PASSWORD_SCHEME):] if marked else stored
    def verify() -> bool:
        try:
            if marked:
                return bcrypt.checkpw(_pre(password), encoded.encode())
            return bcrypt.checkpw(password.encode(), encoded.encode()) or bcrypt.checkpw(_pre(password), encoded.encode())
        except (ValueError, TypeError):
            return False
    return await asyncio.to_thread(verify)
pub = lambda u: {"id": str(u["id"]), "name": u["name"], "email": u["email"], "guest": False, "createdAt": u["created_at"].isoformat()}


class SignUp(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    character: int | None = Field(default=None, ge=0, le=3, strict=True)
    progress: dict | None = None  # guest progress carried over

    @field_validator("progress")
    @classmethod
    def validate_progress(cls, value):
        if value is not None:
            ProgressSnapshot.validate_payload({"v": 1, **value})
        return value


class Login(BaseModel): email: EmailStr; password: str
class EmailIn(BaseModel): email: EmailStr
class TokenIn(BaseModel): token: str
class ResetIn(BaseModel): token: str; password: str = Field(min_length=8, max_length=128)
class NameIn(BaseModel): name: str = Field(min_length=2, max_length=60)
class Ask(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    profile: str | None = Field(None, max_length=1500)
    progress: dict | None = None

    @field_validator("question")
    @classmethod
    def nonblank_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Question cannot be blank")
        return value.strip()

    @field_validator("progress")
    @classmethod
    def validate_progress(cls, value):
        if value is not None:
            ProgressSnapshot.validate_payload(value)
        return value


def set_session(res: Response, uid):
    tok = jwt.encode({"sub": str(uid), "exp": now() + timedelta(days=DAYS)}, SECRET, "HS256")
    res.set_cookie(COOKIE, tok, max_age=DAYS * 86400, httponly=True, path="/",
                   secure=E("COOKIE_SECURE", "false") == "true", samesite=E("COOKIE_SAMESITE", "lax"))


async def current(req: Request):
    try:
        uid = jwt.decode(req.cookies.get(COOKIE, ""), SECRET, ["HS256"])["sub"]
    except Exception:
        err(401, "unauthenticated", "Please log in.")
    u = await pool(req).fetchrow("select * from users where id=$1", uid)
    if not u:
        err(401, "unauthenticated", "Please log in.")
    return u


async def throttle(req, key, limit, seconds):
    n = await pool(req).fetchval(
        "with d as (delete from rate_limits where at < now() - interval '1 day') select count(*) from rate_limits where key=$1 and at > now() - make_interval(secs => $2)",
        key, float(seconds))
    if n >= limit:
        err(429, "rate_limited", "Too many attempts. Please wait a few minutes and try again.")
    await pool(req).execute("insert into rate_limits(key) values($1)", key)


def send_mail(to, subject, body):
    host = E("SMTP_HOST")
    if not host:
        print(f"\n--- EMAIL to {to} | {subject}\n{body}\n---", flush=True)
        return
    m = EmailMessage(); m["From"], m["To"], m["Subject"] = E("SMTP_FROM"), to, subject; m.set_content(body)
    with smtplib.SMTP(host, int(E("SMTP_PORT", "587"))) as s:
        s.starttls(); s.login(E("SMTP_USER"), E("SMTP_PASS")); s.send_message(m)


async def new_token(req, uid, kind, hours):
    raw = secrets.token_urlsafe(32)
    async with pool(req).acquire() as c:
        await c.execute("delete from email_tokens where user_id=$1 and kind=$2", uid, kind)
        await c.execute("insert into email_tokens(user_id,kind,token_hash,expires_at) values($1,$2,$3,now()+make_interval(hours => $4))",
                        uid, kind, sha(raw), hours)
    return raw


async def use_token(req, raw, kind):  # single use: deleted as it is read
    row = await pool(req).fetchrow("delete from email_tokens where token_hash=$1 and kind=$2 returning user_id, expires_at", sha(raw), kind)
    if not row or row["expires_at"] < now():
        err(400, "bad_token", "This link is invalid or has expired. Request a new one.")
    return row["user_id"]


async def mail_verify(req, uid, email, name):
    raw = await new_token(req, uid, "verify", 24)
    await asyncio.to_thread(send_mail, email, "Verify your CareerQuest email",
                            f"Hi {name},\n\nConfirm your email to start your quest:\n{FRONT}/?verify={raw}\n\nThis link expires in 24 hours.")


@app.post("/auth/signup", status_code=201)
async def signup(b: SignUp, req: Request):
    email, prog = b.email.lower(), ({"v": 1, **b.progress} if b.progress is not None else {"v": 1})
    if len(json.dumps(prog)) > 200_000:
        err(413, "too_large", "Progress data is too large.")
    if b.character is not None and prog.get("character") is None:
        prog["character"] = b.character
    try:
        u = await pool(req).fetchrow("insert into users(name,email,password_hash) values($1,$2,$3) returning id",
                                     b.name.strip(), email, await hash_pw(b.password))
    except asyncpg.UniqueViolationError:
        err(409, "email_taken", "That email already has an account. Try logging in instead.")
    await pool(req).execute("insert into progress(user_id,data) values($1,$2::jsonb)", u["id"], json.dumps(prog))
    await mail_verify(req, u["id"], email, b.name.strip())
    return {"needsVerification": True, "email": email}


@app.post("/auth/login")
async def login(b: Login, req: Request, res: Response):
    await throttle(req, f"login:{b.email.lower()}", 10, 900)
    u = await pool(req).fetchrow("select * from users where email=$1", b.email.lower())
    ok = await check_pw(b.password, u["password_hash"] if u else DUMMY)
    if not u or not ok:
        err(401, "bad_credentials", "Email or password is incorrect.")
    if not u["email_verified"]:
        err(403, "email_not_verified", "Please verify your email first. We can resend the link.")
    set_session(res, u["id"])
    return pub(u)


@app.post("/auth/verify")
async def verify(b: TokenIn, req: Request, res: Response):
    uid = await use_token(req, b.token, "verify")
    u = await pool(req).fetchrow("update users set email_verified=true where id=$1 returning *", uid)
    set_session(res, uid)
    return pub(u)


@app.post("/auth/resend")
async def resend(b: EmailIn, req: Request):  # always 200 so emails can't be enumerated
    u = await pool(req).fetchrow("select * from users where email=$1 and not email_verified", b.email.lower())
    recent = u and await pool(req).fetchval(
        "select 1 from email_tokens where user_id=$1 and kind='verify' and created_at > now() - interval '60 seconds'", u["id"])
    if u and not recent:
        await mail_verify(req, u["id"], u["email"], u["name"])
    return {"ok": True}


@app.post("/auth/forgot")
async def forgot(b: EmailIn, req: Request):
    u = await pool(req).fetchrow("select * from users where email=$1", b.email.lower())
    recent = u and await pool(req).fetchval(
        "select 1 from email_tokens where user_id=$1 and kind='reset' and created_at > now() - interval '60 seconds'", u["id"])
    if u and not recent:
        raw = await new_token(req, u["id"], "reset", 1)
        await asyncio.to_thread(send_mail, u["email"], "Reset your CareerQuest password",
                                f"Reset your password here (valid for 1 hour):\n{FRONT}/?reset={raw}\n\nIf you didn't ask for this, ignore this email.")
    return {"ok": True}


@app.post("/auth/reset")
async def reset(b: ResetIn, req: Request):
    uid = await use_token(req, b.token, "reset")
    await pool(req).execute("update users set password_hash=$2, email_verified=true where id=$1", uid, await hash_pw(b.password))
    return {"ok": True}


@app.post("/auth/logout")
async def logout(res: Response):
    res.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@app.get("/auth/me")
async def me(u=Depends(current)): return pub(u)


@app.patch("/auth/me")
async def rename(b: NameIn, req: Request, u=Depends(current)):
    return pub(await pool(req).fetchrow("update users set name=$2 where id=$1 returning *", u["id"], b.name.strip()))


@app.delete("/auth/me")
async def delete_me(req: Request, res: Response, u=Depends(current)):
    await pool(req).execute("delete from users where id=$1", u["id"])
    res.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@app.get("/progress")
async def get_progress(req: Request, u=Depends(current)):
    d = await pool(req).fetchval("select data from progress where user_id=$1", u["id"])
    return json.loads(d) if d else {"v": 1}


@app.put("/progress")
async def put_progress(body: dict, req: Request, u=Depends(current)):
    try:
        ProgressSnapshot.validate_payload(body)
    except (ValueError, TypeError):
        err(422, "bad_progress", "Invalid progress data.")
    await pool(req).execute("insert into progress(user_id,data) values($1,$2::jsonb) on conflict (user_id) do update set data=$2::jsonb, updated_at=now()",
                            u["id"], json.dumps(body))
    return {"ok": True}


@app.post("/rag/ask")
async def rag_ask(b: Ask, req: Request, u=Depends(current)):
    """Ground answers in the catalog and the authenticated user's current context."""
    await throttle(req, f"rag:{u['id']}", 20, 600)
    if b.progress is None:
        saved = await pool(req).fetchval("select data from progress where user_id=$1", u["id"])
        raw = json.loads(saved) if saved else {"v": 1}
        source = "database"
    else:
        raw, source = b.progress, "current"
    snapshot = ProgressSnapshot.validate_payload(raw)
    service = getattr(req.app.state, "rag", None) or RagService()
    return await service.ask(pool(req), str(u["id"]), b.question, snapshot, b.profile, source)


@app.get("/health")
async def health(): return {"ok": True}
@app.get("/debug-smtp")
def debug_smtp(to: str = ""):
    info = {
        "host": os.environ.get("SMTP_HOST", ""),
        "port": os.environ.get("SMTP_PORT", ""),
        "user": os.environ.get("SMTP_USER", ""),
        "pass_set": bool(os.environ.get("SMTP_PASS")),
        "from": os.environ.get("SMTP_FROM", ""),
        "front": os.environ.get("FRONTEND_URL", ""),
    }
    if to:
        try:
            send_mail(to, "Vercel SMTP test", "Sent from the deployed backend.")
            info["result"] = "SENT"
        except Exception as e:
            info["result"] = f"ERROR: {type(e).__name__}: {e}"
    return info
