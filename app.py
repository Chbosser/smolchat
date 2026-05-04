import os
import sqlite3

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeSerializer
from openai import OpenAI
from passlib.hash import argon2

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

DB_PATH = os.getenv("DB_PATH", "app.db")
SESSION_SECRET = os.getenv("SESSION_SECRET", "change-this-secret")
VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://10.0.2.129:8000/v1")
VLLM_API_KEY = os.getenv("VLLM_API_KEY", "secret123")
VLLM_MODEL = os.getenv("VLLM_MODEL", "HuggingFaceTB/SmolLM2-135M-Instruct")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "50"))

serializer = URLSafeSerializer(SESSION_SECRET)

client = OpenAI(
    base_url=VLLM_BASE_URL,
    api_key=VLLM_API_KEY,
)


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


init_db()


def get_current_user(request: Request):
    session = request.cookies.get("session")
    if not session:
        return None

    try:
        user_id = serializer.loads(session)
    except Exception:
        return None

    conn = db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return user


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    user = get_current_user(request)
    if user:
        return RedirectResponse("/chat", status_code=302)
    return RedirectResponse("/login", status_code=302)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    user = get_current_user(request)
    if user:
        return RedirectResponse("/chat", status_code=302)

    return templates.TemplateResponse(
        request=request,
        name="auth.html",
        context={"error": None},
    )


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    user = get_current_user(request)
    if user:
        return RedirectResponse("/chat", status_code=302)

    return templates.TemplateResponse(
        request=request,
        name="auth.html",
        context={"error": None},
    )


@app.post("/register", response_class=HTMLResponse)
def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    verify_password: str = Form(...),
):
    if password != verify_password:
        return templates.TemplateResponse(
            request=request,
            name="auth.html",
            context={"error": "Passwords do not match."},
            status_code=400,
        )

    conn = db()
    try:
        conn.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (email, argon2.hash(password)),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return templates.TemplateResponse(
            request=request,
            name="auth.html",
            context={"error": "Account already exists."},
            status_code=400,
        )

    conn.close()
    return RedirectResponse("/login", status_code=302)


@app.post("/login", response_class=HTMLResponse)
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    conn = db()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()

    if not user or not argon2.verify(password, user["password_hash"]):
        return templates.TemplateResponse(
            request=request,
            name="auth.html",
            context={"error": "Invalid email or password."},
            status_code=401,
        )

    session_token = serializer.dumps(user["id"])

    response = RedirectResponse("/chat", status_code=302)
    response.set_cookie(
        key="session",
        value=session_token,
        httponly=True,
        samesite="lax",
    )
    return response


@app.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("session")
    return response


@app.get("/chat", response_class=HTMLResponse)
def chat_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    conn = db()
    messages = conn.execute(
        "SELECT role, content FROM messages WHERE user_id = ? ORDER BY id ASC",
        (user["id"],),
    ).fetchall()
    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="chat.html",
        context={
            "user_email": user["email"],
            "messages": messages,
        },
    )


@app.post("/chat", response_class=HTMLResponse)
def send_chat(request: Request, prompt: str = Form(...)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    conn = db()

    conn.execute(
        "INSERT INTO messages (user_id, role, content) VALUES (?, ?, ?)",
        (user["id"], "user", prompt),
    )
    conn.commit()

    try:
        response = client.chat.completions.create(
            model=VLLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=MAX_TOKENS,
            timeout=120,
        )
        answer = response.choices[0].message.content
    except Exception as e:
        answer = f"LLM error: {str(e)}"

    conn.execute(
        "INSERT INTO messages (user_id, role, content) VALUES (?, ?, ?)",
        (user["id"], "assistant", answer),
    )
    conn.commit()
    conn.close()

    return RedirectResponse("/chat", status_code=302)
