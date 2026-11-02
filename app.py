import sqlite3
import os
import io
import csv
import json
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException, status, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import hmac
import base64
from http.cookies import SimpleCookie
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.datastructures import MutableHeaders

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "paradesk.db"))
SECRET_KEY = os.getenv("SECRET_KEY", "paradesk-paradox27-secret-key-iitm")
SECURE_COOKIES = os.getenv("SECURE_COOKIES", "false").lower() in ("true", "1")

def sign_session_data(data: dict, secret: bytes) -> str:
    payload = base64.urlsafe_b64encode(json.dumps(data).encode("utf-8")).decode("utf-8")
    sig = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"

def unsign_session_data(token: str, secret: bytes) -> dict:
    if not token or "." not in token:
        return {}
    parts = token.split(".", 1)
    if len(parts) != 2:
        return {}
    payload, sig = parts
    expected_sig = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        return {}
    try:
        decoded_bytes = base64.urlsafe_b64decode(payload.encode("utf-8"))
        return json.loads(decoded_bytes.decode("utf-8"))
    except Exception:
        return {}

class PureCookieSessionMiddleware:
    def __init__(self, app: ASGIApp, secret_key: str = "paradesk-paradox27-secret-key-iitm", cookie_name: str = "px_session", max_age: int = 86400):
        self.app = app
        self.secret = secret_key.encode("utf-8") if isinstance(secret_key, str) else secret_key
        self.cookie_name = cookie_name
        self.max_age = max_age

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        cookie_header = headers.get(b"cookie", b"").decode("latin1")
        session_data = {}
        had_cookie = False
        if cookie_header:
            cookie = SimpleCookie()
            try:
                cookie.load(cookie_header)
                if self.cookie_name in cookie:
                    had_cookie = True
                    raw_val = cookie[self.cookie_name].value
                    session_data = unsign_session_data(raw_val, self.secret)
            except Exception:
                session_data = {}

        scope["session"] = session_data

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                current_session = scope.get("session", {})
                headers_mut = MutableHeaders(scope=message)
                secure_flag = "; Secure" if (SECURE_COOKIES or scope.get("scheme") == "https") else ""
                if current_session:
                    signed_val = sign_session_data(current_session, self.secret)
                    cookie_val = f"{self.cookie_name}={signed_val}; Path=/; Max-Age={self.max_age}; HttpOnly; SameSite=Lax{secure_flag}"
                    headers_mut.append("Set-Cookie", cookie_val)
                elif had_cookie:
                    cookie_val = f"{self.cookie_name}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax{secure_flag}"
                    headers_mut.append("Set-Cookie", cookie_val)
            await send(message)

        await self.app(scope, receive, send_wrapper)

app = FastAPI(title="Paradesk Core Engine - Multi-Event Ground Execution")
app.add_middleware(PureCookieSessionMiddleware, secret_key="paradesk-paradox27-secret-key-iitm")

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=20.0)
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password: str) -> str:
    salt = "paradesk_iitm_salt_2027"
    return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()

def verify_password(plain: str, hashed: str) -> bool:
    return hash_password(plain) == hashed

def get_current_user(request: Request) -> Optional[dict]:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    conn = get_db_connection()
    try:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(user) if user else None
    finally:
        conn.close()

def generate_token(prefix="PX-") -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    random_part = "".join(secrets.choice(alphabet) for _ in range(6))
    return f"{prefix}{random_part}"

def log_audit(conn, event_id: int, action: str, details: str, badge_color: str = "slate"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    conn.execute(
        "INSERT INTO audit_logs (event_id, timestamp, action, details, badge_color) VALUES (?, ?, ?, ?, ?)",
        (event_id, timestamp, action, details, badge_color)
    )

def init_db(force_reseed: bool = False):
    conn = get_db_connection()
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        
        # Check if users table or emails_sent table exists; if not, reseed
        table_info = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
        needs_migration = (table_info is None)

        if force_reseed or needs_migration:
            conn.execute("DROP TABLE IF EXISTS emails_sent")
            conn.execute("DROP TABLE IF EXISTS audit_logs")
            conn.execute("DROP TABLE IF EXISTS teams")
            conn.execute("DROP TABLE IF EXISTS desks")
            conn.execute("DROP TABLE IF EXISTS events")
            conn.execute("DROP TABLE IF EXISTS users")

        # Table: users
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('ADMIN', 'PARTICIPANT')) DEFAULT 'PARTICIPANT',
                phone TEXT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Table: events
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                max_teams INTEGER NOT NULL,
                max_members_per_team INTEGER NOT NULL DEFAULT 4,
                venue_name TEXT NOT NULL,
                event_start DATETIME NOT NULL,
                problem_statement_url TEXT NULL,
                problem_statement_text TEXT NULL,
                rubric_json TEXT NULL,
                freeze_hours_before_end INTEGER DEFAULT 2,
                is_leaderboard_frozen INTEGER DEFAULT 0
            );
        """)

        # Table: desks
        conn.execute("""
            CREATE TABLE IF NOT EXISTS desks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                desk_code TEXT NOT NULL,
                is_occupied INTEGER DEFAULT 0,
                assigned_team_id INTEGER NULL
            );
        """)

        # Table: teams
        conn.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                user_id INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
                team_name TEXT NOT NULL,
                lead_name TEXT NOT NULL,
                lead_email TEXT NOT NULL,
                lead_phone TEXT NOT NULL,
                member_count INTEGER NOT NULL DEFAULT 1,
                member_names TEXT NULL,
                registration_timestamp DATETIME NOT NULL,
                queue_position INTEGER NOT NULL,
                status TEXT CHECK(status IN ('ALLOCATED', 'STANDBY_TOP10', 'WAITLISTED', 'CHECKED_IN', 'NO_SHOW')) NOT NULL,
                unique_checkin_token TEXT UNIQUE NOT NULL,
                assigned_desk_id INTEGER NULL REFERENCES desks(id),
                checkin_timestamp DATETIME NULL,
                score_innovation REAL DEFAULT 0,
                score_technical REAL DEFAULT 0,
                score_presentation REAL DEFAULT 0,
                total_score REAL DEFAULT 0
            );
        """)

        # Table: emails_sent
        conn.execute("""
            CREATE TABLE IF NOT EXISTS emails_sent (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                subject TEXT NOT NULL,
                recipient_count INTEGER NOT NULL,
                recipient_type TEXT NOT NULL,
                body_preview TEXT NOT NULL,
                sent_timestamp TEXT NOT NULL,
                status TEXT DEFAULT 'DELIVERED'
            );
        """)

        # Table: audit_logs
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT NOT NULL,
                badge_color TEXT DEFAULT 'slate'
            );
        """)

        # Seed initial users and events if empty
        user_count = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()["cnt"]
        if user_count == 0:
            now = datetime.now()

            # 1. Admin User
            admin_pwd = hash_password("admin123")
            conn.execute("""
                INSERT INTO users (email, password_hash, full_name, role, phone)
                VALUES (?, ?, ?, 'ADMIN', ?)
            """, ("admin@iitm.ac.in", admin_pwd, "Paradox '27 Lead Organizer", "+91 98400 11111"))

            # 2. Main Participant User (Registered in Event 1)
            p1_pwd = hash_password("participant123")
            cursor_p1 = conn.execute("""
                INSERT INTO users (email, password_hash, full_name, role, phone)
                VALUES (?, ?, ?, 'PARTICIPANT', ?)
            """, ("aarav@smail.iitm.ac.in", p1_pwd, "Aarav Sharma", "+91 98401 12345"))
            p1_user_id = cursor_p1.lastrowid

            # 3. Standby Participant User (Queue in Event 1)
            cursor_p2 = conn.execute("""
                INSERT INTO users (email, password_hash, full_name, role, phone)
                VALUES (?, ?, ?, 'PARTICIPANT', ?)
            """, ("vikram@smail.iitm.ac.in", p1_pwd, "Vikram Nair", "+91 98407 78901"))
            p2_user_id = cursor_p2.lastrowid

            # Rubric definition
            rubric_default = json.dumps([
                {"criteria": "Innovation & Originality", "weight": 40, "field": "score_innovation", "max": 40},
                {"criteria": "Technical Complexity & Schema", "weight": 35, "field": "score_technical", "max": 35},
                {"criteria": "UI/UX & Final Pitch", "weight": 25, "field": "score_presentation", "max": 25}
            ])

            # EVENT 1: Today's Event (Starts in 2 hours -> tokens active!)
            ev1_start = now + timedelta(hours=2)
            cursor_ev1 = conn.execute("""
                INSERT INTO events (
                    name, slug, max_teams, max_members_per_team, venue_name, event_start, 
                    problem_statement_url, problem_statement_text, rubric_json, freeze_hours_before_end, is_leaderboard_frozen
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "HackParadox 2027",
                "hackparadox-2027",
                30,
                4,
                "CRC Complex Hall 101",
                ev1_start.strftime("%Y-%m-%d %H:%M:%S"),
                "https://paradox27.iitm.ac.in/ps/hackparadox.pdf",
                "Build an event-ground capacity recovery and logistics engine that dynamically reclaims idle venue desks, LAN ports, and standby squads under physical campus constraints.",
                rubric_default,
                2,
                0
            ))
            ev1_id = cursor_ev1.lastrowid

            # Provision 30 desks for Event 1
            desk_ids_ev1 = []
            for d in range(1, 31):
                desk_code = f"CRC-T{d:02d}"
                c_desk = conn.execute(
                    "INSERT INTO desks (event_id, desk_code, is_occupied, assigned_team_id) VALUES (?, ?, 0, NULL)",
                    (ev1_id, desk_code)
                )
                desk_ids_ev1.append(c_desk.lastrowid)

            # EVENT 2: Next Week's Event (Starts in 7 days -> tokens locked until 24h prior)
            ev2_start = now + timedelta(days=7)
            cursor_ev2 = conn.execute("""
                INSERT INTO events (
                    name, slug, max_teams, max_members_per_team, venue_name, event_start, 
                    problem_statement_url, problem_statement_text, rubric_json, freeze_hours_before_end, is_leaderboard_frozen
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "AlgoStrike Coding Battle",
                "algostrike-2027",
                20,
                2,
                "CRC Hall 202",
                ev2_start.strftime("%Y-%m-%d %H:%M:%S"),
                "https://paradox27.iitm.ac.in/ps/algostrike.pdf",
                "High-velocity algorithmic competition tackling distributed graph partitioning, cache-coherent memory layouts, and zero-allocation string parsing.",
                rubric_default,
                2,
                0
            ))
            ev2_id = cursor_ev2.lastrowid

            # Provision 20 desks for Event 2
            for d in range(1, 21):
                desk_code = f"ALGO-T{d:02d}"
                conn.execute(
                    "INSERT INTO desks (event_id, desk_code, is_occupied, assigned_team_id) VALUES (?, ?, 0, NULL)",
                    (ev2_id, desk_code)
                )

            # SEED TEAMS FOR EVENT 1:
            # Exactly 30 Allocated Teams (Desks 1 to 30) + Exactly 5 in Standby Queue (31 to 35) = 35 Teams Total
            team_names = [
                "NeuralForge", "ByteCrafters", "AlgoRhythm", "QuantumCoders", "PixelPioneers",
                "SyntaxSquad", "CyberKnights", "DataDynamos", "LogicLoom", "CloudChallengers",
                "BinaryBlaze", "TensorTitans", "VectorVoyagers", "MatrixMinds", "CodeCrafters",
                "DevDragons", "EchoEngineers", "FrontierForces", "GridGiants", "HelixHacks",
                "InfiniteIterators", "KernelKings", "LambdaLegion", "MacroMakers", "NodeNavigators",
                "OmegaOps", "PinnacleParsers", "QuantumQuests", "RustRangers", "SiliconSurfers"
            ]

            # 1 to 30: Allocated to desks 1 to 30
            for idx, name in enumerate(team_names, start=1):
                desk_id = desk_ids_ev1[idx - 1]
                reg_time = now - timedelta(hours=6, minutes=idx*5)
                token = f"PX-CRC{idx:02d}"
                
                # First 5 are physically CHECKED_IN (seated at desk, initial kickoff phase)
                if idx <= 5:
                    status_val = "CHECKED_IN"
                    checkin_ts = (now - timedelta(minutes=45 - idx*5)).strftime("%Y-%m-%d %H:%M:%S")
                else:
                    status_val = "ALLOCATED"
                    checkin_ts = None

                # Initial scores are 0.0 for all participants at hackathon kickoff
                sc_in, sc_tech, sc_pr = 0.0, 0.0, 0.0
                tot_score = 0.0
                u_id = p1_user_id if idx == 1 else None
                lead_mail = "aarav@smail.iitm.ac.in" if idx == 1 else f"lead{idx}@smail.iitm.ac.in"
                lead_name = "Aarav Sharma" if idx == 1 else f"Participant Lead {idx}"
                mem_names = "Aarav Sharma, Sneha Patel, Rohan Gupta, Devansh Roy" if idx == 1 else f"Lead {idx}, Member A, Member B, Member C"

                cursor_team = conn.execute("""
                    INSERT INTO teams (
                        event_id, user_id, team_name, lead_name, lead_email, lead_phone, member_count, member_names,
                        registration_timestamp, queue_position, status, unique_checkin_token,
                        assigned_desk_id, checkin_timestamp, score_innovation, score_technical, score_presentation, total_score
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ev1_id, u_id, name, lead_name, lead_mail, f"+91 98401 {idx:04d}", 4, mem_names,
                    reg_time.strftime("%Y-%m-%d %H:%M:%S"), idx, status_val, token,
                    desk_id, checkin_ts, sc_in, sc_tech, sc_pr, tot_score
                ))
                new_team_id = cursor_team.lastrowid

                # Mark desk occupied
                conn.execute(
                    "UPDATE desks SET assigned_team_id = ?, is_occupied = 1 WHERE id = ?",
                    (new_team_id, desk_id)
                )

            # 5 Standby Teams in Queue (Queue positions 31 to 35)
            standby_names = ["CodeVanguard", "ZeroDayHeroes", "KernelPanics", "TuringMachines", "DataDrifters"]
            for s_idx, s_name in enumerate(standby_names, start=31):
                reg_time = now - timedelta(hours=2, minutes=(s_idx-30)*5)
                token = f"PX-STBY{s_idx:02d}"
                u_id = p2_user_id if s_idx == 31 else None
                lead_mail = "vikram@smail.iitm.ac.in" if s_idx == 31 else f"standby{s_idx}@smail.iitm.ac.in"
                lead_name = "Vikram Nair" if s_idx == 31 else f"Standby Lead {s_idx}"
                mem_names = "Vikram Nair, Ananya Sen, Karthik Varma" if s_idx == 31 else f"Lead {s_idx}, Standby Dev A, Standby Dev B"

                conn.execute("""
                    INSERT INTO teams (
                        event_id, user_id, team_name, lead_name, lead_email, lead_phone, member_count, member_names,
                        registration_timestamp, queue_position, status, unique_checkin_token,
                        assigned_desk_id, checkin_timestamp, score_innovation, score_technical, score_presentation, total_score
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, 0, 0, 0, 0)
                """, (
                    ev1_id, u_id, s_name, lead_name, lead_mail, f"+91 98407 {s_idx:04d}", 3, mem_names,
                    reg_time.strftime("%Y-%m-%d %H:%M:%S"), s_idx, "STANDBY_TOP10", token
                ))

            # Initial Email Log for Event 1
            conn.execute("""
                INSERT INTO emails_sent (event_id, subject, recipient_count, recipient_type, body_preview, sent_timestamp, status)
                VALUES (?, ?, ?, ?, ?, ?, 'DELIVERED')
            """, (
                ev1_id,
                "Paradox '27 Kickoff: Desk Allocation & 24h Check-In Code Active",
                30,
                "ALLOCATED_TEAMS",
                "Your physical desk reservation at CRC Complex Hall 101 is confirmed. Present your check-in code upon arrival.",
                (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
            ))

            log_audit(conn, ev1_id, "INIT", "HackParadox 2027 provisioned: 30 desks fully allocated + 5 teams in standby queue.", "emerald")
            log_audit(conn, ev2_id, "INIT", "AlgoStrike Coding Battle provisioned: 20 desks open for next week.", "blue")

        conn.commit()
    finally:
        conn.close()

# Auto-run DB init
init_db()

# -------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------

def get_event_metrics(conn, event_id: int):
    event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event:
        return None

    max_teams = event["max_teams"]
    max_members = event["max_members_per_team"]
    total_slots_teams = max_teams
    total_slots_members = max_teams * max_members

    allocated_teams = conn.execute(
        "SELECT COUNT(*) as cnt FROM teams WHERE event_id = ? AND status IN ('ALLOCATED', 'CHECKED_IN')",
        (event_id,)
    ).fetchone()["cnt"]

    checked_in_teams = conn.execute(
        "SELECT COUNT(*) as cnt FROM teams WHERE event_id = ? AND status = 'CHECKED_IN'",
        (event_id,)
    ).fetchone()["cnt"]

    standby_teams = conn.execute(
        "SELECT COUNT(*) as cnt FROM teams WHERE event_id = ? AND status = 'STANDBY_TOP10'",
        (event_id,)
    ).fetchone()["cnt"]

    waitlisted_teams = conn.execute(
        "SELECT COUNT(*) as cnt FROM teams WHERE event_id = ? AND status = 'WAITLISTED'",
        (event_id,)
    ).fetchone()["cnt"]

    total_registered = conn.execute(
        "SELECT COUNT(*) as cnt FROM teams WHERE event_id = ? AND status != 'NO_SHOW'",
        (event_id,)
    ).fetchone()["cnt"]

    total_desks = conn.execute(
        "SELECT COUNT(*) as cnt FROM desks WHERE event_id = ?",
        (event_id,)
    ).fetchone()["cnt"]

    occupied_desks = conn.execute(
        "SELECT COUNT(*) as cnt FROM desks WHERE event_id = ? AND is_occupied = 1",
        (event_id,)
    ).fetchone()["cnt"]

    utilization_pct = round((occupied_desks / total_desks * 100), 1) if total_desks > 0 else 0

    return {
        "event": dict(event),
        "total_slots_teams": total_slots_teams,
        "total_slots_members": total_slots_members,
        "allocated_teams": allocated_teams,
        "checked_in_teams": checked_in_teams,
        "standby_teams": standby_teams,
        "waitlisted_teams": waitlisted_teams,
        "total_registered": total_registered,
        "total_desks": total_desks,
        "occupied_desks": occupied_desks,
        "utilization_pct": utilization_pct
    }

# -------------------------------------------------------------
# Authentication & Session Routes
# -------------------------------------------------------------

@app.get("/")
def home(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    if user["role"] == "ADMIN":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    return RedirectResponse(url="/participant/dashboard", status_code=status.HTTP_302_FOUND)

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    user = get_current_user(request)
    if user:
        if user["role"] == "ADMIN":
            return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
        return RedirectResponse(url="/participant/dashboard", status_code=status.HTTP_302_FOUND)

    flash_error = request.query_params.get("error")
    flash_success = request.query_params.get("success")
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"flash_error": flash_error, "flash_success": flash_success}
    )

@app.post("/login")
def login_action(
    request: Request,
    email: str = Form(...),
    password: str = Form(...)
):
    conn = get_db_connection()
    try:
        user = conn.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email.strip(),)).fetchone()
        if not user or not verify_password(password, user["password_hash"]):
            return RedirectResponse(
                url="/login?error=Invalid+email+or+password.+Please+try+again.",
                status_code=status.HTTP_303_SEE_OTHER
            )

        # Establish session
        request.session["user_id"] = user["id"]
        request.session["user_role"] = user["role"]
        request.session["user_email"] = user["email"]
        request.session["user_name"] = user["full_name"]

        if user["role"] == "ADMIN":
            return RedirectResponse(url="/dashboard?success=Welcome+Admin", status_code=status.HTTP_303_SEE_OTHER)
        else:
            return RedirectResponse(url="/participant/dashboard?success=Welcome+back", status_code=status.HTTP_303_SEE_OTHER)

    finally:
        conn.close()

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    flash_error = request.query_params.get("error")
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={"flash_error": flash_error}
    )

@app.post("/register")
def register_action(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    password: str = Form(...)
):
    conn = get_db_connection()
    try:
        clean_email = email.strip().lower()
        existing = conn.execute("SELECT id FROM users WHERE LOWER(email) = ?", (clean_email,)).fetchone()
        if existing:
            return RedirectResponse(
                url="/register?error=An+account+with+this+email+already+exists.+Please+login.",
                status_code=status.HTTP_303_SEE_OTHER
            )

        pwd_hash = hash_password(password)
        cursor = conn.execute("""
            INSERT INTO users (email, password_hash, full_name, role, phone)
            VALUES (?, ?, ?, 'PARTICIPANT', ?)
        """, (clean_email, pwd_hash, full_name.strip(), phone.strip()))
        new_user_id = cursor.lastrowid
        conn.commit()

        # Log user in
        request.session["user_id"] = new_user_id
        request.session["user_role"] = "PARTICIPANT"
        request.session["user_email"] = clean_email
        request.session["user_name"] = full_name.strip()

        return RedirectResponse(
            url="/participant/dashboard?success=Account+created+successfully!+Welcome+to+Paradox+'27.",
            status_code=status.HTTP_303_SEE_OTHER
        )
    finally:
        conn.close()

@app.get("/logout")
def logout_action(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login?success=You+have+been+logged+out+securely.", status_code=status.HTTP_303_SEE_OTHER)

# -------------------------------------------------------------
# Participant Portal (Personal Dashboard & Event Management)
# -------------------------------------------------------------

@app.get("/participant/dashboard", response_class=HTMLResponse)
def participant_dashboard(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login?error=Please+log+in+to+view+your+participant+portal", status_code=status.HTTP_303_SEE_OTHER)

    conn = get_db_connection()
    try:
        # Fetch teams where this user is the owner or lead email matches
        teams_rows = conn.execute("""
            SELECT t.*, e.name as event_name, e.slug as event_slug, e.venue_name, e.event_start,
                   e.problem_statement_url, e.problem_statement_text, e.rubric_json,
                   d.desk_code
            FROM teams t
            JOIN events e ON t.event_id = e.id
            LEFT JOIN desks d ON t.assigned_desk_id = d.id
            WHERE t.user_id = ? OR LOWER(t.lead_email) = LOWER(?)
            ORDER BY e.event_start ASC
        """, (user["id"], user["email"])).fetchall()

        registered_events = []
        registered_event_ids = set()
        now = datetime.now()

        for r in teams_rows:
            team_dict = dict(r)
            registered_event_ids.add(team_dict["event_id"])

            # 24-HOUR TOKEN VISIBILITY RULE
            # Code is ONLY visible within 24 hours of event_start
            event_dt = None
            try:
                event_dt = datetime.strptime(team_dict["event_start"], "%Y-%m-%d %H:%M:%S")
            except Exception:
                pass

            if event_dt:
                time_until_start = event_dt - now
                # Visible if within 24 hours before event OR if event has started/is ongoing
                if time_until_start <= timedelta(hours=24):
                    team_dict["is_code_unlocked"] = True
                    team_dict["unlock_message"] = "ACTIVE & READY FOR GROUND SCAN"
                else:
                    team_dict["is_code_unlocked"] = False
                    unlock_dt = event_dt - timedelta(hours=24)
                    team_dict["unlock_message"] = f"Unlocks 24h prior: {unlock_dt.strftime('%b %d at %I:%M %p')}"
            else:
                team_dict["is_code_unlocked"] = True
                team_dict["unlock_message"] = "ACTIVE"

            # Parse Rubric JSON
            rubric = []
            if team_dict.get("rubric_json"):
                try:
                    rubric = json.loads(team_dict["rubric_json"])
                except Exception:
                    rubric = []
            team_dict["rubric"] = rubric

            # Standby Queue Rank if applicable
            if team_dict["status"] == "STANDBY_TOP10":
                rank_row = conn.execute("""
                    SELECT COUNT(*) as rank_pos FROM teams 
                    WHERE event_id = ? AND status = 'STANDBY_TOP10' AND queue_position <= ?
                """, (team_dict["event_id"], team_dict["queue_position"])).fetchone()
                team_dict["standby_rank"] = rank_row["rank_pos"] if rank_row else 1
            else:
                team_dict["standby_rank"] = None

            registered_events.append(team_dict)

        # Fetch upcoming events that the participant has NOT yet registered for
        all_events = [dict(ev) for ev in conn.execute("SELECT * FROM events ORDER BY event_start ASC").fetchall()]
        upcoming_available = [ev for ev in all_events if ev["id"] not in registered_event_ids]

    finally:
        conn.close()

    flash_success = request.query_params.get("success")
    flash_error = request.query_params.get("error")

    return templates.TemplateResponse(
        request=request,
        name="participant_dashboard.html",
        context={
            "user": user,
            "registered_events": registered_events,
            "upcoming_available": upcoming_available,
            "flash_success": flash_success,
            "flash_error": flash_error
        }
    )

@app.post("/participant/team/{team_id}/update")
def update_team_details(
    request: Request,
    team_id: int,
    team_name: str = Form(...),
    lead_phone: str = Form(...),
    member_count: int = Form(4),
    member_names: str = Form(...)
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login?error=Please+login", status_code=status.HTTP_303_SEE_OTHER)

    conn = get_db_connection()
    try:
        team = conn.execute("SELECT * FROM teams WHERE id = ?", (team_id,)).fetchone()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")

        # Verify ownership
        if team["user_id"] != user["id"] and team["lead_email"].lower() != user["email"].lower():
            raise HTTPException(status_code=403, detail="Not authorized to edit this team")

        conn.execute("""
            UPDATE teams 
            SET team_name = ?, lead_phone = ?, member_count = ?, member_names = ?
            WHERE id = ?
        """, (team_name.strip(), lead_phone.strip(), member_count, member_names.strip(), team_id))

        log_audit(conn, team["event_id"], "TEAM_UPDATE", f"Team '{team_name}' updated member roster details.", "blue")
        conn.commit()

    finally:
        conn.close()

    return RedirectResponse(
        url="/participant/dashboard?success=Team+details+and+members+updated+successfully!",
        status_code=status.HTTP_303_SEE_OTHER
    )

@app.post("/participant/register-event")
def participant_register_event(
    request: Request,
    event_id: int = Form(...),
    team_name: str = Form(...),
    lead_phone: str = Form(...),
    member_count: int = Form(4),
    member_names: Optional[str] = Form(None)
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login?error=Please+login", status_code=status.HTTP_303_SEE_OTHER)

    conn = get_db_connection()
    try:
        event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        max_teams = event["max_teams"]
        now = datetime.now()
        token = generate_token("PX-")

        # Check total teams already registered for this event
        existing_count = conn.execute("SELECT COUNT(*) as cnt FROM teams WHERE event_id = ?", (event_id,)).fetchone()["cnt"]
        queue_pos = existing_count + 1

        # Check available desks
        open_desk = conn.execute(
            "SELECT id, desk_code FROM desks WHERE event_id = ? AND is_occupied = 0 ORDER BY id ASC LIMIT 1",
            (event_id,)
        ).fetchone()

        # FCFS Logic:
        # If open desk and queue_pos <= max_teams -> ALLOCATED
        # Else if queue_pos <= max_teams + 10 -> STANDBY_TOP10
        # Else -> WAITLISTED
        if open_desk and queue_pos <= max_teams:
            assigned_desk_id = open_desk["id"]
            desk_code = open_desk["desk_code"]
            status_val = "ALLOCATED"
            success_msg = f"Registration confirmed! You have been allocated {desk_code}."
        elif queue_pos <= max_teams + 10:
            assigned_desk_id = None
            status_val = "STANDBY_TOP10"
            success_msg = f"Registration confirmed! Standard seats filled: You are placed at Standby Queue #{queue_pos - max_teams}."
        else:
            assigned_desk_id = None
            status_val = "WAITLISTED"
            success_msg = f"Registration confirmed! You have been placed on the priority waitlist (Queue #{queue_pos})."

        mem_names_str = member_names.strip() if member_names else f"{user['full_name']} (Lead)"

        cursor = conn.execute("""
            INSERT INTO teams (
                event_id, user_id, team_name, lead_name, lead_email, lead_phone, member_count, member_names,
                registration_timestamp, queue_position, status, unique_checkin_token, assigned_desk_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event_id, user["id"], team_name.strip(), user["full_name"], user["email"], lead_phone.strip(),
            member_count, mem_names_str, now.strftime("%Y-%m-%d %H:%M:%S"), queue_pos, status_val, token, assigned_desk_id
        ))
        new_team_id = cursor.lastrowid

        if assigned_desk_id:
            conn.execute("UPDATE desks SET is_occupied = 1, assigned_team_id = ? WHERE id = ?", (new_team_id, assigned_desk_id))

        log_audit(conn, event_id, "REGISTRATION", f"New registration: '{team_name}' by {user['full_name']} -> {status_val} (Queue #{queue_pos}).", "emerald")
        conn.commit()

    finally:
        conn.close()

    return RedirectResponse(url=f"/participant/dashboard?success={success_msg}", status_code=status.HTTP_303_SEE_OTHER)

# -------------------------------------------------------------
# Admin Dashboard & Event Operations
# -------------------------------------------------------------

def require_admin(request: Request) -> dict:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login required")
    if user["role"] != "ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return user

@app.get("/dashboard", response_class=HTMLResponse)
def admin_dashboard(request: Request, event_id: Optional[int] = None):
    user = get_current_user(request)
    if not user or user["role"] != "ADMIN":
        if user and user["role"] == "PARTICIPANT":
            return RedirectResponse(url="/participant/dashboard?error=Administrator+access+required", status_code=status.HTTP_303_SEE_OTHER)
        return RedirectResponse(url="/login?error=Please+login+as+an+administrator", status_code=status.HTTP_303_SEE_OTHER)

    conn = get_db_connection()
    try:
        events = [dict(r) for r in conn.execute("SELECT * FROM events ORDER BY id ASC").fetchall()]
        if not events:
            raise HTTPException(status_code=404, detail="No events configured.")

        # Default to first event or requested event_id
        current_event_id = event_id if event_id is not None else events[0]["id"]
        metrics = get_event_metrics(conn, current_event_id)
        if not metrics:
            current_event_id = events[0]["id"]
            metrics = get_event_metrics(conn, current_event_id)

        # Query Desks with assigned team details
        desks_rows = conn.execute("""
            SELECT d.*, t.team_name, t.lead_name, t.lead_phone, t.member_count, t.status as team_status, t.unique_checkin_token
            FROM desks d
            LEFT JOIN teams t ON d.assigned_team_id = t.id
            WHERE d.event_id = ?
            ORDER BY d.id ASC
        """, (current_event_id,)).fetchall()
        desks = [dict(r) for r in desks_rows]

        # Query Teams by Status
        allocated_teams = [dict(r) for r in conn.execute("""
            SELECT t.*, d.desk_code
            FROM teams t
            LEFT JOIN desks d ON t.assigned_desk_id = d.id
            WHERE t.event_id = ? AND t.status = 'ALLOCATED'
            ORDER BY t.queue_position ASC
        """, (current_event_id,)).fetchall()]

        checked_in_teams = [dict(r) for r in conn.execute("""
            SELECT t.*, d.desk_code
            FROM teams t
            LEFT JOIN desks d ON t.assigned_desk_id = d.id
            WHERE t.event_id = ? AND t.status = 'CHECKED_IN'
            ORDER BY t.checkin_timestamp DESC
        """, (current_event_id,)).fetchall()]

        standby_teams = [dict(r) for r in conn.execute("""
            SELECT * FROM teams 
            WHERE event_id = ? AND status = 'STANDBY_TOP10'
            ORDER BY queue_position ASC
        """, (current_event_id,)).fetchall()]

        waitlisted_teams = [dict(r) for r in conn.execute("""
            SELECT * FROM teams 
            WHERE event_id = ? AND status = 'WAITLISTED'
            ORDER BY queue_position ASC
        """, (current_event_id,)).fetchall()]

        no_shows = [dict(r) for r in conn.execute("""
            SELECT * FROM teams 
            WHERE event_id = ? AND status = 'NO_SHOW'
            ORDER BY queue_position ASC
        """, (current_event_id,)).fetchall()]

        audit_logs = [dict(r) for r in conn.execute("""
            SELECT * FROM audit_logs 
            WHERE event_id = ?
            ORDER BY id DESC 
            LIMIT 20
        """, (current_event_id,)).fetchall()]

        emails_sent = [dict(r) for r in conn.execute("""
            SELECT * FROM emails_sent 
            WHERE event_id = ?
            ORDER BY id DESC 
            LIMIT 10
        """, (current_event_id,)).fetchall()]

    finally:
        conn.close()

    flash_success = request.query_params.get("success")
    flash_warning = request.query_params.get("warning")
    flash_error = request.query_params.get("error")

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "user": user,
            "events": events,
            "current_event_id": current_event_id,
            "metrics": metrics,
            "desks": desks,
            "allocated_teams": allocated_teams,
            "checked_in_teams": checked_in_teams,
            "standby_teams": standby_teams,
            "waitlisted_teams": waitlisted_teams,
            "no_shows": no_shows,
            "audit_logs": audit_logs,
            "emails_sent": emails_sent,
            "flash_success": flash_success,
            "flash_warning": flash_warning,
            "flash_error": flash_error
        }
    )

@app.post("/admin/events")
def create_event(
    request: Request,
    name: str = Form(...),
    slug: str = Form(...),
    max_teams: int = Form(30),
    max_members_per_team: int = Form(4),
    venue_name: str = Form("CRC Hall"),
    event_start: str = Form(...)
):
    require_admin(request)
    conn = get_db_connection()
    try:
        clean_slug = slug.strip().lower().replace(" ", "-")
        cursor = conn.execute("""
            INSERT INTO events (name, slug, max_teams, max_members_per_team, venue_name, event_start)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name.strip(), clean_slug, max_teams, max_members_per_team, venue_name.strip(), event_start))
        new_event_id = cursor.lastrowid

        for i in range(1, max_teams + 1):
            desk_code = f"T{i:02d}"
            conn.execute(
                "INSERT INTO desks (event_id, desk_code, is_occupied, assigned_team_id) VALUES (?, ?, 0, NULL)",
                (new_event_id, desk_code)
            )

        log_audit(conn, new_event_id, "EVENT_CREATE", f"Created event '{name}' with {max_teams} desk capacity.", "emerald")
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        conn.close()
        return RedirectResponse(url="/dashboard?error=Event+slug+already+exists", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        conn.close()

    return RedirectResponse(url=f"/dashboard?event_id={new_event_id}&success=Event+created+successfully", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/events/{event_id}/edit-details")
def edit_event_details(
    request: Request,
    event_id: int,
    name: str = Form(...),
    venue_name: str = Form(...),
    event_start: str = Form(...),
    max_teams: int = Form(...),
    max_members_per_team: int = Form(4),
    problem_statement_url: Optional[str] = Form(None),
    problem_statement_text: Optional[str] = Form(None),
    rubric_json: Optional[str] = Form(None)
):
    require_admin(request)
    conn = get_db_connection()
    try:
        conn.execute("""
            UPDATE events 
            SET name = ?, venue_name = ?, event_start = ?, max_teams = ?, 
                max_members_per_team = ?, problem_statement_url = ?, problem_statement_text = ?, rubric_json = ?
            WHERE id = ?
        """, (
            name.strip(), venue_name.strip(), event_start.strip(), max_teams,
            max_members_per_team, problem_statement_url, problem_statement_text, rubric_json, event_id
        ))

        log_audit(conn, event_id, "EVENT_EDIT", f"Admin updated event details, venue ({venue_name}), and kickoff timing.", "blue")
        conn.commit()
    finally:
        conn.close()

    return RedirectResponse(url=f"/dashboard?event_id={event_id}&success=Event+details+updated+successfully!", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/events/{event_id}/send-email")
def send_email_dispatch(
    request: Request,
    event_id: int,
    campaign_type: str = Form(...),
    custom_subject: Optional[str] = Form(None),
    custom_body: Optional[str] = Form(None)
):
    require_admin(request)
    conn = get_db_connection()
    try:
        event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if campaign_type == "BROADCAST_24H_CODES":
            teams = conn.execute("SELECT COUNT(*) as cnt FROM teams WHERE event_id = ? AND status IN ('ALLOCATED', 'CHECKED_IN')", (event_id,)).fetchone()
            count = teams["cnt"]
            subject = f"[{event['name']}] 24h Check-in Pass & Desk Allocation Released"
            body = f"Your desk allocation and 24h check-in code for {event['name']} at {event['venue_name']} are now live on your Paradesk portal."
            recipient_type = "ALLOCATED_TEAMS"

        elif campaign_type == "STANDBY_LOBBY_CALL":
            teams = conn.execute("SELECT COUNT(*) as cnt FROM teams WHERE event_id = ? AND status = 'STANDBY_TOP10'", (event_id,)).fetchone()
            count = teams["cnt"]
            subject = f"[{event['name']}] Urgent: Standby Queue Call - Report to {event['venue_name']} Lobby"
            body = "You are in the Top 10 Standby queue. Please report to the CRC Lobby immediately for desk reclamation during the 15-minute sweep."
            recipient_type = "STANDBY_TOP10"

        elif campaign_type == "VENUE_GUIDE":
            teams = conn.execute("SELECT COUNT(*) as cnt FROM teams WHERE event_id = ? AND status != 'NO_SHOW'", (event_id,)).fetchone()
            count = teams["cnt"]
            subject = f"[{event['name']}] Venue Access, Power Banks & LAN Drop Instructions"
            body = f"Welcome to {event['venue_name']}! LAN ports and charging hubs are active at each desk. Review the problem statement on Paradesk."
            recipient_type = "ALL_PARTICIPANTS"

        else:
            teams = conn.execute("SELECT COUNT(*) as cnt FROM teams WHERE event_id = ? AND status != 'NO_SHOW'", (event_id,)).fetchone()
            count = teams["cnt"]
            subject = custom_subject or f"[{event['name']}] Official Announcement"
            body = custom_body or "Important event update from the organizing committee."
            recipient_type = "ALL_PARTICIPANTS"

        conn.execute("""
            INSERT INTO emails_sent (event_id, subject, recipient_count, recipient_type, body_preview, sent_timestamp, status)
            VALUES (?, ?, ?, ?, ?, ?, 'DELIVERED')
        """, (event_id, subject, count, recipient_type, body, now_str))

        log_audit(conn, event_id, "EMAIL_DISPATCH", f"Dispatched '{subject}' to {count} recipients ({recipient_type}).", "purple")
        conn.commit()

    finally:
        conn.close()

    return RedirectResponse(
        url=f"/dashboard?event_id={event_id}&success=Notification+dispatched+to+{count}+participants!",
        status_code=status.HTTP_303_SEE_OTHER
    )

@app.post("/admin/events/{event_id}/toggle-freeze")
def toggle_leaderboard_freeze(request: Request, event_id: int):
    require_admin(request)
    conn = get_db_connection()
    try:
        current = conn.execute("SELECT is_leaderboard_frozen FROM events WHERE id = ?", (event_id,)).fetchone()
        if not current:
            raise HTTPException(status_code=404, detail="Event not found")
        
        new_val = 0 if current["is_leaderboard_frozen"] == 1 else 1
        conn.execute("UPDATE events SET is_leaderboard_frozen = ? WHERE id = ?", (new_val, event_id))
        
        state_str = "FROZEN (Public View Locked)" if new_val == 1 else "UNFROZEN (Live Scores Visible)"
        log_audit(conn, event_id, "FREEZE_TOGGLE", f"Leaderboard is now {state_str}.", "purple" if new_val == 1 else "emerald")
        conn.commit()
    finally:
        conn.close()

    return RedirectResponse(url=f"/dashboard?event_id={event_id}&success=Leaderboard+freeze+status+updated", status_code=status.HTTP_303_SEE_OTHER)

# -------------------------------------------------------------
# Ground Check-In & No-Show Reclamation
# -------------------------------------------------------------

@app.post("/admin/{event_id}/checkin")
def ground_checkin(request: Request, event_id: int, token_or_id: str = Form(...)):
    require_admin(request)
    conn = get_db_connection()
    query_str = token_or_id.strip()
    try:
        team = conn.execute("""
            SELECT t.*, d.desk_code FROM teams t
            LEFT JOIN desks d ON t.assigned_desk_id = d.id
            WHERE t.event_id = ? AND (t.unique_checkin_token = ? OR t.id = ? OR LOWER(t.team_name) = LOWER(?))
        """, (event_id, query_str, query_str, query_str)).fetchone()

        if not team:
            return RedirectResponse(
                url=f"/dashboard?event_id={event_id}&error=Team+or+Token+'{query_str}'+not+found",
                status_code=status.HTTP_303_SEE_OTHER
            )

        if team["status"] == "CHECKED_IN":
            return RedirectResponse(
                url=f"/dashboard?event_id={event_id}&warning=Team+'{team['team_name']}'+is+already+checked+in+at+{team['desk_code']}",
                status_code=status.HTTP_303_SEE_OTHER
            )

        assigned_desk_id = team["assigned_desk_id"]
        desk_code = team["desk_code"]

        if not assigned_desk_id:
            # Standby team being admitted on the spot
            open_desk = conn.execute(
                "SELECT id, desk_code FROM desks WHERE event_id = ? AND is_occupied = 0 ORDER BY id ASC LIMIT 1",
                (event_id,)
            ).fetchone()

            if not open_desk:
                return RedirectResponse(
                    url=f"/dashboard?event_id={event_id}&error=No+vacant+desks+available+for+standby+admission!",
                    status_code=status.HTTP_303_SEE_OTHER
                )

            assigned_desk_id = open_desk["id"]
            desk_code = open_desk["desk_code"]
            conn.execute("UPDATE desks SET is_occupied = 1, assigned_team_id = ? WHERE id = ?", (team["id"], assigned_desk_id))

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("""
            UPDATE teams 
            SET status = 'CHECKED_IN', assigned_desk_id = ?, checkin_timestamp = ?
            WHERE id = ?
        """, (assigned_desk_id, now_str, team["id"]))

        conn.execute("UPDATE desks SET is_occupied = 1, assigned_team_id = ? WHERE id = ?", (team["id"], assigned_desk_id))

        log_audit(conn, event_id, "CHECK_IN", f"Team '{team['team_name']}' verified with code {team['unique_checkin_token']} -> Seated at {desk_code}.", "emerald")
        conn.commit()

    finally:
        conn.close()

    return RedirectResponse(
        url=f"/dashboard?event_id={event_id}&success=Verified+and+Checked-in+{team['team_name']}+to+{desk_code}!",
        status_code=status.HTTP_303_SEE_OTHER
    )

@app.post("/admin/{event_id}/sweep-noshows")
def sweep_noshows_protocol(request: Request, event_id: int):
    require_admin(request)
    conn = get_db_connection()
    try:
        unreported_teams = [dict(r) for r in conn.execute("""
            SELECT id, team_name, assigned_desk_id 
            FROM teams 
            WHERE event_id = ? AND status = 'ALLOCATED'
        """, (event_id,)).fetchall()]

        if not unreported_teams:
            return RedirectResponse(
                url=f"/dashboard?event_id={event_id}&warning=No+unreported+allocated+teams+to+sweep",
                status_code=status.HTTP_303_SEE_OTHER
            )

        freed_desk_ids = []
        for t in unreported_teams:
            if t["assigned_desk_id"]:
                freed_desk_ids.append(t["assigned_desk_id"])
                conn.execute(
                    "UPDATE desks SET is_occupied = 0, assigned_team_id = NULL WHERE id = ?",
                    (t["assigned_desk_id"],)
                )

            conn.execute(
                "UPDATE teams SET status = 'NO_SHOW', assigned_desk_id = NULL WHERE id = ?",
                (t["id"],)
            )

        # Promote STANDBY_TOP10 teams into the liberated desks
        promoted_count = 0
        if freed_desk_ids:
            standby_candidates = [dict(r) for r in conn.execute("""
                SELECT id, team_name, queue_position 
                FROM teams 
                WHERE event_id = ? AND status = 'STANDBY_TOP10'
                ORDER BY queue_position ASC
            """, (event_id,)).fetchall()]

            for s_team in standby_candidates:
                if not freed_desk_ids:
                    break
                
                new_desk_id = freed_desk_ids.pop(0)
                desk_row = conn.execute("SELECT desk_code FROM desks WHERE id = ?", (new_desk_id,)).fetchone()
                desk_code = desk_row["desk_code"] if desk_row else "Desk"

                conn.execute("""
                    UPDATE teams 
                    SET status = 'ALLOCATED', assigned_desk_id = ?
                    WHERE id = ?
                """, (new_desk_id, s_team["id"]))

                conn.execute("""
                    UPDATE desks 
                    SET is_occupied = 1, assigned_team_id = ?
                    WHERE id = ?
                """, (s_team["id"], new_desk_id))

                promoted_count += 1

        log_audit(
            conn, event_id, "SWEEP_NOSHOW",
            f"15-Min Protocol: Marked {len(unreported_teams)} teams as NO_SHOW. Reclaimed {len(unreported_teams)} desks. Promoted {promoted_count} Standby teams.",
            "rose"
        )
        conn.commit()

    finally:
        conn.close()

    return RedirectResponse(
        url=f"/dashboard?event_id={event_id}&success=15-Min+Cutoff+Swept!+Marked+{len(unreported_teams)}+no-shows,+promoted+{promoted_count}+standby+teams.",
        status_code=status.HTTP_303_SEE_OTHER
    )

# -------------------------------------------------------------
# Scoring & Leaderboard
# -------------------------------------------------------------

@app.post("/admin/{event_id}/score")
def submit_judge_scores(
    request: Request,
    event_id: int,
    team_id: int = Form(...),
    score_innovation: float = Form(0.0),
    score_technical: float = Form(0.0),
    score_presentation: float = Form(0.0)
):
    require_admin(request)
    conn = get_db_connection()
    try:
        total = score_innovation + score_technical + score_presentation
        conn.execute("""
            UPDATE teams 
            SET score_innovation = ?, score_technical = ?, score_presentation = ?, total_score = ?
            WHERE id = ? AND event_id = ?
        """, (score_innovation, score_technical, score_presentation, total, team_id, event_id))

        team = conn.execute("SELECT team_name FROM teams WHERE id = ?", (team_id,)).fetchone()
        t_name = team["team_name"] if team else f"Team {team_id}"

        log_audit(conn, event_id, "SCORE_SUBMIT", f"Evaluated '{t_name}': Innovation {score_innovation}, Tech {score_technical}, Pres {score_presentation} (Total: {total}).", "blue")
        conn.commit()
    finally:
        conn.close()

    return RedirectResponse(url=f"/dashboard?event_id={event_id}&success=Scores+saved+for+{t_name}", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/leaderboard/{event_id}", response_class=HTMLResponse)
def leaderboard_view(request: Request, event_id: int, admin: Optional[int] = 0):
    conn = get_db_connection()
    try:
        event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if not event:
            raise HTTPException(status_code=404, detail="Event not found.")

        leaderboard_rows = conn.execute("""
            SELECT t.id, t.team_name, t.lead_name, t.member_count, t.status,
                   t.score_innovation, t.score_technical, t.score_presentation, t.total_score,
                   d.desk_code
            FROM teams t
            LEFT JOIN desks d ON t.assigned_desk_id = d.id
            WHERE t.event_id = ? AND t.status IN ('CHECKED_IN', 'ALLOCATED')
            ORDER BY t.total_score DESC, t.id ASC
        """, (event_id,)).fetchall()

        teams = [dict(r) for r in leaderboard_rows]
        is_frozen = bool(event["is_leaderboard_frozen"])
        is_admin = bool(admin == 1)

    finally:
        conn.close()

    return templates.TemplateResponse(
        request=request,
        name="leaderboard.html",
        context={
            "event": dict(event),
            "teams": teams,
            "is_frozen": is_frozen,
            "is_admin": is_admin
        }
    )

# -------------------------------------------------------------
# CSV Ingestion & FCFS
# -------------------------------------------------------------

@app.post("/events/{event_id}/import-csv")
def import_csv(request: Request, event_id: int, file: UploadFile = File(...)):
    require_admin(request)
    conn = get_db_connection()
    try:
        event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        max_teams = event["max_teams"]
        content = file.file.read().decode("utf-8-sig", errors="ignore")
        reader = csv.DictReader(io.StringIO(content))
        
        entries = []
        for idx, row in enumerate(reader):
            normalized = {k.strip().lower(): v.strip() for k, v in row.items() if k}
            team_name = normalized.get("team name") or normalized.get("team_name") or f"Team-{idx+1}"
            lead_name = normalized.get("lead name") or normalized.get("team lead") or "Team Lead"
            lead_email = normalized.get("lead email") or normalized.get("email") or f"lead{idx+1}@smail.iitm.ac.in"
            lead_phone = normalized.get("lead phone") or normalized.get("phone") or "+91 98400 00000"
            try:
                member_count = int(normalized.get("member count") or normalized.get("team size") or 4)
            except ValueError:
                member_count = 4

            timestamp_str = normalized.get("timestamp") or normalized.get("time")
            parsed_dt = datetime.now() - timedelta(minutes=(idx * 5))
            if timestamp_str:
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %I:%M:%S %p", "%m/%d/%Y %H:%M:%S"):
                    try:
                        parsed_dt = datetime.strptime(timestamp_str, fmt)
                        break
                    except ValueError:
                        pass

            entries.append({
                "team_name": team_name,
                "lead_name": lead_name,
                "lead_email": lead_email,
                "lead_phone": lead_phone,
                "member_count": member_count,
                "timestamp": parsed_dt
            })

        if not entries:
            return RedirectResponse(url=f"/dashboard?event_id={event_id}&error=CSV+file+was+empty", status_code=status.HTTP_303_SEE_OTHER)

        entries.sort(key=lambda x: x["timestamp"])

        available_desks = [dict(r) for r in conn.execute(
            "SELECT id, desk_code FROM desks WHERE event_id = ? AND is_occupied = 0 ORDER BY id ASC",
            (event_id,)
        ).fetchall()]

        imported_count = len(entries)
        allocated_count = 0
        standby_count = 0
        waitlisted_count = 0
        existing_teams_count = conn.execute("SELECT COUNT(*) as cnt FROM teams WHERE event_id = ?", (event_id,)).fetchone()["cnt"]

        for i, entry in enumerate(entries):
            queue_position = existing_teams_count + i + 1
            token = generate_token("PX-")

            if queue_position <= max_teams and available_desks:
                status_val = "ALLOCATED"
                desk = available_desks.pop(0)
                assigned_desk_id = desk["id"]
                allocated_count += 1
            elif queue_position <= max_teams + 10:
                status_val = "STANDBY_TOP10"
                assigned_desk_id = None
                standby_count += 1
            else:
                status_val = "WAITLISTED"
                assigned_desk_id = None
                waitlisted_count += 1

            cursor = conn.execute("""
                INSERT INTO teams (
                    event_id, team_name, lead_name, lead_email, lead_phone, member_count,
                    registration_timestamp, queue_position, status, unique_checkin_token,
                    assigned_desk_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_id, entry["team_name"], entry["lead_name"], entry["lead_email"], entry["lead_phone"],
                entry["member_count"], entry["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
                queue_position, status_val, token, assigned_desk_id
            ))
            team_id = cursor.lastrowid

            if assigned_desk_id:
                conn.execute(
                    "UPDATE desks SET assigned_team_id = ?, is_occupied = 1 WHERE id = ?",
                    (team_id, assigned_desk_id)
                )

        log_audit(conn, event_id, "CSV_IMPORT", f"Imported {imported_count} teams via FCFS.", "blue")
        conn.commit()

    finally:
        conn.close()

    return RedirectResponse(
        url=f"/dashboard?event_id={event_id}&success=Imported+{imported_count}+teams!+Allocated:+{allocated_count},+Standby:+{standby_count},+Waitlist:+{waitlisted_count}",
        status_code=status.HTTP_303_SEE_OTHER
    )

@app.get("/events/{event_id}/sample-csv")
def download_sample_csv(event_id: int):
    now = datetime.now()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Timestamp", "Team Name", "Lead Name", "Lead Email", "Lead Phone", "Member Count"])
    sample_data = [
        ((now - timedelta(hours=3, minutes=10)).strftime("%Y-%m-%d %H:%M:%S"), "CodeNinjas IITM", "Aditya Sen", "aditya@smail.iitm.ac.in", "+91 98401 11111", 4),
        ((now - timedelta(hours=3, minutes=8)).strftime("%Y-%m-%d %H:%M:%S"), "GlitchHunters", "Kavya Murthy", "kavya@smail.iitm.ac.in", "+91 98402 22222", 3),
        ((now - timedelta(hours=3, minutes=5)).strftime("%Y-%m-%d %H:%M:%S"), "TerminalVelocity", "Sameer Khan", "sameer@smail.iitm.ac.in", "+91 98403 33333", 4)
    ]
    for row in sample_data:
        writer.writerow(row)

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=gform_registrations_sample.csv"}
    )

# -------------------------------------------------------------
# Lead Participant Pass Direct URL (Public viewable via token)
# -------------------------------------------------------------

@app.get("/portal/{unique_checkin_token}", response_class=HTMLResponse)
def participant_portal(request: Request, unique_checkin_token: str):
    conn = get_db_connection()
    try:
        team_row = conn.execute("""
            SELECT t.*, e.name as event_name, e.venue_name, e.event_start, e.problem_statement_url,
                   e.problem_statement_text, e.rubric_json, d.desk_code
            FROM teams t
            JOIN events e ON t.event_id = e.id
            LEFT JOIN desks d ON t.assigned_desk_id = d.id
            WHERE t.unique_checkin_token = ?
        """, (unique_checkin_token.strip(),)).fetchone()

        if not team_row:
            raise HTTPException(status_code=404, detail="Invalid check-in token.")

        team = dict(team_row)
        rubric = []
        if team.get("rubric_json"):
            try:
                rubric = json.loads(team["rubric_json"])
            except Exception:
                rubric = []

        standby_rank = None
        if team["status"] == "STANDBY_TOP10":
            rank_row = conn.execute("""
                SELECT COUNT(*) as rank_pos FROM teams 
                WHERE event_id = ? AND status = 'STANDBY_TOP10' AND queue_position <= ?
            """, (team["event_id"], team["queue_position"])).fetchone()
            standby_rank = rank_row["rank_pos"] if rank_row else 1

    finally:
        conn.close()

    return templates.TemplateResponse(
        request=request,
        name="participant_portal.html",
        context={"team": team, "rubric": rubric, "standby_rank": standby_rank}
    )

# -------------------------------------------------------------
# Admin Reset
# -------------------------------------------------------------

@app.post("/admin/reset")
def reset_to_seeds():
    init_db(force_reseed=True)
    return RedirectResponse(url="/login?success=System+reset+to+fresh+Paradox'27+seed+events", status_code=status.HTTP_303_SEE_OTHER)

# -------------------------------------------------------------
# Production Health Check & Process Entrypoint
# -------------------------------------------------------------

@app.get("/health", response_class=JSONResponse)
def health_check():
    conn = get_db_connection()
    try:
        ev_count = conn.execute("SELECT COUNT(*) as cnt FROM events").fetchone()["cnt"]
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
        ev_count = 0
    finally:
        conn.close()

    is_healthy = (db_status == "healthy")
    return JSONResponse(
        status_code=status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "healthy" if is_healthy else "unhealthy",
            "service": "paradesk-core",
            "database": db_status,
            "events_loaded": ev_count,
            "timestamp": datetime.now().isoformat()
        }
    )

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app:app", host=host, port=port, reload=False)
