"""Small standard-library web server for the Studyflow prototype."""

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from datetime import date, datetime, timedelta, timezone
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from planner import PlanningError, build_plan


ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("STUDYFLOW_DB", ROOT / "studyflow.db"))
PBKDF2_ROUNDS = 310_000
SESSION_DAYS = 30
MAX_BODY_BYTES = 64 * 1024
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
}


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def connect_db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect_db() as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS topics (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                subject TEXT NOT NULL,
                title TEXT NOT NULL,
                estimated_hours REAL,
                deadline TEXT NOT NULL,
                difficulty INTEGER NOT NULL DEFAULT 2,
                priority INTEGER NOT NULL DEFAULT 2,
                completed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                daily_hours REAL NOT NULL DEFAULT 2
            );
            CREATE INDEX IF NOT EXISTS sessions_user_id ON sessions(user_id);
            CREATE INDEX IF NOT EXISTS topics_user_deadline ON topics(user_id, deadline);
        """)


def password_record(password, salt=None):
    salt_bytes = bytes.fromhex(salt) if salt else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, PBKDF2_ROUNDS)
    return digest.hex(), salt_bytes.hex()


def valid_email(email):
    return isinstance(email, str) and len(email) <= 254 and EMAIL_PATTERN.fullmatch(email) is not None


def validate_topic(data, partial=False):
    if not isinstance(data, dict):
        raise ApiError(400, "Topic details must be sent as an object.")
    allowed = {"subject", "title", "estimatedHours", "deadline", "difficulty", "priority", "completed"}
    if set(data) - allowed:
        raise ApiError(400, "The topic contains an unsupported field.")
    result = {}
    for field, maximum in (("subject", 60), ("title", 100)):
        if field not in data and partial:
            continue
        value = data.get(field)
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
            raise ApiError(400, f"{field.capitalize()} is required and must be no longer than {maximum} characters.")
        result[field] = value.strip()
    if "estimatedHours" in data or not partial:
        value = data.get("estimatedHours")
        try:
            hours = float(value)
        except (TypeError, ValueError) as exc:
            raise ApiError(400, "Study estimate must be a number between 0.25 and 100 hours.") from exc
        if not 0.25 <= hours <= 100:
            raise ApiError(400, "Study estimate must be between 0.25 and 100 hours.")
        result["estimatedHours"] = hours
    if "deadline" in data or not partial:
        deadline = data.get("deadline")
        try:
            parsed = date.fromisoformat(deadline)
        except (TypeError, ValueError) as exc:
            raise ApiError(400, "Choose a valid due date.") from exc
        if parsed > date.today() + timedelta(days=365):
            raise ApiError(400, "Choose a due date within the next 365 days.")
        result["deadline"] = parsed.isoformat()
    for field in ("difficulty", "priority"):
        if field not in data and partial:
            continue
        try:
            value = int(data.get(field, 2))
        except (TypeError, ValueError) as exc:
            raise ApiError(400, f"{field.capitalize()} must be 1, 2, or 3.") from exc
        if value not in (1, 2, 3):
            raise ApiError(400, f"{field.capitalize()} must be 1, 2, or 3.")
        result[field] = value
    if "completed" in data or not partial:
        if "completed" in data and not isinstance(data["completed"], bool):
            raise ApiError(400, "Completed must be true or false.")
        result["completed"] = bool(data.get("completed", False))
    return result


class StudyflowHandler(BaseHTTPRequestHandler):
    server_version = "Studyflow/1.0"

    def log_message(self, format_string, *args):
        print(f"{self.log_date_time_string()} {self.client_address[0]} {format_string % args}")

    def send_json(self, status, payload, headers=None):
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        if headers:
            for name, value in headers.items():
                self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, status, message):
        self.send_json(status, {"error": message})

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ApiError(400, "Request length is invalid.") from exc
        if length <= 0 or length > MAX_BODY_BYTES:
            raise ApiError(413 if length > MAX_BODY_BYTES else 400, "Request body is missing or too large.")
        try:
            payload = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ApiError(400, "Request body must contain valid JSON.") from exc
        if not isinstance(payload, dict):
            raise ApiError(400, "Request body must be a JSON object.")
        return payload

    def check_origin(self):
        origin = self.headers.get("Origin")
        if not origin:
            return
        parsed = urlsplit(origin)
        if parsed.netloc.lower() != self.headers.get("Host", "").lower():
            raise ApiError(403, "This request origin is not allowed.")

    def token_hash_from_cookie(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except CookieError:
            return None
        morsel = cookie.get("studyflow_session")
        if not morsel:
            return None
        return hashlib.sha256(morsel.value.encode("utf-8")).hexdigest()

    def current_user(self, connection):
        token_hash = self.token_hash_from_cookie()
        if not token_hash:
            raise ApiError(401, "Please sign in to continue.")
        now = datetime.now(timezone.utc).isoformat()
        row = connection.execute(
            """SELECT users.id, users.email FROM sessions
               JOIN users ON users.id = sessions.user_id
               WHERE sessions.token_hash = ? AND sessions.expires_at > ?""",
            (token_hash, now)
        ).fetchone()
        if not row:
            raise ApiError(401, "Your session has expired. Please sign in again.")
        return row

    def new_session(self, connection, user_id):
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        expires = (datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)).isoformat()
        connection.execute(
            "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
            (token_hash, user_id, expires)
        )
        connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (datetime.now(timezone.utc).isoformat(),))
        return f"studyflow_session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={SESSION_DAYS * 86400}"

    def do_GET(self):
        parsed = urlsplit(self.path)
        if parsed.path.startswith("/api/"):
            try:
                with connect_db() as connection:
                    self.route_get_api(parsed.path, connection)
            except ApiError as exc:
                self.send_error_json(exc.status, str(exc))
            except PlanningError as exc:
                self.send_error_json(400, str(exc))
            return
        self.serve_static(parsed.path)

    def route_get_api(self, path, connection):
        if path == "/api/me":
            user = self.current_user(connection)
            self.send_json(200, {"email": user["email"]})
        elif path == "/api/topics":
            user = self.current_user(connection)
            rows = connection.execute(
                """SELECT id, subject, title, estimated_hours, deadline, difficulty, priority, completed
                   FROM topics WHERE user_id = ? ORDER BY deadline, priority DESC, created_at""",
                (user["id"],)
            ).fetchall()
            self.send_json(200, {"topics": [self.topic_json(row) for row in rows]})
        elif path == "/api/settings":
            user = self.current_user(connection)
            row = connection.execute("SELECT daily_hours FROM user_settings WHERE user_id = ?", (user["id"],)).fetchone()
            self.send_json(200, {"dailyHours": row["daily_hours"] if row else 2})
        elif path == "/api/plan":
            user = self.current_user(connection)
            topics = connection.execute(
                """SELECT id, subject, title, estimated_hours AS estimatedHours, deadline,
                          difficulty, priority, completed
                   FROM topics WHERE user_id = ? ORDER BY deadline, priority DESC, created_at""",
                (user["id"],)
            ).fetchall()
            settings = connection.execute("SELECT daily_hours FROM user_settings WHERE user_id = ?", (user["id"],)).fetchone()
            self.send_json(200, build_plan([dict(row) for row in topics], settings["daily_hours"] if settings else 2))
        else:
            self.send_error_json(404, "That API route was not found.")

    @staticmethod
    def topic_json(row):
        return {
            "id": row["id"],
            "subject": row["subject"],
            "title": row["title"],
            "estimatedHours": row["estimated_hours"],
            "deadline": row["deadline"],
            "difficulty": row["difficulty"],
            "priority": row["priority"],
            "completed": bool(row["completed"]),
        }

    def do_POST(self):
        try:
            self.check_origin()
            path = urlsplit(self.path).path
            if path == "/api/auth/register":
                self.register()
            elif path == "/api/auth/login":
                self.login()
            elif path == "/api/auth/logout":
                self.logout()
            elif path == "/api/topics":
                self.create_topic()
            else:
                self.send_error_json(404, "That API route was not found.")
        except ApiError as exc:
            self.send_error_json(exc.status, str(exc))
        except sqlite3.IntegrityError:
            self.send_error_json(409, "That account or topic already exists.")

    def register(self):
        data = self.read_json()
        email = data.get("email", "")
        password = data.get("password", "")
        if not valid_email(email):
            raise ApiError(400, "Enter a valid email address.")
        if not isinstance(password, str) or not 8 <= len(password) <= 128:
            raise ApiError(400, "Password must be between 8 and 128 characters.")
        digest, salt = password_record(password)
        user_id = secrets.token_urlsafe(16)
        with connect_db() as connection:
            connection.execute(
                "INSERT INTO users (id, email, password_hash, password_salt, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, email.strip().lower(), digest, salt, datetime.now(timezone.utc).isoformat())
            )
            connection.execute("INSERT INTO user_settings (user_id, daily_hours) VALUES (?, 2)", (user_id,))
            cookie = self.new_session(connection, user_id)
        self.send_json(201, {"email": email.strip().lower()}, {"Set-Cookie": cookie})

    def login(self):
        data = self.read_json()
        email = data.get("email", "")
        password = data.get("password", "")
        if not isinstance(email, str) or not isinstance(password, str):
            raise ApiError(400, "Enter your email address and password.")
        with connect_db() as connection:
            user = connection.execute(
                "SELECT id, email, password_hash, password_salt FROM users WHERE email = ?",
                (email.strip().lower(),)
            ).fetchone()
            if not user:
                raise ApiError(401, "Email or password isn't correct.")
            candidate, _ = password_record(password, user["password_salt"])
            if not hmac.compare_digest(candidate, user["password_hash"]):
                raise ApiError(401, "Email or password isn't correct.")
            cookie = self.new_session(connection, user["id"])
        self.send_json(200, {"email": user["email"]}, {"Set-Cookie": cookie})

    def logout(self):
        token_hash = self.token_hash_from_cookie()
        with connect_db() as connection:
            if token_hash:
                connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
        self.send_json(200, {"ok": True}, {"Set-Cookie": "studyflow_session=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"})

    def create_topic(self):
        data = self.read_json()
        topic = validate_topic(data)
        user_id = self.require_user_id()
        topic_id = secrets.token_urlsafe(12)
        with connect_db() as connection:
            connection.execute(
                """INSERT INTO topics
                   (id, user_id, subject, title, estimated_hours, deadline, difficulty, priority, completed, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (topic_id, user_id, topic["subject"], topic["title"], topic["estimatedHours"],
                 topic["deadline"], topic["difficulty"], topic["priority"], int(topic["completed"]),
                 datetime.now(timezone.utc).isoformat())
            )
        self.send_json(201, {"id": topic_id, **topic})

    def do_PATCH(self):
        try:
            self.check_origin()
            match = re.fullmatch(r"/api/topics/([A-Za-z0-9_-]{8,64})", urlsplit(self.path).path)
            if not match:
                self.send_error_json(404, "That API route was not found.")
                return
            topic_id = unquote(match.group(1))
            topic = validate_topic(self.read_json(), partial=True)
            user_id = self.require_user_id()
            if not topic:
                raise ApiError(400, "Provide at least one topic detail to update.")
            columns = {
                "subject": "subject", "title": "title", "estimatedHours": "estimated_hours",
                "deadline": "deadline", "difficulty": "difficulty", "priority": "priority",
                "completed": "completed"
            }
            assignments = ", ".join(f"{columns[key]} = ?" for key in topic)
            values = [int(value) if key == "completed" else value for key, value in topic.items()]
            with connect_db() as connection:
                cursor = connection.execute(
                    f"UPDATE topics SET {assignments} WHERE id = ? AND user_id = ?",
                    (*values, topic_id, user_id)
                )
                if cursor.rowcount == 0:
                    raise ApiError(404, "That topic could not be found.")
            self.send_json(200, {"id": topic_id, **topic})
        except ApiError as exc:
            self.send_error_json(exc.status, str(exc))

    def do_DELETE(self):
        try:
            self.check_origin()
            match = re.fullmatch(r"/api/topics/([A-Za-z0-9_-]{8,64})", urlsplit(self.path).path)
            if not match:
                self.send_error_json(404, "That API route was not found.")
                return
            user_id = self.require_user_id()
            with connect_db() as connection:
                cursor = connection.execute(
                    "DELETE FROM topics WHERE id = ? AND user_id = ?",
                    (match.group(1), user_id)
                )
                if cursor.rowcount == 0:
                    raise ApiError(404, "That topic could not be found.")
            self.send_response(204)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
        except ApiError as exc:
            self.send_error_json(exc.status, str(exc))

    def do_PUT(self):
        try:
            self.check_origin()
            if urlsplit(self.path).path != "/api/settings":
                self.send_error_json(404, "That API route was not found.")
                return
            data = self.read_json()
            try:
                daily_hours = float(data.get("dailyHours"))
            except (TypeError, ValueError) as exc:
                raise ApiError(400, "Available study time must be a number between 0.5 and 12.") from exc
            if not 0.5 <= daily_hours <= 12:
                raise ApiError(400, "Available study time must be between 0.5 and 12 hours.")
            user_id = self.require_user_id()
            with connect_db() as connection:
                connection.execute(
                    """INSERT INTO user_settings (user_id, daily_hours) VALUES (?, ?)
                       ON CONFLICT(user_id) DO UPDATE SET daily_hours = excluded.daily_hours""",
                    (user_id, daily_hours)
                )
            self.send_json(200, {"dailyHours": daily_hours})
        except ApiError as exc:
            self.send_error_json(exc.status, str(exc))

    def require_user_id(self):
        with connect_db() as connection:
            return self.current_user(connection)["id"]

    def serve_static(self, path):
        relative = "index.html" if path == "/" else path.lstrip("/")
        if relative not in {"index.html", "styles.css", "app.js"}:
            self.send_error_json(404, "Page not found.")
            return
        file_path = ROOT / relative
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", MIME_TYPES[file_path.suffix])
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        self.end_headers()
        self.wfile.write(body)


def main():
    initialize_database()
    host = os.environ.get("STUDYFLOW_HOST", "127.0.0.1")
    port = int(os.environ.get("STUDYFLOW_PORT", "8000"))
    server = ThreadingHTTPServer((host, port), StudyflowHandler)
    print(f"Studyflow is ready at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Studyflow.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
